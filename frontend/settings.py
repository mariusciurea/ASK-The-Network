"""Application settings module"""

import uuid
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Frontend application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    APP_NAME: str = "network_agent"
    APP_VERSION: str = "2.2"
    USER_ID: str = "user"
    BASE_URL: str = "http://localhost:8082"
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    LOG_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent / "logs")
    SESSION_DB: str = Field(
        default_factory=lambda: str(Path(__file__).resolve().parent.parent / "session.db")
    )

    @staticmethod
    def get_session_id():
        return str(uuid.uuid4())

settings = Settings()
