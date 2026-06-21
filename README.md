# Salary Manager

Internal salary management web app for ACME's HR team. Replaces Excel-based
compensation tracking for 10,000 employees across the US, UK, and India.

Built as a take-home assessment. See `docs/` for the requirements document,
architecture notes, trade-off discussion, and the AI prompts used while
building the system.

## Repo layout

```
apps/
  api/          FastAPI + Postgres backend
  web/          Next.js (App Router) frontend
docs/
  REQUIREMENTS.md   one-page requirements (goal, scope, non-goals)
  ARCHITECTURE.md   system + data model diagrams
  TRADEOFFS.md      design decisions and what I'd do next
  AI_PROMPTS.md     prompts used with Claude while building
```

## Quick start

```bash
# 1. Backend (Postgres + FastAPI in Docker)
cd apps/api
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml exec api python -m scripts.seed

# 2. Frontend (Next.js on host)
cd ../web
cp .env.example .env.local
npm install
npm run dev
# → http://localhost:3000
```

See `apps/api/README.md` for backend specifics (migrations, tests),
`apps/web/README.md` for frontend specifics (shadcn, auth flow, layout).

## Demo credentials

The seed script creates a single HR user:

- Email: `hr@acme.org`
- Password: see `apps/api/.env.example`

## Live demo

- Frontend: _(Vercel URL — added after deploy)_
- Backend health: _(EC2 URL — added after deploy)_
- Video walkthrough: _(Loom link — added after recording)_
