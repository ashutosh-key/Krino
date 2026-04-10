"""
Post-call scoring task.
Runs Claude Sonnet on the transcript against the criteria version snapshot.
Retries up to 3 times; sets SCORING_FAILED if all attempts exhausted.
"""
from __future__ import annotations
import asyncio
import json
import structlog
from celery_app import celery
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()
MAX_SCORING_ATTEMPTS = 3

SCORING_SYSTEM_PROMPT = """You are a structured interview evaluator. You will be given:
1. An interview transcript
2. A set of evaluation criteria with weights and rubrics
3. The job description context

Your task: score the candidate on each criterion (0–100), identify hard filter results (PASS/FAIL),
generate a 2–3 sentence summary, and return a recommendation (ADVANCE/HOLD/REJECT).

Rules:
- ADVANCE if overall_score >= pass_threshold AND all hard filters PASS
- REJECT if any hard filter is FAIL
- HOLD otherwise
- For each criterion provide 1–3 evidence quotes from the transcript
- overall_score = weighted sum of criterion scores (hard filters excluded from weighting)
- If insufficient data for a criterion, score 0 and note "Insufficient data"

Return ONLY valid JSON matching this schema exactly:
{
  "overall_score": number,
  "recommendation": "ADVANCE"|"HOLD"|"REJECT"|"INSUFFICIENT_DATA",
  "summary_text": string,
  "criteria_scores": [
    {"criterion_id": string, "name": string, "weight": number, "score": number,
     "evidence_quotes": [{"quote": string, "reasoning": string}]}
  ],
  "hard_filters": [
    {"filter_id": string, "name": string, "result": "PASS"|"FAIL", "candidate_answer": string}
  ]
}"""


@celery.task(name="tasks.scoring.score_interview_task", bind=True, max_retries=MAX_SCORING_ATTEMPTS)
def score_interview_task(self, interview_id: str) -> None:
    asyncio.run(_score_interview(self, interview_id))


async def _score_interview(task, interview_id: str) -> None:
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import Interview, InterviewTranscript, InterviewScorecard, EvaluationCriteriaVersion
    from datetime import datetime, timezone
    from anthropic import AsyncAnthropic

    async with AsyncSessionLocal() as db:
        iv_result = await db.execute(select(Interview).where(Interview.id == interview_id))
        interview = iv_result.scalar_one_or_none()
        if interview is None or interview.status not in {"COMPLETED"}:
            return

        # Load transcript
        tr_result = await db.execute(
            select(InterviewTranscript).where(InterviewTranscript.interview_id == interview_id)
        )
        transcript_obj = tr_result.scalar_one_or_none()
        transcript_text = _format_transcript(transcript_obj.turns_json if transcript_obj else [])

        # Load criteria version
        cv_result = await db.execute(
            select(EvaluationCriteriaVersion).where(
                EvaluationCriteriaVersion.id == interview.criteria_version_id
            )
        )
        criteria_version = cv_result.scalar_one_or_none()
        criteria = criteria_version.criteria_json if criteria_version else []

        # Determine pass threshold (from job rounds_config)
        from app.models import Job
        job_result = await db.execute(select(Job).where(Job.id == interview.job_id))
        job = job_result.scalar_one()
        pass_threshold = _get_pass_threshold(job.rounds_config_json, interview.round_number)

        user_prompt = f"""Job role: {job.title}

Evaluation criteria:
{json.dumps(criteria, indent=2)}

Pass threshold: {pass_threshold}

Interview transcript:
{transcript_text}

Score this candidate now."""

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        try:
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=SCORING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text
            # Strip markdown code fences if present
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            result = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("scoring_json_parse_error", attempt=task.request.retries + 1)
            if task.request.retries < MAX_SCORING_ATTEMPTS - 1:
                raise task.retry(countdown=30)
            interview.status = "SCORING_FAILED"
            await db.commit()
            return
        except Exception as exc:
            log.error("scoring_llm_error", error=str(exc), attempt=task.request.retries + 1)
            if task.request.retries < MAX_SCORING_ATTEMPTS - 1:
                raise task.retry(exc=exc, countdown=60)
            interview.status = "SCORING_FAILED"
            await db.commit()
            return

        # Write scorecard
        scorecard = InterviewScorecard(
            interview_id=interview_id,
            criteria_version_id=interview.criteria_version_id,
            overall_score=result.get("overall_score"),
            recommendation=result.get("recommendation"),
            summary_text=result.get("summary_text"),
            criteria_scores_json=result.get("criteria_scores", []),
            hard_filters_json=result.get("hard_filters", []),
            model_used="claude-sonnet-4-6",
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            scored_at=datetime.now(timezone.utc),
        )
        db.add(scorecard)
        interview.status = "SCORED"
        await db.commit()

        log.info("scoring_complete", interview_id=interview_id,
                 score=result.get("overall_score"), recommendation=result.get("recommendation"))

        # Notify recruiter
        try:
            from tasks.notifications import send_notification_task
            send_notification_task.delay(interview_id, "SCORED")
        except Exception:
            pass


def _format_transcript(turns: list) -> str:
    if not turns:
        return "(No transcript available)"
    lines = []
    for t in turns:
        speaker = t.get("speaker", "UNKNOWN")
        text = t.get("text", "")
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def _get_pass_threshold(rounds_config: list, round_number: int) -> int:
    for rc in rounds_config:
        if rc.get("round") == round_number:
            return rc.get("pass_threshold", 70)
    return 70
