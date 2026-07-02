"""Settings"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # dirs
    WORKING_DIR: Path = Path(__file__).resolve().parent.parent.parent
    AGENT_DIR: str = str(WORKING_DIR / "src/network_agent")
    SESSION_SERVICE_URI:str = f"sqlite:///{str(WORKING_DIR / "sessions.db")}"
    DATA_DIR: Path = WORKING_DIR / "src/data"

    #db
    DB_URL:str ="mysql+pymysql://root:ewis2020@localhost:3306/radio_network_data"

    # model
    MODEL_NAME: str = "gemini-3-flash-preview"
    # MODEL_NAME: str = "gemini-3.1-flash-lite"
    GOOGLE_API_KEY: str = ""

    # MCP
    MCP_URL: str = "http://localhost:34/mcp"

    MAX_ROWS: int = 20


settings = Settings()