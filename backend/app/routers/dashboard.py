"""Dashboard analytics endpoint."""
from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Request
from sqlalchemy import select, func, cast
from sqlalchemy.types import Date as SADate

from app.database import AsyncSessionLocal
from app.models.application import JobApplication
from app.routers.auth import require_user
from app.schemas.application import DashboardStats, ActivityPoint, RecentUpdate

router = APIRouter()

FUNNEL_STATUSES = ["applied", "phone_screen", "assessment", "technical", "offer", "rejected", "ghosted"]


@router.get("/stats", response_model=DashboardStats)
async def get_stats(request: Request):
    user_id = require_user(request)

    now = datetime.now(timezone.utc)
    today_start = now - timedelta(hours=24)
    # Calendar week: always start from this Monday at midnight UTC
    days_since_monday = now.weekday()  # Monday=0, Sunday=6
    week_start = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
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

        # Total applications (2026 only)
        total_result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
            )
        )
        total_applications = total_result.scalar() or 0

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

        # Applied this month
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
        total_applications=total_applications,
        applied_today=applied_today,
        applied_this_week=applied_this_week,
        applied_this_month=applied_this_month,
    )


@router.get("/recent-updates", response_model=list[RecentUpdate])
async def get_recent_updates(request: Request):
    """Return applications whose status advanced today (rejections, phone screens, assessments, technical, offers)."""
    user_id = require_user(request)
    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobApplication)
            .where(
                JobApplication.user_id == user_id,
                JobApplication.last_activity_at >= today_midnight,
                JobApplication.status.in_(["applied", "rejected", "phone_screen", "assessment", "technical", "offer"]),
            )
            .order_by(JobApplication.last_activity_at.desc())
        )
        apps = result.scalars().all()

    return [RecentUpdate.model_validate(a) for a in apps]


@router.get("/activity", response_model=list[ActivityPoint])
async def get_activity(request: Request):
    """Daily application counts since the start of 2026."""
    user_id = require_user(request)
    year_start = date(2026, 1, 1)

    async with AsyncSessionLocal() as db:
        day_col = cast(JobApplication.applied_at, SADate).label("day")
        result = await db.execute(
            select(day_col, func.count(JobApplication.id).label("cnt"))
            .where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
            )
            .group_by(day_col)
            .order_by(day_col)
        )
        rows = result.all()

    return [ActivityPoint(date=str(row.day), count=row.cnt) for row in rows]
