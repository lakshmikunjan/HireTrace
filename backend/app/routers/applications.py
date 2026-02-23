"""Job application CRUD + manual scan trigger."""
import logging
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy import select, func

logger = logging.getLogger("hiretrace.scanner")

from app.database import AsyncSessionLocal
from app.models.application import JobApplication
from app.routers.auth import require_user
from app.schemas.application import ApplicationOut, ApplicationStatusUpdate, InterviewStageUpdate, ApplicationFieldUpdate

router = APIRouter()


@router.get("/potential-duplicates", response_model=list[list[ApplicationOut]])
async def potential_duplicates(request: Request):
    """Return two kinds of duplicate groups:
    1. Same company + same job title (exact-match duplicates)
    2. Rejection orphans — a rejected app with no job_title that shares a company name
       with another app that does have a job title (scanner missed the match)
    """
    user_id = require_user(request)
    year_start = date(2026, 1, 1)

    async with AsyncSessionLocal() as db:
        seen_ids: set[uuid.UUID] = set()
        groups: list[list[ApplicationOut]] = []

        # ── Group 1: same company + same job title ──────────────────────────
        dupes = await db.execute(
            select(
                func.lower(JobApplication.company_name).label("norm_co"),
                func.lower(JobApplication.job_title).label("norm_title"),
            )
            .where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
                JobApplication.company_name.isnot(None),
                JobApplication.job_title.isnot(None),
            )
            .group_by(
                func.lower(JobApplication.company_name),
                func.lower(JobApplication.job_title),
            )
            .having(func.count(JobApplication.id) > 1)
        )
        for norm_co, norm_title in dupes.all():
            apps_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user_id,
                    JobApplication.applied_at >= year_start,
                    func.lower(JobApplication.company_name) == norm_co,
                    func.lower(JobApplication.job_title) == norm_title,
                ).order_by(JobApplication.applied_at)
            )
            group = apps_result.scalars().all()
            for a in group:
                seen_ids.add(a.id)
            groups.append([ApplicationOut.model_validate(a) for a in group])

        # ── Group 2: rejection orphans (rejected + no job_title) ────────────
        # These were created when the scanner couldn't match the rejection email
        # to an existing application. Surface them so the user can merge them.
        orphans_result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
                JobApplication.status == "rejected",
                JobApplication.job_title.is_(None),
                JobApplication.company_name.isnot(None),
            )
        )
        orphans = orphans_result.scalars().all()

        for orphan in orphans:
            if orphan.id in seen_ids:
                continue  # already in a group above

            # Find the best sibling: same company, has a job title, not already matched
            siblings_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user_id,
                    JobApplication.applied_at >= year_start,
                    JobApplication.id != orphan.id,
                    JobApplication.company_name.ilike(f"%{orphan.company_name}%"),
                    JobApplication.job_title.isnot(None),
                ).order_by(JobApplication.applied_at.desc())
            )
            siblings = [s for s in siblings_result.scalars().all() if s.id not in seen_ids]

            if siblings:
                best = siblings[0]  # most recent matching app
                seen_ids.add(orphan.id)
                seen_ids.add(best.id)
                # Put the proper application first, orphan second
                groups.append([
                    ApplicationOut.model_validate(best),
                    ApplicationOut.model_validate(orphan),
                ])

    return groups


@router.post("/auto-clean-duplicates")
async def auto_clean_duplicates(request: Request):
    """Automatically resolve obvious duplicates without user input.

    Pass 1 – Rejection orphans (rejected + no job_title that matches a proper app):
      Mark the proper application as rejected, delete the orphan.

    Pass 2 – Exact duplicates (same company + same job title):
      Keep the most recently updated entry; merge any non-null fields into it; delete the rest.

    Returns { merged_orphans, deleted_dupes }.
    """
    user_id = require_user(request)
    year_start = date(2026, 1, 1)
    merged_orphans = 0
    deleted_dupes  = 0

    STATUS_RANK = {
        "offer": 6, "technical": 5, "assessment": 4,
        "phone_screen": 3, "rejected": 2, "applied": 1, "ghosted": 0,
    }

    def best_from_group(apps: list) -> tuple:
        """Return (keeper, rest) sorted by: status rank desc → last_activity_at desc → applied_at desc."""
        def sort_key(a):
            rank = STATUS_RANK.get(a.status, 0)
            activity = a.last_activity_at or datetime.min.replace(tzinfo=None)
            applied  = a.applied_at or datetime.min.replace(tzinfo=None)
            # strip tz for comparison if needed
            if hasattr(activity, "tzinfo") and activity.tzinfo:
                from datetime import timezone
                activity = activity.replace(tzinfo=None)
            if hasattr(applied, "tzinfo") and applied.tzinfo:
                from datetime import timezone
                applied = applied.replace(tzinfo=None)
            return (rank, activity, applied)

        ranked = sorted(apps, key=sort_key, reverse=True)
        return ranked[0], ranked[1:]

    async with AsyncSessionLocal() as db:

        # ── Pass 1: rejection orphans ────────────────────────────────────────
        orphans_result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
                JobApplication.status == "rejected",
                JobApplication.job_title.is_(None),
                JobApplication.company_name.isnot(None),
            )
        )
        orphans = orphans_result.scalars().all()
        processed_ids: set[uuid.UUID] = set()

        for orphan in orphans:
            if orphan.id in processed_ids:
                continue
            siblings_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user_id,
                    JobApplication.applied_at >= year_start,
                    JobApplication.id != orphan.id,
                    JobApplication.company_name.ilike(f"%{orphan.company_name}%"),
                    JobApplication.job_title.isnot(None),
                ).order_by(JobApplication.applied_at.desc())
            )
            sibling = siblings_result.scalars().first()
            if sibling and sibling.id not in processed_ids:
                if not sibling.manually_overridden:
                    sibling.status = "rejected"
                    sibling.rejected_at = sibling.rejected_at or orphan.rejected_at
                    # Take the later of the two activity timestamps
                    sib_act = sibling.last_activity_at
                    orp_act = orphan.last_activity_at
                    if sib_act and orp_act:
                        sibling.last_activity_at = max(sib_act, orp_act)
                    elif orp_act:
                        sibling.last_activity_at = orp_act
                await db.delete(orphan)
                processed_ids.add(orphan.id)
                processed_ids.add(sibling.id)
                merged_orphans += 1

        # Flush so orphans are gone before exact-dup pass
        await db.flush()

        # ── Pass 2: exact duplicates (same company + same job title) ─────────
        dupes_result = await db.execute(
            select(
                func.lower(JobApplication.company_name).label("norm_co"),
                func.lower(JobApplication.job_title).label("norm_title"),
            )
            .where(
                JobApplication.user_id == user_id,
                JobApplication.applied_at >= year_start,
                JobApplication.company_name.isnot(None),
                JobApplication.job_title.isnot(None),
            )
            .group_by(
                func.lower(JobApplication.company_name),
                func.lower(JobApplication.job_title),
            )
            .having(func.count(JobApplication.id) > 1)
        )

        for norm_co, norm_title in dupes_result.all():
            apps_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user_id,
                    JobApplication.applied_at >= year_start,
                    func.lower(JobApplication.company_name) == norm_co,
                    func.lower(JobApplication.job_title) == norm_title,
                )
            )
            group = apps_result.scalars().all()
            if len(group) < 2:
                continue

            keeper, rest = best_from_group(group)

            # Merge any non-null fields from the others into the keeper
            for stale in rest:
                if not keeper.location and stale.location:
                    keeper.location = stale.location
                if not keeper.salary_range and stale.salary_range:
                    keeper.salary_range = stale.salary_range
                await db.delete(stale)
                deleted_dupes += 1

        await db.commit()

    return {"merged_orphans": merged_orphans, "deleted_dupes": deleted_dupes}


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    request: Request,
    platform: str | None = Query(None),
    status: str | None = Query(None),
    remote_only: bool = Query(False),
    has_salary: bool = Query(False),
):
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        year_start = date(2026, 1, 1)
        q = select(JobApplication).where(
            JobApplication.user_id == user_id,
            JobApplication.applied_at >= year_start,
        )

        if platform:
            q = q.where(JobApplication.platform == platform)
        if status:
            q = q.where(JobApplication.status == status)
        if remote_only:
            q = q.where(JobApplication.location.ilike("%remote%"))
        if has_salary:
            q = q.where(JobApplication.salary_range.isnot(None))

        q = q.order_by(JobApplication.applied_at.desc())
        result = await db.execute(q)
        apps = result.scalars().all()
        return [ApplicationOut.model_validate(a) for a in apps]


@router.patch("/{app_id}", response_model=ApplicationOut)
async def update_status(request: Request, app_id: uuid.UUID, body: ApplicationStatusUpdate):
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.id == app_id,
                JobApplication.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        app.status = body.status
        app.manually_overridden = True
        await db.commit()
        await db.refresh(app)
        return ApplicationOut.model_validate(app)


@router.patch("/{app_id}/fields", response_model=ApplicationOut)
async def update_fields(request: Request, app_id: uuid.UUID, body: ApplicationFieldUpdate):
    """Manually update company name, job title, or location."""
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.id == app_id,
                JobApplication.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        if body.company_name is not None:
            app.company_name = body.company_name.strip() or None
        if body.job_title is not None:
            app.job_title = body.job_title.strip() or None
        if body.location is not None:
            app.location = body.location.strip() or None

        app.manually_overridden = True
        await db.commit()
        await db.refresh(app)
        return ApplicationOut.model_validate(app)


@router.patch("/{app_id}/interview-stages", response_model=ApplicationOut)
async def update_interview_stages(request: Request, app_id: uuid.UUID, body: InterviewStageUpdate):
    """Update completion status and scheduling for interview stages."""
    from datetime import datetime, timezone
    
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.id == app_id,
                JobApplication.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        now = datetime.now(timezone.utc)
        updated = False

        # Phone Screen
        if body.phone_screen_completed is not None:
            if body.phone_screen_completed and not app.phone_screen_completed:
                app.phone_screen_completed_at = now
            elif not body.phone_screen_completed:
                app.phone_screen_completed_at = None
            app.phone_screen_completed = body.phone_screen_completed
            updated = True

        if body.phone_screen_scheduled is not None:
            app.phone_screen_scheduled = body.phone_screen_scheduled
            updated = True

        if body.phone_screen_missed is not None:
            app.phone_screen_missed = body.phone_screen_missed
            updated = True

        # Assessment
        if body.assessment_completed is not None:
            if body.assessment_completed and not app.assessment_completed:
                app.assessment_completed_at = now
            elif not body.assessment_completed:
                app.assessment_completed_at = None
            app.assessment_completed = body.assessment_completed
            updated = True

        if body.assessment_scheduled is not None:
            app.assessment_scheduled = body.assessment_scheduled
            updated = True

        if body.assessment_missed is not None:
            app.assessment_missed = body.assessment_missed
            updated = True

        # Technical
        if body.technical_completed is not None:
            if body.technical_completed and not app.technical_completed:
                app.technical_completed_at = now
            elif not body.technical_completed:
                app.technical_completed_at = None
            app.technical_completed = body.technical_completed
            updated = True

        if body.technical_scheduled is not None:
            app.technical_scheduled = body.technical_scheduled
            updated = True

        if body.technical_missed is not None:
            app.technical_missed = body.technical_missed
            updated = True

        if updated:
            app.manually_overridden = True
            app.last_activity_at = now
            await db.commit()
            await db.refresh(app)
        
        return ApplicationOut.model_validate(app)


@router.delete("/{app_id}", status_code=204)
async def delete_application(request: Request, app_id: uuid.UUID):
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.id == app_id,
                JobApplication.user_id == user_id,
            )
        )
        app = result.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        await db.delete(app)
        await db.commit()


@router.post("/scan")
async def trigger_scan(request: Request):
    """Run a full inbox scan for the current user and return the result."""
    from sqlalchemy import select as sa_select
    from app.models.user import User
    from app.services.email_scanner import scan_inbox

    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(sa_select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        new_count, emails_checked = await scan_inbox(user, db)
        logger.info("Manual scan complete for %s — %d new applications (%d emails checked)", user.email, new_count, emails_checked)

    return {"new_applications": new_count, "emails_checked": emails_checked}


@router.delete("/users/me", status_code=204)
async def delete_account(request: Request):
    """Delete all user data and revoke Google tokens."""
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as sa_select
        from app.models.user import User
        from app.services import gmail as gmail_service

        result = await db.execute(sa_select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.google_access_token:
            await gmail_service.revoke_token(user.google_access_token)

        await db.delete(user)  # cascades to job_applications
        await db.commit()

    request.session.clear()
