"""Job application CRUD + manual scan trigger."""
import uuid

from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy import select, delete

from app.database import AsyncSessionLocal
from app.models.application import JobApplication
from app.routers.auth import require_user
from app.schemas.application import ApplicationOut, ApplicationStatusUpdate

router = APIRouter()


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
        q = select(JobApplication).where(JobApplication.user_id == user_id)

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


@router.post("/scan", status_code=202)
async def trigger_scan(request: Request):
    """Enqueue a manual inbox scan for the current user."""
    user_id = require_user(request)
    from app.worker.tasks import scan_user_inbox
    scan_user_inbox.delay(user_id)
    return {"detail": "Scan queued"}


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
