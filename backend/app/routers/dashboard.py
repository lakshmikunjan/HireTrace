"""Dashboard analytics endpoint."""
from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Request
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.application import JobApplication
from app.routers.auth import require_user
from app.schemas.application import DashboardStats

router = APIRouter()

FUNNEL_STATUSES = ["applied", "phone_screen", "assessment", "technical", "offer", "rejected", "ghosted"]


@router.get("/stats", response_model=DashboardStats)
async def get_stats(request: Request):
    user_id = require_user(request)

    now = datetime.now(timezone.utc)
    # Rolling windows — timezone-agnostic so US users always see the right count
    # regardless of UTC offset (avoids "midnight UTC != midnight local" edge case).
    today_start = now - timedelta(hours=24)
    week_start  = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start  = date(2026, 1, 1)

    async with AsyncSessionLocal() as db:
        # Funnel: count per status (2026 only)
        funnel_result = await db.execute(
            select(JobApplication.status, func.count(JobApplication.id))
            .where(JobApplication.user_id == user_id, JobApplication.applied_at >= year_start)
            .group_by(JobApplication.status)
        )
        funnel = {status: 0 for status in FUNNEL_STATUSES}
        for status, count in funnel_result.all():
            if status in funnel:
                funnel[status] = count

        # Platform breakdown (2026 only)
        platform_result = await db.execute(
            select(JobApplication.platform, func.count(JobApplication.id))
            .where(JobApplication.user_id == user_id, JobApplication.applied_at >= year_start)
            .group_by(JobApplication.platform)
        )
        platform_breakdown = {row[0]: row[1] for row in platform_result.all()}

        # Ghosting count (2026 only)
        ghosting_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
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

        # Applied this week (Sunday–Saturday)
        week_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= week_start,
            )
        )
        applied_this_week = week_result.scalar() or 0

        # Applied this month (1st of current month to now)
        month_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= month_start,
            )
        )
        applied_this_month = month_result.scalar() or 0

    return DashboardStats(
        funnel=funnel,
        platform_breakdown=platform_breakdown,
        ghosting_count=ghosting_count,
        applied_today=applied_today,
        applied_this_week=applied_this_week,
        applied_this_month=applied_this_month,
    )
