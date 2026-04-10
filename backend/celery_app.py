from celery import Celery
from app.config import get_settings

settings = get_settings()

celery = Celery(
    "krino",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks.bot_join", "tasks.scoring", "tasks.notifications"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # re-queue on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker
    task_routes={
        "tasks.bot_join.*": {"queue": "bot"},
        "tasks.scoring.*": {"queue": "scoring"},
        "tasks.notifications.*": {"queue": "notifications"},
    },
)
