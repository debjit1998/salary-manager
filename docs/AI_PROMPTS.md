# AI prompts used while building

Two halves:

- **(a) Prompts shipped in the product** — the NL-query system prompt
  and tool schema that go out to Anthropic on every `/nl-query` call.
- **(b) Prompts I gave Claude Code while building** — how AI was used
  to accelerate engineering work without replacing the judgment calls.

---

## (a) Prompts shipped in the product

### The Anthropic call

Every `/nl-query` request becomes one (or, on retry, two) calls to
`client.messages.create` with:

| Field | Source | Cached? |
| --- | --- | --- |
| `model` | `claude-opus-4-7` (`apps/api/app/src/nl/client.py`) | — |
| `max_tokens` | 2048 | — |
| `system[0]` (instructions) | the `INSTRUCTIONS` constant — see below | No |
| `system[1]` (schema block) | auto-derived from Postgres + YAML hints | **Yes** (`cache_control: ephemeral`) |
| `tools` | `[execute_sql]` (one tool, see schema below) | — |
| `messages` | `[{user: "Today is YYYY-MM-DD. Question: …"}]`, plus on retry the assistant's previous `tool_use` + a `tool_result` with `is_error=true` | — |

The date and the user's question are kept in the user message, **not**
in the system prompt, so the cached schema block hits the prompt cache
on every request. Cache TTL is ~5 minutes; cache hits show up as
`cache_read_input_tokens > 0` in the response usage. We expose that on
`/nl-query`'s response under `meta.cache_read_tokens`.

`temperature` is deliberately **not** sent — Opus 4.7 deprecated it.
Determinism is bounded instead by the HARD RULES in the prompt and the
one-step retry loop in `llm_agent.run_agent`.

### The instructions block (verbatim)

This is the `INSTRUCTIONS` constant in `apps/api/app/src/nl/client.py`,
reproduced here verbatim so the prompt history lives in the repo, not
just in code:

> You are a query assistant for ACME's HR analytics tool. The user is
> an HR manager.
>
> Use the `execute_sql` tool to answer the user's question with a single
> read-only SELECT. The query is parsed and validated, runs against a
> read-only Postgres role with a 10-second timeout, and is force-LIMITed
> to 1000 rows. There is no other tool — every question is answered by
> writing SQL.
>
> **HARD RULES** (the backend's sqlglot guard rejects violations —
> wasted round-trip):
>
> - Emit ONE SELECT. No DML (INSERT/UPDATE/DELETE/MERGE), no DDL
>   (CREATE/ALTER/DROP/TRUNCATE), no SET / RESET / SET LOCAL / GRANT /
>   REVOKE / BEGIN / COMMIT / ROLLBACK / SAVEPOINT / LOCK / COPY. Role
>   and timeout are managed by the backend — don't touch them.
> - `PERCENTILE_CONT` always returns double precision (not numeric), so
>   `ROUND(PERCENTILE_CONT(…), 2)` fails. Cast first:
>   `ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)::numeric, 2)`.
>   Same trap for any other aggregate that returns float.
>
> **WRITING GOOD SQL:**
>
> - Use the table + view definitions in the schema below; pay attention
>   to NOTE lines (e.g. "prefer the `employees_current_salary` view over
>   raw `salary_changes`").
> - The REFERENCE DATA blocks under departments, levels, and currencies
>   give you the integer ids and FX rates. Use them directly — don't
>   subquery to look up an id by name when you already have the mapping.
> - Default `status = 'active'` unless the user explicitly asks about
>   terminated employees.
> - Default amounts to USD via `amount_usd` from
>   `employees_current_salary`. If the user asks for a specific currency
>   ("in pounds", "in INR"), convert: `amount_in_target = amount_usd *
>   ratio_to_usd` where `ratio_to_usd` comes from the `currencies` table.
> - Aggregations: `COUNT(*)`, `AVG`, `percentile_cont(0.5) WITHIN GROUP`
>   for median, etc. `GROUP BY` when the user asks for a breakdown.
> - For "top N" questions, `ORDER BY amount_usd DESC LIMIT N`.
> - For salary thresholds ("over $X", "above £Y"), use a `WHERE` clause
>   on `amount_usd` (or the converted amount).
> - For below/within/above band, JOIN `comp_bands` on `(level_id, country)`
>   and compare `ecs.amount` to `cb.band_min/band_max` in the row's
>   native currency.
>
> If you genuinely cannot answer with the data available, say so briefly
> in plain text — do NOT invent values.

### How the schema block is built

The second system text — the one with `cache_control: ephemeral` — is
auto-derived on first request and held in memory for the process
lifetime. Three steps:

1. **Introspect Postgres** via `information_schema.columns` +
   `key_column_usage` (in `nl/schema_prompt.py::introspect`). Returns
   every table, column, type, and foreign-key relationship — the live
   DB is the structural source of truth.
2. **Merge `apps/api/app/src/nl/schema_hints.yaml`** — small,
   hand-maintained file of semantics introspection can't infer:
   - "this table is append-only"
   - "prefer this view over that table"
   - enum values for `text`-typed columns (`country`, `employment_type`,
     `reason`)
   - notes on column meaning (`amount` is annual gross base in native
     currency, not monthly / not total comp)
3. **Render** the merged result into a compact text block. Includes
   REFERENCE DATA listings — every department, level, currency with
   their integer ids — so Claude doesn't have to subquery to look up
   `id_for_dept('Engineering')`.

A startup validator (`validate_hints`) refuses to boot the app if any
table/column referenced in the YAML no longer exists in the DB. Stops
"I dropped a column but forgot the YAML" from silently rotting the
prompt.

### Tool schema (the only tool)

```jsonc
{
  "name": "execute_sql",
  "description": "Run a read-only SELECT against the HR database to answer the user's question. The query is parsed and validated (single SELECT, no DML/DDL, no dangerous functions), executed against a read-only Postgres role with a 10-second timeout and a forced LIMIT 1000. Use the schema and reference data inlined in the system prompt to write accurate joins.",
  "input_schema": {
    "type": "object",
    "properties": {
      "sql": {
        "type": "string",
        "description": "A single SELECT statement, no semicolons, no DML/DDL. Reference the schema below for column names and the REFERENCE DATA blocks for department/level/currency ids."
      }
    },
    "required": ["sql"]
  }
}
```

Defined in `apps/api/app/src/nl/tools.py`. Why one tool, not seven
structured analytics wrappers — see `docs/TRADEOFFS.md` ("SQL-only NL
query").

### The retry loop

When the first tool dispatch fails (sqlglot guard rejection OR Postgres
error), the agent appends two messages to the conversation and calls
the API again exactly once:

```jsonc
// 1. The assistant's previous response (with the tool_use block)
{ "role": "assistant", "content": [...response.content from attempt 1...] }

// 2. A tool_result reporting the failure
{
  "role": "user",
  "content": [{
    "type": "tool_result",
    "tool_use_id": "<the id from the failed tool_use>",
    "content": "tool failed: <truncated error from sql_guard or Postgres>",
    "is_error": true
  }]
}
```

Claude reads the error and emits a corrected SELECT on attempt 2.
After two attempts, the final outcome — success or error — is what
the user sees. Hard cap at 1 retry; no unbounded agentic loop.

Implementation: `apps/api/app/src/nl/llm_agent.py::run_agent`.

---

## (b) Prompts I gave Claude Code while building

I used Claude Code (Opus 4.7) for the entire build. The pattern was
**plan → ask back → implement small chunks → review → commit** rather
than "one prompt, build me the app." Things worth recording:

### Planning sessions (before code)

Before any code, I worked through the product + architecture with
Claude in a structured back-and-forth (~30 min of clarifying questions
each on requirements, data model, NL feature design, deployment shape).
Key decisions reached:

- **Effective-dated salary history with comp bands** over a
  current-salary-only column, because temporal questions ("who got a
  raise this quarter?") and comp-ratio questions ("who's above band?")
  are the questions HR actually asks. The view
  `employees_current_salary` keeps "current salary" cheap without
  denormalising.
- **SQL-only NL** after a brief detour through a hybrid (7 structured
  analytics tools + SQL escape hatch). The hybrid routed
  "close-enough" tools when the question needed a custom filter. The
  trade-off is documented in `TRADEOFFS.md`.
- **Native-currency storage with a fixed FX table**, not USD-only and
  not a live FX feed. The view computes `amount_usd` at query time.
- **Postgres on the EC2** rather than RDS for the take-home (RDS is
  the right answer in production; flagged in `TRADEOFFS.md`).

### Iterative prompts during build (representative)

These are paraphrased from the actual sessions. Each one was followed
by review and incremental commits — not "ship whatever the model
returned":

- _"Scaffold the Alembic migration for the schema we just sketched.
  No autogenerate — I want raw `op.execute()` SQL so the migration
  reads like a SQL file in review."_
- _"The NL prompt needs to know about `employees_current_salary` as a
  view, not the underlying `salary_changes` table. Add a YAML hints
  file that I can hand-maintain for these "prefer-this-over-that"
  facts, and merge it into the auto-derived schema block."_
- _"Add a sqlglot AST validator that allows exactly one SELECT, no
  DML/DDL, no dangerous functions (pg_sleep, pg_read_file…), and
  forces a LIMIT 1000. Reject everything else."_
- _"For the employees grid, the user wants URL-synced multi-select
  filters with shareable links. Axios sends arrays as `?k[]=a&k[]=b`
  by default, FastAPI wants `?k=a&k=b`. Fix both ends."_
- _"After deploy, the cookie wasn't sticking — middleware on
  `salary.dmcodes.org` couldn't see the session set by
  `salary-api.dmcodes.org`. Walk me through the options. What's the
  CSRF posture for each?"_ (Led to the same-parent-domain choice.)
- _"The NL call is masking the real Postgres error with a misleading
  RESET ROLE failure. Why?"_ (Led to the savepoint isolation fix in
  `tools._execute_sql`.)
- _"Opus 4.7 returns 400 on `temperature`. What's the right way to
  pin determinism without it?"_ (Led to dropping `temperature`, keeping
  HARD RULES in the prompt, and adding the retry loop.)
- _"Refactor the NL endpoint: extract the agent loop from `router.py`
  into `llm_agent.py`. Router becomes thin glue. Add one new test for
  the retry path."_

### What I deliberately kept out of AI's hands

- **Schema design.** I drafted the data model myself first, then asked
  the model to critique. The "effective-dated salary history" decision
  was mine; the model surfaced the comp-band table as a useful
  addition.
- **Trade-off documentation.** `TRADEOFFS.md` is my reasoning, not
  Claude's — the model can help phrase, but the actual judgment calls
  (RDS vs containerised Postgres, GitHub Secrets vs SSM Parameter
  Store, etc.) are mine.
- **Test coverage decisions.** What to test, and at what layer (unit
  vs integration), was my call. The model wrote test bodies once I
  said which cases to cover.
- **The cookie / CORS / DNS architecture.** Specifically the choice of
  `Domain=dmcodes.org` over `SameSite=None`. I'd seen this trap
  before in production; the model didn't suggest it unprompted.

### Why I recorded both halves

(a) shows what the deployed product is doing with AI on every request
— this is part of the system surface area, not a development crutch.
(b) shows that the model accelerated the build but didn't make the
decisions — the engineering judgment is mine, the work to express it
is shared.
