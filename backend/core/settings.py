"""Settings"""

from logging import getLogger
from pathlib import Path
from pydantic_settings import BaseSettings


# Defaults that are fine locally and must never reach production.
DEFAULT_JWT_SECRET_KEY = "change-me-in-production"
DEFAULT_DB_URL = "mysql+pymysql://root:Changeme_123@localhost:3306/radio_network_data"


class Settings(BaseSettings):
    """Application settings"""

    # dirs
    WORKING_DIR: Path = Path(__file__).resolve().parent.parent.parent
    AGENT_DIR: str = str(WORKING_DIR / "backend/network_agent")
    SESSION_SERVICE_URI:str = f"sqlite:///{str(WORKING_DIR / "sessions.db")}"
    DATA_DIR: Path = WORKING_DIR / "backend/data"

    #db
    # Local default only. In production set DB_URL (and SESSION_SERVICE_URI)
    # from the environment - see check_production_readiness below.
    DB_URL: str = DEFAULT_DB_URL

    # model
    MODEL_NAME: str = "gemini-3.5-flash"
    GOOGLE_API_KEY: str = ""
    # Text-to-SQL needs the same question to produce the same query.
    MODEL_TEMPERATURE: float = 0.0

    # MCP
    MCP_URL: str = "http://localhost:34/mcp"

    # rows handed back to the model; the rest is stored as an artifact
    MAX_ROWS: int = 20
    # hard LIMIT injected into every generated query
    MAX_SQL_LIMIT: int = 500
    # how long the distinct column values stay cached
    VALUE_CACHE_TTL_SECONDS: int = 600

    # auth
    JWT_SECRET_KEY: str = DEFAULT_JWT_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # deployment
    ENVIRONMENT: str = "local"
    # Browser origins allowed to call the API. "*" is fine locally, but in
    # production it should list the frontend URL.
    ALLOWED_ORIGINS: str = "*"
    # The ADK dev UI has no authentication of its own.
    ENABLE_DEV_UI: bool = True
    # Level for chatty third-party loggers (google_adk, httpx, ...). Set it to
    # WARNING in production: one line per internal step made Railway drop logs.
    LIBRARY_LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in ("production", "prod")

    @property
    def allowed_origins_list(self) -> list[str]:
        """CORS origins as a list, from a comma-separated env variable."""

        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def check_production_readiness(self) -> None:
        """Refuse to start a production deployment with unsafe defaults.

        A forgotten JWT_SECRET_KEY means anyone who has read this repository can
        mint a valid token for any user, so this fails loudly at startup instead
        of silently serving an open API.

        Raises:
            RuntimeError: A required production setting is still at its default.
        """

        if not self.is_production:
            return

        problems = []
        if self.JWT_SECRET_KEY == DEFAULT_JWT_SECRET_KEY:
            problems.append("JWT_SECRET_KEY is still the default value")
        elif len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY is shorter than 32 characters")
        if self.DB_URL == DEFAULT_DB_URL:
            problems.append("DB_URL still points at the local development database")
        if self.ENABLE_DEV_UI:
            # Deliberate while the agent endpoints are used for manual testing,
            # so it is a warning and not a reason to refuse to start.
            getLogger(__name__).warning(
                "ENABLE_DEV_UI is on: the ADK dev UI is reachable without authentication."
            )

        if problems:
            raise RuntimeError(
                "Unsafe configuration for ENVIRONMENT=production: " + "; ".join(problems)
            )


settings = Settings()
