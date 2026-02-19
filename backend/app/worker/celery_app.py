from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "hiretrace",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    # Scan all user inboxes every 15 minutes
    "scan-inboxes-every-15-min": {
        "task": "app.worker.tasks.scan_all_inboxes",
        "schedule": 900,  # seconds
    },
    # Mark ghosted applications daily at 08:00 UTC
    "mark-ghosted-daily": {
        "task": "app.worker.tasks.mark_ghosted_applications",
        "schedule": crontab(hour=8, minute=0),
    },
}
