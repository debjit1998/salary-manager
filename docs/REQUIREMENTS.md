# Requirements — Salary Manager

## Goal

Give ACME's HR manager a web-based tool to manage compensation for ~10,000
employees across the US, UK, and India, and to answer ad-hoc questions
about how the org pays its people — replacing the current Excel-based
workflow.

## User & persona

A single **HR Manager** owns and operates the tool. They view and edit
employee compensation, record raises and promotions, and answer questions
from leadership and managers (e.g. "what's the average L4 engineer salary
in the UK?", "who hasn't had a raise in the last 18 months?", "how many
people are below band?"). They are not a developer; the tool must be
self-explanatory.

## In scope

1. **Authentication** — single HR user, email + bcrypt-hashed password,
   JWT session cookie.
2. **Employee directory** — browse 10k employees with server-side
   pagination, sorting, filtering (department, country, level,
   employment type), and search by name or email.
3. **Employee detail** — view profile, salary timeline, equity grants,
   manager, comp-band position (below / within / above). Edit profile,
   add a new salary change event or equity grant.
4. **Effective-dated salary history** — every compensation change is a
   row in `salary_changes` with an effective date and a reason
   (hire / raise / promo / adjustment). The current salary is always the
   latest row.
5. **Equity grants** — append-only `equity_grants` table holding
   `(employee_id, grant_date, shares)`. An employee's current share
   count is the sum of their grants. Surfaced on the employee detail
   page and queryable via the analytics + NL layer.
6. **Compensation bands** — per (level, country), with min / mid / max
   in native currency. Drives the comp-ratio analytics.
7. **Employment type** — every employee is one of `full_time`,
   `part_time`, or `contractor`. Used as a directory filter and as an
   analytics dimension.
8. **Multi-currency** — salaries stored in native currency (USD / GBP /
   INR). A fixed FX ratio table normalises to USD for analytics.
9. **Structured analytics dashboard** — six panels covering headcount,
   average / median salary by dimension, salary distribution,
   below-band count, raises in the last 12 months, headcount change YoY.
10. **Natural-language query** — chat-style input that translates the
    HR manager's question into a single read-only SELECT against the
    HR schema, with the result rendered as a table. Implemented as
    Anthropic Claude tool-use with a single `execute_sql` tool guarded
    by sqlglot validation, a read-only Postgres role, and a 10-second
    `statement_timeout`. The rationale for SQL-only vs. a hybrid
    structured-tool design is in `docs/TRADEOFFS.md`.

## Out of scope (and why)

| Cut | Reason |
| --- | --- |
| Payroll execution, tax withholding, benefits | Different problem domain — this app records compensation, doesn't disburse it. |
| Multi-tenant orgs, multiple HR users, role hierarchies | The persona is explicitly a single HR manager. Adding RBAC eats time without showing more product judgment. |
| Bulk CSV import / export | Adds tedious UI without exercising new engineering skill. Listed as a follow-up. |
| Live FX feeds | A fixed FX ratio table is sufficient and deterministic; live feeds add an external dependency for no user value at this scale. |
| Mobile responsiveness | This is a desktop power-tool. Optimising for small screens dilutes the UX. |
| Audit log UI | The `salary_changes` table **is** the audit trail; surfaced via the timeline on the employee detail page. |
| Email / Slack notifications, approval workflows | Both presuppose multiple users / roles. |
| 2FA, SSO, password reset flows | Single user, single password baked into the seed; reset is a re-seed. |

## Success criteria

- HR manager can find any of the 10k employees in under 2 seconds via search.
- Structured analytics queries return in under 500 ms on the seeded
  dataset.
- The NL query feature handles at least 8 of 10 representative HR
  questions correctly (test fixture included).
- All endpoints behind auth; secrets never appear in the frontend bundle.
- Fully deployed (FastAPI on AWS EC2, Next.js on Vercel) and reachable
  by a public URL.

## Assumptions called out

- The seeded org has 8 departments, 7 levels (L1–L7), and is distributed
  ~60% US / ~25% IN / ~15% UK.
- FX rates are fixed at app boot — documented in `docs/ARCHITECTURE.md`.
- Salary changes are write-only (no edit / delete of past events) —
  consistent with how real comp history works; corrections are new
  rows with reason = `adjustment`.
