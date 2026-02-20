import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, applications, dashboard

logger = logging.getLogger("hiretrace.scanner")

# ---------------------------------------------------------------------------
# Periodic background scanner (replaces Celery Beat for dev/single-process)
# ---------------------------------------------------------------------------

SCAN_INTERVAL_SECONDS = 15 * 60  # every 15 minutes
INITIAL_DELAY_SECONDS  = 60       # wait 1 min after startup before first scan


async def _periodic_scan_all_users() -> None:
    """
    Background coroutine: wakes up every 15 minutes and scans every user
    whose Gmail token is connected.  Runs for the lifetime of the server.
    """
    await asyncio.sleep(INITIAL_DELAY_SECONDS)
    while True:
        try:
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from app.models.user import User
            from app.services.email_scanner import scan_inbox

            # Collect user IDs first so we don't hold a long-lived session
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_periodic_scan_all_users())
    logger.info("Periodic inbox scanner started (interval=%ds)", SCAN_INTERVAL_SECONDS)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Periodic inbox scanner stopped")


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
