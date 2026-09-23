"""Chat interface."""

import logging

import streamlit as st

from frontend import state
from frontend.helpers.get_conversation import get_conversations
from frontend.services.adk_service import (
    ADKAuthError,
    ADKError,
    ADKService,
    extract_event_text,
    extract_final_text,
)
from frontend.settings import settings
from frontend.ui.components.artifacts import render_artifacts
from frontend.ui.components.base import BaseComponent
from frontend.ui.components.sidebar import get_client


logger = logging.getLogger(__name__)


class ChatComponent(BaseComponent):
    """Main chat interface component"""

    def __init__(self):
        super().__init__("chat")
        self.is_sidebar = False

    def render(self):
        client = get_client()
        if client is None:
            st.info("The backend client is not available")
            return

        if st.session_state[state.CURRENT_SESSION_ID]:
            self._render_conversation(client)
            render_artifacts(client)
        else:
            st.info("Please select or create a session to start chatting")

        prompt = st.chat_input("Ask me anything...")
        if prompt:
            self._handle_user_message(client, prompt)

    # --- history ------------------------------------------------------------

    @staticmethod
    def _render_conversation(client: ADKService) -> None:
        """Render the current conversation, refetching only when it changed."""

        session_id = st.session_state[state.CURRENT_SESSION_ID]
        cache_is_valid = (
            st.session_state[state.CACHED_CONVERSATION_SESSION_ID] == session_id
            and st.session_state[state.CACHED_CONVERSATION] is not None
        )

        if cache_is_valid:
            messages = st.session_state[state.CACHED_CONVERSATION]
        else:
            try:
                session = client.get_session_by_id(session_id)
            except ADKAuthError:
                st.error("Your session expired. Please log in again.")
                state.reset_user_state()
                st.rerun()
            except ADKError as error:
                st.error(f"Could not load the conversation: {error}")
                return

            messages = get_conversations(session)
            st.session_state[state.CACHED_CONVERSATION] = messages
            st.session_state[state.CACHED_CONVERSATION_SESSION_ID] = session_id

        if not messages:
            st.info("There is no conversation within this session")
            return

        st.subheader("Current Conversation")
        for message in messages:
            with st.chat_message("user" if message["role"] == "user" else "assistant"):
                st.markdown(message["text"])

    # --- sending ------------------------------------------------------------

    @staticmethod
    def _handle_user_message(client: ADKService, message: str) -> None:
        """Send the message to the agent and show the answer."""

        if not st.session_state[state.CURRENT_SESSION_ID]:
            try:
                session = client.create_session()
            except ADKError as error:
                st.error(f"Error creating session: {error}")
                return

            st.session_state[state.CURRENT_SESSION_ID] = session["id"]
            st.session_state[state.PENDING_SESSION_ID] = session["id"]
            st.session_state[state.SESSIONS_LOADED] = False

        session_id = st.session_state[state.CURRENT_SESSION_ID]

        with st.chat_message("user"):
            st.markdown(message)

        with st.chat_message("assistant"):
            try:
                if settings.USE_STREAMING:
                    ChatComponent._stream_answer(client, session_id, message)
                else:
                    with st.spinner("Thinking..."):
                        events = client.send_message(session_id, message)
                    answer = extract_final_text(events)
                    st.markdown(answer or "_The agent returned no text._")
            except ADKAuthError:
                st.error("Your session expired. Please log in again.")
                state.reset_user_state()
                st.rerun()
            except ADKError as error:
                st.error(f"Error processing query: {error}")
                return

        # The answer may have produced new artifacts and changed the history.
        state.invalidate_caches()
        st.rerun()

    @staticmethod
    def _stream_answer(client: ADKService, session_id: str, message: str) -> None:
        """Render the answer as it arrives from /run_sse."""

        placeholder = st.empty()
        streamed_text = ""
        final_text = ""

        for event in client.send_message_sse(session_id, message):
            event_text = extract_event_text(event)
            if not event_text:
                continue

            if event.get("partial"):
                streamed_text += event_text
                placeholder.markdown(streamed_text)
            else:
                final_text = event_text

        placeholder.markdown(final_text or streamed_text or "_The agent returned no text._")
