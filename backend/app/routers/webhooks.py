"""
Recall.ai incoming webhooks.
All state transitions triggered by the bot go through here.
"""
from __future__ import annotations
import hashlib
import hmac
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, status
from sqlalchemy import select
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Interview, InterviewTranscript

router = APIRouter()
settings = get_settings()

# Recall.ai sends HMAC-SHA256 in X-Recall-Signature header
def _verify_recall_signature(payload: bytes, signature: str) -> bool:
    if not settings.recall_webhook_secret:
        return True  # skip in dev
    expected = hmac.new(
        settings.recall_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/recall")
async def recall_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("X-Recall-Signature", "")
    if not _verify_recall_signature(payload, sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    body = await request.json()
    event = body.get("event")
    data = body.get("data", {})

    async with AsyncSessionLocal() as db:
        try:
            if event == "bot.join_requested":
                await _handle_bot_joining(data, db)
            elif event == "bot.in_waiting_room":
                await _handle_bot_waiting(data, db)
            elif event == "bot.call_ended":
                await _handle_call_ended(data, db)
            elif event == "bot.fatal_error":
                await _handle_fatal_error(data, db)
            elif event == "transcript.data":
                await _handle_transcript(data, db)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            import structlog
            structlog.get_logger().error("recall_webhook_error", event=event, error=str(exc))

    return {"ok": True}


async def _get_interview_by_bot_id(bot_id: str, db) -> Interview | None:
    result = await db.execute(
        select(Interview).where(Interview.recall_bot_id == bot_id)
    )
    return result.scalar_one_or_none()


async def _handle_bot_joining(data: dict, db) -> None:
    bot_id = data.get("bot_id")
    iv = await _get_interview_by_bot_id(bot_id, db)
    if iv and iv.status == "SCHEDULED":
        iv.status = "JOINING"


async def _handle_bot_waiting(data: dict, db) -> None:
    bot_id = data.get("bot_id")
    iv = await _get_interview_by_bot_id(bot_id, db)
    if iv and iv.status in {"JOINING", "SCHEDULED"}:
        iv.status = "WAITING"


async def _handle_call_ended(data: dict, db) -> None:
    bot_id = data.get("bot_id")
    iv = await _get_interview_by_bot_id(bot_id, db)
    if iv is None:
        return
    if iv.status == "IN_PROGRESS":
        iv.status = "COMPLETED"
        iv.ended_at = datetime.now(timezone.utc)
        # Trigger async scoring
        _enqueue_scoring(iv.id)
    iv.recording_url = data.get("recording_url")


async def _handle_fatal_error(data: dict, db) -> None:
    bot_id = data.get("bot_id")
    iv = await _get_interview_by_bot_id(bot_id, db)
    if iv and iv.status not in {"COMPLETED", "SCORED"}:
        iv.status = "FAILED"
        _enqueue_notification(iv.id, "FAILED")


async def _handle_transcript(data: dict, db) -> None:
    """Append real-time transcript turn from Recall.ai / Deepgram."""
    bot_id = data.get("bot_id")
    iv = await _get_interview_by_bot_id(bot_id, db)
    if iv is None:
        return

    result = await db.execute(
        select(InterviewTranscript).where(InterviewTranscript.interview_id == iv.id)
    )
    transcript = result.scalar_one_or_none()
    if transcript is None:
        transcript = InterviewTranscript(interview_id=iv.id, turns_json=[])
        db.add(transcript)

    turn = {
        "id": data.get("id"),
        "speaker": data.get("speaker"),  # AI|CANDIDATE|OBSERVER
        "text": data.get("text"),
        "timestamp_ms": data.get("timestamp_ms"),
        "confidence": data.get("confidence"),
        "is_human_conducted": iv.takeover_at is not None,
    }
    transcript.turns_json = list(transcript.turns_json) + [turn]


def _enqueue_scoring(interview_id: str) -> None:
    try:
        from tasks.scoring import score_interview_task
        score_interview_task.delay(interview_id)
    except Exception:
        import structlog
        structlog.get_logger().warning("scoring_enqueue_failed", interview_id=interview_id)


def _enqueue_notification(interview_id: str, event_type: str) -> None:
    try:
        from tasks.notifications import send_notification_task
        send_notification_task.delay(interview_id, event_type)
    except Exception:
        pass
