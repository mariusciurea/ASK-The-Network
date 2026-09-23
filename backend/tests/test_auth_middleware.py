"""Tests for the authentication middleware in front of the ADK endpoints.

They run against a miniature app that mimics the ADK routes, so no database,
no agent and no API key are needed.

    python -m pytest backend/tests/test_auth_middleware.py
    python backend/tests/test_auth_middleware.py      # same checks, no pytest
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.core.auth_middleware import AuthMiddleware
from backend.core.settings import settings


OWNER = {"sub": "1", "username": "marius", "email": "marius@test.com"}
INTRUDER = {"sub": "2", "username": "eve", "email": "eve@test.com"}


def _token(claims: dict, expires_in_minutes: int = 60) -> str:
    payload = {
        **claims,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _auth(claims: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(claims)}"}


def _build_client() -> TestClient:
    """An app with the same route shapes as the ADK backend."""

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/login")
    def login():
        return {"access_token": "..."}

    @app.get("/apps/{app_name}/users/{user_id}/sessions")
    def list_sessions(app_name: str, user_id: str):
        return [{"id": "session-1", "user": user_id}]

    @app.post("/run")
    async def run(request: Request):
        # Proves the body survives the middleware inspection intact.
        return {"received": await request.json()}

    app.add_middleware(AuthMiddleware)
    return TestClient(app, raise_server_exceptions=False)


CLIENT = _build_client()
SESSIONS_URL = "/apps/network_agent/users/marius@test.com/sessions"


def test_public_endpoints_need_no_token():
    assert CLIENT.get("/health").status_code == 200
    assert CLIENT.post("/auth/login").status_code == 200


def test_adk_endpoints_require_a_token():
    """This is the hole the middleware closes."""

    assert CLIENT.get(SESSIONS_URL).status_code == 401
    assert CLIENT.post("/run", json={"userId": "marius@test.com"}).status_code == 401


def test_garbage_and_expired_tokens_are_rejected():
    assert CLIENT.get(SESSIONS_URL, headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    assert CLIENT.get(SESSIONS_URL, headers={"Authorization": "Basic abc"}).status_code == 401

    expired = {"Authorization": f"Bearer {_token(OWNER, expires_in_minutes=-5)}"}
    assert CLIENT.get(SESSIONS_URL, headers=expired).status_code == 401

    forged = jwt.encode({**OWNER, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                        "some-other-secret", algorithm="HS256")
    assert CLIENT.get(SESSIONS_URL, headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_owner_reaches_their_own_sessions():
    response = CLIENT.get(SESSIONS_URL, headers=_auth(OWNER))
    assert response.status_code == 200, response.text
    assert response.json()[0]["user"] == "marius@test.com"


def test_other_users_sessions_are_forbidden():
    response = CLIENT.get(SESSIONS_URL, headers=_auth(INTRUDER))
    assert response.status_code == 403, response.text


def test_url_encoded_user_id_is_still_matched():
    encoded_url = "/apps/network_agent/users/marius%40test.com/sessions"
    assert CLIENT.get(encoded_url, headers=_auth(OWNER)).status_code == 200


def test_run_cannot_impersonate_another_user():
    payload = {"userId": "marius@test.com", "sessionId": "s1"}
    assert CLIENT.post("/run", json=payload, headers=_auth(INTRUDER)).status_code == 403


def test_run_body_reaches_the_application_unchanged():
    payload = {
        "userId": "marius@test.com",
        "sessionId": "s1",
        "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
    }
    response = CLIENT.post("/run", json=payload, headers=_auth(OWNER))
    assert response.status_code == 200, response.text
    assert response.json()["received"] == payload


def test_production_readiness_refuses_default_secrets():
    production = settings.model_copy(update={"ENVIRONMENT": "production"})
    try:
        production.check_production_readiness()
    except RuntimeError as error:
        assert "JWT_SECRET_KEY" in str(error)
        return
    raise AssertionError("a production deployment with default secrets must not start")


if __name__ == "__main__":
    failures = 0
    for name, test in sorted(dict(globals()).items()):
        if not name.startswith("test_") or not callable(test):
            continue
        try:
            test()
            print(f"PASS {name}")
        except Exception as error:  # noqa: BLE001 - a standalone runner reports everything
            failures += 1
            print(f"FAIL {name}: {type(error).__name__}: {error}")
    print(f"\n{failures} failure(s)")
    raise SystemExit(1 if failures else 0)
