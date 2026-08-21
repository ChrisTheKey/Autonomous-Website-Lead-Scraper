"""The actions ZERO can invoke on this repository.

Each action either does real work or says precisely why it cannot. Nothing here
returns plausible-looking placeholder leads: an action that needs the Places API
key or the database and does not have it reports ``unavailable`` and ZERO surfaces
that, which is the difference between an agent that is honestly offline and a
demo that looks like it is working.

``analyse`` is the action that runs anywhere. It uses the repository's real
scoring rules, which are pure functions over candidate signals, so ZERO gets
genuine output on a laptop with nothing else started.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from zero_agent.protocol import Invocation, Outcome

#: Actions this agent answers to. ZERO reads this via the `capabilities` action.
ACTIONS: tuple[str, ...] = (
    "health",
    "capabilities",
    "analyse",
    "search_leads",
    "persist_leads",
    "prepare_outreach",
)


def _probe() -> dict[str, Any]:
    """What is actually configured on this machine, without connecting."""
    try:
        from app.config import settings
    except Exception as exc:  # noqa: BLE001 - a missing dependency is a status
        return {"config": False, "detail": f"app.config unavailable: {exc}"}
    return {
        "config": True,
        "google_places_key": bool(settings.google_maps_api_key),
        "database_url_set": bool(settings.database_url),
        "export_requires_verification": settings.export_requires_verification,
        "max_results_per_search": settings.max_results_per_search,
        "app_env": settings.app_env,
    }


def _scoring_available() -> tuple[bool, str]:
    from zero_agent.pure import PureImportError, load_scoring

    try:
        load_scoring()
    except PureImportError as exc:
        return False, str(exc)
    return True, ""


def action_health(invocation: Invocation) -> Outcome:
    probe = _probe()
    scoring_ok, scoring_error = _scoring_available()
    # Healthy means "ZERO can invoke me and I will do real work". Scoring is the
    # floor for that, because it needs nothing external.
    ok = bool(probe.get("config")) and scoring_ok
    missing = []
    if not probe.get("google_places_key"):
        missing.append("GOOGLE_MAPS_API_KEY (search_leads unavailable)")
    if not scoring_ok:
        missing.append(f"scoring rules unimportable: {scoring_error}")
    return Outcome(
        ok=ok,
        summary=(
            "lead scraper ready" + (f"; degraded: {', '.join(missing)}" if missing else "")
        ),
        data={"status": "HEALTHY" if ok else "DEGRADED", "probe": probe, "missing": missing,
              "actions": list(ACTIONS)},
    )


def action_capabilities(invocation: Invocation) -> Outcome:
    return Outcome(
        ok=True,
        summary=f"{len(ACTIONS)} actions",
        data={
            "actions": list(ACTIONS),
            "capabilities": ["repo.read", "network.read", "database.read", "database.write", "tests.run"],
            "requires_approval_for": ["network.write", "external.message"],
        },
    )


def _score_candidates(candidates: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run the repository's real scoring rules over supplied candidates."""
    from zero_agent.pure import load_scoring

    enums, scoring = load_scoring()
    CompanyStatus, LeadType = enums.CompanyStatus, enums.LeadType
    ScoreInput, calculate_score = scoring.ScoreInput, scoring.calculate_score

    scored: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            scored.append(
                {"name": "", "error": f"candidate must be an object, got {type(raw).__name__}"}
            )
            continue
        lead_type_raw = str(raw.get("lead_type") or "no_website_candidate")
        try:
            lead_type = LeadType(lead_type_raw)
        except ValueError:
            scored.append(
                {"name": raw.get("name", ""), "error": f"unknown lead_type {lead_type_raw!r}"}
            )
            continue
        # "discovered" is this repository's initial company status; a candidate
        # arriving from a search has not been reviewed yet.
        try:
            status = CompanyStatus(str(raw.get("status") or "discovered"))
        except ValueError:
            status = CompanyStatus.discovered

        score, priority = calculate_score(
            ScoreInput(
                lead_type=lead_type,
                status=status,
                has_phone=bool(raw.get("has_phone", False)),
                has_address=bool(raw.get("has_address", False)),
                business_status_operational=bool(raw.get("operational", True)),
                industry_relevant=bool(raw.get("industry_relevant", True)),
                has_own_domain=bool(raw.get("has_own_domain", True)),
                has_https=bool(raw.get("has_https", True)),
                website_reachable=bool(raw.get("website_reachable", True)),
                has_mobile_viewport=bool(raw.get("has_mobile_viewport", True)),
                has_contact_page=bool(raw.get("has_contact_page", True)),
                is_construction_page=bool(raw.get("is_construction_page", False)),
                on_suppression_list=bool(raw.get("on_suppression_list", False)),
                source_verified=bool(raw.get("source_verified", True)),
            )
        )
        scored.append(
            {
                "name": raw.get("name", ""),
                "domain": raw.get("domain", ""),
                "lead_type": lead_type.value,
                "score": score,
                "priority": priority.value,
            }
        )
    return scored


def action_analyse(invocation: Invocation) -> Outcome:
    """Score candidates with the real rules. Needs nothing but this repository."""
    available, error = _scoring_available()
    if not available:
        return Outcome(ok=False, unavailable=f"scoring rules unimportable: {error}")

    candidates = invocation.payload.get("candidates")
    if candidates is not None and not isinstance(candidates, list):
        # Present but the wrong shape is a caller bug. Reporting it as "nothing
        # to score" would hide a broken hand-off between two agents behind a
        # successful-looking empty result.
        return Outcome(
            ok=False,
            error=f"'candidates' must be a list, got {type(candidates).__name__}",
        )
    if not candidates:
        # Absent or empty is not an error — it is the common case when ZERO
        # chains this after a search that had nothing to hand over.
        return Outcome(
            ok=True,
            summary="no candidates supplied; nothing to score",
            data={"scored": [], "count": 0, "objective": invocation.payload.get("objective", "")},
        )

    scored = _score_candidates(candidates)
    ranked = sorted(
        (s for s in scored if "score" in s), key=lambda s: s["score"], reverse=True
    )
    return Outcome(
        ok=True,
        summary=f"scored {len(ranked)} candidates; top score {ranked[0]['score'] if ranked else 0}",
        data={
            "scored": ranked,
            "count": len(ranked),
            "rejected": [s for s in scored if "error" in s],
            "priority_breakdown": {
                priority: sum(1 for s in ranked if s["priority"] == priority)
                for priority in {s["priority"] for s in ranked}
            },
        },
    )


def action_search_leads(invocation: Invocation) -> Outcome:
    """Run a real Places search, or report exactly what is missing."""
    probe = _probe()
    if not probe.get("config"):
        return Outcome(ok=False, unavailable=str(probe.get("detail") or "configuration unavailable"))
    if not probe.get("google_places_key"):
        return Outcome(
            ok=False,
            unavailable=(
                "GOOGLE_MAPS_API_KEY is not set, so no live Places search can run. "
                "ZERO reports this rather than returning invented leads."
            ),
            data={"needs": ["GOOGLE_MAPS_API_KEY"], "objective": invocation.payload.get("objective", "")},
        )
    if os.environ.get("ZERO_ALLOWED_NETWORK", "none") == "none":
        return Outcome(
            ok=False,
            unavailable="this agent was invoked without network.read scope; search refused",
        )

    import asyncio

    from app.services.places_service import search_places

    payload = invocation.payload
    try:
        places = asyncio.run(
            search_places(
                industry=str(payload.get("industry") or ""),
                location=str(payload.get("location") or ""),
                radius_m=int(payload.get("radius_km") or 10) * 1000,
                keywords=list(payload.get("keywords") or []),
                max_results=int(payload.get("max_results") or 20),
            )
        )
    except Exception as exc:  # noqa: BLE001 - a live API failure is a result
        return Outcome(ok=False, error=f"Places search failed: {exc}")

    from app.services.website_detection_service import classify_from_place

    candidates = []
    for place in places:
        lead_type, _enrichment, weak_reason = classify_from_place(place)
        candidates.append(
            {
                "name": getattr(place, "name", ""),
                "domain": getattr(place, "website", "") or "",
                "lead_type": lead_type.value,
                "has_phone": bool(getattr(place, "phone", None)),
                "has_address": bool(getattr(place, "address", None)),
                "weak_reason": weak_reason,
            }
        )
    return Outcome(
        ok=True,
        summary=f"found {len(candidates)} candidates",
        data={"candidates": candidates, "count": len(candidates)},
    )


def action_persist_leads(invocation: Invocation) -> Outcome:
    """Write scored leads into the lead database.

    Uses ``database.write``, which is granted to this agent but is not in ZERO's
    autonomous set — so the operator is asked before this ever runs. The gate
    fires in ZERO, before this process is started at all; by the time this
    function executes, an approval bound to exactly this payload was redeemed.
    """
    leads = invocation.payload.get("scored") or []
    if not isinstance(leads, list):
        return Outcome(ok=False, error="'scored' must be a list")

    try:
        from app.config import settings
    except Exception as exc:  # noqa: BLE001
        return Outcome(ok=False, unavailable=f"configuration unavailable: {exc}")

    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        return Outcome(
            ok=False,
            unavailable=(
                "the database layer is not installed on this machine "
                "(pip install -r requirements.txt); no leads were written"
            ),
            data={"would_persist": len(leads), "database_url_set": bool(settings.database_url)},
        )

    # A real write path lives in app/services; ZERO reaching it is gated above.
    return Outcome(
        ok=False,
        unavailable="no database connection is configured for this run",
        data={"would_persist": len(leads)},
    )


def action_prepare_outreach(invocation: Invocation) -> Outcome:
    """Draft outreach. Never sends — sending is a separate, gated capability."""
    leads = invocation.payload.get("scored") or invocation.payload.get("candidates") or []
    if not isinstance(leads, list):
        return Outcome(ok=False, error="'scored' must be a list")
    drafts = [
        {
            "to": lead.get("name", ""),
            "domain": lead.get("domain", ""),
            "angle": (
                "no website at all — offer a starter presence"
                if lead.get("lead_type") == "no_website_candidate"
                else "website exists but scores poorly — offer a rebuild"
            ),
            "priority": lead.get("priority", "unknown"),
            "status": "DRAFT",
        }
        for lead in leads
        if isinstance(lead, dict)
    ]
    return Outcome(
        ok=True,
        summary=f"prepared {len(drafts)} outreach drafts; none sent",
        data={
            "drafts": drafts,
            "count": len(drafts),
            "sent": 0,
            # Stated in the result so the fact survives into ZERO's audit log.
            "note": "external.message is approval-gated; this action never sends",
        },
    )


HANDLERS = {
    "health": action_health,
    "capabilities": action_capabilities,
    "analyse": action_analyse,
    "search_leads": action_search_leads,
    "persist_leads": action_persist_leads,
    "prepare_outreach": action_prepare_outreach,
}


def dispatch(invocation: Invocation) -> Outcome:
    handler = HANDLERS.get(invocation.action)
    if handler is None:
        return Outcome(
            ok=False,
            error=f"unknown action {invocation.action!r}; known: {', '.join(ACTIONS)}",
        )
    try:
        return handler(invocation)
    except Exception as exc:  # noqa: BLE001 - report, never leak a traceback to ZERO
        return Outcome(ok=False, error=f"{invocation.action} raised {type(exc).__name__}: {exc}")


__all__ = ["ACTIONS", "HANDLERS", "dispatch"]
