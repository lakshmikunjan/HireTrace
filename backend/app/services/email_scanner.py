"""
Email scanner orchestrator.

Fetches new Gmail messages for a user, deduplicates via email_message_id,
parses each email, and upserts job applications into the database.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.application import JobApplication
from app.services import gmail as gmail_service
from app.services.parser import parse_email


async def scan_inbox(user: User, db: AsyncSession) -> int:
    """
    Scan the user's Gmail inbox for new application confirmation emails.
    Returns the number of new applications saved.
    """
    messages = gmail_service.list_new_messages(user)
    new_count = 0

    for msg_ref in messages:
        message_id = msg_ref["id"]

        # Deduplication check
        existing = await db.execute(
            select(JobApplication).where(JobApplication.email_message_id == message_id)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        # Fetch full message detail
        detail = gmail_service.get_message_detail(user, message_id)

        # Run hybrid parsing
        result = parse_email(
            sender=detail["sender"],
            subject=detail["subject"],
            body=detail["body"],
        )

        # Create the application record
        app = JobApplication(
            user_id=user.id,
            company_name=result.company_name,
            job_title=result.job_title,
            location=result.location,
            salary_range=result.salary_range,
            platform=result.platform,
            status="applied",
            applied_at=detail["date"] or datetime.now(timezone.utc),
            last_activity_at=detail["date"] or datetime.now(timezone.utc),
            email_message_id=message_id,
            parse_confidence=result.confidence,
            raw_email_snippet=detail["snippet"],
        )
        db.add(app)
        new_count += 1

    # Update last_scan_at timestamp
    user.last_scan_at = datetime.now(timezone.utc)
    await db.commit()

    return new_count
