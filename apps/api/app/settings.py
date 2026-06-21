from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration sourced from environment variables.

    Values are resolved in this order (highest wins):
        1. Environment variables (always set in dev compose and prod EC2)
        2. .env file in the cwd (gitignored, opt-in for local dev)
        3. Defaults declared below

    Fields without a default are REQUIRED — the app refuses to boot if
    they are missing. This catches misconfigured deploys at boot rather
    than letting the app run with an unsafe placeholder secret.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Required (no default; misconfig fails loud at boot) -----------
    database_url: str
    jwt_secret: str

    # --- Optional (safe defaults) -------------------------------------
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    # Set the Secure flag on the session cookie. False for local http;
    # set True in prod (where the frontend is over https). Without this
    # the cookie won't be sent cross-origin from the Vercel app.
    cookie_secure: bool = False

    cors_origins: str = "http://localhost:3000"

    anthropic_api_key: str | None = None

    # Seed user — only read by scripts/seed.py.
    hr_user_email: str = "hr@acme.org"
    hr_user_password: str = "acme-demo-2026"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
