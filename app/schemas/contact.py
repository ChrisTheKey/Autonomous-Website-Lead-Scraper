from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ContactReviewStatus


class ContactOut(BaseModel):
    id: int
    company_id: int
    full_name: str | None
    role: str | None
    email: str | None
    phone: str | None
    source_url: str | None
    source_type: str
    confidence_score: float
    is_personal_data: bool
    review_status: ContactReviewStatus
    created_at: datetime

    model_config = {"from_attributes": True}
