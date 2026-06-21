# salary-manager-api

FastAPI backend for the salary manager assessment. Postgres + Docker Compose
for local dev; the same Dockerfile ships to AWS ECR for prod.

## Quick start (local dev)

```bash
cd apps/api
docker compose -f docker-compose.dev.yml up
```

When you see `Application startup complete`, hit the health checks:

```bash
curl localhost:8000/health        # {"status":"ok"}
curl localhost:8000/health/db     # {"db":"up","result":{"ok":1}}
```

Open a `psql` shell against the local DB (host port defaults to 5432;
override with `POSTGRES_HOST_PORT=5433` in `apps/api/.env` if you have
another Postgres running locally; user / password / db all default to
`salary`):

```bash
psql -h localhost -p 5432 -U salary -d salary_manager
# password prompt: salary
```

Or skip the host client entirely:

```bash
docker compose -f docker-compose.dev.yml exec db psql -U salary -d salary_manager
```

### Optional: override defaults with `.env`

The compose file uses `${VAR:-default}` everywhere, so it boots with no
setup. To override anything — most commonly to enable the NL-query
feature, which needs a real Anthropic key — copy the example file and
edit:

```bash
cp .env.example .env
# edit .env, fill in ANTHROPIC_API_KEY=sk-ant-...
docker compose -f docker-compose.dev.yml up
```

`apps/api/.env` is gitignored. Docker Compose auto-loads it from the
directory you run compose in. The `/nl-query` endpoint returns
`503 NL feature disabled` until a real key is set.

## Migrations (Alembic, raw SQL)

We use Alembic with raw `op.execute("CREATE TABLE …")` migrations — no ORM
models, no autogenerate. This keeps SQL explicit and makes the analytics-
heavy queries that follow easy to reason about.

```bash
# Apply all pending migrations
docker compose -f docker-compose.dev.yml exec api alembic upgrade head

# Create a new migration file (writes to alembic/versions/)
docker compose -f docker-compose.dev.yml exec api alembic revision -m "add foo table"

# Revert the most recent migration
docker compose -f docker-compose.dev.yml exec api alembic downgrade -1
```

## Tests

### Layout

```
tests/
├── conftest.py                ← top-level: just sets harmless env defaults
├── unit/                      ← pure-python, no DB, no FastAPI
│   ├── test_auth_primitives.py
│   ├── test_employee_helpers.py
│   └── test_analytics_helpers.py
└── integration/               ← real Postgres (in the dev compose stack)
    ├── conftest.py            ← per-session: creates salary_manager_test DB,
    │                            drops + re-migrates schema, per-test SAVEPOINT
    ├── test_auth_endpoints.py
    ├── test_employees_endpoints.py
    └── test_analytics_endpoints.py
```

### Run inside the dev container (recommended — no host setup needed)

The dev image (`target: dev` in the Dockerfile) layers pytest, ruff,
and the test directory on top of the runtime image, so the api
container has everything it needs. The container's `TEST_DATABASE_URL`
points at `db:5432` (the docker network hostname) automatically.

```bash
docker compose -f docker-compose.dev.yml up -d

docker compose -f docker-compose.dev.yml exec api pytest tests/unit
docker compose -f docker-compose.dev.yml exec api pytest tests/integration
docker compose -f docker-compose.dev.yml exec api pytest               # both

# Lint
docker compose -f docker-compose.dev.yml exec api ruff check .
docker compose -f docker-compose.dev.yml exec api ruff format --check .
```

The `tests/` directory is bind-mounted, so editing a test file on the
host shows up immediately in the next pytest run — no rebuild.

### Or run from the host (faster startup, needs a venv)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/unit                                    # nothing else needed
pytest tests/integration                             # needs `docker compose up -d`
```

The host-side conftest defaults `TEST_DATABASE_URL` to
`localhost:5432/salary_manager_test`. If you've set `POSTGRES_HOST_PORT`
to a non-default port:

```bash
TEST_DATABASE_URL=postgresql+psycopg://salary:salary@localhost:5433/salary_manager_test \
  pytest tests/integration
```

### Why two databases?

Integration tests use a **dedicated** `salary_manager_test` database
on the same Postgres instance so the seeded 10k-employee dev DB stays
untouched. Schema is dropped and re-migrated at the start of every
pytest session; per-test transactions are rolled back, so the suite
leaves no residue.

## Production deploy

GitHub Actions builds the image, pushes it to ECR, and runs the deploy
on the EC2 via SSM Run-Command. Secrets live in **GitHub Encrypted
Secrets** and are passed to the EC2 inline in the Run-Command call;
AWS auth uses **OIDC** (no static AWS keys in GH Secrets).

The deploy steps on the EC2:

1. `docker compose -f docker-compose.prod.yml pull`            # refresh image
2. `docker compose -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head`
3. `docker compose -f docker-compose.prod.yml run --rm --no-deps api python -m scripts.seed`  # idempotent
4. `docker compose -f docker-compose.prod.yml up -d`           # recreate api

`DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `HR_USER_PASSWORD`,
and the Postgres creds never appear in the source, in the image, in CI
logs (GH masks them), or in the host filesystem. They live encrypted in
GH Secrets, decrypted briefly inside the GH Actions runner, transit
encrypted to the EC2 via SSM Run-Command, and only ever exist as
process env on the running container. See `.github/workflows/` once
the deploy is wired up. The trade-off vs. SSM Parameter Store is in
`docs/TRADEOFFS.md`.

## Layout

```
apps/api/
  Dockerfile                # multi-stage: base → builder → runtime (prod) → dev (tests)
  docker-compose.dev.yml    # local: source-mount, live reload, exposed ports
  docker-compose.prod.yml   # EC2: prebuilt image, env from GH Secrets via SSM
  requirements.txt          # runtime deps (pinned)
  requirements-dev.txt      # dev/test extras (pytest, ruff, httpx)
  .env.example              # documented env vars
  pyproject.toml            # ruff + pytest config
  alembic.ini               # Alembic config (URL injected at runtime)
  alembic/
    env.py                  # reads DATABASE_URL via app.settings
    versions/
      0001_initial_schema.py
      0002_nl_readonly_role.py
  app/
    main.py                 # FastAPI app, /health, healthcheck log filter
    settings.py             # Pydantic-settings (DATABASE_URL + JWT_SECRET required)
    db.py                   # SQLAlchemy engine + get_session dependency
    src/
      router.py             # top-level aggregator that main.py mounts
      common/
        auth.py             # bcrypt + JWT helpers, get_current_user dependency
      user/
        router.py           # POST /auth/login, /auth/logout, GET /auth/me
      employee/
        router.py           # GET/PATCH /employees, +/salary-changes, +/equity-grants
        queries.py          # SQL + parse_sort + build_filters (multi-select aware)
        schemas.py          # Pydantic in/out models for the employee surface
      analytics/
        router.py           # /analytics/{headcount-by, avg-salary-by, …} (7 tools)
        queries.py          # 7 typed analytics functions (reused by the NL endpoint)
        schemas.py
      lookup/
        router.py           # GET /lookups → {departments, levels, currencies}
  scripts/
    seed.py                 # idempotent seed: 1 HR user + 10k employees + history
  tests/
    conftest.py             # top-level: harmless env defaults for collection
    unit/
      test_auth_primitives.py
      test_employee_helpers.py
      test_analytics_helpers.py
    integration/
      conftest.py           # creates salary_manager_test, migrates, SAVEPOINT
      test_auth_endpoints.py
      test_employees_endpoints.py
      test_analytics_endpoints.py
```

## API surface (auth required on everything except `/health*`)

```
POST   /auth/login                            sets the session cookie
POST   /auth/logout                           clears the session cookie
GET    /auth/me                               current HR user

GET    /employees?…                           paginated + sorted + filtered + searched
GET    /employees/{id}                        profile + history + grants + manager
PATCH  /employees/{id}                        update profile (dept/level/manager/type/status)
POST   /employees/{id}/salary-changes         append-only salary history
POST   /employees/{id}/equity-grants          append-only grants

GET    /lookups                               departments + levels + currencies

GET    /analytics/headcount-by?dimension=…
GET    /analytics/avg-salary-by?dimension=…   includes median (percentile_cont)
GET    /analytics/salary-distribution         fixed USD buckets
GET    /analytics/comp-ratio-vs-band          summary + out-of-band list
POST   /analytics/top-earners                 body: { n, filters }
POST   /analytics/raises-in-period            body: { start, end, filters }
POST   /analytics/headcount-change            body: { start, end, dimension }
```

**Multi-select filters** — every list/analytics filter param accepts
repeated keys: `?country=US&country=UK&band_position=below`. FastAPI
parses this into `list[str] | None`; SQL uses `column = ANY(:values)`.
