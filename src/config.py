"""
Configuration management.
Loads settings from environment variables.
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    """Application configuration from environment variables."""

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # YouTube
    YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

    # Discovery mode: "polling" or "websub"
    DISCOVERY_MODE: str = os.getenv("DISCOVERY_MODE", "polling")

    # WebSub settings
    WEBSUB_CALLBACK_URL: str = os.getenv("WEBSUB_CALLBACK_URL", "")  # e.g., https://creatrr.app/webhooks/youtube
    WEBSUB_HUB_URL: str = "https://pubsubhubbub.appspot.com/subscribe"
    WEBSUB_LEASE_SECONDS: int = int(os.getenv("WEBSUB_LEASE_SECONDS", str(10 * 24 * 60 * 60)))  # 10 days default
    WEBSUB_RENEWAL_BUFFER_HOURS: int = 24  # Renew 24 hours before expiry

    # Server settings
    PORT: int = int(os.getenv("PORT", "8080"))

    # Intervals
    POLLING_INTERVAL_MINUTES: int = int(os.getenv("POLLING_INTERVAL_MINUTES", "15"))
    SNAPSHOT_WORKER_INTERVAL_MINUTES: int = int(os.getenv("SNAPSHOT_WORKER_INTERVAL_MINUTES", "5"))
    BASELINE_UPDATE_HOURS: int = int(os.getenv("BASELINE_UPDATE_HOURS", "12"))

    # Snapshot windows (in hours, except 7d and 14d)
    SNAPSHOT_WINDOWS = {
        "0h": 0,
        "1h": 1,
        "6h": 6,
        "12h": 12,
        "24h": 24,
        "48h": 48,
        "7d": 24 * 7,    # 168 hours
        "14d": 24 * 14,  # 336 hours
    }

    # Baseline calculation
    BASELINE_SAMPLE_SIZE: int = 30  # Number of videos to use for median calculation
    BASELINE_MIN_SAMPLE: int = 5    # Minimum videos needed before calculating baseline

    # Retry settings
    MAX_SNAPSHOT_ATTEMPTS: int = 3

    # Trend Detection - OpenRouter
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")  # Cheap and good
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Trend Detection - Rules
    TREND_MIN_CHANNELS: int = 3           # Minimum channels for a topic to be trending
    TREND_MIN_PERFORMANCE: float = 1.5    # Minimum performance ratio (1.5x baseline)
    TREND_WINDOW_DAYS: int = 14           # Look back 14 days for trends

    @classmethod
    def validate(cls) -> list[str]:
        """
        Validate that required config is present.
        Returns list of missing/invalid config keys.
        """
        errors = []

        if not cls.SUPABASE_URL:
            errors.append("SUPABASE_URL is missing")
        if not cls.SUPABASE_KEY:
            errors.append("SUPABASE_KEY is missing")
        if not cls.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY is missing")
        if cls.DISCOVERY_MODE not in ("polling", "websub"):
            errors.append(f"DISCOVERY_MODE must be 'polling' or 'websub', got '{cls.DISCOVERY_MODE}'")

        return errors


# Validate on import (will print warnings but not crash)
_config_errors = Config.validate()
if _config_errors:
    print("Configuration warnings:")
    for error in _config_errors:
        print(f"  - {error}")
