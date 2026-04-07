# Krino PRD — v4 Addendum
**Base document:** krino-prd-v3.md
**Date:** 2026-04-07
**Status:** READY FOR ENGINEERING KICKOFF

This addendum closes the 5 remaining gaps identified in the v3 PM review.
Read alongside v3. Where sections conflict, v4 addendum takes precedence.

---

## Gap 1 — OQ6 RESOLVED: Pre-Interview Page Hosting

**Decision:** Krino-hosted. FastAPI serves a lightweight static HTML/JS page at
`/pre-interview/{interview_token}`.

**Rationale:** The page requires no user auth, has a token-scoped URL,
and its functionality (WebRTC media check + consent checkbox) is simple enough
to build as a single FastAPI route serving a self-contained HTML file.
No separate Lovable build or service needed for v1.

**Backend implications:**
- New route: `GET /pre-interview/{token}` — public, no auth
- Token = `HMAC-SHA256(interview_id + server_secret)`, expires T+24h
- On page load: validate token → fetch interview metadata (role, company, duration)
  → render page. If token expired or invalid: show "This link has expired" page.
- On consent checkbox click: `POST /pre-interview/{token}/consent` → sets
  `interviews.pre_interview_consent_at`; returns the Google Meet link in response.
- No sensitive data (candidate name, score) exposed in this route.

**Template customisation (§3.2 email template):** Fixed in v1. The clipboard
email template body is a system default with only `[Role]`, `[Company]`,
`[pre-interview URL]`, `[Meet link]`, and `[X minutes]` as variable slots
(pulled from tenant + interview config). No tenant-editable template in v1.
Full customisation deferred to v2 (adds `email_templates` table + admin editor).

---

## Gap 2 — INSUFFICIENT_DATA Recruiter Exit Path

When `interview_scorecards.recommendation = INSUFFICIENT_DATA` (AI conducted
<50% of interview due to take-over), the recruiter sees:

**Scorecard banner:**
> ⚠ This interview was primarily conducted by a human. Insufficient AI data
> to generate a score. You can re-invite the candidate for a full AI interview,
> or add a manual assessment below.

**Available actions in the report UI:**

| Action | Behaviour | DB effect |
|---|---|---|
| **Re-invite for full interview** | Opens scheduling modal pre-filled for same round. Original INSUFFICIENT_DATA interview is preserved (not overwritten). | New `interviews` row created; original row status unchanged |
| **Add manual assessment** | Recruiter enters free-text notes + selects override recommendation (ADVANCE / HOLD / REJECT) | Populates `recruiter_override`, `recruiter_override_notes`, `overridden_by`, `overridden_at` on existing scorecard |

No maximum re-invite count in v1.

The INSUFFICIENT_DATA status does not block the candidate from being advanced.
Recruiter can select "Add manual assessment → ADVANCE" and then trigger Round 2
scheduling from the same report page — the same as any other override flow.

---

## Gap 3 — OQ2: Recall.ai Video Injection Spike — Go/No-Go Criteria & Fallback

**Spike definition (2 engineering days max):**
Attempt to inject a looping WebGL video (a simple animated test scene, not the
full avatar) as the Recall.ai bot's video feed in a live Google Meet call.
Success criterion: a participant in the meeting sees the animated video playing
in the bot's tile (not a black screen, not a static image).

**Go/No-Go gate:**
- **GO:** Animated video visible in bot tile → V2 and V3 are in sprint scope.
- **NO-GO:** Black screen or static image only → V2 and V3 are deferred to v2.
  V4 (static company logo fallback) remains in v1 scope and is the only
  avatar requirement. All other requirements are unaffected.

**If NO-GO — sprint planning rule:**
Remove V2 and V3 from the v1 backlog. Add to v2 roadmap.
Add a note in the product: "AI avatar is audio-only in this version. Visual
presence (animated avatar) is coming soon." The bot's audio (TTS voice) still
plays normally — candidates hear Scout; they just see a static logo image.

**Spike owner:** Engineering lead.
**Spike must complete before:** Sprint 1 planning for the interface/avatar team.

---

## Gap 4 — Recall.ai Join Failure — Candidate & Recruiter Experience

This scenario (bot fails to join; state → FAILED) was not addressed in v3.

**Trigger:** Recall.ai bot join attempt fails after 2 retries within the
JOINING window (e.g., Meet link expired, platform API error, rate limit).

**Recruiter experience:**
- Immediate in-app notification + email:
  > "The AI interviewer could not join [Candidate]'s interview scheduled at
  > [time]. The meeting may still be active. Please join manually or reschedule."
- Dashboard: interview card shows FAILED status + "Reschedule" button.
- Recruiter can reschedule (creates a new SCHEDULED interview) or join manually
  (in which case the interview proceeds as a human-only session; recruiter
  manually adds notes afterward).

**Candidate experience:**
Candidate is in the Google Meet but no bot appears. After ~5 minutes with no
one present, they will likely leave. There is no automated notification to
the candidate in v1 (manual outreach is already the baseline for all candidate
communication). The recruiter is responsible for reaching out.

This is acceptable for v1 given the manual outreach model. Automated candidate
notification for FAILED interviews is a v1.1 item alongside automated outreach.

**Differentiate from INTERRUPTED (bot drops mid-interview):**
INTERRUPTED is handled in §3.6 of v3 (in-meeting chat message, partial transcript
saved). FAILED (never joined) has no in-meeting channel; recruiter notification
only.

---

## Gap 5 — Cross-Version Comparison Warning — Display Specification

The v3 review noted the warning location was unspecified. Closing that now.

**Where the warning appears:**
1. **Scorecard report page (§3.9):** Shown in the header of the Scores section
   if `scorecard.criteria_version_id` differs from the job's currently active
   criteria version. Text: "Scored using criteria v[N]. [View differences]"
   This is informational only — always shown if version differs, not actionable.

2. **Compare view (§3.9):** If any two candidates being compared have different
   `criteria_version_id` values, a banner appears above the comparison grid:
   > ⚠ These candidates were scored under different criteria versions (v[X] and
   > v[Y]). Overall score comparison may not be meaningful.
   > [View criteria differences]
   Per-criteria columns are shown only for criteria IDs that exist in **both**
   versions. Criteria present in only one version are shown in a separate
   "Version-specific criteria" section with a grey background.

3. **NOT shown:** In the candidate queue list view (too noisy), in email
   notifications, or in Scout responses (Scout adds a verbal note if asked
   to compare directly).

---

## Resolved Open Questions Summary

| OQ | Resolution |
|---|---|
| OQ1 | RESOLVED: Krino gets its own GCP project (separate from RoleSignal). Reasons: spinout-ready, SOC 2 audit isolation, independent IAM, separate Calendar API quota. Takes 5 minutes to create. |
| OQ3 | RESOLVED: Krino gets its own Firebase project (correct for standalone product) |
| OQ4 | RESOLVED (v3): Recall.ai join-by-URL; guest display name; waiting room caveat |
| OQ5 | RESOLVED: Default persona name = "Scout" |
| OQ6 | RESOLVED (this doc): Krino-hosted FastAPI route; token-based; no tenant-editable template in v1 |
| OQ10 | RESOLVED: Internal use only for now, but all SOC 2 controls targeted in v1 architecture (see §Gap 6 below) |
| OQ11 | RESOLVED (v3): No-recording mode out of scope; consent gate is binary in v1 |
| OQ12 | RESOLVED (v3): 15-min escalation SLA, business hours, recruiter manual follow-up |
| Email template config | RESOLVED (this doc): Fixed system default in v1; full customisation in v2 |
| INSUFFICIENT_DATA exit path | RESOLVED (this doc): Re-invite or manual assessment; no max retries |
| Recall.ai FAILED join UX | RESOLVED (this doc): Recruiter notified; candidate no automated message in v1 |
| Cross-version warning location | RESOLVED (this doc): Scorecard header + compare view banner |
| OQ2 Spike fallback | RESOLVED (this doc): NO-GO → V2/V3 deferred; V4 static logo only |

## Still Open (legal gates — do not block engineering or build)

| OQ | Owner | Blocks |
|---|---|---|
| OQ2: Recall.ai video injection spike result | Engineering lead | V2/V3 sprint planning only |
| OQ7: Multi-party consent law | Legal | Pilot with real candidates |
| OQ8: EU AI Act compliance | Legal | Pilot with real candidates |
| OQ9: Recording ownership | Legal | Phase 2 design |

---

## Gap 6 — SOC 2 Architecture Controls

**Decision:** Build all SOC 2 Type II controls into v1 architecture. No certification pursued yet — internal use only — but the architecture must support it from day 1.

SOC 2 is not a fixed checklist, but the Trust Service Criteria map to these concrete architectural requirements for Krino:

### CC6 — Logical and Physical Access Controls (already partially addressed)

| Control | Implementation |
|---|---|
| RBAC with least privilege | ✓ Already designed (Appendix A in v3) |
| MFA for admin users | Firebase Authentication supports MFA. **Add to T4:** Admin and Recruiter roles must enroll MFA before accessing the Krino dashboard. Enforced via Firebase Auth policy per tenant. |
| Session expiry | JWT tokens expire in 1 hour; refresh token rotation via Firebase. |
| Service-to-service auth | Internal Celery jobs use a shared secret header, not open endpoints. Recall.ai webhook receiver validates a `X-Recall-Signature` HMAC header. |
| No shared credentials | Each tenant has its own API key (T6). Service account credentials stored in environment secrets, never in code. |

### CC7 — System Monitoring and Anomaly Detection

| Control | Implementation |
|---|---|
| Centralised logging | All application logs shipped to a log aggregator (Fly.io log drain → e.g., Papertrail or Logtail). Retention ≥ 90 days. |
| Uptime monitoring | External uptime monitor (e.g., Better Uptime) on the `/health` endpoint. PagerDuty or equivalent alert for >2 min downtime. |
| Error rate alerting | Alert if HTTP 5xx rate > 1% over 5-min window. |
| Anomalous access patterns | Alert on: >10 failed auth attempts from same IP in 5 min (rate limit + lockout); unusual tenant data volume spikes. |

### CC8 — Change Management

| Control | Implementation |
|---|---|
| No direct pushes to main | Branch protection required; PRs mandatory; at least 1 approval. |
| CI pipeline | Automated tests + dependency vulnerability scan (Dependabot or Snyk) on every PR. |
| Secrets never in code | `.env` files gitignored; secrets via Fly.io secrets or equivalent. Secret scanning in CI (GitHub secret scanning). |
| Deployment audit | Every production deployment logged with deployer identity, timestamp, and commit SHA. |

### CC9 — Risk Management / Vendor Assessment

| Control | Implementation |
|---|---|
| Sub-processor register | Document all vendors processing candidate data: Recall.ai, Anthropic, ElevenLabs, Neon, Fly.io, Firebase, SendGrid, Simli. Used for GDPR Article 28 DPA and SOC 2 vendor risk. |
| Vendor SOC 2 status | Collect SOC 2 reports from: Neon (database), Firebase (auth), Fly.io (hosting), Recall.ai (if available). Store in internal compliance folder. |

### A1 — Availability

| Control | Implementation |
|---|---|
| Database backups | Neon provides automated daily backups with point-in-time recovery. Verify backup restore works before launch. |
| Recovery time objective (RTO) | Target: <4 hours for full service restoration after major incident. Document runbook. |
| Celery worker redundancy | Deploy ≥2 Celery worker instances on Fly.io. Redis should be a managed instance (Upstash or Fly.io Redis) with persistence enabled. |

### C1 — Confidentiality

| Control | Implementation |
|---|---|
| Encryption in transit | TLS 1.2+ enforced everywhere. Fly.io handles this for public endpoints. Internal Celery ↔ Redis traffic on private network. |
| Encryption at rest | Neon PostgreSQL: encryption at rest enabled (default). Interview recordings stored in object storage (e.g., Cloudflare R2 or S3) with server-side encryption (AES-256). |
| Candidate data scoping | No candidate PII in application logs. Log only IDs, not names or email addresses. |

### Additional Table: `audit_logs` (new — required for SOC 2 evidence)

```sql
audit_logs (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID REFERENCES tenants,      -- NULL for system events
  user_id         UUID REFERENCES tenant_users,  -- NULL for automated actions
  action          TEXT NOT NULL,
    -- Examples: USER_LOGIN, USER_LOGOUT, INTERVIEW_SCHEDULED, INTERVIEW_DELETED,
    --           CRITERIA_UPDATED, API_KEY_CREATED, CANDIDATE_DELETED,
    --           SCORECARD_VIEWED, OVERRIDE_APPLIED, TENANT_CREATED
  resource_type   TEXT,                          -- interview | candidate | job | tenant | user
  resource_id     UUID,
  ip_address      INET,
  user_agent      TEXT,
  metadata_json   JSONB DEFAULT '{}',            -- action-specific details
  created_at      TIMESTAMPTZ DEFAULT now(),
  INDEX(tenant_id, created_at),
  INDEX(user_id, created_at),
  INDEX(action, created_at)
)
```

Retention: audit_logs are never deleted in v1 (not subject to the 90-day recording retention policy). They are the evidentiary backbone for SOC 2 and must be immutable. In Phase 2, add a 7-year retention policy with archival to cold storage.

**What NOT to log:** Candidate PII (names, emails, resume text). Log resource IDs only. The audit trail should be safe to show to a SOC 2 auditor without exposing candidate data.

---

## Kickoff Readiness Verdict

**READY FOR ENGINEERING KICKOFF. All owner decisions resolved.**

Engineering can begin immediately on all tracks:
- Database schema (v3 §6.1 + `audit_logs` table above)
- Authentication + multi-tenancy + RBAC + MFA enforcement
- Job configuration API (criteria, question bank)
- Google Calendar API integration (uses RoleSignal GCP project)
- Firebase project creation (separate Krino Firebase project)
- Recall.ai bot join + interview state machine
- Post-call scoring pipeline
- Scout agent tools + A2A endpoint
- SOC 2 controls: centralised logging, uptime monitoring, CI hardening, audit_logs

Parallel: Recall.ai video injection spike (OQ2). Avatar stories wait for GO verdict.
Legal gates (OQ7, OQ8, OQ9) block pilot with real candidates only — not build.
