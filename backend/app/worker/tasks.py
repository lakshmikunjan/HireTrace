"""Celery tasks for background email scanning and ghosting detection."""
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update

from app.worker.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.application import JobApplication
from app.config import settings


def _run_async(coro):
    """Run an async coroutine in a Celery task (synchronous context)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.worker.tasks.scan_all_inboxes", bind=True, max_retries=3)
def scan_all_inboxes(self):
    """Scan Gmail inboxes for all users who have connected their account."""
    async def _scan():
        from app.services.email_scanner import scan_inbox

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.google_refresh_token.isnot(None))
            )
            users = result.scalars().all()

            total_new = 0
            for user in users:
                try:
                    new = await scan_inbox(user, db)
                    total_new += new
                except Exception as exc:
                    # Log and continue — don't fail the whole task for one user
                    print(f"[scan_all_inboxes] Error scanning user {user.id}: {exc}")

            return total_new

    return _run_async(_scan())


@celery_app.task(name="app.worker.tasks.scan_user_inbox", bind=True, max_retries=3)
def scan_user_inbox(self, user_id: str):
    """Scan Gmail inbox for a single user (triggered manually via POST /scan)."""
    async def _scan():
        from app.services.email_scanner import scan_inbox

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return 0
            return await scan_inbox(user, db)

    return _run_async(_scan())


@celery_app.task(name="app.worker.tasks.mark_ghosted_applications")
def mark_ghosted_applications():
    """
    Mark applications as 'ghosted' if they have had no activity
    for more than GHOSTING_DAYS days and are still in 'applied' status.
    """
    async def _mark():
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.ghosting_days)

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(JobApplication)
                .where(
                    JobApplication.status == "applied",
                    JobApplication.manually_overridden.is_(False),
                    JobApplication.last_activity_at < cutoff,
                )
                .values(status="ghosted")
            )
            await db.commit()

    _run_async(_mark())
