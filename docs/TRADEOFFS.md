# Design trade-offs

Decisions I made deliberately, what they cost, and what I'd change with
more time. Filled in as I build; this file is intentionally a
work-in-progress and gets a final pass at the end.

## SQLAlchemy Core instead of an ORM

**Decision:** Use SQLAlchemy Core (and Alembic with raw `op.execute(...)`
migrations) rather than an ORM like SQLModel or Tortoise.

**Why:** Most of this app's value lives in analytics queries — joins,
window functions, aggregates over `salary_changes` to derive current
salary. ORMs make the simple cases easy and the analytics cases painful.
With Core I write SQL directly, see the query plan, and migrations stay
explicit.

**Cost:** A bit more boilerplate for CRUD endpoints. Acceptable —
the CRUD surface here is small.

## Postgres co-located on the EC2 instead of RDS

**Decision:** Run Postgres in the same Docker Compose as FastAPI on a
single EC2 (`t4g.small`, 2 GB RAM, ~$14/mo).

**Why:** Fits a 10k-row dataset comfortably; halves deployment moving
parts; no IAM / VPC / subnet plumbing to think about; mirrors the deploy
pattern from a prior project of mine. Money matters too — RDS minimum
is ~$15/mo, EC2 t3.small is ~$15/mo total.

**Cost:** No managed backups, no automatic failover. For a production
multi-user system I'd move to RDS or Aurora Serverless.

## GitHub Secrets + OIDC + SSM Run-Command (not SSM Parameter Store)

**Decision:** Production secrets (`DATABASE_URL`, `ANTHROPIC_API_KEY`,
`JWT_SECRET`, `HR_USER_PASSWORD`, the Postgres creds) live in GitHub
Encrypted Secrets. The deploy workflow authenticates to AWS via OIDC,
builds + pushes the image to ECR, and runs the deploy on the EC2 via
SSM Run-Command — passing the secrets through as command parameters
that the EC2 turns into env vars for `docker compose up`.

**Why:** For the take-home scope this matches the actual security
requirements with markedly less setup than SSM Parameter Store. The
real differences:

|                                   | GH Secrets + OIDC | SSM Parameter Store |
| --------------------------------- | ----------------- | ------------------- |
| Setup time                        | 5 min             | 20–30 min           |
| Cost                              | $0                | $0 (Standard tier)  |
| Rotation without redeploy         | re-paste in UI    | `put-parameter`     |
| Audit log (per-fetch)             | GH Actions logs   | CloudTrail          |
| Secrets exposed to forks?         | No (GH disables)  | N/A                 |
| Secret transits GH runner memory? | Yes               | No                  |
| Public repo safe?                 | Yes               | Yes                 |

The "secret transits GH runner memory" property is the only meaningful
downside. For this app (small blast radius, single user, $5 of
Anthropic credit), it doesn't outweigh the simpler setup.

**Safety practices applied regardless:**
- GH Actions pinned to commit SHAs (not floating tags) to defend
  against compromised third-party actions.
- AWS access via OIDC (`role-to-assume`); no static AWS keys in GH
  Secrets.
- `pull_request_target` is not used for any workflow that touches
  secrets — only `push` to `main` and `workflow_dispatch`.
- Deploy scripts never `echo` or transform secret values.
- The seed script reads `HR_USER_PASSWORD` once, bcrypts it, then
  the plaintext is gone — the DB only ever holds the hash.

**What I'd switch to for a real product:** SSM Parameter Store, mainly
for the rotation-without-redeploy and CloudTrail-per-fetch properties.
Listed in the "what I'd add next" section.

## Single HR user, no role hierarchy

**Decision:** One seeded user, JWT cookie session, no signup / reset.

**Why:** The requirements doc explicitly names a single HR manager
persona. Adding multi-user / RBAC / invitations consumes a day of work
that doesn't differentiate the submission. Mentioned as a follow-up.

**Cost:** Not realistic for a real B2B product, but in scope of the
take-home it's the right cut.

## NL schema description: auto-derived from Postgres + hand-maintained hints

**Decision:** The schema block in the NL-query system prompt is not
hand-written. It's assembled at app boot from (a) `information_schema`
introspection of the live DB and (b) a small `schema_hints.yaml` with
semantic annotations that introspection can't infer (append-only
tables, prefer-this-view guidance, valid enum values for text columns).

**Why:** A hand-written prompt is the obvious first version, but it's
a second source of truth that drifts from the schema. Every migration
becomes "did anyone remember to update the prompt?" — exactly the kind
of long-tail bug that's painful to debug because the LLM fails
plausibly rather than loudly. Auto-deriving the structural part removes
drift entirely; the YAML only changes when **semantics** change, which
is rare.

**Cost:** One Python module to introspect, one YAML file to maintain,
one startup validator that refuses to boot if the YAML references a
gone column. Total: ~150 lines.

**What I'm not doing (and why):** Schema linking / RAG — embedding each
table's description and retrieving the top-K relevant tables per
question. At 9 tables the whole schema fits comfortably in the prompt;
this matters past ~30 tables. Listed as a follow-up.

## Hybrid NL query (tools first, SQL fallback)

**Decision:** Claude picks from 7 parameterised analytics tools; if it
can't, it falls back to generating a `SELECT` against a read-only
Postgres role behind a sqlglot guard.

**Why:**

- The tool layer covers the common HR questions deterministically and
  is trivially unit-testable.
- A pure tool-only design dead-ends on the long tail; a pure
  raw-SQL-from-LLM design is harder to test and reason about, and slower
  to iterate on.
- The hybrid keeps the common path fast and safe and gives the long
  tail a controlled escape hatch.

**Cost:** More code paths to maintain and test. Mitigated by keeping
the fallback narrow (single SELECT, read-only role, 10 s timeout, forced
LIMIT) and logging every NL query for review.

## Native-currency-only storage; USD computed at query time

**Decision:** Monetary rows (`salary_changes`, `comp_bands`) store the
native amount + `currency_code` only. The USD-equivalent is computed
at query time by JOINing `currencies` and dividing by `ratio_to_usd`.
The `employees_current_salary` view encapsulates the JOIN so the rest
of the app doesn't repeat it.

**Why:** Payroll truth lives in native currency — that's what's on the
employment contract. Storing only the native amount keeps the schema
simple, never drifts if the FX table moves, and avoids any
write-time / backfill machinery. At 10k rows the extra JOIN on
analytics queries is negligible (the `currencies` table is three rows).

**Considered alternatives:**

- _USD only:_ historical truth is lost as soon as FX moves. The detail
  page would show a slightly-different GBP number every time the rate
  changes, even though the employee's actual contract hasn't moved.
- _Dual storage (native + denormalised `*_usd`):_ buys faster aggregates
  at the cost of one denormalised column per money table and a
  write-time computation in the app layer. At this scale not worth the
  schema noise.

## Fixed FX ratio table instead of live feed

**Decision:** Static `currencies.ratio_to_usd` column.

**Why:** Deterministic behaviour, no external dependency in the demo,
no API quotas to manage. The numbers are documented and easy to change
in a migration.

**Cost:** Not suitable for a real comp tool; would integrate ECB / Fixer
on a daily refresh in production.

## Append-only `salary_changes`

**Decision:** No update or delete on past comp events; corrections are
new rows with `reason = 'adjustment'`.

**Why:** Matches how real comp history works (you don't rewrite the
past), gives a free audit trail, and simplifies the "current salary" view.

**Cost:** Slightly more rows in the table. Trivial at 10k employees.

## What I'd add next (not done in the take-home)

- **NL feature:** schema-linking via embeddings (RAG) for when the
  schema grows past ~30 tables; CI-gated eval suite with accuracy
  thresholds; per-tool contract versioning
- Bulk CSV import / export
- Multi-user with RBAC + invitations
- Approval workflow for raises above a configurable threshold
- Live FX with a daily refresh job
- Move Postgres to RDS, add point-in-time recovery
- Move secrets from GitHub Secrets to AWS SSM Parameter Store (rotation
  without redeploy, CloudTrail per-fetch audit log, no transit through
  GitHub Actions runner memory)
- Slack notification on every salary change for the manager's manager
- Two-factor auth, SSO
- Per-employee notes / comments
- "Compare comp ratio of this hire against their cohort" view
