"""
Application Configuration

This module defines the Settings class, which reads all application
configuration from environment variables (or a .env file in the project root).
Using Pydantic's BaseSettings ensures that:

  1. Every required variable is present at startup — a missing required
     variable raises a ValidationError before the app serves any requests.
  2. Types are coerced and validated automatically (e.g. BCRYPT_ROUNDS is
     always an int, CORS_ORIGINS is always a list).
  3. Secrets never need to be hard-coded in source files.

Environment variables (all names are case-sensitive):

  DATABASE_URL                 — PostgreSQL connection string.
                                 Format: postgresql://<user>:<pass>@<host>:<port>/<db>
                                 Required in production; defaults to a local dev DB.

  JWT_SECRET_KEY               — HMAC secret for signing access tokens.
                                 Must be at least 32 random characters.
                                 Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"

  JWT_REFRESH_SECRET_KEY       — Separate HMAC secret for refresh tokens.
                                 Using a distinct key means a compromised access
                                 token secret does not expose refresh tokens.

  ALGORITHM                    — JWT signing algorithm.  HS256 (HMAC-SHA256)
                                 is the default and is sufficient for this app.

  ACCESS_TOKEN_EXPIRE_MINUTES  — Lifetime of an access token in minutes.
                                 Short-lived tokens limit the exposure window
                                 if a token is stolen.  Default: 30 minutes.

  REFRESH_TOKEN_EXPIRE_DAYS    — Lifetime of a refresh token in days.
                                 Longer-lived so users stay logged in across
                                 sessions without re-entering credentials.
                                 Default: 7 days.

  BCRYPT_ROUNDS                — bcrypt work factor (cost parameter).
                                 Higher values make brute-force attacks slower
                                 but also slow down login.  Default: 12.
                                 Use 4 in CI/CD to keep test runs fast.

  CORS_ORIGINS                 — List of allowed CORS origins.
                                 Default ["*"] allows all origins (fine for
                                 development; restrict in production).

  REDIS_URL                    — Redis connection URL for token blacklisting.
                                 Optional — if not set, blacklisting is skipped
                                 (revoked tokens remain valid until expiry).

Usage:
  Import the cached getter wherever settings are needed:

      from app.core.config import get_settings
      settings = get_settings()
      print(settings.DATABASE_URL)

  The module-level `settings` singleton is provided for convenience in
  modules that are always imported (e.g. database.py, jwt.py).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """
    Pydantic BaseSettings model for application configuration.

    Each class attribute corresponds to an environment variable of the same
    name.  The defaults below are suitable for local development only —
    production deployments must override DATABASE_URL, both JWT secret keys,
    and optionally REDIS_URL via environment variables or a .env file.
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    # Connection string for the primary PostgreSQL database.
    # Override via DATABASE_URL env var in all non-local environments.
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fastapi_db"

    # ------------------------------------------------------------------
    # JWT / Token authentication
    # ------------------------------------------------------------------
    # Secret key used to sign and verify access tokens.
    # CHANGE THIS in production — the default value is not secure.
    JWT_SECRET_KEY: str = "your-super-secret-key-change-this-in-production"

    # Separate secret for refresh tokens.  Using a different key ensures
    # that a leaked access-token secret cannot be used to forge refresh tokens.
    JWT_REFRESH_SECRET_KEY: str = "your-refresh-secret-key-change-this-in-production"

    # HMAC algorithm for JWT signing.  HS256 uses a symmetric key (same key
    # to sign and verify), which is appropriate for a single-service app.
    ALGORITHM: str = "HS256"

    # How long before an access token expires (in minutes).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # How long before a refresh token expires (in days).
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    # bcrypt work factor.  Each increment roughly doubles the hashing time.
    # 12 is the recommended production default as of 2024.
    BCRYPT_ROUNDS: int = 12

    # Allowed CORS origins.  ["*"] permits all origins — safe for development
    # but should be restricted to known frontend domains in production.
    CORS_ORIGINS: List[str] = ["*"]

    # ------------------------------------------------------------------
    # Redis (optional)
    # ------------------------------------------------------------------
    # Redis URL used for JWT blacklisting (logout invalidation).
    # If not set or unreachable, the blacklist feature is silently skipped
    # and tokens remain valid until their natural expiry.
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    class Config:
        # Load values from a .env file in the project root when present.
        # Variables defined in the environment always take precedence.
        env_file = ".env"
        case_sensitive = True


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

# Module-level singleton for modules that import settings at load time
# (e.g. database.py, jwt.py).  Safe to use because Settings is immutable
# after construction.
settings = Settings()


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    The @lru_cache decorator ensures that only one Settings object is ever
    constructed per interpreter process, regardless of how many modules call
    get_settings().  This avoids redundant .env file reads and validation
    overhead on every request.

    Use this function as a FastAPI dependency when you want the cache to be
    easily overridable in tests:

        app.dependency_overrides[get_settings] = lambda: Settings(DATABASE_URL="...")

    Returns:
        The application-wide Settings instance.
    """
    return Settings()
