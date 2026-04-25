from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_base_url: str = os.getenv(
        "NVIDIA_BASE_URL",
        "https://integrate.api.nvidia.com/v1",
    )
    nvidia_model: str = os.getenv(
        "NVIDIA_MODEL",
        "meta/llama-3.1-70b-instruct",
    )
    bot_username: str = os.getenv("BOT_USERNAME", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    memory_db_path: str = os.getenv("MEMORY_DB_PATH", str(BASE_DIR / "data" / "memory.db"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
    port: int = int(os.getenv("PORT", "8080"))

    def require_telegram(self) -> None:
        if not self.telegram_bot_token:
            raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")

    def require_nvidia(self) -> None:
        if not self.nvidia_api_key:
            raise ValueError("Missing NVIDIA_API_KEY in .env")


settings = Settings()
