"""
Default evaluation criteria and question banks per role type.
Matches PRD §4.5 defaults exactly.
"""

_BACKEND_CRITERIA = [
    {
        "id": "tech_depth", "name": "Technical Knowledge & Depth", "weight": 30,
        "description": "Systems, data structures, CS fundamentals appropriate to seniority",
        "scoring_rubric": "90-100: Expert; can teach. 70-89: Strong; production-ready. 50-69: Solid; some gaps. <50: Concerning gaps for role.",
        "is_hard_filter": False,
    },
    {
        "id": "problem_solving", "name": "Problem-Solving Approach", "weight": 20,
        "description": "Structures problems clearly, considers edge cases, iterates under constraints",
        "scoring_rubric": "High: systematic, handles unknowns well. Mid: structured but misses edge cases. Low: reactive, not structured.",
        "is_hard_filter": False,
    },
    {
        "id": "relevant_exp", "name": "Relevant Experience", "weight": 20,
        "description": "Experience aligns with JD; examples are specific and verifiable",
        "scoring_rubric": "High: specific, quantified examples directly relevant. Mid: relevant but vague. Low: limited or tangential.",
        "is_hard_filter": False,
    },
    {
        "id": "communication", "name": "Communication Clarity", "weight": 15,
        "description": "Explains technical concepts clearly; concise but not terse",
        "scoring_rubric": "High: clear, structured, no jargon overload. Mid: mostly clear. Low: hard to follow.",
        "is_hard_filter": False,
    },
    {
        "id": "motivation", "name": "Motivation & Culture Fit", "weight": 15,
        "description": "Genuine interest in role; values alignment; quality of questions asked",
        "scoring_rubric": "High: researched company, asks insightful questions. Mid: generic interest. Low: disengaged or misaligned.",
        "is_hard_filter": False,
    },
    {
        "id": "hf_location", "name": "Location / Work Authorisation", "weight": 0,
        "description": "Hard filter: authorised to work in required location",
        "scoring_rubric": "PASS/FAIL only",
        "is_hard_filter": True,
    },
    {
        "id": "hf_notice", "name": "Notice Period", "weight": 0,
        "description": "Hard filter: can join within required timeframe",
        "scoring_rubric": "PASS/FAIL only",
        "is_hard_filter": True,
    },
]

_FRONTEND_CRITERIA = [
    {
        "id": "ui_craft", "name": "UI Craft & Attention to Detail", "weight": 30,
        "description": "CSS, accessibility, performance, cross-browser considerations",
        "scoring_rubric": "High: thinks in layers (performance, a11y, visual). Mid: functional but skips detail. Low: surface only.",
        "is_hard_filter": False,
    },
    {
        "id": "js_ts", "name": "JavaScript / TypeScript Depth", "weight": 25,
        "description": "Async patterns, closures, type system, bundling",
        "scoring_rubric": "High: nuanced, idiomatic. Mid: solid but gaps. Low: surface knowledge.",
        "is_hard_filter": False,
    },
    {
        "id": "component_arch", "name": "Component Architecture", "weight": 20,
        "description": "State management, reusability, separation of concerns",
        "scoring_rubric": "High: discusses trade-offs (prop drilling vs context vs external). Mid: uses patterns but can't explain why. Low: no clear architecture thinking.",
        "is_hard_filter": False,
    },
    {
        "id": "communication", "name": "Communication Clarity", "weight": 15,
        "description": "Explains technical decisions; can discuss design/product trade-offs",
        "scoring_rubric": "Standard rubric",
        "is_hard_filter": False,
    },
    {
        "id": "motivation", "name": "Motivation & Culture Fit", "weight": 10,
        "description": "Interest in product quality; design sensibility",
        "scoring_rubric": "Standard rubric",
        "is_hard_filter": False,
    },
    {
        "id": "hf_location", "name": "Location / Work Authorisation", "weight": 0,
        "description": "Hard filter", "scoring_rubric": "PASS/FAIL", "is_hard_filter": True,
    },
]

_AI_ML_CRITERIA = [
    {
        "id": "ml_fundamentals", "name": "ML Fundamentals", "weight": 30,
        "description": "Model selection, training, evaluation, overfitting, feature engineering",
        "scoring_rubric": "High: intuitive and rigorous. Mid: knows methods, can't explain theory. Low: surface familiarity.",
        "is_hard_filter": False,
    },
    {
        "id": "systems", "name": "MLOps / Systems Thinking", "weight": 25,
        "description": "Training pipelines, serving latency, monitoring, data drift",
        "scoring_rubric": "High: has shipped models to prod. Mid: understands concepts. Low: no prod experience.",
        "is_hard_filter": False,
    },
    {
        "id": "problem_solving", "name": "Problem Framing", "weight": 20,
        "description": "Turns ambiguous business problems into ML problem statements",
        "scoring_rubric": "High: structured decomposition. Mid: jumps to models. Low: unclear.",
        "is_hard_filter": False,
    },
    {
        "id": "communication", "name": "Communication Clarity", "weight": 15,
        "description": "Explains ML concepts to non-technical stakeholders",
        "scoring_rubric": "Standard rubric", "is_hard_filter": False,
    },
    {
        "id": "motivation", "name": "Motivation & Culture Fit", "weight": 10,
        "description": "Genuine interest in applied AI; research vs product balance",
        "scoring_rubric": "Standard rubric", "is_hard_filter": False,
    },
    {
        "id": "hf_location", "name": "Location / Work Authorisation", "weight": 0,
        "description": "Hard filter", "scoring_rubric": "PASS/FAIL", "is_hard_filter": True,
    },
]

_FULLSTACK_CRITERIA = [
    {
        "id": "backend_depth", "name": "Backend Depth", "weight": 25,
        "description": "APIs, databases, caching, queuing, auth",
        "scoring_rubric": "Standard technical rubric", "is_hard_filter": False,
    },
    {
        "id": "frontend_depth", "name": "Frontend Depth", "weight": 25,
        "description": "Component architecture, state management, performance",
        "scoring_rubric": "Standard technical rubric", "is_hard_filter": False,
    },
    {
        "id": "system_design", "name": "System Design", "weight": 20,
        "description": "End-to-end thinking across stack; scalability trade-offs",
        "scoring_rubric": "High: fluent across stack, makes principled trade-offs. Mid: stronger in one area. Low: silo thinking.",
        "is_hard_filter": False,
    },
    {
        "id": "communication", "name": "Communication Clarity", "weight": 15,
        "description": "Standard", "scoring_rubric": "Standard", "is_hard_filter": False,
    },
    {
        "id": "motivation", "name": "Motivation & Culture Fit", "weight": 15,
        "description": "Standard", "scoring_rubric": "Standard", "is_hard_filter": False,
    },
    {
        "id": "hf_location", "name": "Location / Work Authorisation", "weight": 0,
        "description": "Hard filter", "scoring_rubric": "PASS/FAIL", "is_hard_filter": True,
    },
]

_CRITERIA_BY_ROLE = {
    "backend": _BACKEND_CRITERIA,
    "frontend": _FRONTEND_CRITERIA,
    "ai_ml": _AI_ML_CRITERIA,
    "fullstack": _FULLSTACK_CRITERIA,
}

_BACKEND_QUESTIONS = [
    {"id": "hf_loc", "text": "Are you authorised to work in [location] and able to join within [notice period]?",
     "criterion_id": "hf_location", "required": True, "probe_depth": "surface", "is_hard_filter": True},
    {"id": "q1", "text": "Tell me about a time you had to scale a system under production pressure. What was the challenge and how did you approach it?",
     "criterion_id": "tech_depth", "required": True, "probe_depth": "probe-deeply"},
    {"id": "q2", "text": "Walk me through how you'd design a URL shortener that handles 100 million requests per day.",
     "criterion_id": "problem_solving", "required": True, "probe_depth": "probe-once"},
    {"id": "q3", "text": "What's the most complex database schema you've designed? What trade-offs did you make?",
     "criterion_id": "tech_depth", "required": True, "probe_depth": "probe-once"},
    {"id": "q4", "text": "Describe a production incident you were responsible for resolving. What caused it and how did you fix it?",
     "criterion_id": "relevant_exp", "required": True, "probe_depth": "probe-deeply"},
    {"id": "q5", "text": "How do you approach API design — what principles guide your decisions?",
     "criterion_id": "tech_depth", "required": True, "probe_depth": "probe-once"},
    {"id": "q6", "text": "Tell me about a time you had to advocate for a technical decision that others pushed back on.",
     "criterion_id": "communication", "required": True, "probe_depth": "probe-once"},
    {"id": "q7", "text": "What draws you to this role specifically?",
     "criterion_id": "motivation", "required": True, "probe_depth": "surface"},
    {"id": "q8", "text": "How do you stay current with backend engineering developments?",
     "criterion_id": "motivation", "required": False, "probe_depth": "surface"},
    {"id": "q9", "text": "Describe your experience with distributed systems — consistency, availability, partition tolerance trade-offs.",
     "criterion_id": "tech_depth", "required": False, "probe_depth": "probe-deeply"},
    {"id": "q10", "text": "What's your approach to testing — what do you test and what do you leave untested?",
     "criterion_id": "tech_depth", "required": False, "probe_depth": "probe-once"},
]


def get_default_criteria(role_type: str) -> list[dict]:
    return _CRITERIA_BY_ROLE.get(role_type, _BACKEND_CRITERIA)


def get_default_questions(role_type: str) -> list[dict]:
    # For now return backend questions for all types; expand per role in v1.1
    return _BACKEND_QUESTIONS
