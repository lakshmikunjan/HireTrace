import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ApplicationStatus = Literal[
    "applied", "phone_screen", "technical", "offer", "rejected", "ghosted"
]
ApplicationPlatform = Literal["linkedin", "indeed", "direct"]


class ApplicationOut(BaseModel):
    id: uuid.UUID
    company_name: str | None
    job_title: str | None
    location: str | None
    salary_range: str | None
    platform: str
    status: str
    applied_at: datetime | None
    last_activity_at: datetime | None
    parse_confidence: float | None
    manually_overridden: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationFilters(BaseModel):
    platform: ApplicationPlatform | None = None
    status: ApplicationStatus | None = None
    remote_only: bool = False
    has_salary: bool = False


class DashboardStats(BaseModel):
    funnel: dict[str, int]
    platform_breakdown: dict[str, int]
    ghosting_count: int
    applied_today: int
    applied_this_week: int
