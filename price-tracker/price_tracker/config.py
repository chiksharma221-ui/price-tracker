"""Central configuration, loaded from environment variables / a .env file.

Nothing here is required to have real values for the project to run in demo
mode -- every integration (MongoDB, Telegram, email) degrades gracefully to a
local/offline fallback if it isn't configured. See README.md for the full
list of variables and what happens when each one is missing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv  # optional dependency, see requirements.txt

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value else default
    except ValueError:
        return default


@dataclass
class Settings:
    # --- Storage -----------------------------------------------------
    mongo_uri: str | None = field(default_factory=lambda: os.getenv("MONGO_URI"))
    mongo_db_name: str = field(default_factory=lambda: os.getenv("MONGO_DB_NAME", "price_tracker"))
    json_store_path: Path = field(default_factory=lambda: DATA_DIR / "store.json")

    # --- Scheduler -----------------------------------------------------
    scrape_interval_minutes: int = field(default_factory=lambda: _int("SCRAPE_INTERVAL_MINUTES", 30))
    request_timeout_seconds: int = field(default_factory=lambda: _int("REQUEST_TIMEOUT_SECONDS", 15))
    min_delay_seconds: float = field(default_factory=lambda: float(os.getenv("MIN_DELAY_SECONDS", "2")))
    max_delay_seconds: float = field(default_factory=lambda: float(os.getenv("MAX_DELAY_SECONDS", "6")))
    max_retries: int = field(default_factory=lambda: _int("MAX_RETRIES", 3))

    # --- Concurrency / queue ------------------------------------------------
    # With REDIS_URL set, checks are enqueued as jobs and run by any number of
    # `rq worker scrape` processes; without it they run in a local thread pool.
    redis_url: str | None = field(default_factory=lambda: os.getenv("REDIS_URL"))
    scrape_concurrency: int = field(default_factory=lambda: _int("SCRAPE_CONCURRENCY", 4))
    # Minimum gap between two requests to the same site, across all workers.
    per_domain_min_interval_seconds: float = field(
        default_factory=lambda: float(os.getenv("PER_DOMAIN_MIN_INTERVAL_SECONDS", "5")))

    # --- API -----------------------------------------------------------------
    # Optional shared secret required on write endpoints (the Chrome extension
    # sends it as X-API-Token). Leave unset for local use.
    api_token: str | None = field(default_factory=lambda: os.getenv("API_TOKEN"))
    cors_origins: str = field(default_factory=lambda: os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))

    # --- Notifications ---------------------------------------------------
    telegram_bot_token: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))

    smtp_host: str | None = field(default_factory=lambda: os.getenv("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: _int("SMTP_PORT", 587))
    smtp_user: str | None = field(default_factory=lambda: os.getenv("SMTP_USER"))
    smtp_password: str | None = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))
    alert_email_to: str | None = field(default_factory=lambda: os.getenv("ALERT_EMAIL_TO"))

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.alert_email_to)

    @property
    def redis_configured(self) -> bool:
        return bool(self.redis_url)

    @property
    def mongo_configured(self) -> bool:
        return bool(self.mongo_uri)


settings = Settings()
