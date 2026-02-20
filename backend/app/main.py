import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, applications, dashboard

logger = logging.getLogger("hiretrace.scanner")

# ---------------------------------------------------------------------------
# Periodic background scanner
# ---------------------------------------------------------------------------

SCAN_INTERVAL_SECONDS = 60 * 60  # every hour
INITIAL_DELAY_SECONDS  = 60       # wait 1 min after startup before first scan


async def _periodic_scan_all_users() -> None:
    """Wakes up every hour and scans every connected user's Gmail inbox."""
    await asyncio.sleep(INITIAL_DELAY_SECONDS)
    while True:
        try:
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from app.models.user import User
            from app.services.email_scanner import scan_inbox

            async with AsyncSessionLocal() as db:
                rows = await db.execute(
                    select(User.id).where(User.google_access_token.isnot(None))
                )
                user_ids = [r[0] for r in rows.all()]

            logger.info("Periodic scan: %d user(s) queued", len(user_ids))

            for uid in user_ids:
                try:
                    async with AsyncSessionLocal() as db:
                        user = await db.get(User, uid)
                        if user:
                            new_count = await scan_inbox(user, db)
                            logger.info(
                                "Periodic scan done for %s — %d new", user.email, new_count
                            )
                except Exception:
                    logger.exception("Periodic scan failed for user %s", uid)

        except Exception:
            logger.exception("Periodic scan loop error")

        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Nightly auto-ghosting
# ---------------------------------------------------------------------------

GHOST_INTERVAL_SECONDS = 24 * 60 * 60  # run daily
GHOST_INITIAL_DELAY    = 10 * 60        # start 10 min after server startup
GHOST_DAYS             = 90


async def _nightly_auto_ghost() -> None:
    """
    Flip 'applied' applications with no activity in 90+ days to 'ghosted'.
    Respects manually_overridden so user edits are never clobbered.
    """
    await asyncio.sleep(GHOST_INITIAL_DELAY)
    while True:
        try:
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from app.models.application import JobApplication

            cutoff = datetime.now(timezone.utc) - timedelta(days=GHOST_DAYS)
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(JobApplication).where(
                        JobApplication.status == "applied",
                        JobApplication.last_activity_at < cutoff,
                        JobApplication.manually_overridden.is_(False),
                    )
                )
                apps = result.scalars().all()
                for app in apps:
                    app.status = "ghosted"
                await db.commit()

            if apps:
                logger.info("Auto-ghost: marked %d application(s) as ghosted", len(apps))

        except Exception:
            logger.exception("Auto-ghost task error")

        await asyncio.sleep(GHOST_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Weekly digest email
# ---------------------------------------------------------------------------

def _seconds_until_next_monday_8am_utc() -> float:
    """Return seconds until next Monday 08:00 UTC (or this Monday if it hasn't passed)."""
    now = datetime.now(timezone.utc)
    days_ahead = (0 - now.weekday()) % 7  # Monday = 0
    if days_ahead == 0 and now.hour >= 8:
        days_ahead = 7
    target = (now + timedelta(days=days_ahead)).replace(
        hour=8, minute=0, second=0, microsecond=0
    )
    return max(0.0, (target - now).total_seconds())


def _build_digest_html(
    email: str,
    week_count: int,
    total: int,
    response_rate: str,
    advanced: list,
) -> str:
    WEEKLY_GOAL = 150
    goal_pct = min(100, round(week_count / WEEKLY_GOAL * 100))
    bar_color = "#10b981" if goal_pct >= 100 else "#3b82f6" if goal_pct >= 50 else "#6366f1"
    goal_label = "🎉 Goal reached!" if goal_pct >= 100 else f"{goal_pct}% of weekly goal"

    STATUS_LABELS = {
        "phone_screen": "Phone Screen",
        "assessment":   "Assessment",
        "technical":    "Technical",
        "offer":        "Offer",
    }
    STATUS_COLORS = {
        "phone_screen": "#ede9fe; color:#7c3aed",
        "assessment":   "#ffedd5; color:#c2410c",
        "technical":    "#fef3c7; color:#b45309",
        "offer":        "#d1fae5; color:#065f46",
    }

    rows_html = ""
    for app in advanced[:10]:
        label = STATUS_LABELS.get(app.status, app.status.title())
        style = STATUS_COLORS.get(app.status, "#f3f4f6; color:#374151")
        company = app.company_name or "Unknown"
        title_part = f" <span style='color:#9ca3af'>· {app.job_title}</span>" if app.job_title else ""
        rows_html += f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;font-size:14px;color:#111827;">
            {company}{title_part}
          </td>
          <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;text-align:right;">
            <span style="background:{style};font-size:11px;padding:3px 10px;border-radius:9999px;font-weight:600;">
              {label}
            </span>
          </td>
        </tr>"""

    advanced_section = f"""
      <h3 style="font-size:14px;font-weight:600;color:#374151;margin:24px 0 8px;">
        Advanced This Week
      </h3>
      <table width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
    """ if rows_html else ""

    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;border:1px solid #e5e7eb;overflow:hidden;">

        <!-- Header -->
        <tr>
          <td style="background:#6366f1;padding:24px 32px;">
            <p style="margin:0;font-size:20px;font-weight:700;color:#fff;">HireTrace</p>
            <p style="margin:4px 0 0;font-size:13px;color:#c7d2fe;">Weekly Job Search Digest</p>
          </td>
        </tr>

        <!-- Body -->
        <tr><td style="padding:28px 32px;">

          <!-- Stat row -->
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
            <tr>
              <td width="33%" style="text-align:center;padding:16px;background:#f9fafb;border-radius:12px;">
                <p style="margin:0;font-size:28px;font-weight:700;color:#111827;">{week_count}</p>
                <p style="margin:4px 0 0;font-size:12px;color:#6b7280;">Applied this week</p>
              </td>
              <td width="4%"></td>
              <td width="29%" style="text-align:center;padding:16px;background:#f9fafb;border-radius:12px;">
                <p style="margin:0;font-size:28px;font-weight:700;color:#6366f1;">{response_rate}</p>
                <p style="margin:4px 0 0;font-size:12px;color:#6b7280;">Response rate</p>
              </td>
              <td width="4%"></td>
              <td width="30%" style="text-align:center;padding:16px;background:#f9fafb;border-radius:12px;">
                <p style="margin:0;font-size:28px;font-weight:700;color:#111827;">{total}</p>
                <p style="margin:4px 0 0;font-size:12px;color:#6b7280;">Total 2026</p>
              </td>
            </tr>
          </table>

          <!-- Weekly goal progress -->
          <h3 style="font-size:14px;font-weight:600;color:#374151;margin:0 0 8px;">
            Weekly Goal — {goal_label}
          </h3>
          <div style="background:#e5e7eb;border-radius:9999px;height:10px;overflow:hidden;margin-bottom:4px;">
            <div style="background:{bar_color};width:{goal_pct}%;height:10px;border-radius:9999px;"></div>
          </div>
          <p style="margin:4px 0 0;font-size:12px;color:#9ca3af;">{week_count} of 150 applications</p>

          {advanced_section}

          <!-- CTA -->
          <div style="text-align:center;margin-top:28px;">
            <a href="http://localhost:5173/dashboard"
               style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
                      font-size:14px;font-weight:600;padding:12px 28px;border-radius:10px;">
              Open Dashboard
            </a>
          </div>

        </td></tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px;border-top:1px solid #f1f5f9;text-align:center;">
            <p style="margin:0;font-size:11px;color:#9ca3af;">
              Sent by HireTrace to {email} · Every Monday at 8am UTC
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def _weekly_digest() -> None:
    """Send a weekly digest email to every connected user every Monday at 08:00 UTC."""
    await asyncio.sleep(_seconds_until_next_monday_8am_utc())
    while True:
        try:
            from sqlalchemy import select, func
            from app.database import AsyncSessionLocal
            from app.models.user import User
            from app.models.application import JobApplication
            from app.services.gmail import send_digest_email

            async with AsyncSessionLocal() as db:
                rows = await db.execute(
                    select(User.id).where(User.google_access_token.isnot(None))
                )
                user_ids = [r[0] for r in rows.all()]

            for uid in user_ids:
                try:
                    async with AsyncSessionLocal() as db:
                        user = await db.get(User, uid)
                        if not user:
                            continue

                        week_start = datetime.now(timezone.utc) - timedelta(days=7)

                        total = (await db.execute(
                            select(func.count()).select_from(JobApplication)
                            .where(JobApplication.user_id == uid)
                        )).scalar() or 0

                        week_count = (await db.execute(
                            select(func.count()).select_from(JobApplication)
                            .where(
                                JobApplication.user_id == uid,
                                JobApplication.applied_at >= week_start,
                            )
                        )).scalar() or 0

                        responded = (await db.execute(
                            select(func.count()).select_from(JobApplication)
                            .where(
                                JobApplication.user_id == uid,
                                JobApplication.status.in_([
                                    "phone_screen", "assessment", "technical",
                                    "offer", "rejected",
                                ]),
                            )
                        )).scalar() or 0

                        response_rate = (
                            f"{responded / total * 100:.1f}%" if total > 0 else "—"
                        )

                        advanced_result = await db.execute(
                            select(JobApplication).where(
                                JobApplication.user_id == uid,
                                JobApplication.last_activity_at >= week_start,
                                JobApplication.status.in_([
                                    "phone_screen", "assessment", "technical", "offer",
                                ]),
                            ).order_by(JobApplication.last_activity_at.desc())
                        )
                        advanced = advanced_result.scalars().all()

                        html = _build_digest_html(
                            user.email, week_count, total, response_rate, advanced
                        )
                        send_digest_email(user, html)
                        logger.info("Weekly digest sent to %s", user.email)

                except Exception:
                    logger.exception("Weekly digest failed for user %s", uid)

        except Exception:
            logger.exception("Weekly digest loop error")

        await asyncio.sleep(7 * 24 * 60 * 60)  # sleep exactly one week


@asynccontextmanager
async def lifespan(app: FastAPI):
    scan_task  = asyncio.create_task(_periodic_scan_all_users())
    ghost_task = asyncio.create_task(_nightly_auto_ghost())
    digest_task = asyncio.create_task(_weekly_digest())
    logger.info(
        "Background tasks started: scanner(interval=%ds), auto-ghost, weekly-digest",
        SCAN_INTERVAL_SECONDS,
    )
    yield
    for task in (scan_task, ghost_task, digest_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Background tasks stopped")


app = FastAPI(
    title="HireTrace API",
    description="Automated job application tracker via Gmail parsing",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=60 * 60 * 24 * 30,  # 30 days
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])


@app.get("/health")
async def health():
    return {"status": "ok"}
