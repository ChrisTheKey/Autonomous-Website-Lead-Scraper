"""
Claude-powered AI analysis for lead enrichment and scoring.

Uses claude-opus-4-8 with adaptive thinking for complex analysis tasks.
Streaming is used for all requests to avoid timeout issues.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import anthropic
import structlog

from app.config import settings

log = structlog.get_logger()

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


_SYSTEM_PROMPT = """You are an expert B2B lead qualification analyst.
You evaluate local businesses for digital marketing opportunities —
specifically whether they need a new website or website improvements.

Rules:
- Base analysis only on provided data; never invent facts.
- Be concise and structured.
- Score from 0-100: 0=no opportunity, 100=ideal prospect.
- Respond ONLY with valid JSON matching the requested schema."""


@dataclass
class AICompanyAnalysis:
    opportunity_score: int = 0
    opportunity_summary: str = ""
    industry_relevance: str = ""
    recommended_services: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    outreach_angle: str = ""
    confidence: float = 0.0


@dataclass
class AIContactClassification:
    is_decision_maker: bool = False
    decision_maker_confidence: float = 0.0
    role_normalized: str = ""
    outreach_priority: int = 0


async def analyse_company(
    company_name: str,
    industry: str | None,
    location: str | None,
    website: str | None,
    phone: str | None,
    website_signals: dict[str, Any] | None = None,
    crawled_text: str | None = None,
) -> AICompanyAnalysis:
    """Run Claude analysis on a company to determine digital marketing opportunity."""
    if not settings.anthropic_api_key:
        log.warning("ai_service.no_api_key")
        return AICompanyAnalysis()

    client = _get_client()

    context_parts = [
        f"Company: {company_name}",
        f"Industry: {industry or 'unknown'}",
        f"Location: {location or 'unknown'}",
        f"Has website: {'Yes - ' + website if website else 'No'}",
        f"Phone available: {'Yes' if phone else 'No'}",
    ]

    if website_signals:
        context_parts.append(f"Website quality signals: {json.dumps(website_signals)}")

    if crawled_text:
        excerpt = crawled_text[:2000]
        context_parts.append(f"Website content excerpt:\n{excerpt}")

    user_message = "\n".join(context_parts)
    user_message += """

Respond with this exact JSON schema:
{
  "opportunity_score": <0-100 integer>,
  "opportunity_summary": "<1-2 sentence summary of the opportunity>",
  "industry_relevance": "<high|medium|low>",
  "recommended_services": ["<service1>", "<service2>"],
  "risk_flags": ["<flag1>"],
  "outreach_angle": "<specific angle for first contact, max 1 sentence>",
  "confidence": <0.0-1.0 float>
}"""

    try:
        full_text = ""
        async with client.messages.stream(
            model=settings.claude_model,
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                full_text += text

        data = json.loads(full_text.strip())
        return AICompanyAnalysis(
            opportunity_score=int(data.get("opportunity_score", 0)),
            opportunity_summary=data.get("opportunity_summary", ""),
            industry_relevance=data.get("industry_relevance", ""),
            recommended_services=data.get("recommended_services", []),
            risk_flags=data.get("risk_flags", []),
            outreach_angle=data.get("outreach_angle", ""),
            confidence=float(data.get("confidence", 0.0)),
        )

    except json.JSONDecodeError:
        log.error("ai_service.json_parse_error", raw=full_text[:200])
        return AICompanyAnalysis()
    except anthropic.APIError as e:
        log.error("ai_service.api_error", error=str(e))
        return AICompanyAnalysis()


async def classify_contact(
    full_name: str | None,
    role: str | None,
    company_name: str | None,
) -> AIContactClassification:
    """Classify a contact to determine if they are a decision maker."""
    if not settings.anthropic_api_key:
        return AIContactClassification()

    client = _get_client()

    user_message = f"""Contact data:
Name: {full_name or 'unknown'}
Role/Title: {role or 'unknown'}
Company: {company_name or 'unknown'}

Respond with this exact JSON:
{{
  "is_decision_maker": <true|false>,
  "decision_maker_confidence": <0.0-1.0>,
  "role_normalized": "<standardized role title in English>",
  "outreach_priority": <1-5 integer, 5=highest>
}}"""

    try:
        full_text = ""
        async with client.messages.stream(
            model=settings.claude_model,
            max_tokens=256,
            system="You are a B2B sales expert. Classify business contacts by decision-making authority. Respond only with valid JSON.",
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                full_text += text

        data = json.loads(full_text.strip())
        return AIContactClassification(
            is_decision_maker=bool(data.get("is_decision_maker", False)),
            decision_maker_confidence=float(data.get("decision_maker_confidence", 0.0)),
            role_normalized=data.get("role_normalized", role or ""),
            outreach_priority=int(data.get("outreach_priority", 1)),
        )

    except (json.JSONDecodeError, anthropic.APIError) as e:
        log.error("ai_service.classify_contact_error", error=str(e))
        return AIContactClassification()


async def generate_batch_analysis(companies: list[dict[str, Any]]) -> list[AICompanyAnalysis]:
    """Analyse multiple companies concurrently."""
    import asyncio

    tasks = [
        analyse_company(
            company_name=c.get("name", ""),
            industry=c.get("industry"),
            location=c.get("location"),
            website=c.get("website"),
            phone=c.get("phone"),
        )
        for c in companies
    ]
    return await asyncio.gather(*tasks)


async def score_lead_with_ai(
    company_name: str,
    industry: str | None,
    location: str | None,
    has_website: bool,
    phone: str | None,
    website_signals: dict[str, Any] | None = None,
) -> int:
    """Return a 0-100 AI-based opportunity score for a lead."""
    analysis = await analyse_company(
        company_name=company_name,
        industry=industry,
        location=location,
        website=None if not has_website else "exists",
        phone=phone,
        website_signals=website_signals,
    )
    return analysis.opportunity_score
