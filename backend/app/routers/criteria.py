"""Evaluation criteria versions — read, create new version, list."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from pydantic import BaseModel
from app.deps import AnyTenantUser, RecruiterOrAbove, DB
from app.models import EvaluationCriteriaVersion
from app.services.audit import log_action

router = APIRouter()


class CriteriaVersionCreate(BaseModel):
    job_id: str
    criteria_json: list[dict]
    # [{id, name, weight, description, scoring_rubric, is_hard_filter}]


@router.get("/job/{job_id}")
async def list_criteria_versions(job_id: str, user: AnyTenantUser, db: DB):
    result = await db.execute(
        select(EvaluationCriteriaVersion)
        .where(
            EvaluationCriteriaVersion.tenant_id == user.tenant_id,
            EvaluationCriteriaVersion.job_id == job_id,
        )
        .order_by(EvaluationCriteriaVersion.version_number.desc())
    )
    return result.scalars().all()


@router.get("/job/{job_id}/active")
async def get_active_criteria(job_id: str, user: AnyTenantUser, db: DB):
    result = await db.execute(
        select(EvaluationCriteriaVersion)
        .where(
            EvaluationCriteriaVersion.tenant_id == user.tenant_id,
            EvaluationCriteriaVersion.job_id == job_id,
            EvaluationCriteriaVersion.is_active == True,
        )
        .order_by(EvaluationCriteriaVersion.version_number.desc())
        .limit(1)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        raise HTTPException(status_code=404, detail="No active criteria version found")
    return cv


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_criteria_version(body: CriteriaVersionCreate, user: RecruiterOrAbove, db: DB):
    # Validate weights sum to 100 (excluding hard filters)
    scored = [c for c in body.criteria_json if not c.get("is_hard_filter")]
    total_weight = sum(c.get("weight", 0) for c in scored)
    if abs(total_weight - 100) > 0.01:
        raise HTTPException(
            status_code=422,
            detail=f"Scored criteria weights must sum to 100 (got {total_weight})"
        )

    # Deactivate all existing versions for this job
    await db.execute(
        update(EvaluationCriteriaVersion)
        .where(
            EvaluationCriteriaVersion.job_id == body.job_id,
            EvaluationCriteriaVersion.tenant_id == user.tenant_id,
        )
        .values(is_active=False)
    )

    # Get next version number
    result = await db.execute(
        select(EvaluationCriteriaVersion)
        .where(EvaluationCriteriaVersion.job_id == body.job_id)
        .order_by(EvaluationCriteriaVersion.version_number.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    next_version = (latest.version_number + 1) if latest else 1

    cv = EvaluationCriteriaVersion(
        tenant_id=user.tenant_id,
        job_id=body.job_id,
        version_number=next_version,
        is_active=True,
        criteria_json=body.criteria_json,
        created_by=user.id,
    )
    db.add(cv)
    await log_action(db, user, "CRITERIA_UPDATED", "job", body.job_id,
                     metadata={"new_version": next_version})
    return cv
