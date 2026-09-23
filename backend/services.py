"""App entrypoint"""

from google.adk.cli.fast_api import get_fast_api_app

from backend.core.auth_middleware import AuthMiddleware
from backend.core.logger_config import setup_logging
from backend.core.settings import settings
from backend.database.db import Base, engine
from backend.database import db_models as _db_models
from backend.routers.auth import router as auth_router


setup_logging()
settings.check_production_readiness()
Base.metadata.create_all(engine)


app = get_fast_api_app(
    agents_dir=settings.AGENT_DIR,
    session_service_uri=settings.SESSION_SERVICE_URI,
    artifact_service_uri=None,
    allow_origins=settings.allowed_origins_list,
    # The ADK dev UI is an unauthenticated console; keep it out of production.
    web=settings.ENABLE_DEV_UI,
)
app.include_router(auth_router)

# Added last, so it wraps everything: no ADK endpoint is reachable without a
# valid token, and nobody can act as another user.
app.add_middleware(AuthMiddleware)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe used by the container and by Railway."""

    return {"status": "ok", "environment": settings.ENVIRONMENT}


# uvicorn backend.services:app --host 0.0.0.0 --port 8082 --reload
