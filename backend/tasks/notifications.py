"""
Recruiter notification task — in-app + email on interview status changes.
"""
from __future__ import annotations
import asyncio
import structlog
from celery_app import celery
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

STATUS_SUBJECTS = {
    "SCORED": "Interview complete — scorecard ready",
    "FAILED": "Interview failed — bot could not join",
    "INTERRUPTED": "Interview interrupted — technical issue",
    "ESCALATED": "Candidate requested human — action needed",
    "NO_SHOW": "Candidate no-show",
    "CONSENT_DECLINED": "Candidate declined recording consent",
}


@celery.task(name="tasks.notifications.send_notification_task")
def send_notification_task(interview_id: str, event_type: str) -> None:
    asyncio.run(_send_notification(interview_id, event_type))


def _send_notification_sync(interview_id: str, event_type: str) -> None:
    """Synchronous wrapper for use inside other sync contexts."""
    asyncio.run(_send_notification(interview_id, event_type))


async def _send_notification(interview_id: str, event_type: str) -> None:
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import Interview, Candidate, Job, TenantUser

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Interview, Candidate, Job)
            .join(Candidate, Interview.candidate_id == Candidate.id)
            .join(Job, Interview.job_id == Job.id)
            .where(Interview.id == interview_id)
        )
        row = result.one_or_none()
        if row is None:
            return
        interview, candidate, job = row

        subject = STATUS_SUBJECTS.get(event_type, f"Interview update: {event_type}")
        body = _build_email_body(event_type, candidate.name, job.title, interview_id)

        # Get recruiter email (created_by)
        if interview.created_by:
            user_result = await db.execute(
                select(TenantUser).where(TenantUser.id == interview.created_by)
            )
            recruiter = user_result.scalar_one_or_none()
            if recruiter and recruiter.email:
                await _send_email(recruiter.email, subject, body)

        log.info("notification_sent", interview_id=interview_id, event=event_type)


async def _send_email(to: str, subject: str, body: str) -> None:
    """Send via SendGrid. No-op if API key not configured."""
    if not settings.sendgrid_api_key:
        log.debug("sendgrid_not_configured_skipping_email", to=to, subject=subject)
        return
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": settings.sendgrid_from_email},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            },
            timeout=10,
        )
        if resp.status_code not in {200, 202}:
            log.error("sendgrid_error", status=resp.status_code, body=resp.text)


def _build_email_body(event_type: str, candidate_name: str, job_title: str, interview_id: str) -> str:
    base_url = "https://app.krino.ai"
    templates = {
        "SCORED": (
            f"The interview with {candidate_name} for {job_title} is complete.\n\n"
            f"View scorecard: {base_url}/interviews/{interview_id}\n\n"
            "Scout has scored the interview and a recommendation is ready for your review."
        ),
        "FAILED": (
            f"Scout could not join {candidate_name}'s interview for {job_title}.\n\n"
            f"Reschedule: {base_url}/interviews/{interview_id}\n\n"
            "Please contact the candidate to reschedule or join manually."
        ),
        "ESCALATED": (
            f"{candidate_name} requested a human interviewer during their {job_title} interview.\n\n"
            f"View interview: {base_url}/interviews/{interview_id}\n\n"
            "Please reach out to the candidate within 15 minutes (business hours)."
        ),
        "NO_SHOW": (
            f"{candidate_name} did not join their {job_title} interview.\n\n"
            f"Reschedule: {base_url}/interviews/{interview_id}"
        ),
    }
    return templates.get(event_type, f"Interview update ({event_type}) for {candidate_name}.")
