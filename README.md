# Krino

AI-powered video interview platform. Scout conducts live, adaptive video interviews via Google Meet, scores candidates against consistent role-specific criteria, and delivers detailed scorecards to recruiters.

## Structure

```
Krino/
├── backend/      FastAPI microservice (Python 3.12)
├── frontend/     React + Vite + ShadCN (TypeScript)
└── docs/         PRD and design specifications
```

## Stack

**Backend:** FastAPI · PostgreSQL (Neon) · Celery + Redis · Recall.ai · Claude (Haiku + Sonnet) · ElevenLabs · Google Calendar API · Firebase Auth · Fly.io

**Frontend:** React · Vite · TypeScript · ShadCN/UI · Tailwind CSS

## Docs

- [PRD v3](docs/prd-v3.md) — full product requirements
- [PRD v4 Addendum](docs/prd-v4-addendum.md) — final decisions and SOC 2 controls
