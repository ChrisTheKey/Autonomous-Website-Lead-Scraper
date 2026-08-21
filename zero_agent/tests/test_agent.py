"""The ZERO child-agent surface of this repository.

Two things are being protected here.

The first is the *process contract*: HWD-ZERO writes one JSON invocation to
stdin and reads the last JSON object on stdout. If that drifts, ZERO stops being
able to run this repository, and it stops in a way no unit test of the services
would notice — so the tests below run the entry point as a real subprocess.

The second is honesty. An action that cannot run must report ``unavailable`` and
return nothing that looks like a result. A scraper that returned plausible
placeholder leads when its API key was missing would be worse than one that
failed loudly, because the leads would be acted on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from zero_agent.actions import ACTIONS, dispatch
from zero_agent.protocol import Invocation, Outcome
from zero_agent.pure import PureImportError, load_scoring

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_agent(payload: dict) -> tuple[int, dict]:
    """Invoke the agent exactly as HWD-ZERO does."""
    completed = subprocess.run(
        [sys.executable, "-m", "zero_agent"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
        check=False,
    )
    last = ""
    for line in reversed(completed.stdout.strip().splitlines()):
        if line.strip().startswith("{"):
            last = line.strip()
            break
    assert last, f"agent printed no JSON result:\n{completed.stdout}\n{completed.stderr}"
    return completed.returncode, json.loads(last)


# ------------------------------------------------------------ process contract


def test_the_agent_answers_a_health_invocation() -> None:
    code, result = run_agent({"action": "health", "mission_id": "T"})
    assert code == 0
    assert result["ok"] is True
    assert result["data"]["status"] in {"HEALTHY", "DEGRADED"}
    # Scoring is the floor: whatever else is missing, these are usable.
    assert "analyse" in result["data"]["usable_actions"]


def test_degraded_health_always_names_what_is_missing() -> None:
    """DEGRADED with no reason is a status an operator cannot act on."""
    _code, result = run_agent({"action": "health"})
    if result["data"]["status"] == "DEGRADED":
        assert result["data"]["missing"], "degraded without a reason"
        assert all(entry.strip() for entry in result["data"]["missing"])
        assert result["summary"].startswith("lead scraper degraded:")


def test_analysis_survives_a_missing_configuration_layer(monkeypatch) -> None:
    """On Termux pydantic needs a Rust toolchain, so app.config may be absent.

    The scoring path must not care: it loads two dependency-free modules
    directly, and an agent that can score is an agent ZERO can use.
    """
    from zero_agent import actions

    monkeypatch.setattr(
        actions, "_probe", lambda: {"config": False, "detail": "No module named 'pydantic'"}
    )
    health = actions.dispatch(Invocation(action="health"))
    assert health.ok is True
    assert health.data["status"] == "DEGRADED"
    assert "pydantic" in health.data["missing"][0]
    assert "analyse" in health.data["usable_actions"]
    assert "search_leads" not in health.data["usable_actions"]

    scored = actions.dispatch(
        Invocation(
            action="analyse",
            payload={"candidates": [{"name": "X", "lead_type": "no_website_candidate"}]},
        )
    )
    assert scored.ok is True
    assert scored.data["count"] == 1


def test_the_result_is_the_last_stdout_line_even_with_log_noise() -> None:
    code, result = run_agent({"action": "capabilities"})
    assert code == 0
    assert set(result["data"]["actions"]) == set(ACTIONS)


def test_an_unknown_action_is_refused_with_the_known_list() -> None:
    code, result = run_agent({"action": "rm_rf_everything"})
    assert code == 1
    assert result["ok"] is False
    assert "unknown action" in result["error"]


def test_a_malformed_invocation_is_rejected() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "zero_agent"],
        input="{not json",
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 2
    assert "not valid JSON" in completed.stdout


def test_an_absent_prerequisite_exits_three_not_one() -> None:
    """ZERO distinguishes "cannot run" from "ran and failed"."""
    code, result = run_agent({"action": "search_leads", "payload": {"location": "Bern"}})
    assert code == 3
    assert result["ok"] is False
    assert result["unavailable"]
    assert "GOOGLE_MAPS_API_KEY" in result["unavailable"]
    # Nothing lead-shaped is returned when the search could not run.
    assert not result["data"].get("candidates")


# ------------------------------------------------------------------- scoring


def test_the_scoring_rules_load_without_the_database_layer() -> None:
    """The point of zero_agent.pure: no SQLAlchemy, no asyncpg, no Postgres."""
    enums, scoring = load_scoring()
    assert hasattr(scoring, "calculate_score")
    assert enums.LeadType.no_website_candidate


def test_the_pure_loader_refuses_a_module_that_gained_dependencies(monkeypatch, tmp_path) -> None:
    """A future refactor must break here rather than silently load something else."""
    from zero_agent import pure

    impostor = tmp_path / "enums.py"
    impostor.write_text("import definitely_not_installed_xyz\n")
    monkeypatch.setitem(pure.PURE_MODULES, "app.models.enums", impostor)
    monkeypatch.delitem(sys.modules, "app.models.enums", raising=False)
    with pytest.raises(PureImportError, match="no longer dependency-free"):
        pure.load_scoring()


def test_analysis_uses_the_repositorys_real_scoring_rules() -> None:
    code, result = run_agent(
        {
            "action": "analyse",
            "payload": {
                "candidates": [
                    {
                        "name": "Kein Web GmbH",
                        "lead_type": "no_website_candidate",
                        "has_phone": True,
                        "has_address": True,
                        "operational": True,
                        "industry_relevant": True,
                    },
                    {
                        "name": "Schwache Seite AG",
                        "lead_type": "weak_website_candidate",
                        "has_own_domain": False,
                        "has_https": False,
                        "has_mobile_viewport": False,
                        "has_contact_page": False,
                    },
                    {
                        "name": "Gute Seite AG",
                        "lead_type": "weak_website_candidate",
                    },
                ]
            },
        }
    )
    assert code == 0
    scored = {item["name"]: item for item in result["data"]["scored"]}
    # 40 + 20 + 15 + 15 + 10, exactly the repository's own rule.
    assert scored["Kein Web GmbH"]["score"] == 100
    assert scored["Kein Web GmbH"]["priority"] == "high_priority"
    # A site that is fine scores worse than one that is broken.
    assert scored["Gute Seite AG"]["score"] < scored["Schwache Seite AG"]["score"]
    # Results are ranked.
    ranks = [item["score"] for item in result["data"]["scored"]]
    assert ranks == sorted(ranks, reverse=True)


def test_a_suppressed_company_is_blocked_not_scored() -> None:
    code, result = run_agent(
        {
            "action": "analyse",
            "payload": {
                "candidates": [
                    {
                        "name": "Nicht kontaktieren AG",
                        "lead_type": "no_website_candidate",
                        "has_phone": True,
                        "on_suppression_list": True,
                    }
                ]
            },
        }
    )
    assert code == 0
    entry = result["data"]["scored"][0]
    assert entry["priority"] == "blocked"
    assert entry["score"] == 0


def test_an_unknown_lead_type_is_rejected_rather_than_defaulted() -> None:
    code, result = run_agent(
        {"action": "analyse", "payload": {"candidates": [{"name": "X", "lead_type": "made_up"}]}}
    )
    assert code == 0
    assert result["data"]["scored"] == []
    assert "made_up" in result["data"]["rejected"][0]["error"]


def test_no_candidates_is_an_honest_empty_result_not_an_error() -> None:
    code, result = run_agent({"action": "analyse", "payload": {"objective": "Bern"}})
    assert code == 0
    assert result["ok"] is True
    assert result["data"]["scored"] == []
    assert "nothing to score" in result["summary"]


# ------------------------------------------------------------------- outreach


def test_preparing_outreach_never_sends() -> None:
    code, result = run_agent(
        {
            "action": "prepare_outreach",
            "payload": {
                "scored": [
                    {"name": "A", "lead_type": "no_website_candidate", "priority": "high_priority"},
                    {"name": "B", "lead_type": "weak_website_candidate", "priority": "medium_priority"},
                ]
            },
        }
    )
    assert code == 0
    assert result["data"]["sent"] == 0
    assert all(draft["status"] == "DRAFT" for draft in result["data"]["drafts"])
    assert "never sends" in result["data"]["note"]


# ------------------------------------------------------------------- manifest


def test_the_manifest_matches_the_implemented_actions() -> None:
    """A manifest that promised an action the code lacks would mislead ZERO."""
    import yaml

    manifest = yaml.safe_load((REPO_ROOT / "agent.yaml").read_text(encoding="utf-8"))
    assert manifest["id"] == "lead_scraper"
    assert manifest["parent"] == "zero"
    assert manifest["entry_point"] == "zero_agent/__main__.py"
    assert manifest["execution_adapter"] == "python_module"
    declared = {action["id"] for action in manifest["actions"]}
    assert declared == set(ACTIONS)


def test_the_manifest_never_claims_a_sending_capability() -> None:
    import yaml

    manifest = yaml.safe_load((REPO_ROOT / "agent.yaml").read_text(encoding="utf-8"))
    assert "external.message" not in manifest["capabilities"]
    assert "external.publish" not in manifest["capabilities"]
    assert "external.message" in manifest["requires_approval_for"]


def test_a_malformed_handoff_is_an_error_not_an_empty_result() -> None:
    """A broken hand-off between agents must not look like "nothing to do"."""
    outcome = dispatch(Invocation(action="analyse", payload={"candidates": "not-a-list"}))
    assert outcome.ok is False
    assert "must be a list" in outcome.error


def test_a_non_object_candidate_is_rejected_individually() -> None:
    outcome = dispatch(Invocation(action="analyse", payload={"candidates": [None, 42]}))
    assert outcome.ok is True
    assert outcome.data["scored"] == []
    assert len(outcome.data["rejected"]) == 2


def test_dispatch_never_raises_out_of_the_agent(monkeypatch) -> None:
    """A handler that explodes is reported, not propagated into ZERO.

    ZERO reads this agent's stdout; an uncaught traceback would reach it as a
    parse failure with no explanation rather than as a result it can act on.
    """
    from zero_agent import actions

    def explode(_invocation):
        raise RuntimeError("the disk caught fire")

    monkeypatch.setitem(actions.HANDLERS, "analyse", explode)
    outcome = actions.dispatch(Invocation(action="analyse"))
    assert isinstance(outcome, Outcome)
    assert outcome.ok is False
    assert "the disk caught fire" in outcome.error
    assert "RuntimeError" in outcome.error
