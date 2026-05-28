"""
OpenAI Agents SDK integration for multi-step autonomous lead processing.
"""

from agents import Agent, Runner, function_tool

from app.core.config import settings


@function_tool
async def search_company_info(company_name: str, website: str) -> str:
    """Fetch and summarise publicly available info about a company."""
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(website, follow_redirects=True)
            text = resp.text[:3000]
        except Exception as exc:
            text = f"Could not fetch: {exc}"
    return f"Company: {company_name}\nWebsite content excerpt:\n{text}"


@function_tool
async def score_lead(company_name: str, description: str) -> dict:
    """Score a lead from 1–10 based on available data."""
    score = min(10, max(1, len(description) // 50 + 3))
    return {"company": company_name, "score": score, "tier": "hot" if score >= 7 else "warm"}


lead_agent = Agent(
    name="LeadResearcher",
    instructions=(
        "You autonomously research and score B2B leads. "
        "Use the available tools to gather company info and produce a final lead score."
    ),
    tools=[search_company_info, score_lead],
    model=settings.openai_model,
)


async def run_lead_agent(company_name: str, website: str) -> str:
    result = await Runner.run(
        lead_agent,
        input=f"Research and score this lead — Company: {company_name}, Website: {website}",
    )
    return result.final_output
