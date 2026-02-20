#!/usr/bin/env python3
"""
Re-fetch and re-parse Indeed applications from Gmail using the fixed parser.
Only fills in fields that are currently NULL — never overwrites existing data.

Run from the backend directory:
    python scripts/reparse_all_indeed.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.application import JobApplication
from app.models.user import User
from app.services import gmail as gmail_service
from app.services.parser import parse_email


def _cap(val: str | None, limit: int = 250) -> str | None:
    return val[:limit] if val else None


async def reparse_all_indeed():
    year_start = date(2026, 1, 1)

    async with AsyncSessionLocal() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        total_fixed = 0

        for user in users:
            print(f"\nUser: {user.email}")

            # Only target Indeed apps missing at least one key field
            apps_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user.id,
                    JobApplication.platform == "indeed",
                    JobApplication.applied_at >= year_start,
                    JobApplication.email_message_id.isnot(None),
                    (
                        JobApplication.company_name.is_(None)
                        | JobApplication.job_title.is_(None)
                        | JobApplication.location.is_(None)
                    ),
                )
            )
            apps = apps_result.scalars().all()
            print(f"  Found {len(apps)} Indeed applications with missing fields")

            for app in apps:
                try:
                    detail = gmail_service.get_message_detail(user, app.email_message_id)
                    snippet = detail["snippet"] or ""
                    html_body = detail["body"] or ""
                    body = (snippet + "\n" + html_body).strip() if snippet else html_body

                    parsed = parse_email(
                        sender=detail["sender"],
                        subject=detail["subject"],
                        body=body,
                    )

                    changed = False
                    if parsed.company_name and not app.company_name:
                        app.company_name = _cap(parsed.company_name)
                        changed = True
                    if parsed.job_title and not app.job_title:
                        app.job_title = _cap(parsed.job_title)
                        changed = True
                    if parsed.location and not app.location:
                        app.location = _cap(parsed.location)
                        changed = True

                    if changed:
                        total_fixed += 1
                        print(f"  ✓ {app.job_title or '?'} @ {app.company_name or '?'} ({app.location or '?'})")

                except Exception as e:
                    print(f"  ✗ {app.id}: {e}")

        await db.commit()
        print(f"\nDone — {total_fixed} applications updated.")


if __name__ == "__main__":
    asyncio.run(reparse_all_indeed())
