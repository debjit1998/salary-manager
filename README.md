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

- Frontend: <https://salary.dmcodes.org>
- Backend health: <https://salary-api.dmcodes.org/health>

Sign in with the demo credentials above.

## Try it

The most interesting surface is the **Ask AI** drawer on the dashboard —
plain-English questions get answered by Claude routing through a single
`execute_sql` tool with `sqlglot` validation, a read-only Postgres role,
and a 10-second statement timeout. A few prompts that exercise different
parts of the system:

| Question | What it shows |
| --- | --- |
| `Who is the highest-paid engineer in India?` | LLM-generated SQL with native-currency conversion + filter |
| `Average salary by level, in USD` | Aggregate over a JOIN with the FX table |
| `How many people are above their comp band?` | Multi-table join + computed `band_position` |
| `Top 10 earners` | Simple ORDER BY LIMIT — fast path |
| `Headcount by department for full-time employees only` | Filter + group-by |
| `Show salary distribution above $100k USD` | Custom range, exactly the kind of question the SQL escape hatch was added for |

Other surfaces worth poking at:

- **Employees grid** — server-side filter / sort / paginate with URL-synced
  multi-select facets. Click "CSV" to download every row matching the
  current filters.
- **Employee detail** — salary timeline chart + history table; "Record
  raise" + "Edit profile" sheets write through to the API.
