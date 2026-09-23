"""Settings"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # dirs
    WORKING_DIR: Path = Path(__file__).resolve().parent.parent.parent
    AGENT_DIR: str = str(WORKING_DIR / "backend/network_agent")
    SESSION_SERVICE_URI:str = f"sqlite:///{str(WORKING_DIR / "sessions.db")}"
    DATA_DIR: Path = WORKING_DIR / "backend/data"

    #db
    DB_URL:str ="mysql+pymysql://root:Changeme_123@localhost:3306/radio_network_data"

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
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24


settings = Settings()
