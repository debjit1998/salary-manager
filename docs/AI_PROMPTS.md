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

### Analytics tool schemas

_Filled in once the tool layer is implemented. Each of the 7 tools is
defined with a JSON Schema for the LLM and a Python function on the
backend. Both are reproduced here side by side so the mapping is clear._

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
- **Hybrid tool-use + SQL fallback** for NL, rather than tools-only or
  raw-SQL-only, to keep the common path safe and deterministic while
  not dead-ending on the long tail.
- **Native-currency storage with a fixed FX ratio table**, rather than
  USD-only or a live FX feed — see `TRADEOFFS.md`.

### Build prompts

_Added as the project progresses. The aim is to show how AI was used
to accelerate, not to replace, engineering judgment — e.g. "scaffold the
Alembic migration file" rather than "build me the whole app."_
