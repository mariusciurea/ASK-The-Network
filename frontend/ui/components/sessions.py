"""Conversation session management."""

import logging

import streamlit as st

from frontend import state
from frontend.helpers.get_conversation import get_first_user_question
from frontend.services.adk_service import ADKAuthError, ADKError, ADKService
from frontend.settings import settings
from frontend.ui.components.base import BaseComponent
from frontend.ui.components.sidebar import get_client


logger = logging.getLogger(__name__)

NEW_SESSION_PLACEHOLDER = "Choose an option"


@st.cache_data(ttl=300, show_spinner=False)
def _session_label(_client: ADKService, user_id: str, session_id: str) -> str:
    """Return the label of a session, cached per user and session.

    Labelling a session means fetching it, because the list endpoint does not
    return the events. Caching turns that into one request per session instead
    of one per session on every rerun. `_client` is not part of the cache key -
    the leading underscore tells Streamlit not to hash it.
    """

    try:
        session = _client.get_session_by_id(session_id)
    except ADKError as error:
        logger.info("Could not label session %s: %s", session_id, error)
        return ""

    return get_first_user_question(session, settings.SESSION_LABEL_LENGTH)


class SessionManagerComponent(BaseComponent):
    """Component for managing conversation sessions"""

    def __init__(self):
        super().__init__("session_manager")
        self.is_sidebar = True

    def render(self):
        client = get_client()
        if client is None:
            st.warning("The backend client is not available")
            return

        if not st.session_state[state.SESSIONS_LOADED] or st.button(
            "🔄 Refresh Sessions", key="refresh_sessions"
        ):
            self._load_sessions(client)

        if not st.session_state[state.ALL_SESSION_IDS]:
            st.info("No sessions available")
            if st.button("Create First Session", key="create_first_session"):
                self._create_new_session(client)
            return

        self._render_selector()
        self._render_actions(client)

    # --- data ---------------------------------------------------------------

    @staticmethod
    def _load_sessions(client: ADKService) -> None:
        """Load the session list and label the most recent ones."""

        try:
            sessions = client.get_sessions()
        except ADKAuthError:
            st.error("Your session expired. Please log in again.")
            state.reset_user_state()
            st.rerun()
        except ADKError as error:
            st.error(f"Error loading sessions: {error}")
            return

        # Newest first, so the bounded labelling budget is spent where it shows.
        sessions.sort(key=lambda item: item.get("lastUpdateTime") or 0, reverse=True)
        session_ids = [session["id"] for session in sessions]

        labels: list[str] = []
        for index, session_id in enumerate(session_ids):
            label = ""
            if index < settings.SESSION_LABEL_LIMIT:
                label = _session_label(client, client.user_id, session_id)
            labels.append(label or f"Session {session_id[:8]}...")

        st.session_state[state.ALL_SESSION_IDS] = [None, *session_ids]
        st.session_state[state.ALL_SESSION_LABELS] = [NEW_SESSION_PLACEHOLDER, *labels]
        st.session_state[state.SESSIONS_LOADED] = True

    # --- rendering ----------------------------------------------------------

    @staticmethod
    def _render_selector() -> None:
        session_ids = st.session_state[state.ALL_SESSION_IDS]
        labels = dict(zip(session_ids, st.session_state[state.ALL_SESSION_LABELS]))

        pending_session_id = st.session_state[state.PENDING_SESSION_ID]
        if pending_session_id and pending_session_id in session_ids:
            st.session_state[state.CURRENT_SESSION_ID] = pending_session_id
            st.session_state[state.SESSION_SELECTOR] = pending_session_id
            st.session_state[state.PENDING_SESSION_ID] = None
        elif st.session_state.get(state.SESSION_SELECTOR) not in session_ids:
            current = st.session_state[state.CURRENT_SESSION_ID]
            st.session_state[state.SESSION_SELECTOR] = current if current in session_ids else None

        selected_session_id = st.selectbox(
            "Please select the session",
            options=session_ids,
            format_func=lambda session_id: labels.get(session_id, NEW_SESSION_PLACEHOLDER),
            key=state.SESSION_SELECTOR,
        )

        if selected_session_id != st.session_state[state.CURRENT_SESSION_ID]:
            st.session_state[state.CURRENT_SESSION_ID] = selected_session_id
            state.invalidate_caches()

    def _render_actions(self, client: ADKService) -> None:
        new_column, delete_column = st.columns(2)

        with new_column:
            if st.button("New Session", key="new_session_btn"):
                self._create_new_session(client)

        with delete_column:
            if st.button(
                "Delete Session",
                key="delete_session_btn",
                disabled=not st.session_state[state.CURRENT_SESSION_ID],
            ):
                self._delete_session(client)

    # --- actions ------------------------------------------------------------

    @staticmethod
    def _create_new_session(client: ADKService) -> None:
        """Create a new conversation session"""

        try:
            session = client.create_session()
        except ADKError as error:
            st.error(f"Error creating session: {error}")
            return

        session_id = session["id"]
        state.invalidate_caches()
        st.session_state[state.CURRENT_SESSION_ID] = session_id
        st.session_state[state.PENDING_SESSION_ID] = session_id
        st.session_state[state.SESSIONS_LOADED] = False
        st.success(f"Created new session: {session_id[:8]}...")
        st.rerun()

    @staticmethod
    def _delete_session(client: ADKService) -> None:
        """Delete the current session"""

        session_id = st.session_state[state.CURRENT_SESSION_ID]
        if not session_id:
            return

        try:
            client.delete_session(session_id)
        except ADKError as error:
            st.error(f"Error deleting session: {error}")
            return

        _session_label.clear()
        state.reset_conversation_state()
        st.rerun()
