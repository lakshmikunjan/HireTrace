"""
Email scanner orchestrator.

Fetches new Gmail messages for a user, deduplicates via email_message_id (and
a 48-hour fuzzy window on company+title), parses each email, and upserts job
applications into the database.  Also scans for rejection and assessment emails
and updates statuses accordingly.
"""
import logging
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parseaddr

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.application import JobApplication
from app.services import gmail as gmail_service
from app.services.parser import parse_email
from app.services.parser.rejection import extract_company
from app.services.gmail import (
    list_phone_screen_messages,
    list_technical_messages,
)

logger = logging.getLogger("hiretrace.scanner")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cap(val: str | None, limit: int = 250) -> str | None:
    return val[:limit] if val else None


def _extract_display_name(from_header: str) -> str | None:
    """
    Parse the display name from a 'From' header.
    e.g.  '"Google Recruiting" <noreply@google.com>'  →  'Google Recruiting'
    Returns None for generic/noise sender names.
    """
    _GENERIC = {
        "no-reply", "noreply", "do not reply", "donotreply",
        "notifications", "notification", "mailer", "support",
        "jobs", "recruiting", "recruitment", "talent", "careers",
        "hiring", "hr", "team", "alerts", "info", "hello",
        "indeed", "linkedin", "glassdoor",
    }
    display, _ = parseaddr(from_header)
    display = display.strip().strip('"').strip("'")
    if not display or len(display) < 3:
        return None
    if display.lower() in _GENERIC:
        return None
    return display


def _fuzzy_ratio(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _detect_status_from_body(body: str) -> str:
    """
    Peek at the email body to detect if this confirmation email actually signals
    a stage beyond 'applied' (e.g. a phone-screen invite, offer, etc.).
    """
    lower = body.lower()
    OFFER_PHRASES = [
        "we'd like to offer", "we are pleased to offer",
        "offer of employment", "formal offer",
    ]
    TECHNICAL_PHRASES = [
        "technical interview", "coding interview", "system design interview",
        "tech interview", "virtual onsite",
    ]
    PHONE_PHRASES = [
        "phone screen", "phone interview", "intro call",
        "introductory call", "recruiter call", "15-minute call",
        "30-minute call", "quick call", "phone conversation",
    ]
    if any(p in lower for p in OFFER_PHRASES):
        return "offer"
    if any(p in lower for p in TECHNICAL_PHRASES):
        return "technical"
    if any(p in lower for p in PHONE_PHRASES):
        return "phone_screen"
    return "applied"


async def _find_duplicate_application(
    db: AsyncSession,
    user_id: str,
    company: str | None,
    title: str | None,
    received_at: datetime,
) -> "JobApplication | None":
    """
    Look for an existing applied row within a 48-hour window that is
    'close enough' to the current email (fuzzy company + title match).
    Returns the existing row if found, otherwise None.
    """
    if not company and not title:
        return None

    window_start = received_at - timedelta(hours=48)
    window_end = received_at + timedelta(hours=48)

    result = await db.execute(
        select(JobApplication).where(
            JobApplication.user_id == user_id,
            JobApplication.applied_at >= window_start,
            JobApplication.applied_at <= window_end,
        )
    )
    candidates = result.scalars().all()

    for candidate in candidates:
        company_ok = (
            _fuzzy_ratio(candidate.company_name, company) >= 0.82
            or (company and candidate.company_name
                and (company.lower() in candidate.company_name.lower()
                     or candidate.company_name.lower() in company.lower()))
        )
        title_ok = (
            not title
            or not candidate.job_title
            or _fuzzy_ratio(candidate.job_title, title) >= 0.75
        )
        if company_ok and title_ok:
            return candidate

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _compute_after_date(user: User) -> str:
    """
    Return a Gmail 'after:YYYY/MM/DD' filter string.
    On the first ever scan, go back to 2026-01-01.
    On subsequent scans, use (last_scan_at - 2 hours) so we never miss an
    email that arrived just before the previous scan completed.
    """
    from datetime import date as _date, timedelta as _td
    year_start = _date(2026, 1, 1)
    if user.last_scan_at:
        cutoff = max(
            (user.last_scan_at - _td(hours=2)).date(),
            year_start,
        )
    else:
        cutoff = year_start
    return f"after:{cutoff.strftime('%Y/%m/%d')}"


async def scan_inbox(user: User, db: AsyncSession) -> tuple[int, int]:
    """
    Scan the user's Gmail inbox for new application confirmation emails,
    rejection emails, assessment emails, phone screen invites, and technical
    interview invitations.  Also repairs any existing 2026 rows that are still
    missing company / title / location.
    Returns (new_applications_saved, emails_checked).
    """
    after_date = _compute_after_date(user)
    logger.info("Scanning inbox for %s (filter: %s)", user.email, after_date)

    new_count, emails_checked = await _scan_applications(user, db, after_date)
    await _scan_rejections(user, db, after_date)
    await _scan_assessments(user, db, after_date)
    await _scan_phone_screens(user, db, after_date)
    await _scan_technical_interviews(user, db, after_date)
    await _repair_null_fields(user, db)

    user.last_scan_at = datetime.now(timezone.utc)
    await db.commit()

    return new_count, emails_checked


# ---------------------------------------------------------------------------
# Repair: re-fetch & re-parse rows that are missing company / title / location
# ---------------------------------------------------------------------------

async def _repair_null_fields(user: User, db: AsyncSession) -> None:
    """
    For any 2026 row that still has a null company_name, job_title, or
    location AND has a stored email_message_id, re-fetch the full email from
    Gmail and re-parse it with the current (improved) parsers.
    Only fills in fields that are currently null — never overwrites data.
    """
    from datetime import date as _date
    year_start = _date(2026, 1, 1)

    result = await db.execute(
        select(JobApplication).where(
            JobApplication.user_id == user.id,
            JobApplication.applied_at >= year_start,
            JobApplication.email_message_id.isnot(None),
            # Only repair rows that are missing at least one key field
            (
                JobApplication.company_name.is_(None)
                | JobApplication.job_title.is_(None)
                | JobApplication.location.is_(None)
            ),
        ).limit(500)
    )
    rows = result.scalars().all()

    for row in rows:
        try:
            detail = gmail_service.get_message_detail(user, row.email_message_id)
            snippet = detail["snippet"] or ""
            html_body = detail["body"] or ""
            body = (snippet + "\n" + html_body).strip() if snippet else html_body

            parsed = parse_email(
                sender=detail["sender"],
                subject=detail["subject"],
                body=body,
            )

            # Metadata fallback: sender display name
            if not parsed.company_name:
                display = _extract_display_name(detail["sender"])
                if display:
                    parsed.company_name = display

            # Only fill genuinely null fields — preserve existing data
            if parsed.company_name and not row.company_name:
                row.company_name = _cap(parsed.company_name)
            if parsed.job_title and not row.job_title:
                row.job_title = _cap(parsed.job_title)
            if parsed.location and not row.location:
                row.location = _cap(parsed.location)
            if parsed.salary_range and not row.salary_range:
                row.salary_range = _cap(parsed.salary_range)

        except Exception:
            pass  # Don't let one bad fetch break the whole repair pass


# ---------------------------------------------------------------------------
# Application confirmation scan
# ---------------------------------------------------------------------------

async def _scan_applications(user: User, db: AsyncSession, after_date: str = "after:2026/01/01") -> tuple[int, int]:
    """Scan for application confirmation emails and create new records.
    Returns (new_count, emails_checked).
    """
    messages = gmail_service.list_new_messages(user, after_date=after_date)
    emails_checked = len(messages)
    logger.info("Gmail returned %d messages for %s", emails_checked, user.email)
    new_count = 0

    for msg_ref in messages:
        message_id = msg_ref["id"]

        # Fast path: exact dedup by message ID
        existing_by_id = await db.execute(
            select(JobApplication).where(JobApplication.email_message_id == message_id)
        )
        if existing_by_id.scalar_one_or_none() is not None:
            continue

        detail = gmail_service.get_message_detail(user, message_id)

        # Skip LinkedIn notification emails that are not application confirmations.
        # Checking subject here (before parsing) avoids an unnecessary LLM call.
        subject_lower = detail["subject"].lower()
        if "was viewed by" in subject_lower or "viewed your profile" in subject_lower:
            continue

        snippet = detail["snippet"] or ""
        html_body = detail["body"] or ""
        body = (snippet + "\n" + html_body).strip() if snippet else html_body

        result = parse_email(
            sender=detail["sender"],
            subject=detail["subject"],
            body=body,
        )

        received_at = detail["date"] or datetime.now(timezone.utc)

        # Metadata fallback 1: sender display name
        if not result.company_name:
            display = _extract_display_name(detail["sender"])
            if display:
                result.company_name = display

        # Metadata fallback 2: snippet context (first ~55 chars) so the row is
        # identifiable in the UI even when the company name can't be parsed.
        # Only for direct applications - never show "Indeed Apply" or "LinkedIn Apply"
        if not result.company_name and result.platform == "direct" and snippet:
            preview = snippet[:60].strip()
            if preview:
                result.company_name = preview if len(preview) <= 55 else preview[:52].rsplit(" ", 1)[0] + "…"
        # For platform emails, leave company_name as None rather than showing platform name
        elif not result.company_name and result.platform in ("linkedin", "indeed"):
            result.company_name = None

        # Windowed dedup: find a near-duplicate row in the ±48 h window.
        # Skip for platform emails (linkedin/indeed) — message_id exact-dedup
        # is sufficient and fuzzy matching creates false positives when many
        # applications share the same placeholder company ("Indeed Apply").
        fuzzy_dup = None
        if result.platform == "direct":
            fuzzy_dup = await _find_duplicate_application(
                db, user.id, result.company_name, result.job_title, received_at
            )
        if fuzzy_dup is not None:
            # Always stamp message_id so exact-dedup works on future scans
            if not fuzzy_dup.email_message_id:
                fuzzy_dup.email_message_id = message_id
            fuzzy_dup.last_activity_at = received_at

            # Platform-priority merge: prefer the direct company email's richer
            # data over the platform (LinkedIn/Indeed) confirmation email.
            if fuzzy_dup.platform in ("linkedin", "indeed") and result.platform == "direct":
                if result.company_name:
                    fuzzy_dup.company_name = _cap(result.company_name)
                if result.job_title:
                    fuzzy_dup.job_title = _cap(result.job_title)
                if result.location:
                    fuzzy_dup.location = _cap(result.location)
                if result.salary_range:
                    fuzzy_dup.salary_range = _cap(result.salary_range)
                fuzzy_dup.platform = "direct"
            continue

        # Status detection: confirmation emails sometimes invite a call/interview
        status = _detect_status_from_body(body)

        app = JobApplication(
            user_id=user.id,
            company_name=_cap(result.company_name),
            job_title=_cap(result.job_title),
            location=_cap(result.location),
            salary_range=_cap(result.salary_range),
            platform=result.platform,
            status=status,
            applied_at=received_at,
            last_activity_at=received_at,
            email_message_id=message_id,
            parse_confidence=result.confidence,
            raw_email_snippet=detail["snippet"],
        )
        try:
            async with db.begin_nested():
                db.add(app)
                await db.flush()
            new_count += 1
        except IntegrityError:
            # Concurrent scan already inserted this message — skip it
            pass

    return new_count, emails_checked


# ---------------------------------------------------------------------------
# Rejection scan
# ---------------------------------------------------------------------------

async def _scan_rejections(user: User, db: AsyncSession, after_date: str = "after:2026/01/01") -> None:
    """
    Scan for rejection emails and update matching application status to 'rejected'.
    Only updates applications that haven't been manually overridden.
    """
    messages = gmail_service.list_rejection_messages(user, after_date=after_date)

    for msg_ref in messages:
        message_id = msg_ref["id"]

        detail = gmail_service.get_message_detail(user, message_id)
        snippet = detail["snippet"] or ""
        html_body = detail["body"] or ""
        body = (snippet + "\n" + html_body).strip() if snippet else html_body
        company = extract_company(
            sender=detail["sender"],
            subject=detail["subject"],
            body=body,
        )
        # Try display name as fallback for rejection company
        if not company:
            company = _extract_display_name(detail["sender"])
        if not company:
            continue

        received_at = detail["date"] or datetime.now(timezone.utc)

        # Deduplication: check if this email is already stored
        dup = await db.execute(
            select(JobApplication).where(JobApplication.email_message_id == message_id)
        )
        existing = dup.scalar_one_or_none()
        if existing is not None:
            # Already marked rejected → nothing to do
            if existing.status == "rejected":
                continue
            # Stored as "applied" (e.g. LinkedIn sends the same email for both
            # confirmation and rejection) → update it directly to rejected
            if not existing.manually_overridden:
                existing.status = "rejected"
                existing.rejected_at = received_at
                existing.last_activity_at = received_at
            continue

        # Try to find a matching active application and update it
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user.id,
                JobApplication.company_name.ilike(f"%{company}%"),
                JobApplication.manually_overridden.is_(False),
                JobApplication.status.in_(["applied", "phone_screen", "technical", "assessment"]),
            )
        )
        matched_apps = result.scalars().all()

        if matched_apps:
            # Update only the most recent matching application to avoid duplicates
            latest_app = max(matched_apps, key=lambda app: app.applied_at or app.created_at)
            latest_app.status = "rejected"
            latest_app.rejected_at = received_at
            latest_app.last_activity_at = received_at
            # Tag with rejection email ID to prevent reprocessing
            if not latest_app.email_message_id:
                latest_app.email_message_id = message_id
        else:
            # Phase 2: ilike failed — try fuzzy ratio match across all non-rejected/non-offer apps.
            # This handles cases where the rejection email company name is slightly different
            # (e.g. "HungerRush" vs "HungerRush, Inc.") or where the ilike pattern didn't fire.
            fuzzy_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user.id,
                    JobApplication.company_name.isnot(None),
                    JobApplication.manually_overridden.is_(False),
                    JobApplication.status.notin_(["rejected", "offer"]),
                )
            )
            active_apps = fuzzy_result.scalars().all()

            best_match = None
            best_score = 0.0
            for candidate in active_apps:
                score = _fuzzy_ratio(candidate.company_name, company)
                # Also accept clear substring containment
                if score < 0.82 and candidate.company_name and company:
                    cn = candidate.company_name.lower()
                    co = company.lower()
                    if co in cn or cn in co:
                        score = 0.82
                if score >= 0.82 and score > best_score:
                    best_score = score
                    best_match = candidate

            if best_match is not None:
                best_match.status = "rejected"
                best_match.rejected_at = received_at
                best_match.last_activity_at = received_at
                if not best_match.email_message_id:
                    best_match.email_message_id = message_id
            else:
                # Phase 3: Still no match — create a new rejected record as a last resort.
                # Guard against creating a duplicate rejection for the same company within 24 h.
                recent_window = received_at - timedelta(hours=24)
                existing_rejection = await db.execute(
                    select(JobApplication).where(
                        JobApplication.user_id == user.id,
                        JobApplication.company_name.ilike(f"%{company}%"),
                        JobApplication.status == "rejected",
                        JobApplication.applied_at >= recent_window,
                    )
                )
                if existing_rejection.scalar_one_or_none() is None:
                    db.add(JobApplication(
                        user_id=user.id,
                        company_name=_cap(company),
                        job_title=None,
                        platform="direct",
                        status="rejected",
                        applied_at=received_at,
                        rejected_at=received_at,
                        last_activity_at=received_at,
                        email_message_id=message_id,
                        parse_confidence=0.5,
                        raw_email_snippet=detail["snippet"],
                    ))


# ---------------------------------------------------------------------------
# Assessment scan
# ---------------------------------------------------------------------------

async def _scan_assessments(user: User, db: AsyncSession, after_date: str = "after:2026/01/01") -> None:
    """
    Scan for assessment/coding-challenge emails and update matching application
    status to 'assessment'. Only updates applications that haven't been manually
    overridden and are still in 'applied' status.
    """
    messages = gmail_service.list_assessment_messages(user, after_date=after_date)

    for msg_ref in messages:
        message_id = msg_ref["id"]

        detail = gmail_service.get_message_detail(user, message_id)
        snippet = detail["snippet"] or ""
        html_body = detail["body"] or ""
        body = (snippet + "\n" + html_body).strip() if snippet else html_body
        company = extract_company(
            sender=detail["sender"],
            subject=detail["subject"],
            body=body,
        )
        if not company:
            company = _extract_display_name(detail["sender"])
        if not company:
            continue

        # Deduplication: skip if this email was already processed
        dup = await db.execute(
            select(JobApplication).where(JobApplication.email_message_id == message_id)
        )
        if dup.scalar_one_or_none() is not None:
            continue

        received_at = detail["date"] or datetime.now(timezone.utc)

        # Try to find a matching applied application and update it
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user.id,
                JobApplication.company_name.ilike(f"%{company}%"),
                JobApplication.manually_overridden.is_(False),
                JobApplication.status == "applied",
            )
        )
        matched_apps = result.scalars().all()

        if matched_apps:
            # Update only the most recent matching application to avoid duplicates
            latest_app = max(matched_apps, key=lambda app: app.applied_at or app.created_at)
            latest_app.status = "assessment"
            latest_app.last_activity_at = received_at
            if not latest_app.email_message_id:
                latest_app.email_message_id = message_id
        else:
            # No matching applied app — create a new assessment record
            # But first check if we already have an assessment for this company recently
            recent_window = received_at - timedelta(hours=24)
            existing_assessment = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user.id,
                    JobApplication.company_name.ilike(f"%{company}%"),
                    JobApplication.status == "assessment",
                    JobApplication.applied_at >= recent_window,
                )
            )
            if existing_assessment.scalar_one_or_none() is None:
                db.add(JobApplication(
                    user_id=user.id,
                    company_name=_cap(company),
                    job_title=None,
                    platform="direct",
                    status="assessment",
                    applied_at=received_at,
                    last_activity_at=received_at,
                    email_message_id=message_id,
                    parse_confidence=0.5,
                    raw_email_snippet=detail["snippet"],
                ))


# ---------------------------------------------------------------------------
# Phone screen invite scan
# ---------------------------------------------------------------------------

async def _scan_phone_screens(user: User, db: AsyncSession, after_date: str = "after:2026/01/01") -> None:
    """
    Scan for recruiter / scheduling emails and advance matching 'applied'
    applications to 'phone_screen'.
    """
    messages = list_phone_screen_messages(user, after_date=after_date)

    for msg_ref in messages:
        message_id = msg_ref["id"]

        # Skip already-processed messages
        dup = await db.execute(
            select(JobApplication).where(JobApplication.email_message_id == message_id)
        )
        if dup.scalar_one_or_none() is not None:
            continue

        detail = gmail_service.get_message_detail(user, message_id)
        snippet = detail["snippet"] or ""
        html_body = detail["body"] or ""
        body = (snippet + "\n" + html_body).strip() if snippet else html_body

        company = extract_company(
            sender=detail["sender"],
            subject=detail["subject"],
            body=body,
        )
        if not company:
            company = _extract_display_name(detail["sender"])
        if not company:
            continue

        received_at = detail["date"] or datetime.now(timezone.utc)

        # Find the most recent matching 'applied' app and advance it
        result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user.id,
                JobApplication.company_name.ilike(f"%{company}%"),
                JobApplication.manually_overridden.is_(False),
                JobApplication.status == "applied",
            )
        )
        matched = result.scalars().all()
        if not matched:
            # Fuzzy fallback
            fuzzy_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user.id,
                    JobApplication.company_name.isnot(None),
                    JobApplication.manually_overridden.is_(False),
                    JobApplication.status == "applied",
                )
            )
            candidates = fuzzy_result.scalars().all()
            best, best_score = None, 0.0
            for c in candidates:
                score = _fuzzy_ratio(c.company_name, company)
                if score >= 0.82 and score > best_score:
                    best_score, best = score, c
            if best:
                matched = [best]

        if matched:
            latest = max(matched, key=lambda a: a.applied_at or a.created_at)
            latest.status = "phone_screen"
            latest.last_activity_at = received_at
            if not latest.email_message_id:
                latest.email_message_id = message_id


# ---------------------------------------------------------------------------
# Technical interview invite scan
# ---------------------------------------------------------------------------

async def _scan_technical_interviews(user: User, db: AsyncSession, after_date: str = "after:2026/01/01") -> None:
    """
    Scan for technical interview invitation emails and advance matching
    applications (applied / phone_screen / assessment) to 'technical'.
    """
    messages = list_technical_messages(user, after_date=after_date)

    for msg_ref in messages:
        message_id = msg_ref["id"]

        dup = await db.execute(
            select(JobApplication).where(JobApplication.email_message_id == message_id)
        )
        if dup.scalar_one_or_none() is not None:
            continue

        detail = gmail_service.get_message_detail(user, message_id)
        snippet = detail["snippet"] or ""
        html_body = detail["body"] or ""
        body = (snippet + "\n" + html_body).strip() if snippet else html_body

        company = extract_company(
            sender=detail["sender"],
            subject=detail["subject"],
            body=body,
        )
        if not company:
            company = _extract_display_name(detail["sender"])
        if not company:
            continue

        received_at = detail["date"] or datetime.now(timezone.utc)

        result = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == user.id,
                JobApplication.company_name.ilike(f"%{company}%"),
                JobApplication.manually_overridden.is_(False),
                JobApplication.status.in_(["applied", "phone_screen", "assessment"]),
            )
        )
        matched = result.scalars().all()
        if not matched:
            fuzzy_result = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == user.id,
                    JobApplication.company_name.isnot(None),
                    JobApplication.manually_overridden.is_(False),
                    JobApplication.status.in_(["applied", "phone_screen", "assessment"]),
                )
            )
            candidates = fuzzy_result.scalars().all()
            best, best_score = None, 0.0
            for c in candidates:
                score = _fuzzy_ratio(c.company_name, company)
                if score >= 0.82 and score > best_score:
                    best_score, best = score, c
            if best:
                matched = [best]

        if matched:
            latest = max(matched, key=lambda a: a.applied_at or a.created_at)
            latest.status = "technical"
            latest.last_activity_at = received_at
            if not latest.email_message_id:
                latest.email_message_id = message_id
