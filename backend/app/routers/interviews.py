"""
Interview scheduling, status transitions, and cancellation.
Bot join is handled by the Celery task triggered on creation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.deps import AnyTenantUser, RecruiterOrAbove, DB
from app.models import Interview, Job, Candidate, EvaluationCriteriaVersion, QuestionBankVersion, Tenant
from app.services.audit import log_action
from app.services.pre_interview import generate_pre_interview_token

router = APIRouter()

TERMINAL_STATUSES = {"COMPLETED", "SCORED", "SCORING_FAILED", "FAILED", "NO_SHOW",
                     "CONSENT_DECLINED", "INTERRUPTED", "ESCALATED", "CANCELLED"}


class InterviewCreate(BaseModel):
    job_id: str
    candidate_id: str
    round_number: int = 1
    scheduled_at: datetime
    host_type: str = "SYSTEM_HOST"  # SYSTEM_HOST | EXTERNAL_HOST
    meeting_link: str | None = None  # required for EXTERNAL_HOST
    recruiter_briefing_notes: str | None = None
    observer_email: str | None = None


class InterviewCancel(BaseModel):
    reason: str | None = None


@router.get("/")
async def list_interviews(
    user: AnyTenantUser,
    db: DB,
    job_id: str | None = None,
    candidate_id: str | None = None,
    status_filter: str | None = None,
):
    q = select(Interview).where(Interview.tenant_id == user.tenant_id)
    if job_id:
        q = q.where(Interview.job_id == job_id)
    if candidate_id:
        q = q.where(Interview.candidate_id == candidate_id)
    if status_filter:
        q = q.where(Interview.status == status_filter)
    q = q.order_by(Interview.scheduled_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{interview_id}")
async def get_interview(interview_id: str, user: AnyTenantUser, db: DB):
    return await _get_interview_or_404(interview_id, user.tenant_id, db)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_interview(body: InterviewCreate, user: RecruiterOrAbove, db: DB):
    # Validate job + candidate belong to tenant
    job = await _get_or_404(Job, body.job_id, user.tenant_id, db)
    candidate = await _get_or_404(Candidate, body.candidate_id, user.tenant_id, db)

    if body.host_type == "EXTERNAL_HOST" and not body.meeting_link:
        raise HTTPException(status_code=422, detail="meeting_link required for EXTERNAL_HOST")

    # Snapshot active criteria + question bank versions at scheduling time
    crit_result = await db.execute(
        select(EvaluationCriteriaVersion)
        .where(EvaluationCriteriaVersion.job_id == body.job_id, EvaluationCriteriaVersion.is_active == True)
        .order_by(EvaluationCriteriaVersion.version_number.desc())
        .limit(1)
    )
    criteria_version = crit_result.scalar_one_or_none()

    qb_result = await db.execute(
        select(QuestionBankVersion)
        .where(
            QuestionBankVersion.job_id == body.job_id,
            QuestionBankVersion.round_number == body.round_number,
            QuestionBankVersion.is_active == True,
        )
        .order_by(QuestionBankVersion.version_number.desc())
        .limit(1)
    )
    question_bank_version = qb_result.scalar_one_or_none()

    # Fetch tenant for persona snapshot
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one()

    interview = Interview(
        tenant_id=user.tenant_id,
        job_id=body.job_id,
        candidate_id=body.candidate_id,
        round_number=body.round_number,
        scheduled_at=body.scheduled_at,
        host_type=body.host_type,
        meeting_link=body.meeting_link,
        recruiter_briefing_notes=body.recruiter_briefing_notes,
        criteria_version_id=criteria_version.id if criteria_version else None,
        question_bank_version_id=question_bank_version.id if question_bank_version else None,
        ai_persona_name=tenant.ai_persona_name,
        ai_persona_voice=tenant.ai_persona_voice,
        created_by=user.id,
        status="SCHEDULED",
    )

    # Generate pre-interview token (HMAC, 24h expiry)
    interview.pre_interview_token = generate_pre_interview_token(interview.id)

    db.add(interview)
    await db.flush()

    await log_action(db, user, "INTERVIEW_SCHEDULED", "interview", interview.id)

    # Enqueue bot join task (fires at scheduled_at - 2min)
    _enqueue_bot_join(interview)

    return interview


@router.patch("/{interview_id}/cancel")
async def cancel_interview(interview_id: str, body: InterviewCancel, user: RecruiterOrAbove, db: DB):
    interview = await _get_interview_or_404(interview_id, user.tenant_id, db)
    if interview.status not in {"SCHEDULED", "WAITING"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel interview in status '{interview.status}'"
        )
    interview.status = "CANCELLED"
    await log_action(db, user, "INTERVIEW_CANCELLED", "interview", interview.id,
                     metadata={"reason": body.reason})
    return interview


@router.get("/{interview_id}/invite-text")
async def get_invite_text(interview_id: str, user: AnyTenantUser, db: DB):
    """Return the clipboard email template for candidate invite."""
    interview = await _get_interview_or_404(interview_id, user.tenant_id, db)
    job_result = await db.execute(select(Job).where(Job.id == interview.job_id))
    job = job_result.scalar_one()
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one()

    pre_url = f"https://app.krino.ai/pre-interview/{interview.pre_interview_token}"
    subject = f"Interview Invitation — {job.title} at {tenant.name}"
    body = (
        f"Hi,\n\n{tenant.name} would like to invite you for a brief AI-conducted video interview "
        f"for the {job.title} role.\n\n"
        f"Please review what to expect before joining:\n{pre_url}\n\n"
        f"Join here: {interview.meeting_link or '(link will be provided)'}\n\n"
        f"Duration: approx 30 minutes.\n\n"
        f"Best,\nThe {tenant.name} Team"
    )
    return {"subject": subject, "body": body, "meet_link": interview.meeting_link}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_interview_or_404(interview_id: str, tenant_id: str, db: AsyncSession) -> Interview:
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.tenant_id == tenant_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    return obj


async def _get_or_404(model, obj_id: str, tenant_id: str, db: AsyncSession):
    result = await db.execute(
        select(model).where(model.id == obj_id, model.tenant_id == tenant_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def _enqueue_bot_join(interview: Interview) -> None:
    """Queue the Celery bot_join task to fire 2 minutes before scheduled_at."""
    try:
        from tasks.bot_join import bot_join_task
        from datetime import timedelta
        eta = interview.scheduled_at - timedelta(minutes=2)
        bot_join_task.apply_async(args=[interview.id], eta=eta)
    except Exception:
        # Celery may not be running in dev — log and continue
        import structlog
        structlog.get_logger().warning("celery_enqueue_failed", interview_id=interview.id)
