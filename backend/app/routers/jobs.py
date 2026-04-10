from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Any
from app.deps import AnyTenantUser, RecruiterOrAbove, DB
from app.models import Job, EvaluationCriteriaVersion, QuestionBankVersion
from app.services.default_criteria import get_default_criteria, get_default_questions
from app.services.audit import log_action

router = APIRouter()


class JobCreate(BaseModel):
    title: str
    description: str | None = None
    role_type: str  # backend|frontend|ai_ml|fullstack|custom
    rounds_config: list[dict] = []
    next_steps_timeline: str = "3–5 business days"


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    role_type: str | None = None
    rounds_config: list[dict] | None = None
    next_steps_timeline: str | None = None
    status: str | None = None


@router.get("/")
async def list_jobs(user: AnyTenantUser, db: DB):
    result = await db.execute(
        select(Job).where(Job.tenant_id == user.tenant_id).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    return jobs


@router.get("/{job_id}")
async def get_job(job_id: str, user: AnyTenantUser, db: DB):
    job = await _get_job_or_404(job_id, user.tenant_id, db)
    return job


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, user: RecruiterOrAbove, db: DB):
    job = Job(
        tenant_id=user.tenant_id,
        title=body.title,
        description=body.description,
        role_type=body.role_type,
        rounds_config_json=body.rounds_config or [{"round": 1, "max_duration_min": 30, "pass_threshold": 70}],
        next_steps_timeline=body.next_steps_timeline,
        created_by=user.id,
    )
    db.add(job)
    await db.flush()  # get job.id

    # Auto-generate criteria v1 from role type
    criteria = EvaluationCriteriaVersion(
        tenant_id=user.tenant_id,
        job_id=job.id,
        role_type=body.role_type,
        version_number=1,
        is_active=True,
        criteria_json=get_default_criteria(body.role_type),
        created_by=user.id,
    )
    db.add(criteria)
    await db.flush()

    # Auto-generate question bank v1
    questions = QuestionBankVersion(
        job_id=job.id,
        round_number=1,
        version_number=1,
        is_active=True,
        questions_json=get_default_questions(body.role_type),
    )
    db.add(questions)

    await log_action(db, user, "JOB_CREATED", "job", job.id)
    return job


@router.patch("/{job_id}")
async def update_job(job_id: str, body: JobUpdate, user: RecruiterOrAbove, db: DB):
    job = await _get_job_or_404(job_id, user.tenant_id, db)
    if body.title is not None:
        job.title = body.title
    if body.description is not None:
        job.description = body.description
    if body.role_type is not None:
        job.role_type = body.role_type
    if body.rounds_config is not None:
        job.rounds_config_json = body.rounds_config
    if body.next_steps_timeline is not None:
        job.next_steps_timeline = body.next_steps_timeline
    if body.status is not None:
        job.status = body.status
    await log_action(db, user, "JOB_UPDATED", "job", job.id)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, user: RecruiterOrAbove, db: DB):
    job = await _get_job_or_404(job_id, user.tenant_id, db)
    job.status = "closed"
    await log_action(db, user, "JOB_DELETED", "job", job.id)


async def _get_job_or_404(job_id: str, tenant_id: str, db: AsyncSession) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
