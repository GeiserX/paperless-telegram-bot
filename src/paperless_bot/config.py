"""
Configuration management for Paperless Telegram Bot.
Loads and validates settings from environment variables.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration settings loaded from environment variables."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # =====================================================================
        # TELEGRAM BOT
        # =====================================================================
        self.telegram_bot_token = self._get_required_env("TELEGRAM_BOT_TOKEN")

        # Comma-separated Telegram user IDs allowed to use the bot
        # If empty, anyone can use it (not recommended)
        allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        self.telegram_allowed_users = self._parse_id_set(allowed_users_str)

        # =====================================================================
        # PAPERLESS-NGX
        # =====================================================================
        self.paperless_url = self._get_required_env("PAPERLESS_URL")
        self.paperless_token = self._get_required_env("PAPERLESS_TOKEN")

        # =====================================================================
        # BEHAVIOR
        # =====================================================================
        self.max_search_results = int(os.getenv("MAX_SEARCH_RESULTS", "10"))

        # =====================================================================
        # LOGGING
        # =====================================================================
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        if log_level == "WARN":
            log_level = "WARNING"
        self.log_level = getattr(logging, log_level, logging.INFO)

        # =====================================================================
        # HEALTH CHECK
        # =====================================================================
        self.health_port = int(os.getenv("HEALTH_PORT", "8080"))

        logger.info("Configuration loaded successfully")
        if self.telegram_allowed_users:
            logger.info(f"Bot restricted to {len(self.telegram_allowed_users)} allowed user(s)")
        else:
            logger.warning("TELEGRAM_ALLOWED_USERS is empty — bot is open to anyone!")

    def _get_required_env(self, key: str) -> str:
        """Get a required environment variable."""
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Required environment variable '{key}' is not set. "
                "Please set it in your .env file or container environment."
            )
        return value

    @staticmethod
    def _parse_id_set(id_str: str) -> set[int]:
        """Parse comma-separated ID string into a set of integers."""
        if not id_str or not id_str.strip():
            return set()
        return {int(uid.strip()) for uid in id_str.split(",") if uid.strip()}


def setup_logging(config: Config):
    """Configure logging for the application."""
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
