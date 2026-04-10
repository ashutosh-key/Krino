"""
Scout agent — recruiter-facing AI assistant.
Maintains persistent conversation context per user session.
"""
from __future__ import annotations
from fastapi import APIRouter
from sqlalchemy import select
from pydantic import BaseModel
from anthropic import AsyncAnthropic
from app.deps import AnyTenantUser, DB
from app.models import ScoutConversation, InterviewScorecard, Interview, Candidate, Job
from app.config import get_settings

router = APIRouter()
settings = get_settings()
_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


class ScoutMessage(BaseModel):
    message: str
    conversation_id: str | None = None  # if None, start a new conversation


@router.post("/chat")
async def scout_chat(body: ScoutMessage, user: AnyTenantUser, db: DB):
    # Load or create conversation
    conv = await _get_or_create_conversation(body.conversation_id, user, db)

    # Build context: recent scorecards for this tenant
    context = await _build_context(user.tenant_id, db)

    # Append user message
    conv.display_messages_json = list(conv.display_messages_json)
    conv.display_messages_json.append({"role": "user", "content": body.message})

    conv.llm_messages_json = list(conv.llm_messages_json)
    conv.llm_messages_json.append({"role": "user", "content": body.message})

    system_prompt = f"""You are Scout, an AI recruiting assistant for the Krino platform.
You have access to interview scorecards, transcripts, and candidate evaluations for this organisation.

{context}

Help recruiters make informed decisions. Be concise, specific, and data-driven.
When comparing candidates, cite actual scores and criteria. Always recommend specific next actions."""

    try:
        response = await _get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=conv.llm_messages_json,
        )
        reply = response.content[0].text
    except Exception as exc:
        reply = "I'm having trouble connecting right now. Please try again in a moment."
        import structlog
        structlog.get_logger().error("scout_llm_error", error=str(exc))

    # Append assistant response
    conv.llm_messages_json.append({"role": "assistant", "content": reply})
    conv.display_messages_json.append({"role": "assistant", "content": reply})

    # Flush both in same transaction
    from datetime import datetime, timezone
    conv.updated_at = datetime.now(timezone.utc)

    return {
        "conversation_id": conv.id,
        "reply": reply,
        "display_messages": conv.display_messages_json,
    }


@router.get("/conversations")
async def list_conversations(user: AnyTenantUser, db: DB):
    result = await db.execute(
        select(ScoutConversation)
        .where(
            ScoutConversation.tenant_id == user.tenant_id,
            ScoutConversation.user_id == user.id,
        )
        .order_by(ScoutConversation.updated_at.desc())
        .limit(20)
    )
    return result.scalars().all()


async def _get_or_create_conversation(
    conversation_id: str | None,
    user,
    db,
) -> ScoutConversation:
    if conversation_id:
        result = await db.execute(
            select(ScoutConversation).where(
                ScoutConversation.id == conversation_id,
                ScoutConversation.tenant_id == user.tenant_id,
                ScoutConversation.user_id == user.id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    conv = ScoutConversation(
        tenant_id=user.tenant_id,
        user_id=user.id,
        llm_messages_json=[],
        display_messages_json=[],
    )
    db.add(conv)
    await db.flush()
    return conv


async def _build_context(tenant_id: str, db) -> str:
    """Build a brief context string from recent scorecards."""
    result = await db.execute(
        select(InterviewScorecard, Interview, Candidate, Job)
        .join(Interview, InterviewScorecard.interview_id == Interview.id)
        .join(Candidate, Interview.candidate_id == Candidate.id)
        .join(Job, Interview.job_id == Job.id)
        .where(Interview.tenant_id == tenant_id)
        .order_by(InterviewScorecard.scored_at.desc())
        .limit(20)
    )
    rows = result.all()
    if not rows:
        return "No interviews scored yet for this organisation."

    lines = ["Recent interview scorecards:"]
    for sc, iv, cand, job in rows:
        effective_rec = sc.recruiter_override or sc.recommendation or "PENDING"
        lines.append(
            f"- {cand.name} | {job.title} | Round {iv.round_number} | "
            f"Score: {sc.overall_score} | {effective_rec} | "
            f"Date: {iv.scheduled_at.date() if iv.scheduled_at else 'N/A'}"
        )
    return "\n".join(lines)
