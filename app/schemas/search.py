from datetime import datetime

from pydantic import BaseModel, Field


class SearchCreate(BaseModel):
    industry: str = Field(..., min_length=1, max_length=255, examples=["Coiffeur"])
    location: str = Field(..., min_length=1, max_length=255, examples=["Zürich"])
    radius_km: int = Field(10, ge=1, le=100)
    max_results: int = Field(100, ge=1, le=500)
    keywords: list[str] = Field(default_factory=list, examples=[["Damen", "Barber"]])
    target: str = Field("no_website", pattern="^(no_website|weak_website|all)$")


class SearchOut(BaseModel):
    id: int
    industry: str
    location: str
    radius_km: int
    keywords: list[str] | None
    target: str
    max_results: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
