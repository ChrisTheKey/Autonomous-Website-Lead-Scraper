"""
Pydantic AI agent for autonomous lead research and decision-making.
"""

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from app.core.config import settings

_model = OpenAIModel(settings.openai_model, api_key=settings.openai_api_key)


class LeadResearchResult(BaseModel):
    company_name: str
    is_qualified: bool
    qualification_reason: str
    recommended_action: str
    estimated_deal_size: str


lead_research_agent = Agent(
    model=_model,
    result_type=LeadResearchResult,
    system_prompt=(
        "You are an autonomous B2B lead researcher. "
        "Given information about a business, determine if it is a qualified lead, "
        "explain your reasoning, recommend a next action, "
        "and estimate potential deal size (small/medium/large/enterprise)."
    ),
)


async def research_lead(company_info: str) -> LeadResearchResult:
    result = await lead_research_agent.run(company_info)
    return result.data
