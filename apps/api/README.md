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

Open a `psql` shell against the local DB (user/password/db = `salary`):

```bash
psql -h localhost -U salary -d salary_manager
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

## Tests + lint (outside Docker, faster iteration)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

ruff check .
ruff format --check .
pytest -q                                 # /health/db is skipped if DATABASE_URL is unset
```

## Production deploy

GitHub Actions builds the image, pushes it to ECR, and runs the deploy on
the EC2 via SSM:

1. `docker compose -f docker-compose.prod.yml pull` (refresh `:latest`)
2. `docker compose -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head`
3. `docker compose -f docker-compose.prod.yml up -d` (recreates api; db stays running)

`DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, and the Postgres creds
are fetched from SSM Parameter Store on the EC2 itself — they never
appear in CI logs or GitHub secrets. See `.github/workflows/` once the
deploy is wired up.

## Layout

```
apps/api/
  Dockerfile                # multi-stage; single image used by dev and prod
  docker-compose.dev.yml    # local: source-mount + live reload + exposed ports
  docker-compose.prod.yml   # EC2: prebuilt image, env from SSM, restart policy
  requirements.txt          # runtime deps (pinned)
  requirements-dev.txt      # dev/test extras
  .env.example              # documented env vars
  pyproject.toml            # ruff + pytest config
  alembic.ini               # Alembic config (URL injected at runtime)
  alembic/
    env.py                  # reads DATABASE_URL via app.settings
    versions/               # migration files
  app/
    main.py                 # FastAPI app + /health endpoints (more added as we go)
    settings.py             # Pydantic-settings
    db.py                   # SQLAlchemy engine + session dependency
  scripts/                  # one-off scripts (seed, etc.) — added later
  tests/                    # pytest tests — added later
```
