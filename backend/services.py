"""App entrypoint"""

from google.adk.cli.fast_api import get_fast_api_app
from backend.core.settings import settings
from backend.core.logger_config import setup_logging
from backend.database.db import Base, engine
from backend.database import db_models as _db_models
from backend.routers.auth import router as auth_router


setup_logging()
Base.metadata.create_all(engine)


app = get_fast_api_app(
    agents_dir=settings.AGENT_DIR,
    session_service_uri=settings.SESSION_SERVICE_URI,
    artifact_service_uri=None,
    allow_origins=["*"],
    web=True,
)
app.include_router(auth_router)


# uvicorn backend.services:app --host 0.0.0.0 --port 8082 --reload
