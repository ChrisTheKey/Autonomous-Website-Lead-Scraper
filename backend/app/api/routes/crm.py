from fastapi import APIRouter
from pydantic import BaseModel

from app.crm.hubspot import sync_lead_to_hubspot
from app.crm.pipedrive import sync_lead_to_pipedrive
from app.crm.salesforce import sync_lead_to_salesforce

router = APIRouter()


class CRMSyncRequest(BaseModel):
    lead_id: int
    crm: str  # "hubspot" | "pipedrive" | "salesforce"


@router.post("/sync")
async def sync_to_crm(payload: CRMSyncRequest) -> dict:
    crm = payload.crm.lower()
    if crm == "hubspot":
        result = await sync_lead_to_hubspot(payload.lead_id)
    elif crm == "pipedrive":
        result = await sync_lead_to_pipedrive(payload.lead_id)
    elif crm == "salesforce":
        result = await sync_lead_to_salesforce(payload.lead_id)
    else:
        return {"error": f"Unknown CRM: {crm}"}
    return {"crm": crm, "result": result}
