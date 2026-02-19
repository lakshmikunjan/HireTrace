"""Dashboard analytics endpoint."""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.application import JobApplication
from app.routers.auth import require_user
from app.schemas.application import DashboardStats

router = APIRouter()

FUNNEL_STATUSES = ["applied", "phone_screen", "technical", "offer", "rejected", "ghosted"]


@router.get("/stats", response_model=DashboardStats)
async def get_stats(request: Request):
    user_id = require_user(request)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())

    async with AsyncSessionLocal() as db:
        # Funnel: count per status
        funnel_result = await db.execute(
            select(JobApplication.status, func.count(JobApplication.id))
            .where(JobApplication.user_id == user_id)
            .group_by(JobApplication.status)
        )
        funnel = {status: 0 for status in FUNNEL_STATUSES}
        for status, count in funnel_result.all():
            if status in funnel:
                funnel[status] = count

        # Platform breakdown
        platform_result = await db.execute(
            select(JobApplication.platform, func.count(JobApplication.id))
            .where(JobApplication.user_id == user_id)
            .group_by(JobApplication.platform)
        )
        platform_breakdown = {row[0]: row[1] for row in platform_result.all()}

        # Ghosting count
        ghosting_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.status == "ghosted",
            )
        )
        ghosting_count = ghosting_result.scalar() or 0

        # Applied today
        today_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= today_start,
            )
        )
        applied_today = today_result.scalar() or 0

        # Applied this week
        week_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= week_start,
            )
        )
        applied_this_week = week_result.scalar() or 0

    return DashboardStats(
        funnel=funnel,
        platform_breakdown=platform_breakdown,
        ghosting_count=ghosting_count,
        applied_today=applied_today,
        applied_this_week=applied_this_week,
    )
