# Krino — Product Requirements Document
**Version:** 3.0 (Draft)
**Date:** 2026-04-07
**Status:** Engineering Review

**Changelog from v2:**
- Sections 4.3–4.10 written to full requirement level with acceptance criteria
- Added consent-decline sub-journey and no-recording mode scoped out
- Defined take-over scorecard behavior (partial AI score + INSUFFICIENT_DATA logic)
- Added recruiter invite clipboard template spec
- Specified STT vendor (Deepgram via Recall.ai)
- Defined Claude JSON failure fallback behavior
- Specified interview_round_context JSON schema
- Added tenant_usage table schema
- Added full webhook event catalogue with all payload schemas
- Clarified scout_conversations write-time sync
- Resolved OQ4 (Option B bot join mechanism — Recall.ai join-by-URL)
- Resolved OQ12 (escalation SLA set as product decision: 15 min business hours)
- Added A2A authentication model (tenant API key in Authorization header)
- Added cross-version comparison policy
- Added scoring consistency CI test methodology
- Clarified Hindi scope (interview language, UI stays English)
- Added STT cost line to cost model
- Added Phase 1 invariant for candidates.tenant_id
- Tightened candidates NOT NULL constraint note

---

## 1. Overview

### 1.1 Product Summary

Krino is an AI-powered video interview platform. A configurable AI agent joins scheduled Google Meet calls, conducts structured yet adaptive interviews informed by the candidate's own resume, scores candidates against consistent role-specific criteria, and delivers detailed scorecards to recruiters. It is a standalone FastAPI microservice that integrates with RoleSignal but deploys and sells independently.

### 1.2 Vision

Replace the generic, robotic first-round screening call with an AI interviewer that is resume-aware, dynamically adaptive, visually present, and consistent — so every candidate gets a fair, thorough, and efficient evaluation regardless of recruiter bandwidth.

Long-term: two-sided talent marketplace where candidates earn reusable AI-verified profiles.

### 1.3 Ideal Customer Profile (v1)

**Primary:** Mid-market technology companies (50–500 employees), 2–10 recruiters, ≥20 technical interviews/month, no dedicated interview tooling.

**Secondary:** Technical recruiting agencies running high-volume screening for multiple clients.

**Not targeted v1:** Enterprises requiring SOC 2, ATS integrations beyond RoleSignal, or HIPAA.

### 1.4 Target Users

| User | Role |
|---|---|
| Recruiter | Configures jobs, schedules interviews, reviews scorecards, sends candidate invites |
| Hiring Manager | Reviews scorecards, advances or rejects candidates, adds notes |
| Company Admin | Manages users, evaluation criteria, AI persona, tenant config |
| Candidate | Receives invite, joins Google Meet, completes interview |

### 1.5 Competitive Differentiation

| Competitor | Weakness | Krino's edge |
|---|---|---|
| HireVue | Async video only, no live AI, $50k+/yr | Live adaptive AI, affordable, instant setup |
| Spark Hire | Human-reviewed async, slow | Real-time AI scoring, instant scorecard |
| Karat | Human interviewers, $300–600/interview | AI-conducted, 50x cheaper |
| Paradox/Olivia | Chat/text only, no voice or video | Live video with visual AI presence |
| Generic AI bots | No visual, phone-only, not resume-aware | Resume-aware, video-native, cinematic avatar |

Core defensible differentiators: (1) resume-aware adaptive questioning, (2) visual AI presence in video meeting, (3) consistent criteria-based scoring with transcript evidence, (4) multi-round context carry-forward.

---

## 2. Goals & Success Metrics

### 2.1 Business Goals

- Reduce recruiter time on first-round screening by ≥70%
- Consistent, auditable evaluation across all candidates for a given role
- Multi-round workflows without added recruiter overhead
- Data model supports future talent marketplace (Phase 2/3)

### 2.2 v1 Success Metrics

| Metric | Definition | Target |
|---|---|---|
| Interview completion rate | Interviews where candidate answered all required Qs / interviews where candidate joined and consented | ≥75% |
| Bot join success rate | Scheduled interviews where bot joined within 60s of T-0 / all scheduled interviews | ≥98% |
| Recruiter decision latency | Median time from interview.COMPLETED to recruiter action | <24 hours |
| Candidate satisfaction | Post-interview survey (1–5 scale, sent in confirmation email) | ≥3.8/5.0 |
| AI scoring consistency | Std dev of overall_score for same transcript run 10× through scoring pipeline | <3 points |
| Cost per completed interview | Total infra cost / completed interviews | <$2.00 |
| System uptime | Krino API availability | ≥99.5% |

### 2.3 Phase 1 Instrumentation (for Phase 2 analysis)

Must be collected in v1 even if not surfaced in dashboards:
- AI recommendation vs eventual recruiter decision (advance/reject)
- 90-day outcome hook (was advanced candidate eventually hired?)
- Per-question answer quality scores

---

## 3. User Journeys

### 3.1 Job Setup (One-Time Per Job)

```
1. Create Job
   - Title, paste / upload job description
   - Select Role Type: backend | frontend | ai_ml | fullstack | custom
   - System auto-generates evaluation criteria + question bank from JD + role type

2. Review & Edit Evaluation Criteria
   - View default criteria for selected role type
   - Adjust weights (must sum to 100% for non-hard-filter criteria)
   - Add / remove / rename criteria
   - Mark criteria as hard filter (pass/fail, excluded from weighted score)
   - Or: replace entirely with custom criteria

3. Review & Edit Question Bank
   - View auto-generated questions organised by criterion
   - Mark: required (always asked) vs optional (asked if time permits)
   - Set probe depth per question: surface | probe-once | probe-deeply
   - Add custom questions; tag to criterion
   - Configure hard filter questions (asked first, before scored questions)
   - Set pre-canned answers for common candidate questions (salary, team, remote)

4. Set Interview Settings
   - Max duration: 15 | 20 | 30 | 45 minutes
   - Number of rounds: 1–5
   - Pass score threshold per round (0–100)
   - AI persona name (e.g., "Alex")
   - AI persona voice: female-en | male-en | neutral-en | female-hi | male-hi
   - Next-steps timeline text (used in post-interview confirmation email)

5. Save → Job status: ACTIVE
   System creates evaluation_criteria_versions record (version 1) and
   question_bank_versions record (version 1) for Round 1.
```

### 3.2 Scheduling an Interview

```
1. Navigate to Job → Candidate Queue → select candidate(s)
2. Click "Schedule Interview"

3. Interview Setup Modal:
   a. Round number (defaults to 1)
   b. Scheduling mode:
      Option A — System-managed:
        Enter date, time, duration, meeting title, optional agenda
        System creates Google Meet via Calendar API (service account is host)
        System adds Recall.ai bot to the meeting
      Option B — External link:
        Recruiter pastes existing Google Meet URL
        System registers link; schedules bot to join via URL
        Warning displayed: "Note: AI cannot end this meeting — it will leave
        when done. If the meeting has a waiting room, you must admit the bot manually."
   c. Observer toggle: "Allow team member to join as observer"
      If enabled: enter observer email → system generates separate calendar invite
   d. Optional custom AI briefing note (overrides job-level note for this interview)

4. Click "Schedule"
   → Interview record created: status SCHEDULED
   → Celery job queued: fire at scheduled_at minus 2 minutes to join
   
5. System shows invite clipboard panel:
   ┌──────────────────────────────────────────────────────────┐
   │ Ready to send to candidate                               │
   │                                                          │
   │ [Copy email template]   [Copy Meet link only]            │
   │                                                          │
   │ Email template:                                          │
   │   To: [candidate email if entered]                       │
   │   Subject: Interview Invitation — [Role] at [Company]   │
   │   Body: "Hi [Name], [Company] would like to invite       │
   │   you for a brief AI-conducted video interview for        │
   │   [Role]. Please review what to expect:                  │
   │   [pre-interview URL]. Join here: [Meet link].            │
   │   Duration: approx [X] minutes."                         │
   └──────────────────────────────────────────────────────────┘

6. Recruiter sends invite manually via their own email/messaging
```

### 3.3 Candidate Pre-Interview Experience

```
1. Candidate clicks pre-interview URL: /pre-interview/{interview_token}
   Token expires 24 hours after scheduled_at.
   
2. Pre-interview page (Krino-hosted):
   - "What to expect": duration, format ("you'll speak with an AI interviewer"), 
     topic areas covered
   - Camera and microphone test (WebRTC media check in browser)
   - Disclosure text (fixed, not editable per tenant):
     "This interview is conducted by an AI. The session will be recorded and 
      transcribed for evaluation purposes. By proceeding, you confirm you consent 
      to this recording."
   - Checkbox: "I understand and consent" → required to reveal Meet link
   - "Join Interview" button → opens Google Meet in new tab

3. Alternative: candidate joins Meet directly without visiting pre-interview page.
   Verbal consent inside the meeting is always enforced regardless.
```

### 3.4 AI Conducts the Interview

```
PHASE 1 — JOINING
  Celery job fires at T-2min → Recall.ai bot created and joins meeting.
  Avatar: joining animation.
  Scout joins with display name: "[Persona Name] (AI Interviewer)"
  
  If candidate not yet present: Scout waits in silence.
  No-show timeout: 10 minutes from T-0 (not from bot join).
  → Timeout reached with no candidate: Scout leaves.
    Status → NO_SHOW. Recruiter notified.

PHASE 2 — CONSENT GATE
  Scout: "Hi [Candidate Name], I'm [Persona], an AI interviewer for [Company]. 
  Before we begin, I want to let you know that this conversation will be 
  recorded and used to evaluate your application for [Role]. 
  Do I have your consent to proceed?"

  Consent decision tree:
  
  → YES / affirmative (any of: "yes", "sure", "okay", "go ahead", "I consent"):
    log consent_given=TRUE, consent_at, consent_transcript_segment_id
    Proceed to HARD_FILTERS.
  
  → NO / refusal:
    Scout: "Understood. I'll let the [Company] team know you'd prefer
    a different format. Someone will be in touch with you shortly. 
    Thank you for your time."
    Bot leaves meeting immediately.
    Status → CONSENT_DECLINED.
    Audio captured during consent gate: NOT retained (only the transcript 
    of the consent exchange is stored for the legal record; no recording_url set).
    Recruiter notified: "[Candidate] declined recording consent."
  
  → AMBIGUOUS / silence:
    Scout: "Just to confirm — are you happy to proceed with a recorded 
    AI interview today?"
    → If still ambiguous/silent: treat as NO (same flow as refusal).

PHASE 3 — HARD FILTERS
  Scout asks all hard-filter questions first, in configured order.
  Each answer logged as PASS or FAIL in hard_filters_json.
  IMPORTANT: If a hard filter answer is FAIL, Scout continues the interview 
  regardless. The AI does NOT cut the interview short or indicate failure. 
  Recruiter decides. This prevents AI auto-rejection liability.

PHASE 4 — ADAPTIVE INTERVIEW
  Scout works through the question bank. Adaptation rules:
  
  A. Required questions asked in configured order.
  B. Per answer:
     - Claude evaluates: clear, specific, relevant?
     - If YES → next question.
     - If vague/incomplete → follow-up per configured probe depth.
       probe-once: one targeted follow-up ("Can you be specific about X?")
       probe-deeply: up to two follow-ups before moving on.
  C. Optional questions asked if time budget allows (80% threshold).
  D. If candidate already demonstrated a criterion covered by a later 
     optional question → that optional question skipped.
  E. Scout references resume: "I noticed you worked on [X] at [Company] —
     walk me through your role in that."
  F. Scout simulates 1–2s thinking pause before each response.
  G. Full conversation context maintained in every Claude call.
  
  Time management:
    At 80% of configured duration: Scout wraps optional questions.
    At 95%: Scout moves directly to closing regardless.

PHASE 5 — CANDIDATE QUESTIONS
  Scout: "That's everything I needed to cover. Do you have any questions 
  about the role or the team?"
  
  Scout answers using recruiter-configured pre-canned answers verbatim.
  For out-of-scope questions:
    "That's a great question — I don't have that detail to hand, but I'll 
     make sure the team addresses it when they follow up with you."
  Maximum 3 candidate questions before Scout closes.

PHASE 6 — CLOSING
  Scout: "Thank you [Name]. It was great speaking with you. The team will 
  review your interview and be in touch within [next_steps_timeline]. 
  Have a wonderful day!"
  
  Option A (Scout is host): Scout ends meeting for all participants.
  Option B (Scout is not host): Scout leaves meeting.
  Status → COMPLETED. Async scoring job queued.
  Confirmation email to candidate queued (fires within 5 minutes).

CLAUDE JSON FAILURE FALLBACK
  If Claude returns malformed JSON or empty response:
  Attempt 1: Retry with "Respond ONLY with valid JSON" suffix appended.
  If retry fails: Scout says "Let me take a moment." (1.5s pause) and 
    advances to the next required question.
  If 3+ consecutive Claude failures: Status → INTERRUPTED.
    Scout: "I'm experiencing a technical issue. I apologise for the 
    interruption — the team will be in touch to reschedule."
    Bot leaves. Recruiter notified with error detail.
```

### 3.5 Mid-Call Human Escalation

```
Trigger: candidate says "I want a real person" / "talk to a human" or semantically equivalent.

Attempt 1: "I understand. I'm here to have a genuine conversation so the right 
people can follow up. I have just a few more questions — shall we continue?"

Attempt 2: "I hear you. The team reviews everything personally and will follow 
up with you directly. Would you share just a bit more?"

Attempt 3: "Of course. I'll make sure the team knows you'd prefer to speak 
with someone directly. They'll be in touch soon. Thank you."
Scout leaves. Status → ESCALATED. Recruiter notified immediately.

Product decision: Recruiter has 15 minutes (business hours, 9am–6pm recruiter 
timezone) to acknowledge the escalation. No automated fallback — recruiter must 
manually contact candidate. If recruiter is outside business hours, notification 
queues for next business day opening.
```

### 3.6 Technical Failure Mid-Interview

```
Trigger: Recall.ai bot drops / STT fails / Claude timeout >15s (3 consecutive).

Auto-recovery:
  1. System attempts bot rejoin within 30 seconds.
  2. If rejoin succeeds: Scout rejoins, says "I apologise for the brief 
     interruption — let's continue from where we left off." Resumes from 
     last confirmed transcript turn.
  3. If rejoin fails (2 attempts):
     Scout sends Google Meet in-chat message:
       "[Persona]: I've encountered a technical issue. 
        The team will be in touch to reschedule."
     Status → INTERRUPTED. Partial transcript saved. Recruiter notified.
     Reschedule prompt surfaced in dashboard.
```

### 3.7 No-Show

```
Scout joins at T-2min. Candidate does not join by T+10min.
Scout leaves. Status → NO_SHOW. Recruiter notified.
Dashboard shows "Reschedule" action button for the interview.
```

### 3.8 Team Member Take-Over

```
Team member joins using observer invite link.

Default — observer mode:
  Team member visible in meeting. Scout continues as primary interviewer.
  Team member can view live transcript in Krino dashboard (separate tab).

Take-over:
  Team member clicks "Take over interview" in Krino live monitor dashboard.
  System signals Recall.ai bot.
  Scout: "I'll hand over to [Team Member Name] who has just joined. 
         Good luck with the rest of the conversation, [Candidate Name]."
  Scout stops asking questions. Continues transcribing silently.
  interviews.takeover_at and takeover_by recorded.

Post-call scoring when take-over occurred:
  - AI-conducted portion (before takeover_at): scored normally.
  - Human-conducted portion (after takeover_at): transcript captured, 
    labelled HUMAN_CONDUCTED; not scored by AI.
  - If AI conducted ≥50% of interview:
      overall_score = AI-scored portion score.
      Scorecard displays banner: "Note: Interview was partially human-conducted.
      Score reflects the first [X] minutes only. Please review the full transcript 
      for the human-conducted portion."
  - If AI conducted <50% of interview:
      overall_score = null. recommendation = INSUFFICIENT_DATA.
      Scorecard displays: "Insufficient AI-conducted interview data to score.
      Please review the full transcript and score manually."
      Recruiter prompted to provide manual override score + recommendation.
```

### 3.9 Recruiter Reviews Results

```
Notification: "Interview complete — [Candidate] · [Role] · Round [N]"

Report page:
  Header:   Candidate name, role, round, date, duration
  Summary:  AI recommendation pill: ADVANCE | HOLD | REJECT | INSUFFICIENT_DATA
            Overall score gauge (0–100)
            Scout 2–3 sentence summary paragraph
            Criteria version note: "Scored using criteria v[N]"
  
  Scores:   Per-criteria card:
              Criterion · Weight · Score bar
              ↳ Expandable: 1–3 evidence quotes from transcript
                e.g. "When asked about [X], candidate said '...' — Score: 72/100"
  
  Hard Filters: PASS ✓ / FAIL ✗ for each, with candidate's verbatim answer
  
  Transcript: Timestamped, speaker-labelled (AI / CANDIDATE / OBSERVER)
              Searchable by keyword
              Audio playback with transcript sync
              Human-conducted segments highlighted in orange if applicable
  
  Cross-version warning (if comparing across criteria versions):
    "⚠ This candidate was scored under criteria v[X]. Candidate [Y] used v[Z].
     Comparison may not be meaningful. [View criteria differences]"
  
  Actions:
    [Advance to Round N+1] → opens scheduling modal pre-filled for next round
    [Reject]               → opens rejection email template composer
    [Flag for human review]→ adds internal flag tag
    [Add internal notes]   → free text, recruiter-only
    [Override recommendation] → dropdown + mandatory note field
```

### 3.10 New Tenant Onboarding

```
Step 1: Organisation name, logo, industry
Step 2: Connect Google account for Calendar API (or skip → Option B only)
Step 3: AI persona name and voice selection
Step 4: Create first job (guided wizard — paste JD, confirm role type, preview criteria)
Step 5: Test interview
  → System schedules a test interview with built-in dummy candidate
  → Recruiter joins as observer to validate bot join, audio, avatar
  → Test interview not scored; used only to verify setup
Step 6: Invite team members (Recruiter / Hiring Manager / Viewer roles)
→ First real interview ready
```

---

## 4. Feature Requirements

### 4.1 Interview Engine

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| F1 | AI conducts full interview via Google Meet as a video participant | Bot joins meeting, completes all 6 phases without manual intervention | P0 |
| F2 | AI generates questions from JD + candidate resume + prior round answers | Two candidates for same job receive different opening questions; questions reference specific candidate experience | P0 |
| F3 | AI asks adaptive follow-ups referencing candidate's actual words | Follow-up explicitly quotes or paraphrases what the candidate just said | P0 |
| F4 | AI maintains full conversation context | AI does not re-ask provided information; references prior answers in later questions | P0 |
| F5 | Configurable probe depth per question: surface / once / deeply | Depth setting enforced; probe-deeply triggers up to 2 follow-ups before moving on | P0 |
| F6 | Pre-canned answers for candidate questions + graceful deferral | Configured answers delivered verbatim; out-of-scope triggers deferral script | P1 |
| F7 | Time budget enforcement: 80% threshold (wrap optionals), 95% threshold (close) | Interview ends at 95% of configured duration regardless of remaining questions | P1 |
| F8 | Configurable persona name and voice per tenant | Persona name in all AI speech; voice matches selection | P1 |
| F9 | 1–2s thinking pause, variable | Pause duration varies ±300ms to avoid mechanical regularity | P1 |
| F10 | Mid-call escalation: 3-attempt → ESCALATED | Attempt count tracked; exact scripts from §3.5 used | P0 |
| F11 | Handle silence >8s and off-topic responses | Silence: "Take your time — I'm listening"; Off-topic: gentle redirect to question | P1 |
| F12 | Verbal consent gate (mandatory, not skippable) | CONSENT_DECLINED path fully implemented per §3.4; consent fields populated in DB | P0 |
| F13 | Team member take-over → note-taker mode | Dashboard button triggers mode switch; takeover_at/by recorded; scoring split per §3.8 | P1 |
| F14 | 10-minute no-show timeout | NO_SHOW status set at T+10; recruiter notified | P0 |
| F15 | Auto-recovery on bot drop: 2 attempts, then INTERRUPTED | Rejoin attempted within 30s; fallback in-meeting chat message per §3.6 | P0 |
| F16 | Claude JSON failure fallback | Retry once; if fails, advance to next required question; 3+ consecutive → INTERRUPTED | P0 |

### 4.2 AI Avatar

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| V1 | Technical spike: validate Recall.ai virtual camera video injection into Google Meet | Spike result documented before v1 build. Go = V2–V3 in scope. No-go = V4 only + roadmap note | P0 (spike) |
| V2 | WebGL default avatar with 5 states: joining / listening / thinking / speaking / closing | Each state visually distinct; transitions <300ms; renders headless Chrome on Fly.io | P1 |
| V3 | Avatar streamed as bot video feed into Google Meet | Candidate sees avatar in bot participant tile; no black screen | P1 |
| V4 | Static fallback: company logo image displayed as bot video if rendering fails | Always available; never a broken tile | P0 |
| V5 | Premium: Simli real-time lip-synced avatar | Activates via tenant config; fallback to V2 if Simli unavailable | P2 |
| V6 | Tenant colour palette for default avatar | Admin sets hex colours; applied to WebGL scene | P2 |

### 4.3 Scheduling & Meeting Management

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| S1 | Option A: System creates Google Meet via Calendar API (service account per tenant) | Calendar.events.insert() called; Meet link returned and stored; calendar event ID stored in interviews.meeting_id | P0 |
| S2 | Option B: Recruiter pastes Google Meet URL; system registers and schedules bot join | URL validated (must match meet.google.com pattern); Recall.ai bot scheduled to join via URL; host_type=EXTERNAL_HOST stored; warning shown about waiting room risk | P0 |
| S3 | Option B bot join mechanism | Recall.ai join-by-URL: headless Chrome navigates to Meet URL; bot joins as guest with display name "[Persona] (AI Interviewer)". If waiting room active, recruiter must admit manually (communicated at scheduling) | P0 |
| S4 | Recruiter configures: title, date/time, duration, agenda, custom AI briefing notes | All fields editable in scheduling modal; briefing_notes injected into AI system prompt | P0 |
| S5 | Bot auto-joins at T-2min | Celery job queued at interview creation with eta=scheduled_at-120s; confirmed joined via Recall.ai webhook within 60s of T-0 | P0 |
| S6 | Option A: Scout ends meeting after closing | Recall.ai API call to end session AND meeting after CLOSING phase | P0 |
| S7 | Option B: Scout leaves meeting after closing | Recall.ai API call to remove bot only | P0 |
| S8 | Observer invite generated on toggle | Separate Google Calendar invite sent to observer email; invite includes same Meet link; observer tagged in system | P1 |
| S9 | Pre-interview page | Hosted at /pre-interview/{token}; token = HMAC(interview_id + secret); expires T+24h; camera/mic test, disclosure, consent checkbox → reveals Meet link | P1 |
| S10 | Candidate confirmation email | Triggered on interview.COMPLETED; delivered within 5 min via SendGrid; contains: thanks, next-steps timeline from job config, recruiter contact email; tenant-branded HTML template | P1 |
| S11 | Recruiter notification on status change | In-app + email on: COMPLETED, FAILED, INTERRUPTED, ESCALATED, NO_SHOW, CONSENT_DECLINED; delivered within 2 min of status change | P0 |
| S12 | Interview cancellation | Recruiter can cancel any interview in SCHEDULED or WAITING state; Celery job dequeued; if bot already joined, Recall.ai bot removed; status → CANCELLED; no automated candidate notification | P1 |
| S13 | Recruiter invite clipboard panel | Shown immediately after scheduling; provides "Copy email template" and "Copy Meet link only" buttons; template pre-filled per §3.2 | P1 |

### 4.4 Scoring & Analysis

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| SC1 | Post-call async scoring; Celery job triggered on COMPLETED status | Scorecard created ≤5 min after status → COMPLETED; scored_at recorded | P0 |
| SC2 | Overall score (0–100) = weighted sum of criteria scores | Score = Σ(criterion_score × criterion_weight); stored to 2 decimal places | P0 |
| SC3 | Per-criteria score (0–100) with 1–3 evidence quotes | Claude identifies quotes during scoring pass; "no data" → score=0 with note | P0 |
| SC4 | Hard filter pass/fail tracked separately; never averaged into overall score | Hard filters shown as PASS ✓ / FAIL ✗ with verbatim candidate answer | P0 |
| SC5 | Recommendation: ADVANCE if score ≥ threshold AND all hard filters PASS; REJECT if any hard filter FAIL; HOLD otherwise | Logic enforced in scoring service; not configurable per interview | P0 |
| SC6 | 2–3 sentence AI summary | Summary covers: strongest signal, main concern, recommendation rationale | P0 |
| SC7 | Scorecard stores criteria_version_id | Scores always interpretable against the criteria version active at scheduling time | P0 |
| SC8 | Scoring retry: 3 attempts on failure | If all 3 fail: status → SCORING_FAILED; recruiter notified; interview still accessible with transcript | P0 |
| SC9 | Round N scoring briefed with all prior round context | interview_round_context.round_summaries_json injected into scoring prompt for round 2+ | P1 |
| SC10 | Recruiter override with mandatory note | Override stored with override_by, override_at, override_note; original AI recommendation preserved | P1 |
| SC11 | Scorecard internal-only | No API endpoint, link, or email exposes scorecard data to candidates or unauthenticated callers | P0 |
| SC12 | AI recommendation is advisory only; no automated advancement or rejection | All advance/reject actions require explicit recruiter click | P0 |
| SC13 | Scoring consistency CI test | 10 test transcripts run through scoring pipeline 5× nightly; std dev <3 points per transcript; CI fails if any transcript fails | P1 |

### 4.5 Evaluation Criteria Management

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| E1 | Default criteria set per role type auto-loaded | Defaults from config loaded on role type selection; weights sum to 100% | P0 |
| E2 | Admin adjusts weights; system validates sum to 100% | Fractional weights supported; validation on save | P0 |
| E3 | Admin adds, removes, renames criteria | Changes take effect on next interview; existing scorecards unaffected | P0 |
| E4 | Admin fully replaces with custom criteria | Custom criteria fully supported; role type defaults can be ignored entirely | P0 |
| E5 | Per-job recruiter evaluation instructions (free text) | Stored in jobs table; injected into scoring prompt as additional context, not as criteria | P1 |
| E6 | Each saved criteria config creates a new immutable version | version_number incremented on save; previous versions immutable; scorecard references version at scheduling time | P0 |
| E7 | Active criteria version used at scheduling time, not at interview time | criteria_version_id snapshot taken when interview is created, not when it runs | P0 |

**Default Criteria:**

*Backend Engineer:*
| Criterion | Weight | Rubric |
|---|---|---|
| Technical knowledge & depth | 30% | Systems, data structures, CS fundamentals appropriate to seniority |
| Problem-solving approach | 20% | Structures problems clearly, considers edge cases |
| Relevant experience | 20% | Experience aligns with JD; examples are specific and verifiable |
| Communication clarity | 15% | Explains technical concepts clearly; concise but not terse |
| Motivation & culture fit | 15% | Genuine interest in role; values alignment; quality of questions asked |
| Hard filters | Pass/Fail | Location, notice period, salary expectations, work authorisation |

*(Similar tables for AI/ML, Frontend, Full Stack — with role-appropriate criterion names and weights.)*

### 4.6 Question Bank

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| Q1 | Auto-generate question set from JD + role type | Minimum 10 scored questions + configured hard filter questions on job create | P0 |
| Q2 | Recruiter adds, removes, reorders questions | Drag-and-drop reorder; required/optional toggle | P1 |
| Q3 | Each question tagged to a criterion; required/optional designation required | Untagged questions blocked on save | P1 |
| Q4 | AI generates dynamic follow-ups beyond question bank | Follow-ups generated in context; not pre-scripted | P0 |
| Q5 | Hard filter questions always first | Order enforced by interview engine; not reorderable past the hard-filter boundary | P0 |
| Q6 | Question bank snapshot taken at scheduling time | question_bank_version_id stored in interview; recruiter edits after scheduling do not affect in-flight interviews | P0 |
| Q7 | Round 2+ question banks are distinct and separately configurable | Each round has its own question bank; Round 2 defaults are depth-probing variants of Round 1 questions | P1 |

### 4.7 Scout Agent

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| A1 | Answers questions about completed interviews | Can retrieve and summarise any interview within tenant scope | P0 |
| A2 | Compares candidates for same job | Side-by-side summary + scores; cross-version warning shown if criteria differ | P0 |
| A3 | Surfaces candidates to advance | "Who should I advance for [job]?" returns ranked list with reasoning | P1 |
| A4 | Identifies patterns across results | "What are common gaps for [role]?" gives aggregate analysis | P1 |
| A5 | Triggers next-round scheduling via chat | "Schedule round 2 for [candidate]" opens scheduling modal pre-filled | P1 |
| A6 | Suggests criteria improvements | After ≥20 interviews, identifies low-signal criteria | P2 |
| A7 | A2A endpoint: POST /api/agent/query | Accepts from_agent, context, query; returns structured response; authenticated via tenant API key (Bearer token); rate-limited to 100 req/min per key | P1 |
| A8 | Persistent conversation context within tenant session | llm_messages_json maintained; context survives page navigation | P0 |
| A9 | Global slide-in panel from any page | Consistent with Sera UX pattern | P0 |

### 4.8 Multi-Round Support

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| R1 | Job supports up to 5 rounds, each independently configured | rounds_config_json stores array of round configs | P0 |
| R2 | Each round has own question bank, criteria weights, time budget | Round N config editable independently in job settings | P1 |
| R3 | Recruiter manually triggers each subsequent round from scorecard | "Advance to Round 2" → scheduling modal pre-filled for round 2; requires explicit recruiter action | P0 |
| R4 | AI in round 2+ briefed with all prior round context | interview_round_context.round_summaries_json injected into system prompt | P1 |
| R5 | Candidate status tracked per job | PENDING → SCHEDULED → IN_PROGRESS → PASSED / FAILED / ESCALATED / NO_SHOW / CANCELLED | P0 |

### 4.9 Multi-Tenancy

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| T1 | Full tenant data isolation | All queries include WHERE tenant_id = :tid; enforced at ORM layer; automated isolation test suite | P0 |
| T2 | Each tenant configures AI persona name and voice | Stored in tenants table; applied to all interviews | P1 |
| T3 | Per-tenant Google OAuth for Calendar API | OAuth flow stores refresh token per tenant; Option B always available as fallback if no token | P1 |
| T4 | Role-based access: Admin, Recruiter, Hiring Manager, Viewer | Enforced at API layer; each role's permissions documented in §appendix | P1 |
| T5 | Usage tracking per tenant | tenant_usage table updated after each interview | P1 |
| T6 | Tenant API keys | Key generation and rotation in admin settings; used for RoleSignal integration and A2A | P2 |

### 4.10 RoleSignal Integration

| ID | Requirement | Acceptance Criteria | Priority |
|---|---|---|---|
| I1 | RoleSignal pushes candidate + job to Krino | POST /api/integrations/rolesignal/candidates; authenticated via tenant API key; creates/updates candidate + job_candidate link | P1 |
| I2 | Krino emits webhook events | Events: interview.scheduled, interview.started, interview.completed, interview.failed, score.ready, interview.escalated; full payload schemas in §6.3 | P1 |
| I3 | RoleSignal fetches scorecard via API | GET /api/interviews/{id}/scorecard; requires tenant API key; returns score, recommendation, summary, criteria_scores | P2 |

---

## 5. Technical Architecture

### 5.1 Service Architecture

```
┌───────────────────────────────────────────────────────────┐
│                         KRINO                             │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ REST API │  │ Webhook   │  │  Scout   │  │  Admin  │ │
│  │ (FastAPI)│  │ Receiver  │  │  Agent   │  │  API    │ │
│  └──────────┘  │ /recall   │  └──────────┘  └─────────┘ │
│                └──────────┘                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │                Services Layer                       │  │
│  │  InterviewOrchestrator  │  QuestionGenerator        │  │
│  │  AsyncScorer            │  AvatarStreamManager      │  │
│  │  MeetingManager         │  ConsentHandler           │  │
│  │  RoundContextBuilder    │  WebhookEmitter           │  │
│  │  STTHandler             │  NotificationService      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │          Background Jobs (Celery + Redis)           │  │
│  │  bot_join_job  │  scoring_job  │  notification_job  │  │
│  │  webhook_delivery_job  │  recording_expiry_job      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │              PostgreSQL (Neon)                      │  │
│  └────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
        │           │           │           │
   Recall.ai    Google       Claude      ElevenLabs
   (bot+STT)    Calendar     Haiku/      (TTS)
   (Deepgram)   API          Sonnet
        │
   Simli (P2)
```

### 5.2 Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Backend | Python 3.12 / FastAPI | Async-native |
| Database | PostgreSQL (Neon) | Multi-tenant |
| Job scheduler | Celery + Redis | Production-grade; distributed; DLQ |
| Meeting bot + STT | Recall.ai (Deepgram transcription) | Google Meet join, audio injection, diarised transcription |
| AI avatar (default) | Three.js / WebGL → virtual camera | Requires V1 spike confirmation |
| AI avatar (premium) | Simli (P2) | Real-time lip-sync |
| LLM — conversation | claude-haiku-4-5 | Low latency for real-time turns |
| LLM — scoring | claude-sonnet-4-6 | Higher quality for post-call analysis |
| TTS | ElevenLabs | Via Recall.ai audio output |
| Meeting creation | Google Calendar API (per-tenant OAuth) | Service account per tenant for Option A |
| Auth | Firebase (JWT) | Multi-tenant aware |
| Hosting | Fly.io | Docker, auto-scaling |
| Email | SendGrid | Transactional; HTML templates |
| Cache | Redis | Celery broker + rate limiting |

### 5.3 STT Vendor

**Recall.ai uses Deepgram** as its underlying STT engine. Transcription is delivered via Recall.ai's real-time transcript webhook. Krino does not integrate directly with Deepgram. STT cost is included in the Recall.ai $0.15/hr transcription line item.

Hindi STT: Recall.ai / Deepgram supports Hindi. No additional integration needed.

### 5.4 Latency Budget (STT → AI response, p95 target ≤4s)

| Component | Budget |
|---|---|
| Recall.ai STT + webhook delivery | 400–800ms |
| Krino server + Claude Haiku inference (streaming) | 600–1200ms |
| ElevenLabs TTS first audio chunk (streaming) | 300–600ms |
| Recall.ai audio injection + Google Meet codec | 200–400ms |
| Simulated thinking pause | 500–1000ms (intentional) |
| **Total p95** | **~3.5–4.0s** |

Use streaming TTS output: ElevenLabs streams audio chunks; first chunk starts playing before full TTS is generated. This keeps perceived latency under 4s even if total generation exceeds 3s.

### 5.5 Interview State Machine

```
                    ┌──────────┐
              ┌────►│SCHEDULED │◄──── manual reschedule
              │     └────┬─────┘
              │          │ T-2min: Celery bot_join_job fires
              │     ┌────▼──────┐
              │     │ JOINING   │──── join fails (2 attempts) ──► FAILED
              │     └────┬──────┘
              │          │ bot confirmed in meeting
              │     ┌────▼──────┐
              │     │ WAITING   │──── T+10min no candidate ─────► NO_SHOW
              │     └────┬──────┘
              │          │ candidate detected in meeting
              │     ┌────▼──────────┐
              │     │ CONSENT_GATE  │──── NO/ambiguous ──────────► CONSENT_DECLINED
              │     └────┬──────────┘
              │          │ consent given
              │     ┌────▼──────────┐
              │     │ IN_PROGRESS   │──── 3× escalation ─────────► ESCALATED
              │     │               │──── bot drop (2 attempts) ──► INTERRUPTED
              │     │               │──── 3× Claude failures ─────► INTERRUPTED
              │     └────┬──────────┘
              │          │ all phases complete
              │     ┌────▼──────────┐
              │     │  COMPLETED    │
              │     └────┬──────────┘
              │          │ scoring Celery job
              │     ┌────▼──────────┐
              │     │   SCORED      │──── scoring fails (3 attempts) ► SCORING_FAILED
              │     └───────────────┘

Recruiter-initiated transitions:
  SCHEDULED → CANCELLED  (before bot joins)
  INTERRUPTED → SCHEDULED  (reschedule)
  NO_SHOW → SCHEDULED  (reschedule)
```

### 5.6 Adaptive Interview — Claude Prompt Structure

**System prompt (assembled per turn):**
1. Persona block (company, persona name, role)
2. Candidate brief (name, resume summary, key experiences)
3. Job brief (JD summary, required skills, recruiter briefing notes)
4. Evaluation criteria (names, weights, rubrics — from criteria version)
5. Current phase + phase instructions
6. Question queue (remaining required + optional, with probe depth)
7. Full conversation history (all prior turns)
8. Round context (rounds 2+ only: prior round summaries)
9. Adaptation rules (F3, F4, F5 logic stated explicitly)

**Claude response schema (JSON):**
```json
{
  "speech": "Text Scout should speak aloud",
  "phase_update": "HARD_FILTERS|INTERVIEWING|CANDIDATE_QUESTIONS|CLOSING|null",
  "questions_remaining": ["q_id_1", "q_id_2"],
  "skip_question_ids": ["q_id_3"],
  "probe_this_answer": true,
  "probe_question": "Can you be more specific about X?",
  "resume_reference": "I noticed you worked on Y at Z —"
}
```

**Failure fallback (F16):**
- Malformed/empty response → retry once with `"Respond ONLY with valid JSON. Do not include markdown."` suffix
- Second failure → `speech = "Let me take a moment."` + advance to next required question
- 3+ consecutive failures → interview transitions to INTERRUPTED

---

## 6. Data Model

### 6.1 Full Schema

```sql
-- ─────────────────────────────────────────────
-- MULTI-TENANCY
-- ─────────────────────────────────────────────
tenants (
  id            UUID PK DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  slug          TEXT UNIQUE NOT NULL,
  plan          TEXT DEFAULT 'starter',
  google_refresh_token  TEXT,               -- Option A: Calendar API; NULL if not connected
  ai_persona_name       TEXT DEFAULT 'Alex',
  ai_persona_voice      TEXT DEFAULT 'female-en',
  settings_json         JSONB DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT now()
)

tenant_users (
  id            UUID PK DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants,
  firebase_uid  TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin','recruiter','hiring_manager','viewer')),
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id, firebase_uid)
)

-- ─────────────────────────────────────────────
-- JOBS
-- ─────────────────────────────────────────────
jobs (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants,
  external_id     TEXT,                         -- ATS / RoleSignal reference
  title           TEXT NOT NULL,
  description     TEXT,
  role_type       TEXT NOT NULL,                -- backend|frontend|ai_ml|fullstack|custom
  rounds_config_json  JSONB NOT NULL DEFAULT '[]',
    -- [{round, max_duration_min, pass_threshold, custom_briefing}]
  next_steps_timeline TEXT DEFAULT '3–5 business days',
  status          TEXT DEFAULT 'active',
  created_by      UUID REFERENCES tenant_users,
  created_at      TIMESTAMPTZ DEFAULT now()
)

-- ─────────────────────────────────────────────
-- EVALUATION CRITERIA (VERSIONED)
-- ─────────────────────────────────────────────
evaluation_criteria_versions (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants,
  job_id          UUID REFERENCES jobs,         -- NULL = role-type default
  role_type       TEXT,
  version_number  INT NOT NULL,
  is_active       BOOLEAN DEFAULT TRUE,
  criteria_json   JSONB NOT NULL,
    -- [{id, name, weight, description, scoring_rubric, is_hard_filter}]
  created_by      UUID REFERENCES tenant_users,
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(job_id, version_number)
)

-- ─────────────────────────────────────────────
-- QUESTION BANKS (VERSIONED)
-- ─────────────────────────────────────────────
question_bank_versions (
  id              UUID PK DEFAULT gen_random_uuid(),
  job_id          UUID NOT NULL REFERENCES jobs,
  round_number    INT NOT NULL DEFAULT 1,
  version_number  INT NOT NULL,
  is_active       BOOLEAN DEFAULT TRUE,
  questions_json  JSONB NOT NULL,
    -- [{id, text, criterion_id, required, probe_depth, tags}]
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(job_id, round_number, version_number)
)

-- ─────────────────────────────────────────────
-- CANDIDATES
-- Phase 1 invariant: tenant_id IS NOT NULL for all Phase 1 records.
-- Nullable column reserved for Phase 2 marketplace candidates.
-- Phase 1 DB constraint: CHECK (tenant_id IS NOT NULL) enforced via app layer.
-- Phase 2 migration will DROP this app-level constraint.
-- ─────────────────────────────────────────────
candidates (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID REFERENCES tenants,      -- NOT NULL in Phase 1 (see above)
  external_id     TEXT,                         -- Manatal / ATS ID
  name            TEXT NOT NULL,
  email           TEXT,
  phone           TEXT,
  resume_url      TEXT,
  resume_text     TEXT,
  profile_json    JSONB DEFAULT '{}',
  -- Phase 2 hooks (feature-flagged in v1, must remain FALSE):
  verified_at             TIMESTAMPTZ,
  marketplace_visible     BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT now(),
  INDEX(tenant_id),
  INDEX(external_id)
)

-- ─────────────────────────────────────────────
-- INTERVIEWS
-- ─────────────────────────────────────────────
interviews (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants,
  job_id          UUID NOT NULL REFERENCES jobs,
  candidate_id    UUID NOT NULL REFERENCES candidates,
  round_number    INT NOT NULL DEFAULT 1,
  status          TEXT NOT NULL DEFAULT 'SCHEDULED',
    -- SCHEDULED|JOINING|WAITING|CONSENT_GATE|IN_PROGRESS
    -- |COMPLETED|SCORED|SCORING_FAILED
    -- |FAILED|NO_SHOW|CONSENT_DECLINED|INTERRUPTED|ESCALATED|CANCELLED
  meeting_type    TEXT DEFAULT 'google_meet',
  host_type       TEXT,                         -- SYSTEM_HOST|EXTERNAL_HOST
  meeting_link    TEXT,
  meeting_id      TEXT,                         -- Google Meet ID
  scheduled_at    TIMESTAMPTZ NOT NULL,
  started_at      TIMESTAMPTZ,
  ended_at        TIMESTAMPTZ,
  duration_seconds INT,
  -- Consent
  consent_given   BOOLEAN,
  consent_at      TIMESTAMPTZ,
  consent_transcript_segment_id UUID,
  -- Configuration snapshots (taken at scheduling time)
  criteria_version_id       UUID REFERENCES evaluation_criteria_versions,
  question_bank_version_id  UUID REFERENCES question_bank_versions,
  -- Recall.ai
  recall_bot_id   TEXT,
  recording_url   TEXT,
  recording_expires_at  TIMESTAMPTZ,
  -- AI config
  ai_persona_name TEXT,
  ai_persona_voice TEXT,
  recruiter_briefing_notes TEXT,
  -- Observer / take-over
  observer_invite_link  TEXT,
  takeover_at     TIMESTAMPTZ,
  takeover_by     UUID REFERENCES tenant_users,
  -- Pre-interview page
  pre_interview_token TEXT UNIQUE,
  pre_interview_consent_at TIMESTAMPTZ,         -- consent given on page (before call)
  created_by      UUID REFERENCES tenant_users,
  created_at      TIMESTAMPTZ DEFAULT now()
)

-- ─────────────────────────────────────────────
-- TRANSCRIPTS
-- ─────────────────────────────────────────────
interview_transcripts (
  id              UUID PK DEFAULT gen_random_uuid(),
  interview_id    UUID NOT NULL REFERENCES interviews,
  turns_json      JSONB NOT NULL DEFAULT '[]',
    -- [{id, speaker (AI|CANDIDATE|OBSERVER), text, timestamp_ms, confidence,
    --    is_consent_utterance, is_hard_filter_answer, is_human_conducted}]
  raw_text        TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
)

-- ─────────────────────────────────────────────
-- STRUCTURED Q&A (per question asked)
-- ─────────────────────────────────────────────
interview_questions_asked (
  id              UUID PK DEFAULT gen_random_uuid(),
  interview_id    UUID NOT NULL REFERENCES interviews,
  question_id     TEXT NOT NULL,               -- from bank, or "adaptive_[n]"
  question_text   TEXT NOT NULL,
  criterion_id    TEXT,
  is_adaptive     BOOLEAN DEFAULT FALSE,
  is_hard_filter  BOOLEAN DEFAULT FALSE,
  asked_at_ms     INT,                         -- timestamp in recording
  candidate_answer_text TEXT,
  answer_start_ms INT,
  answer_end_ms   INT,
  probe_count     INT DEFAULT 0,
  -- Populated by scoring job:
  criterion_score NUMERIC(5,2),
  evidence_quotes JSONB,                       -- [{quote, reasoning}]
  INDEX(interview_id)
)

-- ─────────────────────────────────────────────
-- SCORECARDS
-- ─────────────────────────────────────────────
interview_scorecards (
  id              UUID PK DEFAULT gen_random_uuid(),
  interview_id    UUID NOT NULL REFERENCES interviews,
  criteria_version_id UUID REFERENCES evaluation_criteria_versions,
  overall_score   NUMERIC(5,2),                -- null if INSUFFICIENT_DATA
  recommendation  TEXT,                        -- ADVANCE|HOLD|REJECT|INSUFFICIENT_DATA
  summary_text    TEXT,
  criteria_scores_json  JSONB,
    -- [{criterion_id, name, weight, score, evidence_quotes[{quote, reasoning}]}]
  hard_filters_json JSONB,
    -- [{filter_id, name, result (PASS|FAIL), candidate_answer}]
  partial_interview BOOLEAN DEFAULT FALSE,     -- TRUE if takeover < 50% threshold
  model_used      TEXT,
  tokens_in       INT,
  tokens_out      INT,
  scored_at       TIMESTAMPTZ,
  -- Recruiter override
  recruiter_override        TEXT,
  recruiter_override_notes  TEXT,
  overridden_by   UUID REFERENCES tenant_users,
  overridden_at   TIMESTAMPTZ
)

-- ─────────────────────────────────────────────
-- MULTI-ROUND CONTEXT
-- ─────────────────────────────────────────────
interview_round_context (
  id              UUID PK DEFAULT gen_random_uuid(),
  candidate_id    UUID NOT NULL REFERENCES candidates,
  job_id          UUID NOT NULL REFERENCES jobs,
  round_summaries_json JSONB NOT NULL DEFAULT '[]',
    -- [{
    --   round: 1,
    --   interview_id: "uuid",
    --   overall_score: 74.5,
    --   recommendation: "ADVANCE",
    --   ai_summary: "Candidate showed strong backend fundamentals...",
    --   criteria_scores: [{criterion_id, score}],
    --   hard_filter_results: [{filter, result}],
    --   key_strengths: ["distributed systems knowledge"],
    --   key_gaps: ["limited cloud experience"],
    --   scout_briefing: "In round 1, candidate demonstrated X but showed gaps in Y.
    --                    Round 2 should probe deeper into Z."
    -- }]
  updated_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(candidate_id, job_id)
)

-- ─────────────────────────────────────────────
-- SCOUT CONVERSATIONS
-- llm_messages_json: full Claude API context (system + user + assistant turns,
--   tool results). Never shown to users.
-- display_messages_json: human-readable chat history. Written at call time,
--   not derived from llm_messages_json after the fact.
-- Both written in the same DB transaction per message.
-- ─────────────────────────────────────────────
scout_conversations (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants,
  user_id         UUID NOT NULL REFERENCES tenant_users,
  llm_messages_json    JSONB NOT NULL DEFAULT '[]',
  display_messages_json JSONB NOT NULL DEFAULT '[]',
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
)

-- ─────────────────────────────────────────────
-- USAGE TRACKING
-- ─────────────────────────────────────────────
tenant_usage (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants,
  period_month    DATE NOT NULL,               -- first day of month
  interviews_scheduled    INT DEFAULT 0,
  interviews_completed    INT DEFAULT 0,
  interviews_failed       INT DEFAULT 0,
  interviews_no_show      INT DEFAULT 0,
  interviews_escalated    INT DEFAULT 0,
  interviews_consent_declined INT DEFAULT 0,
  total_duration_minutes  NUMERIC(10,2) DEFAULT 0,
  recall_cost_usd         NUMERIC(8,4) DEFAULT 0,
  llm_cost_usd            NUMERIC(8,4) DEFAULT 0,
  tts_cost_usd            NUMERIC(8,4) DEFAULT 0,
  stt_cost_usd            NUMERIC(8,4) DEFAULT 0,  -- included in recall_cost but tracked separately
  total_cost_usd          NUMERIC(8,4) DEFAULT 0,
  updated_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id, period_month)
)

-- ─────────────────────────────────────────────
-- WEBHOOK EVENTS (outbound)
-- ─────────────────────────────────────────────
webhook_events (
  id              UUID PK DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants,
  event_type      TEXT NOT NULL,
  payload_json    JSONB NOT NULL,
  target_url      TEXT NOT NULL,
  status          TEXT DEFAULT 'pending',      -- pending|delivered|failed
  attempts        INT DEFAULT 0,
  last_attempted_at TIMESTAMPTZ,
  delivered_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
)
```

### 6.2 Candidate Progression State (per job)

```
Candidate's status within a specific job:
PENDING → INVITED → SCHEDULED → IN_PROGRESS → 
  PASSED_ROUND_N → SCHEDULED (round N+1) → ...
  FAILED | ESCALATED | NO_SHOW | WITHDRAWN | CANCELLED
```

Stored as a derived status from the latest interview record for that candidate + job combination. No separate table needed in v1.

### 6.3 Webhook Event Catalogue

All events include a shared envelope:
```json
{
  "event": "<event_type>",
  "krino_version": "1.0",
  "tenant_id": "uuid",
  "timestamp": "ISO8601",
  ...event-specific fields
}
```

**interview.scheduled**
```json
{ "interview_id": "uuid", "candidate_id": "uuid", "job_id": "uuid",
  "round": 1, "scheduled_at": "ISO8601", "meeting_link": "https://..." }
```

**interview.started**
```json
{ "interview_id": "uuid", "candidate_id": "uuid", "job_id": "uuid",
  "round": 1, "started_at": "ISO8601" }
```

**interview.completed**
```json
{ "interview_id": "uuid", "candidate_id": "uuid", "job_id": "uuid",
  "round": 1, "status": "COMPLETED", "duration_seconds": 1420,
  "completed_at": "ISO8601" }
```

**score.ready**
```json
{ "interview_id": "uuid", "candidate_id": "uuid", "job_id": "uuid",
  "round": 1, "overall_score": 74.5, "recommendation": "ADVANCE",
  "scorecard_url": "https://app.krino.ai/interviews/{id}/scorecard" }
```

**interview.failed** (FAILED, INTERRUPTED, CONSENT_DECLINED, NO_SHOW)
```json
{ "interview_id": "uuid", "candidate_id": "uuid", "job_id": "uuid",
  "round": 1, "status": "INTERRUPTED", "reason": "bot_drop_unrecoverable",
  "failed_at": "ISO8601" }
```

**interview.escalated**
```json
{ "interview_id": "uuid", "candidate_id": "uuid", "job_id": "uuid",
  "round": 1, "escalated_at": "ISO8601",
  "partial_transcript_available": true }
```

---

## 7. Scout Agent

### 7.1 Tool Definitions

```python
tools = [
  get_interview(interview_id: str) -> InterviewReport
  list_interviews(
    job_id: str,
    status: str = None,
    round: int = None,
    min_score: float = None,
    max_score: float = None,
    limit: int = 20
  ) -> List[InterviewSummary]
  compare_candidates(interview_ids: List[str]) -> CandidateComparison
  get_job_summary(job_id: str) -> JobInterviewStats
  get_candidate_history(candidate_id: str) -> CandidateRoundHistory
  pattern_analysis(job_id: str) -> PatternReport      # requires ≥5 interviews
  schedule_next_round(interview_id: str) -> SchedulingModalData
  suggest_criteria(job_id: str) -> CriteriaSuggestions  # P2, requires ≥20 interviews
]
```

### 7.2 A2A Interface

```
POST /api/agent/query
Authorization: Bearer <tenant_api_key>
Content-Type: application/json

Request:
{
  "from_agent": "sera",            // informational, for logging only
  "protocol": "a2a-v1",
  "context": {
    "candidate_external_id": "...",
    "job_external_id": "..."
  },
  "query": "What was this candidate's interview score and recommendation?"
}

Response:
{
  "agent": "scout",
  "response_text": "Candidate scored 74.5/100 in Round 1 (recommendation: ADVANCE). Strongest in technical knowledge (82/100). Main gap: communication clarity (61/100).",
  "structured_data": {
    "overall_score": 74.5,
    "recommendation": "ADVANCE",
    "round": 1,
    "interview_id": "uuid"
  }
}

Rate limit: 100 requests/minute per tenant API key.
```

### 7.3 Scout Persona

Scout is professional, warm, and concise. In the interview, Scout uses the company-configured persona name. In the dashboard, Scout is always "Scout." Scout never exposes scorecard data to candidates.

---

## 8. Language Support

| Language | Scope in v1 |
|---|---|
| English | Full: UI, interview language, scorecards, email templates |
| Hindi | Interview language only: Scout can conduct full interviews in Hindi using ElevenLabs Hindi TTS and Claude's native Hindi comprehension. STT (Deepgram via Recall.ai) supports Hindi. Scorecards and the admin UI are generated in English regardless of interview language. Question bank remains English; Scout translates at runtime. Hindi UI deferred to v2. |

---

## 9. Compliance & Privacy

| Area | Requirement | Implementation |
|---|---|---|
| AI disclosure | Candidate must know before interview | Pre-interview page (if visited) + verbal disclosure + consent gate |
| Consent storage | Verbal consent captured and stored | consent_given, consent_at, consent_transcript_segment_id in interviews table |
| Consent-declined data | Audio not retained on decline | recording_url null; only consent exchange transcript retained |
| Recording notice | Google Meet native banner | Enabled by Recall.ai bot presence |
| No auto-rejection | AI is advisory only | SC12: all advance/reject require recruiter action |
| No biometrics | Scoring from transcript only | No video frames analysed |
| Data retention | Recordings expire per tenant config (30–365 days; default 90) | recording_expiry_job in Celery; recording_expires_at in interviews |
| GDPR Art. 17 | Candidate deletion on request | DELETE /api/candidates/{id} removes PII; transcripts anonymised |
| Internal scorecards | Candidates cannot access scores | SC11 enforced at API layer |
| Multi-party consent | See OQ7 — legal review required before pilot | Not resolved in PRD; requires legal opinion |
| AI Act compliance | See OQ8 — human confirmation of all decisions is the primary mitigation | SC12 is the control |

---

## 10. Non-Functional Requirements

| Requirement | Target | How Measured |
|---|---|---|
| Bot join success rate | ≥98% | webhook_events + interviews table; alerted if <95% in 24h |
| Bot join latency | ≤60s from T-0 | started_at - scheduled_at |
| STT→AI response (p95) | ≤4s | Per-turn timing logged in interview log |
| Post-call scoring | ≤5 min | scored_at - ended_at |
| API uptime | ≥99.5% | External uptime monitor |
| Concurrent interviews | ≥50 | Load tested pre-launch |
| Scoring consistency | Std dev <3 pts | Nightly CI test (SC13) |
| Tenant data isolation | Zero cross-tenant leakage | Automated isolation test suite |

---

## 11. Cost Model

### Per-interview breakdown (25-minute video interview)

| Component | Calculation | Cost |
|---|---|---|
| Recall.ai recording | $0.50/hr × 0.42hr | $0.21 |
| Recall.ai transcription (Deepgram) | $0.15/hr × 0.42hr | $0.06 |
| Claude Haiku (conversation, ~50 turns) | 25k tokens ≈ $0.002 | $0.002 |
| Claude Sonnet (scoring, ~8k in + 1k out) | ≈ $0.025 | $0.025 |
| ElevenLabs TTS (~10min AI speech) | $0.015/min × 10 | $0.15 |
| Simli premium avatar (20% of interviews) | $0.05/min × 10min × 20% | $0.10 |
| Fly.io + Redis infra | $15/month / 100 interviews | $0.15 |
| **Total per interview** | | **~$0.70** |

| Volume | Monthly cost |
|---|---|
| 50 interviews/month | ~$35 |
| 100 interviews/month | ~$70 |
| 200 interviews/month | ~$140 |
| 300 interviews/month | ~$210 |

---

## 12. Out of Scope for v1

- Outbound phone calls / phone bridge
- **Automated candidate outreach** — acknowledged GTM liability; target v1.1 (6–8 weeks post-launch)
- ATS integrations beyond RoleSignal
- Candidate-facing scorecard or feedback
- Video facial / emotion analysis
- Zoom, Microsoft Teams (Google Meet only in v1)
- Phase 2: Candidate self-serve portal and verified profiles
- Phase 3: Talent marketplace
- Hindi admin UI (interview language supported; UI deferred to v2)
- SOC 2 compliance (v2, pending enterprise pipeline)
- Real-time coaching for human interviewers
- Mobile app

---

## 13. Future Phases

### Phase 2 — Candidate Portal
Candidates sign up and get AI-verified for a role type. Portable verified profile badge. Phase 2 activates the `candidates.marketplace_visible` and `candidates.verified_at` fields via feature flag + migration that removes the NOT NULL constraint on `tenant_id`.

### Phase 3 — Talent Marketplace
Companies search pre-verified candidates. Subscription / per-hire pricing. Scout + Sera full integration. India/Hindi market as differentiation.

---

## 14. Open Questions

| # | Question | Status | Owner |
|---|---|---|---|
| OQ1 | Which Google Cloud project / service account owns Calendar API access? | Open | Ashutosh |
| OQ2 | **Technical spike: can Recall.ai inject a custom WebGL video stream as bot video feed in Google Meet?** Result gates V2–V3. | Pre-build blocker | Engineering |
| OQ3 | Should Krino share RoleSignal's Firebase project or have its own? | Open | Ashutosh |
| OQ4 | Option B join mechanism | **RESOLVED**: Recall.ai join-by-URL; bot joins as guest "[Persona] (AI Interviewer)"; if waiting room active, recruiter must admit manually (communicated at scheduling) | Engineering |
| OQ5 | Default AI persona name for internal use before tenant customisation | Open | Ashutosh |
| OQ6 | Pre-interview page: hosted by Krino (FastAPI-served HTML) or Lovable frontend? | Open | Design |
| OQ7 | **Legal: Recording basis in multi-party consent jurisdictions (CA, IL, EU).** Verbal consent from candidate alone may be insufficient. Required legal review before any pilot with real candidates. | Pre-pilot legal gate | Legal / Ashutosh |
| OQ8 | **Legal: AI recommendation under EU AI Act or equivalent.** SC12 (human confirmation required) is primary control. Confirm this is sufficient with legal counsel. | Pre-pilot | Legal |
| OQ9 | Who owns interview recording + transcript — tenant or candidate? Affects GDPR portability and Phase 2 design. | Pre-launch | Legal / Product |
| OQ10 | Does Krino need SOC 2 Type II before enterprise sales? If yes, which controls must be in v1 architecture? | Pre-GTM | Ashutosh |
| OQ11 | No-recording mode for candidates who decline but still want to interview? **Currently out of scope** — consent gate is binary. If needed, requires audio pipeline rework. Flag for v1.1 if customer demand. | Deferred to v1.1 | Product |
| OQ12 | Escalation SLA | **RESOLVED**: 15-minute window during business hours (9am–6pm recruiter timezone). No automated fallback. Recruiter must manually contact candidate. Notifications queue for next business day if outside hours. | Product |

---

## Appendix A: Role-Based Access Permissions

| Action | Admin | Recruiter | Hiring Manager | Viewer |
|---|---|---|---|---|
| Create / edit jobs | ✓ | ✓ | — | — |
| Edit evaluation criteria | ✓ | — | — | — |
| Schedule interviews | ✓ | ✓ | — | — |
| View scorecards | ✓ | ✓ | ✓ | ✓ |
| Advance / reject candidates | ✓ | ✓ | ✓ | — |
| Override AI recommendation | ✓ | ✓ | — | — |
| Manage users | ✓ | — | — | — |
| View usage / billing | ✓ | — | — | — |
| Generate API keys | ✓ | — | — | — |
| Configure AI persona | ✓ | — | — | — |

---

*Document prepared for engineering review. V3 addresses all PM review feedback from v1 and v2.*
