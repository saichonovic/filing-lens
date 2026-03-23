from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/filinglens",
    )
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    sec_user_agent: str = os.getenv(
        "SEC_USER_AGENT",
        "FilingLens/0.1 research@example.com",
    )


settings = Settings()
