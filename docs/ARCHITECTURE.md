# Architecture

## System overview

```
        ┌──────────────────┐                  ┌─────────────────────────────┐
        │   Vercel         │   HTTPS / JSON   │   AWS EC2 (single instance) │
        │   Next.js (App   │ ───────────────▶ │  ┌──────────────────────┐   │
        │   Router)        │  cookie session  │  │  FastAPI (Docker)    │   │
        │   shadcn/ui      │ ◀─────────────── │  └──────┬───────────────┘   │
        └──────────────────┘                  │         │ asyncpg            │
                                              │  ┌──────▼───────────────┐   │
                                              │  │  Postgres 16 (Docker)│   │
                                              │  └──────────────────────┘   │
                                              └─────────┬───────────────────┘
                                                        │ HTTPS
                                                        ▼
                                              api.anthropic.com  (NL query)
```

- **Frontend** is a Next.js (App Router) app deployed on Vercel. It holds
  no secrets; the Anthropic API key never leaves the backend.
- **Backend** is a FastAPI service deployed to a single EC2 via Docker
  Compose (mirrors a prior production deploy of mine for fast turnaround).
  Postgres is co-located on the same EC2 — fine for a 10k-row dataset
  and a take-home; production would split it out to RDS.
- **Instance choice: `t4g.small`** (ARM, 2 vCPU burst, 2 GB RAM) with
  16 GB gp3 EBS and an Elastic IP, in `us-east-1`. ~$14/mo on-demand.
  Sized for the workload (Postgres + FastAPI + Docker overhead want
  ~700 MB RAM at idle, leaves headroom for query bursts and image
  pulls during deploys). `t4g.micro` would save $6/mo but leaves
  Postgres uncomfortably close to the OOM line. Reasoning written up
  in `TRADEOFFS.md`.
- **Secrets** (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `JWT_SECRET`) live in
  **AWS SSM Parameter Store** and are fetched on the EC2 itself. They
  never appear in CI logs or GitHub secrets.
- **Migrations** are Alembic with raw `op.execute(...)` SQL — no ORM
  models, no autogenerate. Run on every deploy via
  `docker compose run --rm --no-deps api alembic upgrade head`.

## Data model

```
                ┌────────────┐         ┌────────────┐
                │ departments│         │   levels   │
                └─────┬──────┘         └──────┬─────┘
                      │                       │
                      │      ┌──────────────────┐   │
                      └─────▶│    employees     │◀──┘
                             ├──────────────────┤
                             │ id               │
                             │ name             │
                             │ email            │
                             │ country          │  (US / UK / IN)
                             │ dept_id          │
                             │ level_id         │
                             │ manager_id       │  (self-ref)
                             │ employment_type  │  (full_time/part_time/contractor)
                             │ hire_date        │
                             │ status           │
                             └─────┬────────────┘
                                   │ 1..N
                  ┌────────────────┼────────────────┐
                  ▼                                 ▼
       ┌────────────────────┐              ┌────────────────────┐
       │  salary_changes    │              │   equity_grants    │
       ├────────────────────┤              ├────────────────────┤
       │ id                 │              │ id                 │
       │ employee_id        │              │ employee_id        │
       │ effective_date     │              │ grant_date         │
       │ amount  (native)   │              │ shares (int)       │
       │ currency_code      │ ─▶ currencies│ created_by         │
       │ reason (enum)      │              │ created_at         │
       │ note               │              └────────────────────┘
       │ created_by         │
       └────────────────────┘

                          ┌────────────────────┐
                          │ employees_current  │   VIEW
                          │ _salary            │   = latest salary_changes per employee
                          └────────────────────┘

      ┌────────────┐                           ┌────────────────────────┐
      │ currencies │                           │       comp_bands       │
      ├────────────┤                           ├────────────────────────┤
      │ code (PK)  │                           │ level_id               │
      │ name       │                           │ country                │
      │ ratio_to_  │                           │ currency_code          │
      │  usd       │                           │ band_min      (native) │
      │            │                           │ band_mid      (native) │
      └────────────┘                           │ band_max      (native) │
                                               └────────────────────────┘

                          ┌────────────────────┐
                          │  nl_query_log      │   audit / observability
                          ├────────────────────┤
                          │ question           │
                          │ tool_picked        │  (nullable; null when SQL fallback)
                          │ sql_emitted        │  (nullable; null when tool was used)
                          │ latency_ms         │
                          │ input_tokens       │
                          │ output_tokens      │
                          │ created_at         │
                          └────────────────────┘
```

### Notes on the model

- **Current salary is a view**, not a column. Single source of truth;
  no denormalisation to drift.
- **`salary_changes.amount` is the annual gross base salary** in the
  employee's native currency, _not_ monthly, hourly, or total
  comp — e.g. US `150000.00` USD, UK `85000.00` GBP, India `2500000.00`
  INR. Bonuses and equity are deliberately excluded from this number;
  equity gets its own table. This keeps "salary" unambiguous in the
  analytics layer and in the NL prompt's schema description.
- **Monetary values are stored in native currency only.** USD figures
  are computed at query time by JOINing `currencies` and dividing by
  `ratio_to_usd`. The `employees_current_salary` view bakes this JOIN
  in so application code rarely has to think about it. The trade-off
  (cleaner schema vs. an extra JOIN per analytics query) is documented
  in `TRADEOFFS.md`.
- `salary_changes` is **append-only**. Corrections are new rows with
  `reason = 'adjustment'`. This makes the table itself the audit log.
- **`equity_grants.shares` is the grant delta**, not a running total.
  Each row is one grant event; an employee's current share count is
  `SUM(shares)` over their rows. We deliberately don't model vesting,
  exercises, refreshes, or sales — each row is a flat grant. Storing
  deltas (rather than a single `shares` column on `employees`) is what
  makes time-based questions answerable — _"how many shares granted in
  2026?"_, _"average L5 grant size?"_ — which is exactly what the NL
  feature is for.
- `equity_grants` is **append-only**, same reason as `salary_changes`.
- `comp_bands` are keyed by `(level_id, country)`. A US L4 has different
  band figures than a UK L4.
- `currencies.ratio_to_usd` is the fixed exchange table, seeded with
  mid-market rates captured on **2026-06-21**:

  | code | name           | ratio_to_usd |
  | ---- | -------------- | ------------ |
  | USD  | US Dollar      | 1.000000     |
  | GBP  | Pound Sterling | 0.755800     |
  | INR  | Indian Rupee   | 94.460000    |

  Interpretation: `ratio_to_usd` is "how much of this currency equals
  1 USD." So `amount_usd = amount / ratio_to_usd`. Used at query time
  by the `employees_current_salary` view and the analytics layer. No
  live FX dependency; if rates need refreshing it's a one-line
  migration.
- `employment_type` is one of `full_time | part_time | contractor`.
  Useful both as a filter on the directory and as an analytics
  dimension ("avg salary of full-timers vs contractors at L4").

## NL query request flow

```
  Browser           FastAPI             Anthropic              Postgres
    │                  │                    │                      │
    │  POST /nl-query  │                    │                      │
    │  { question }    │                    │                      │
    ├─────────────────▶│                    │                      │
    │                  │  messages.create   │                      │
    │                  │  + cached system   │                      │
    │                  │  + 7 tools         │                      │
    │                  ├───────────────────▶│                      │
    │                  │   tool_use OR text │                      │
    │                  │◀───────────────────┤                      │
    │                  │                    │                      │
    │                  │  if tool_use:      │                      │
    │                  │    parameterised   │                      │
    │                  │    SQL via Core    ├─────────────────────▶│
    │                  │                    │                      │
    │                  │  else (no tool):   │                      │
    │                  │    sqlglot guard   │                      │
    │                  │    + read-only DB  │                      │
    │                  │    role + 3s       │                      │
    │                  │    statement_      │                      │
    │                  │    timeout         ├─────────────────────▶│
    │                  │                    │                      │
    │                  │  log to            │                      │
    │                  │  nl_query_log      ├─────────────────────▶│
    │                  │                    │                      │
    │   { rows, meta } │                    │                      │
    │◀─────────────────┤                    │                      │
```

### Why hybrid (tool-use first, SQL fallback)

- **Tool-use covers 80%+ of HR questions** with deterministic,
  unit-tested SQL. Zero injection surface — the LLM picks a tool and
  fills typed args; the SQL is hand-written.
- **The SQL fallback prevents "I don't know" dead-ends** on the long tail.
  Guarded by sqlglot (single `SELECT`, no DML, no DDL), a read-only DB
  role (no write grants regardless of what SQL is generated), and a
  3-second `statement_timeout`.
- **The trade-off** is documented in `TRADEOFFS.md`.

### How Claude knows the schema (auto-derived + hints)

The system prompt's schema block is not hand-written. At app boot we:

1. **Introspect Postgres** via `information_schema.columns` +
   `key_column_usage` to discover every table, column, type, and
   foreign-key relationship. This is the structural source of truth —
   we ask the live DB rather than maintaining a duplicate description.
2. **Merge with `apps/api/app/nl/schema_hints.yaml`** — a small,
   hand-maintained file of semantic annotations introspection can't
   infer: "this table is append-only", "prefer this view over that
   table", valid enum values for `text`-typed columns (`reason`,
   `country`, `employment_type`), etc.
3. **Render** the merged result into a compact text block and cache it
   in memory until the next app restart.

```
deploy → app starts → introspect_postgres()
                       merge schema_hints.yaml
                       render → cached SCHEMA_PROMPT
                       │
                       ▼
every /nl-query → Anthropic call with SCHEMA_PROMPT in the
                  prompt-cached system message (cheap).
```

A YAML-vs-schema validator runs at startup and refuses to boot if the
hints reference a table or column that no longer exists. This catches
"I dropped a column but forgot the YAML" before the app accepts
traffic.

**What this buys:**

- A migration that adds a column flows into the prompt on the next
  deploy with **zero hand-editing**. The schema description can't drift
  from the schema.
- Hand-editing is only needed when **semantics** change — which is rare
  compared to structural changes.
- Reviewable: a migration diff + a YAML diff (if any) tells the whole
  story.

**What this is not (and why that's OK at take-home scale):**

- We don't do schema linking / RAG-based table selection. With 9 tables
  the whole schema fits in ~700 tokens and dumping all of it is fine.
  Past ~30 tables we'd embed table descriptions and retrieve the top-K
  per question — flagged in `TRADEOFFS.md` as a follow-up.
- There's no CI-gated eval suite with accuracy thresholds — we ship a
  small `tests/nl_eval.py` with representative questions, runnable
  manually, but breakage doesn't block deploy.

## Test strategy

- **Backend (pytest):** analytics tools individually with a seeded test
  DB; auth happy-path + wrong-password + expired-token; NL routing
  with Anthropic mocked; sqlglot guard with known-bad inputs.
- **Frontend (Vitest + RTL):** login form, employees table, NL chat
  rendering for the two response shapes (rows vs. chart).
- **End-to-end:** one Playwright smoke that logs in, lists employees,
  opens detail, and runs an NL query.

## Performance considerations

- All employee-list queries use a single composite index on
  `(department_id, country, level_id)` plus a trigram index on
  `lower(name)` for the search box. Target p95 < 100 ms at 10k rows.
- Analytics queries hit indexed columns and the `employees_current_
  salary` view. Target < 500 ms.
- NL tool-use end-to-end target: < 2.5 s p95 (Anthropic call dominates;
  prompt caching keeps token cost low).
