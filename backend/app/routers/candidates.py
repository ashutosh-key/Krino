from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.deps import AnyTenantUser, RecruiterOrAbove, DB
from app.models import Candidate
from app.services.audit import log_action

router = APIRouter()


class CandidateCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    external_id: str | None = None
    resume_url: str | None = None
    resume_text: str | None = None


class CandidateUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    resume_url: str | None = None
    resume_text: str | None = None


@router.get("/")
async def list_candidates(user: AnyTenantUser, db: DB):
    result = await db.execute(
        select(Candidate).where(Candidate.tenant_id == user.tenant_id).order_by(Candidate.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: str, user: AnyTenantUser, db: DB):
    return await _get_candidate_or_404(candidate_id, user.tenant_id, db)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_candidate(body: CandidateCreate, user: RecruiterOrAbove, db: DB):
    candidate = Candidate(
        tenant_id=user.tenant_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        external_id=body.external_id,
        resume_url=body.resume_url,
        resume_text=body.resume_text,
    )
    db.add(candidate)
    return candidate


@router.patch("/{candidate_id}")
async def update_candidate(candidate_id: str, body: CandidateUpdate, user: RecruiterOrAbove, db: DB):
    c = await _get_candidate_or_404(candidate_id, user.tenant_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(c, field, value)
    return c


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(candidate_id: str, user: RecruiterOrAbove, db: DB):
    c = await _get_candidate_or_404(candidate_id, user.tenant_id, db)
    await db.delete(c)
    await log_action(db, user, "CANDIDATE_DELETED", "candidate", candidate_id)


async def _get_candidate_or_404(candidate_id: str, tenant_id: str, db: AsyncSession) -> Candidate:
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id, Candidate.tenant_id == tenant_id)
    )
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c
