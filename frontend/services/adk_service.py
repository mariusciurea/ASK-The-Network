"""Services for consuming the API endpoints"""
import json
import requests
import streamlit as st
from urllib.parse import quote
from frontend.settings import settings
from typing import Dict, Iterator, List
import logging


class ADKService:
    """Service class for Google ADK API interactions"""

    def __init__(self):
        self.base_url = settings.BASE_URL
        self.session = requests.Session()
        auth_token = st.session_state.get("auth_token")
        if auth_token:
            self.session.headers.update({"Authorization": f"Bearer {auth_token}"})

    @property
    def user_id(self) -> str:
        """Return the ADK user id for the logged-in user."""
        auth_user = st.session_state.get("auth_user") or {}
        return auth_user.get("email") or settings.USER_ID

    @property
    def encoded_user_id(self) -> str:
        """Return the URL-safe ADK user id."""
        return quote(self.user_id, safe="")

    def create_session(self) -> Dict:
        """Create a new conversation session"""
        try:
            response = self.session.post(
                f"{self.base_url}/apps/{settings.APP_NAME}/users/{self.encoded_user_id}/sessions/{settings.get_session_id()}"
            )
            logging.info(f"Create session response status: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Error creating session: {e}")
            return {}

    def get_session_by_id(self, session_id: str) -> List[Dict]:
        """Get a specific session by session id"""
        try:
            response = self.session.get(
                f"{self.base_url}/apps/{settings.APP_NAME}/users/{self.encoded_user_id}/sessions/{session_id}"
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return []

    def get_sessions(self) -> List[Dict]:
        """Get all sessions"""
        try:
            response = self.session.get(
                f"{self.base_url}/apps/{settings.APP_NAME}/users/{self.encoded_user_id}/sessions"
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return []



    def _message_payload(self, session_id: str, message: str, streaming: bool = False) -> Dict:
        """Build the payload expected by the ADK /run and /run_sse endpoints."""
        return {
            "appName": settings.APP_NAME,
            "userId": self.user_id,
            "sessionId": session_id,
            "newMessage": {
                "role": "user",
                "parts": [{"text": message}]
            },
            "streaming": streaming,
        }

    def send_message(self, session_id: str, message: str) -> Dict:
        """Send a message to an agent in a session"""

        try:
            payload = self._message_payload(session_id, message)
            response = self.session.post(f"{self.base_url}/run", json=payload)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def send_message_sse(self, session_id: str, message: str) -> Iterator[Dict]:
        """Send a message to an agent and stream ADK events from /run_sse."""

        payload = self._message_payload(session_id, message, streaming=True)

        try:
            with self.session.post(
                f"{self.base_url}/run_sse",
                json=payload,
                headers={"Accept": "text/event-stream"},
                stream=True,
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
                    except json.JSONDecodeError as e:
                        yield {"error": f"Invalid SSE event: {e}"}
        except requests.RequestException as e:
            yield {"error": str(e)}

    def delete_session(self, session_id: str):
        """Delete a specific session"""
        try:
            response = self.session.delete(
                f"{self.base_url}/apps/{settings.APP_NAME}/users/{self.encoded_user_id}/sessions/{session_id}"
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}

