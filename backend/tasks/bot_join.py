"""
Bot join task — fires 2 minutes before scheduled_at.
Creates a Recall.ai bot and registers its ID on the interview.
"""
from __future__ import annotations
import asyncio
import httpx
import structlog
from celery_app import celery
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

MAX_JOIN_ATTEMPTS = 2


@celery.task(name="tasks.bot_join.bot_join_task", bind=True, max_retries=MAX_JOIN_ATTEMPTS)
def bot_join_task(self, interview_id: str) -> None:
    asyncio.run(_bot_join(self, interview_id))


async def _bot_join(task, interview_id: str) -> None:
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import Interview

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Interview).where(Interview.id == interview_id))
        interview = result.scalar_one_or_none()
        if interview is None:
            log.error("bot_join_interview_not_found", interview_id=interview_id)
            return
        if interview.status == "CANCELLED":
            log.info("bot_join_cancelled_interview", interview_id=interview_id)
            return

        interview.status = "JOINING"

        try:
            bot_id = await _create_recall_bot(interview)
            interview.recall_bot_id = bot_id
            log.info("bot_join_success", interview_id=interview_id, bot_id=bot_id)
        except Exception as exc:
            log.error("bot_join_failed", interview_id=interview_id, error=str(exc),
                      attempt=task.request.retries + 1)
            if task.request.retries < MAX_JOIN_ATTEMPTS - 1:
                raise task.retry(exc=exc, countdown=30)
            # All attempts exhausted
            interview.status = "FAILED"
            from tasks.notifications import _send_notification_sync
            _send_notification_sync(interview_id, "FAILED")

        await db.commit()


async def _create_recall_bot(interview) -> str:
    """Call Recall.ai API to create and schedule a bot for the interview."""
    headers = {
        "Authorization": f"Token {settings.recall_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "meeting_url": interview.meeting_link,
        "bot_name": f"{interview.ai_persona_name or 'Scout'} (AI Interviewer)",
        "transcription_options": {
            "provider": "deepgram",
            "deepgram": {"language": "en-US"},
        },
        "real_time_transcription": {
            "destination_url": f"https://api.krino.ai/webhooks/recall",
            "partial_results": False,
        },
        "automatic_leave": {
            "waiting_room_timeout": 600,  # 10 min no-show
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.recall_api_base}/bot/",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["id"]
