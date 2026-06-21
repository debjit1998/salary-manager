# syntax=docker/dockerfile:1.7

# --- Base: shared by builder and runtime ----------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# --- Builder: install deps into a venv ------------------------------------
FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# --- Runtime: tiny image with just venv + app code ------------------------
FROM base AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app -d /app app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Dev: runtime + pytest/ruff/etc + tests dir --------------------------
# Used by docker-compose.dev.yml so tests can run in the same Python
# environment as the app, no host venv required. Prod uses `runtime`
# above, which excludes this layer.
FROM runtime AS dev
USER root
# `/app` was created by WORKDIR as root in the base stage. Pytest needs
# to write `.pytest_cache/` into it, so make it owned by the app user.
RUN chown app:app /app
# requirements-dev.txt starts with `-r requirements.txt`, so both files
# need to be in the build context for pip to resolve the include.
COPY requirements.txt requirements-dev.txt ./
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements-dev.txt
COPY --chown=app:app pyproject.toml .
COPY --chown=app:app tests ./tests
USER app
