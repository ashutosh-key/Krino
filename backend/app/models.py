"""
SQLAlchemy ORM models — all 15 tables from Krino PRD v3 + v4 addendum.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Tenants ──────────────────────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(Text, default="starter")
    logo_url: Mapped[str | None] = mapped_column(Text)
    google_refresh_token: Mapped[str | None] = mapped_column(Text)
    ai_persona_name: Mapped[str] = mapped_column(Text, default="Scout")
    ai_persona_voice: Mapped[str] = mapped_column(Text, default="female-en")
    settings_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[TenantUser]] = relationship(back_populates="tenant")
    jobs: Mapped[list[Job]] = relationship(back_populates="tenant")
    api_keys: Mapped[list[TenantApiKey]] = relationship(back_populates="tenant")


class TenantUser(Base):
    __tablename__ = "tenant_users"
    __table_args__ = (UniqueConstraint("tenant_id", "firebase_uid"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    firebase_uid: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # admin|recruiter|hiring_manager|viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # SHA-256 of raw key
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="api_keys")


# ── Jobs ─────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(Text, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    role_type: Mapped[str] = mapped_column(Text, nullable=False)  # backend|frontend|ai_ml|fullstack|custom
    rounds_config_json: Mapped[list] = mapped_column(JSONB, default=list)
    # [{round, max_duration_min, pass_threshold, custom_briefing}]
    next_steps_timeline: Mapped[str] = mapped_column(Text, default="3–5 business days")
    status: Mapped[str] = mapped_column(Text, default="active")  # active|paused|closed
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="jobs")
    criteria_versions: Mapped[list[EvaluationCriteriaVersion]] = relationship(back_populates="job")
    question_bank_versions: Mapped[list[QuestionBankVersion]] = relationship(back_populates="job")
    interviews: Mapped[list[Interview]] = relationship(back_populates="job")


# ── Evaluation Criteria (versioned) ──────────────────────────────────────────

class EvaluationCriteriaVersion(Base):
    __tablename__ = "evaluation_criteria_versions"
    __table_args__ = (UniqueConstraint("job_id", "version_number"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"))
    role_type: Mapped[str | None] = mapped_column(Text)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    criteria_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    # [{id, name, weight, description, scoring_rubric, is_hard_filter}]
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job | None] = relationship(back_populates="criteria_versions")


# ── Question Banks (versioned) ────────────────────────────────────────────────

class QuestionBankVersion(Base):
    __tablename__ = "question_bank_versions"
    __table_args__ = (UniqueConstraint("job_id", "round_number", "version_number"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    questions_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    # [{id, text, criterion_id, required, probe_depth, tags, is_hard_filter}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="question_bank_versions")


# ── Candidates ────────────────────────────────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("ix_candidates_tenant_id", "tenant_id"),
        Index("ix_candidates_external_id", "external_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"))
    # NOT NULL in Phase 1; nullable reserved for Phase 2 marketplace
    external_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    resume_url: Mapped[str | None] = mapped_column(Text)
    resume_text: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Phase 2 hooks (always False in Phase 1)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    marketplace_visible: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    interviews: Mapped[list[Interview]] = relationship(back_populates="candidate")


# ── Interviews ────────────────────────────────────────────────────────────────

class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (
        Index("ix_interviews_tenant_id", "tenant_id"),
        Index("ix_interviews_status", "status"),
        Index("ix_interviews_scheduled_at", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("candidates.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1)

    # State machine
    status: Mapped[str] = mapped_column(Text, default="SCHEDULED")
    # SCHEDULED|JOINING|WAITING|CONSENT_GATE|IN_PROGRESS
    # |COMPLETED|SCORED|SCORING_FAILED
    # |FAILED|NO_SHOW|CONSENT_DECLINED|INTERRUPTED|ESCALATED|CANCELLED

    # Meeting
    meeting_type: Mapped[str] = mapped_column(Text, default="google_meet")
    host_type: Mapped[str | None] = mapped_column(Text)  # SYSTEM_HOST|EXTERNAL_HOST
    meeting_link: Mapped[str | None] = mapped_column(Text)
    meeting_id: Mapped[str | None] = mapped_column(Text)

    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    # Consent
    consent_given: Mapped[bool | None] = mapped_column(Boolean)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_transcript_segment_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))

    # Version snapshots (taken at scheduling time)
    criteria_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("evaluation_criteria_versions.id")
    )
    question_bank_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("question_bank_versions.id")
    )

    # Recall.ai
    recall_bot_id: Mapped[str | None] = mapped_column(Text)
    recording_url: Mapped[str | None] = mapped_column(Text)
    recording_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # AI config (snapshot from tenant at scheduling time)
    ai_persona_name: Mapped[str | None] = mapped_column(Text)
    ai_persona_voice: Mapped[str | None] = mapped_column(Text)
    recruiter_briefing_notes: Mapped[str | None] = mapped_column(Text)

    # Observer / take-over
    observer_invite_link: Mapped[str | None] = mapped_column(Text)
    takeover_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    takeover_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"))

    # Pre-interview page
    pre_interview_token: Mapped[str | None] = mapped_column(Text, unique=True)
    pre_interview_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="interviews")
    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    transcript: Mapped[InterviewTranscript | None] = relationship(back_populates="interview", uselist=False)
    questions_asked: Mapped[list[InterviewQuestionAsked]] = relationship(back_populates="interview")
    scorecard: Mapped[InterviewScorecard | None] = relationship(back_populates="interview", uselist=False)


# ── Transcripts ───────────────────────────────────────────────────────────────

class InterviewTranscript(Base):
    __tablename__ = "interview_transcripts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("interviews.id"), nullable=False, unique=True, index=True
    )
    turns_json: Mapped[list] = mapped_column(JSONB, default=list)
    # [{id, speaker (AI|CANDIDATE|OBSERVER), text, timestamp_ms, confidence,
    #   is_consent_utterance, is_hard_filter_answer, is_human_conducted}]
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    interview: Mapped[Interview] = relationship(back_populates="transcript")


# ── Questions Asked ───────────────────────────────────────────────────────────

class InterviewQuestionAsked(Base):
    __tablename__ = "interview_questions_asked"
    __table_args__ = (Index("ix_iqa_interview_id", "interview_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("interviews.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)  # from bank, or "adaptive_N"
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    criterion_id: Mapped[str | None] = mapped_column(Text)
    is_adaptive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hard_filter: Mapped[bool] = mapped_column(Boolean, default=False)
    asked_at_ms: Mapped[int | None] = mapped_column(Integer)
    candidate_answer_text: Mapped[str | None] = mapped_column(Text)
    answer_start_ms: Mapped[int | None] = mapped_column(Integer)
    answer_end_ms: Mapped[int | None] = mapped_column(Integer)
    probe_count: Mapped[int] = mapped_column(Integer, default=0)
    # Populated by scoring job
    criterion_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    evidence_quotes: Mapped[list | None] = mapped_column(JSONB)  # [{quote, reasoning}]

    interview: Mapped[Interview] = relationship(back_populates="questions_asked")


# ── Scorecards ────────────────────────────────────────────────────────────────

class InterviewScorecard(Base):
    __tablename__ = "interview_scorecards"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    interview_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("interviews.id"), nullable=False, unique=True, index=True
    )
    criteria_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("evaluation_criteria_versions.id")
    )
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 2))  # null if INSUFFICIENT_DATA
    recommendation: Mapped[str | None] = mapped_column(Text)  # ADVANCE|HOLD|REJECT|INSUFFICIENT_DATA
    summary_text: Mapped[str | None] = mapped_column(Text)
    criteria_scores_json: Mapped[list | None] = mapped_column(JSONB)
    # [{criterion_id, name, weight, score, evidence_quotes[{quote, reasoning}]}]
    hard_filters_json: Mapped[list | None] = mapped_column(JSONB)
    # [{filter_id, name, result (PASS|FAIL), candidate_answer}]
    partial_interview: Mapped[bool] = mapped_column(Boolean, default=False)
    model_used: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Recruiter override
    recruiter_override: Mapped[str | None] = mapped_column(Text)
    recruiter_override_notes: Mapped[str | None] = mapped_column(Text)
    overridden_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"))
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    interview: Mapped[Interview] = relationship(back_populates="scorecard")


# ── Multi-round Context ───────────────────────────────────────────────────────

class InterviewRoundContext(Base):
    __tablename__ = "interview_round_context"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("candidates.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    round_summaries_json: Mapped[list] = mapped_column(JSONB, default=list)
    # [{round, interview_id, overall_score, recommendation, ai_summary,
    #   criteria_scores, hard_filter_results, key_strengths, key_gaps, scout_briefing}]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Scout Conversations ───────────────────────────────────────────────────────

class ScoutConversation(Base):
    __tablename__ = "scout_conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"), nullable=False)
    llm_messages_json: Mapped[list] = mapped_column(JSONB, default=list)
    display_messages_json: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Tenant Usage ──────────────────────────────────────────────────────────────

class TenantUsage(Base):
    __tablename__ = "tenant_usage"
    __table_args__ = (UniqueConstraint("tenant_id", "period_month"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True)
    period_month: Mapped[str] = mapped_column(Text, nullable=False)  # "2026-04" (YYYY-MM)
    interviews_scheduled: Mapped[int] = mapped_column(Integer, default=0)
    interviews_completed: Mapped[int] = mapped_column(Integer, default=0)
    interviews_failed: Mapped[int] = mapped_column(Integer, default=0)
    interviews_no_show: Mapped[int] = mapped_column(Integer, default=0)
    interviews_escalated: Mapped[int] = mapped_column(Integer, default=0)
    interviews_consent_declined: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_minutes: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    recall_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    llm_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    tts_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    stt_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Webhook Events (outbound) ─────────────────────────────────────────────────

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("ix_webhook_events_tenant_id", "tenant_id"),
        Index("ix_webhook_events_status", "status"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|delivered|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Audit Logs (SOC 2 — immutable, never deleted) ─────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenants.id"))
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tenant_users.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # USER_LOGIN, USER_LOGOUT, INTERVIEW_SCHEDULED, INTERVIEW_DELETED,
    # CRITERIA_UPDATED, API_KEY_CREATED, CANDIDATE_DELETED,
    # SCORECARD_VIEWED, OVERRIDE_APPLIED, TENANT_CREATED
    resource_type: Mapped[str | None] = mapped_column(Text)  # interview|candidate|job|tenant|user
    resource_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
