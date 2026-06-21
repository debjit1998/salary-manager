# AI prompts used while building

This file documents (a) the AI prompts that ship as part of the running
product — primarily the NL-query system prompt and tool schemas — and
(b) the prompts I gave to Claude Code while developing the system, so
the assessor can see how AI was used intentionally.

## (a) Prompts shipped in the product

### NL-query system prompt

_Filled in once the NL endpoint is implemented. Will be reproduced
verbatim here, including the cached schema description that Claude sees
on every request._

### Tool schema

The NL endpoint exposes exactly one tool — `execute_sql` — defined in
`apps/api/app/src/nl/tools.py`. Claude generates a single SELECT; the
backend validates it via `sql_guard.validate_select` and runs it
against the read-only `nl_readonly` Postgres role with a 10-second
`statement_timeout`. See `docs/TRADEOFFS.md` ("SQL-only NL query")
for the reasoning behind this design vs. the structured-tool hybrid
we originally shipped.

## (b) Prompts I gave Claude Code while building

_Recorded as the build progresses. The repo's commit history shows
the evolution; this file is the curated "intentional use of AI" view._

### Planning session

The product plan (data model, NL query design, milestones) was developed
through a structured back-and-forth with Claude Opus 4.7 over ~30 min
of clarifying questions before any code was written. Highlights of the
decisions reached, and why:

- **Effective-dated salary history + bands** over current-salary-only,
  because it lets the NL query feature answer temporal and comp-ratio
  questions — which are the questions HR actually asks.
- **SQL-only NL** (after a brief detour through a structured-tool
  hybrid). The hybrid kept routing to "close-enough" tools when
  questions needed custom filters; routing everything through SQL
  with strong guard rails (sqlglot validation, read-only role,
  timeout, forced LIMIT) traded that error class for a uniform path.
  See `docs/TRADEOFFS.md` for the full reasoning.
- **Native-currency storage with a fixed FX ratio table**, rather than
  USD-only or a live FX feed — see `TRADEOFFS.md`.

### Build prompts

_Added as the project progresses. The aim is to show how AI was used
to accelerate, not to replace, engineering judgment — e.g. "scaffold the
Alembic migration file" rather than "build me the whole app."_
