"""HTTP client for the ADK backend.

Everything that talks to the backend lives here: the UI never builds a URL or
handles a status code. Three things this client is strict about:

* every request has a timeout - a hung backend must not pin a Streamlit worker
  thread forever;
* only idempotent requests are retried - re-sending a chat message would run
  the agent twice;
* failures raise, they do not return an empty list that the UI mistakes for
  "no data".
"""

import json
import logging
import uuid
from typing import Any, Iterator
from urllib.parse import quote

import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from frontend import state
from frontend.settings import settings


logger = logging.getLogger(__name__)


class ADKError(RuntimeError):
    """A call to the backend failed."""


class ADKAuthError(ADKError):
    """The backend rejected the credentials; the user has to log in again."""


def describe_http_error(error: requests.RequestException) -> str:
    """Turn a requests exception into something worth showing a user."""

    response = getattr(error, "response", None)
    if response is None:
        return str(error)

    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None

    return detail or response.text.strip()[:300] or f"HTTP {response.status_code}"


class ADKService:
    """Service class for Google ADK API interactions"""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.BASE_URL).rstrip("/")
        self.session = requests.Session()

        # Retry only what is safe to repeat, and only on transient failures.
        retry = Retry(
            total=settings.MAX_RETRIES,
            connect=settings.MAX_RETRIES,
            read=0,
            backoff_factor=0.5,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "DELETE"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # --- identity -----------------------------------------------------------

    @property
    def auth_token(self) -> str | None:
        """Read the token on every call, so a re-login is picked up at once."""

        return st.session_state.get(state.AUTH_TOKEN)

    @property
    def user_id(self) -> str:
        """Return the ADK user id for the logged-in user."""

        auth_user = st.session_state.get(state.AUTH_USER) or {}
        return auth_user.get("email") or settings.USER_ID

    @property
    def encoded_user_id(self) -> str:
        """Return the URL-safe ADK user id."""

        return quote(self.user_id, safe="")

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        token = self.auth_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    # --- plumbing -----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _sessions_url(self, session_id: str = "") -> str:
        path = (
            f"/apps/{settings.APP_NAME}/users/{self.encoded_user_id}/sessions"
        )
        return self._url(f"{path}/{session_id}" if session_id else path)

    def _request(
        self,
        method: str,
        url: str,
        *,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Perform a request and return the decoded JSON body.

        Raises:
            ADKAuthError: The backend returned 401/403.
            ADKError: Any other transport or HTTP failure.
        """

        read_timeout = timeout or settings.REQUEST_TIMEOUT_SECONDS

        try:
            response = self.session.request(
                method,
                url,
                headers=self._headers(kwargs.pop("headers", None)),
                timeout=(settings.CONNECT_TIMEOUT_SECONDS, read_timeout),
                **kwargs,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            message = describe_http_error(error)
            logger.warning("%s %s failed: %s", method, url, message)
            if error.response is not None and error.response.status_code in (401, 403):
                raise ADKAuthError(message) from error
            raise ADKError(message) from error
        except requests.RequestException as error:
            logger.warning("%s %s failed: %s", method, url, error)
            raise ADKError(f"Could not reach the backend: {error}") from error

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as error:
            raise ADKError(f"Backend returned a non-JSON response: {error}") from error

    # --- sessions -----------------------------------------------------------

    def create_session(self) -> dict[str, Any]:
        """Create a new conversation session"""

        return self._request("POST", self._sessions_url(str(uuid.uuid4())))

    def get_session_by_id(self, session_id: str) -> dict[str, Any]:
        """Get a specific session by session id"""

        return self._request("GET", self._sessions_url(session_id))

    def get_sessions(self) -> list[dict[str, Any]]:
        """Get all sessions of the current user"""

        return self._request("GET", self._sessions_url()) or []

    def delete_session(self, session_id: str) -> None:
        """Delete a specific session"""

        self._request("DELETE", self._sessions_url(session_id))

    # --- messages -----------------------------------------------------------

    def _message_payload(self, session_id: str, message: str, streaming: bool = False) -> dict:
        """Build the payload expected by the ADK /run and /run_sse endpoints."""

        return {
            "appName": settings.APP_NAME,
            "userId": self.user_id,
            "sessionId": session_id,
            "newMessage": {
                "role": "user",
                "parts": [{"text": message}],
            },
            "streaming": streaming,
        }

    def send_message(self, session_id: str, message: str) -> list[dict[str, Any]]:
        """Send a message to the agent and return the resulting ADK events."""

        events = self._request(
            "POST",
            self._url("/run"),
            json=self._message_payload(session_id, message),
            timeout=settings.AGENT_TIMEOUT_SECONDS,
        )
        return events or []

    def send_message_sse(self, session_id: str, message: str) -> Iterator[dict[str, Any]]:
        """Send a message to an agent and stream ADK events from /run_sse."""

        payload = self._message_payload(session_id, message, streaming=True)

        try:
            with self.session.post(
                self._url("/run_sse"),
                json=payload,
                headers=self._headers({"Accept": "text/event-stream"}),
                stream=True,
                timeout=(settings.CONNECT_TIMEOUT_SECONDS, settings.AGENT_TIMEOUT_SECONDS),
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue

                    event_data = line[5:].strip()
                    if not event_data:
                        continue

                    try:
                        yield json.loads(event_data)
                    except json.JSONDecodeError as error:
                        raise ADKError(f"Invalid SSE event: {error}") from error
        except requests.HTTPError as error:
            message = describe_http_error(error)
            if error.response is not None and error.response.status_code in (401, 403):
                raise ADKAuthError(message) from error
            raise ADKError(message) from error
        except requests.RequestException as error:
            raise ADKError(f"Could not reach the backend: {error}") from error

    # --- artifacts ----------------------------------------------------------

    def _artifact_url(self, session_id: str, artifact_name: str = "", suffix: str = "") -> str:
        """Build an ADK artifact endpoint URL."""

        encoded_artifact_name = quote(artifact_name, safe="")
        artifact_path = (
            "/artifacts"
            if not encoded_artifact_name
            else f"/artifacts/{encoded_artifact_name}{suffix}"
        )
        return f"{self._sessions_url(session_id)}{artifact_path}"

    def list_artifacts(self, session_id: str) -> list[str]:
        """List the artifact names attached to a session."""

        return self._request("GET", self._artifact_url(session_id)) or []

    def get_artifact_versions(self, session_id: str, artifact_name: str) -> list[dict[str, Any]]:
        """Load metadata for all versions of an artifact."""

        return self._request(
            "GET",
            self._artifact_url(session_id, artifact_name, "/versions/metadata"),
        ) or []

    def get_artifact_version(
        self,
        session_id: str,
        artifact_name: str,
        version: int | str,
    ) -> dict[str, Any]:
        """Load one version of an artifact."""

        return self._request(
            "GET",
            self._artifact_url(session_id, artifact_name, f"/versions/{version}"),
        )


def extract_event_text(event: dict[str, Any]) -> str:
    """Extract displayable text from a single ADK event."""

    content = event.get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return ""

    has_function_call = any(
        part.get("functionCall") or part.get("function_call")
        for part in parts
    )
    if has_function_call:
        return ""

    return "".join(
        part.get("text", "")
        for part in parts
        if part.get("text") and not part.get("thought")
    )


def extract_final_text(events: list[dict[str, Any]]) -> str:
    """Return the agent's answer from a /run response.

    The response is the whole event trajectory: tool calls, tool results and
    intermediate messages from sub-agents. The answer is the last event that
    carries text, not the first one.
    """

    for event in reversed(events):
        text = extract_event_text(event)
        if text.strip():
            return text

    return ""
