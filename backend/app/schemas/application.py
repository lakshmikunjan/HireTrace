import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ApplicationStatus = Literal[
    "applied", "phone_screen", "assessment", "technical", "offer", "rejected", "ghosted"
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
    rejected_at: datetime | None
    last_activity_at: datetime | None
    phone_screen_completed: bool
    phone_screen_completed_at: datetime | None
    phone_screen_scheduled: datetime | None
    phone_screen_missed: bool
    assessment_completed: bool
    assessment_completed_at: datetime | None
    assessment_scheduled: datetime | None
    assessment_missed: bool
    technical_completed: bool
    technical_completed_at: datetime | None
    technical_scheduled: datetime | None
    technical_missed: bool
    parse_confidence: float | None
    manually_overridden: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class InterviewStageUpdate(BaseModel):
    phone_screen_completed: bool | None = None
    phone_screen_scheduled: datetime | None = None
    phone_screen_missed: bool | None = None
    assessment_completed: bool | None = None
    assessment_scheduled: datetime | None = None
    assessment_missed: bool | None = None
    technical_completed: bool | None = None
    technical_scheduled: datetime | None = None
    technical_missed: bool | None = None


class ApplicationFieldUpdate(BaseModel):
    company_name: str | None = None
    job_title: str | None = None
    location: str | None = None


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
    applied_this_month: int
    total_applications: int


class ActivityPoint(BaseModel):
    date: str   # "YYYY-MM-DD"
    count: int


class RecentUpdate(BaseModel):
    company_name: str | None
    job_title: str | None
    status: str
    last_activity_at: datetime | None

    model_config = {"from_attributes": True}
