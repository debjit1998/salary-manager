"""Top-level test config — runs before any test module is imported.

Sets harmless defaults for the two REQUIRED settings (DATABASE_URL,
JWT_SECRET) so that `from app.something import …` works during test
collection — `app.settings.Settings()` would otherwise raise.

Integration tests override DATABASE_URL with the real test-DB URL in
`tests/integration/conftest.py`. Unit tests never touch the DB, so the
unreachable default is fine for them — if a unit test accidentally
tries to connect, it'll fail fast and visibly.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@unreachable.invalid:0/test",
)
os.environ.setdefault("JWT_SECRET", "unit-test-secret-do-not-use-in-prod")
