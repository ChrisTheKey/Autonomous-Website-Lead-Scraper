from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.extractor import extract_lead_data, summarize_lead

router = APIRouter()


class ExtractionRequest(BaseModel):
    html: str
    url: str


class SummarizeRequest(BaseModel):
    lead_id: int


@router.post("/extract")
async def extract(payload: ExtractionRequest) -> dict:
    lead_data = await extract_lead_data(payload.html, payload.url)
    return lead_data.model_dump()


@router.post("/summarize")
async def summarize(payload: SummarizeRequest) -> dict:
    summary = await summarize_lead(payload.lead_id)
    return {"lead_id": payload.lead_id, "summary": summary}
