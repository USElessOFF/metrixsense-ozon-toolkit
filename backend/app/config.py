"""Конфигурация приложения из окружения"""

from __future__ import annotations

import os
import secrets as secret_utils
from pathlib import Path

import structlog
from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


def find_project_root(marker: str = "requirements.txt") -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker).exists() or (parent.parent / marker).exists():
            return parent.parent if (parent.parent / marker).exists() else parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()
ENV_PATH = os.getenv("METRIXSENSE_ENV_FILE", str(PROJECT_ROOT / ".env"))
load_dotenv(ENV_PATH)


def _load_or_create_secret_key(data_dir: Path) -> str:
    env_value = os.getenv("SECRET_KEY", "").strip()
    if env_value:
        return env_value
    key_file = data_dir / ".secret_key"
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        key = secret_utils.token_hex(32)
        data_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="utf-8")
        key_file.chmod(0o600)
        logger.info("[MetrixSense] Generated new SECRET_KEY", path=str(key_file))
        return key
    except OSError:
        logger.warning("[MetrixSense] Could not persist SECRET_KEY, using ephemeral")
        return secret_utils.token_hex(32)


class Settings(BaseSettings):

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True

    CORS_ORIGINS: str = (
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    DB_PATH: str = str(PROJECT_ROOT / "data" / "metrixsense.db")
    DATA_DIR: str = str(PROJECT_ROOT / "data")

    DATABASE_URL: str = ""

    OZON_SELLER_CLIENT_ID: str = ""
    OZON_SELLER_API_KEY: str = ""

    OZON_PERFORMANCE_CLIENT_ID: str = ""
    OZON_PERFORMANCE_SECRET: str = ""

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = str(PROJECT_ROOT / "logs")
    ENVIRONMENT: str = "development"

    SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 72

    DEFAULT_USERNAME: str = "metrixsense"
    DEFAULT_PASSWORD: str = "metrixsense"

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _finalize(self) -> Settings:
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.LOG_DIR, exist_ok=True)
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite+aiosqlite:///{self.DB_PATH}"  # type: ignore[union-attr]
        if not self.SECRET_KEY:
            self.SECRET_KEY = _load_or_create_secret_key(Path(self.DATA_DIR))
        return self


settings = Settings()
