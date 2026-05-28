"""
LangChain-powered lead qualification and enrichment chain.
Uses langchain + langchain-openai for structured pipelines.
"""

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import settings

_llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)

_qualify_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a B2B sales qualification assistant. "
            "Score leads from 1-10 and explain briefly.",
        ),
        (
            "human",
            "Company: {company_name}\nWebsite: {website}\n"
            "Industry: {industry}\nDescription: {description}",
        ),
    ]
)

_enrich_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Suggest 3 personalised outreach subject lines for this lead."),
        (
            "human",
            "Company: {company_name}\nIndustry: {industry}\nDescription: {description}",
        ),
    ]
)

qualify_chain = _qualify_prompt | _llm
enrich_chain = _enrich_prompt | _llm


async def qualify_lead(company_name: str, website: str, industry: str, description: str) -> str:
    result = await qualify_chain.ainvoke(
        {
            "company_name": company_name,
            "website": website,
            "industry": industry,
            "description": description,
        }
    )
    return result.content


async def generate_outreach(company_name: str, industry: str, description: str) -> str:
    result = await enrich_chain.ainvoke(
        {
            "company_name": company_name,
            "industry": industry,
            "description": description,
        }
    )
    return result.content
