from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from pydantic import BaseModel
from app.deps import AnyTenantUser, RecruiterOrAbove, DB
from app.models import InterviewScorecard, Interview
from app.services.audit import log_action

router = APIRouter()


class ScorecardOverride(BaseModel):
    recommendation: str  # ADVANCE|HOLD|REJECT
    notes: str


@router.get("/{interview_id}")
async def get_scorecard(interview_id: str, user: AnyTenantUser, db: DB):
    scorecard = await _get_scorecard_or_404(interview_id, user.tenant_id, db)
    await log_action(db, user, "SCORECARD_VIEWED", "interview", interview_id)
    return scorecard


@router.patch("/{interview_id}/override")
async def override_recommendation(
    interview_id: str,
    body: ScorecardOverride,
    user: RecruiterOrAbove,
    db: DB,
):
    if body.recommendation not in {"ADVANCE", "HOLD", "REJECT"}:
        raise HTTPException(status_code=422, detail="recommendation must be ADVANCE, HOLD, or REJECT")

    scorecard = await _get_scorecard_or_404(interview_id, user.tenant_id, db)
    scorecard.recruiter_override = body.recommendation
    scorecard.recruiter_override_notes = body.notes
    scorecard.overridden_by = user.id

    from datetime import datetime, timezone
    scorecard.overridden_at = datetime.now(timezone.utc)

    await log_action(db, user, "OVERRIDE_APPLIED", "interview", interview_id,
                     metadata={"override_recommendation": body.recommendation})
    return scorecard


async def _get_scorecard_or_404(interview_id: str, tenant_id: str, db) -> InterviewScorecard:
    # Verify interview belongs to tenant
    iv_result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.tenant_id == tenant_id)
    )
    if iv_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    sc_result = await db.execute(
        select(InterviewScorecard).where(InterviewScorecard.interview_id == interview_id)
    )
    sc = sc_result.scalar_one_or_none()
    if sc is None:
        raise HTTPException(status_code=404, detail="Scorecard not available yet")
    return sc
