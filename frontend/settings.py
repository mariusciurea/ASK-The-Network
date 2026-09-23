"""Application settings module"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Frontend application settings.

    Every value can be overridden with an environment variable of the same
    name, which is how the Railway deployment is configured.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    APP_NAME: str = "network_agent"
    APP_VERSION: str = "2.3"

    # Backend base URL. On Railway point this at the backend service, ideally
    # over private networking: http://<backend-service>.railway.internal:8082
    BASE_URL: str = "http://localhost:8082"

    # ADK user id used before anyone is logged in.
    USER_ID: str = "user"

    # HTTP budgets. Without them a hung backend keeps a Streamlit worker
    # thread busy forever and the app stops serving other users.
    REQUEST_TIMEOUT_SECONDS: float = Field(default=15.0, gt=0)
    AGENT_TIMEOUT_SECONDS: float = Field(default=180.0, gt=0)
    CONNECT_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    MAX_RETRIES: int = Field(default=2, ge=0, le=5)

    # How many sessions get a "first question" label in the sidebar. Each label
    # costs one extra request, so this bounds the page-load cost.
    SESSION_LABEL_LIMIT: int = Field(default=15, ge=0)
    SESSION_LABEL_LENGTH: int = Field(default=40, ge=10)

    # Artifacts are held in memory while displayed; refuse the huge ones.
    MAX_ARTIFACT_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)
    MAX_ARTIFACT_PREVIEW_ROWS: int = Field(default=500, gt=0)

    # Stream the answer token by token (/run_sse) instead of waiting (/run).
    USE_STREAMING: bool = False

    @field_validator("BASE_URL")
    @classmethod
    def normalise_base_url(cls, value: str) -> str:
        """Drop the trailing slash so URLs never contain a double slash."""

        value = value.strip().rstrip("/")
        if not value:
            raise ValueError("BASE_URL must point at the backend service")
        return value


settings = Settings()
