"""
AI-powered lead extraction using OpenAI + Instructor for structured output,
with LangChain and LlamaIndex as optional enrichment layers.
"""

from __future__ import annotations

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings

_openai = AsyncOpenAI(api_key=settings.openai_api_key)
_client = instructor.from_openai(_openai)


class ExtractedLead(BaseModel):
    company_name: str = Field(description="Official company or business name")
    email: str | None = Field(None, description="Primary contact email")
    phone: str | None = Field(None, description="Primary phone number")
    address: str | None = Field(None, description="Full physical address")
    city: str | None = Field(None, description="City")
    country: str | None = Field(None, description="Country")
    description: str | None = Field(None, description="One-sentence company description")
    industry: str | None = Field(None, description="Industry / sector")


async def extract_lead_data(html: str, url: str) -> ExtractedLead:
    truncated = html[:12_000]
    lead = await _client.chat.completions.create(
        model=settings.openai_model,
        response_model=ExtractedLead,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a data extraction assistant. "
                    "Extract structured business lead information from raw HTML. "
                    "Return only what is explicitly present in the HTML."
                ),
            },
            {
                "role": "user",
                "content": f"URL: {url}\n\nHTML:\n{truncated}",
            },
        ],
    )
    return lead


async def summarize_lead(lead_id: int) -> str:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.lead import Lead

    async with AsyncSessionLocal() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            return ""

    prompt = (
        f"Company: {lead.company_name}\n"
        f"Website: {lead.website}\n"
        f"Email: {lead.email}\n"
        f"Phone: {lead.phone}\n"
        f"Address: {lead.address}\n"
        f"Description: {lead.description}\n"
    )
    response = await _openai.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "Summarize this business lead in 2–3 sentences for a sales team."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
    )
    return response.choices[0].message.content or ""
