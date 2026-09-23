"""Authentication for the ADK endpoints.

`get_fast_api_app` mounts the agent API without any authentication: anyone who
knows the URL can call /run with any userId, list another user's sessions and
download their artifacts. The login in the frontend only protects the frontend.

This middleware closes that gap. It runs in front of the whole app and:

* requires a valid bearer token on everything that is not explicitly public;
* checks that the user id in the URL belongs to the caller, so one account
  cannot read another account's sessions or artifacts;
* checks the same for the userId in the body of /run and /run_sse.

It is a pure ASGI middleware because the body of /run has to be inspected and
then handed to the application untouched.
"""

import json
import re
from urllib.parse import unquote
from logging import getLogger
from typing import Any

import jwt
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.core.settings import settings


logger = getLogger(__name__)
auth_logger = getLogger("audit.auth")

# Everything a browser needs before it has a token, plus the health probe.
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/auth/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# /apps/{app_name}/users/{user_id}/...
USER_IN_PATH = re.compile(r"^/apps/[^/]+/users/([^/]+)")

# Endpoints that carry the user id in the JSON body instead of the path.
USER_IN_BODY_PATHS: tuple[str, ...] = ("/run", "/run_sse")

MAX_BODY_BYTES = 2 * 1024 * 1024


class AuthMiddleware:
    """Require a valid JWT and enforce that callers only touch their own data."""

    def __init__(self, app: ASGIApp, public_prefixes: tuple[str, ...] = PUBLIC_PATH_PREFIXES):
        self.app = app
        self.public_prefixes = public_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        if method == "OPTIONS" or self._is_public(path):
            await self.app(scope, receive, send)
            return

        identity = self._identity_from_headers(scope)
        if identity is None:
            await self._reject(scope, receive, send, 401, "Missing or invalid authentication token")
            return

        path_user = USER_IN_PATH.match(path)
        if path_user and not self._owns(identity, path_user.group(1)):
            auth_logger.warning(
                "User %s tried to access data of %s", identity["email"], path_user.group(1)
            )
            await self._reject(scope, receive, send, 403, "You can only access your own sessions")
            return

        if path.rstrip("/") in USER_IN_BODY_PATHS:
            await self._call_with_checked_body(identity, scope, receive, send)
            return

        await self.app(scope, receive, send)

    # --- helpers ------------------------------------------------------------

    def _is_public(self, path: str) -> bool:
        return path == "/health" or path.startswith(self.public_prefixes)

    @staticmethod
    def _identity_from_headers(scope: Scope) -> dict[str, Any] | None:
        """Decode the bearer token, or return None when it is missing/invalid."""

        header_value = ""
        for name, value in scope.get("headers", []):
            if name == b"authorization":
                header_value = value.decode("latin-1")
                break

        scheme, _, token = header_value.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.PyJWTError as error:
            logger.info("Rejected token: %s", error)
            return None

        return {
            "user_id": payload.get("sub", ""),
            "username": payload.get("username", ""),
            "email": (payload.get("email") or "").lower(),
        }

    @staticmethod
    def _owns(identity: dict[str, Any], requested_user_id: str) -> bool:
        """Whether the caller may act as the given ADK user id."""

        requested = unquote(requested_user_id).strip().lower()
        return requested in {identity["email"], identity["username"].lower(), identity["user_id"]}

    async def _call_with_checked_body(
        self,
        identity: dict[str, Any],
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Validate the userId inside the request body, then replay the body."""

        messages: list[Message] = []
        body = b""
        more_body = True

        while more_body:
            message = await receive()
            messages.append(message)
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
            if len(body) > MAX_BODY_BYTES:
                await self._reject(scope, receive, send, 413, "Request body too large")
                return

        try:
            payload = json.loads(body or b"{}")
            requested_user = str(payload.get("userId", ""))
        except (ValueError, AttributeError):
            await self._reject(scope, receive, send, 400, "Invalid JSON body")
            return

        if requested_user and not self._owns(identity, requested_user):
            auth_logger.warning(
                "User %s tried to run as %s", identity["email"], requested_user
            )
            await self._reject(scope, receive, send, 403, "You can only run the agent as yourself")
            return

        replay: list[Message] = list(messages)

        async def replay_receive() -> Message:
            if replay:
                return replay.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        detail: str,
    ) -> None:
        response = JSONResponse({"detail": detail}, status_code=status_code)
        await response(scope, receive, send)
