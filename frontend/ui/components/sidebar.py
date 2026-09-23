"""Sidebar: identity and the shared backend client."""

import logging

import streamlit as st

from frontend import state
from frontend.services.adk_service import ADKService
from frontend.ui.components.base import BaseComponent


logger = logging.getLogger(__name__)


def get_client() -> ADKService | None:
    """Return the backend client of the current browser session.

    One client per user session keeps the underlying connection pool alive
    between reruns instead of opening a new TCP connection per interaction.
    """

    client = st.session_state.get(state.ADK_CLIENT)
    if client is None:
        client = ADKService()
        st.session_state[state.ADK_CLIENT] = client
    return client


class SidebarComponent(BaseComponent):
    """Sidebar component for the logged-in user and the backend client."""

    def __init__(self):
        super().__init__("sidebar")
        self.is_sidebar = True

    def render(self):
        st.title("Ask The Network")

        auth_user = st.session_state.get(state.AUTH_USER)
        if auth_user:
            st.caption(f"Logged in as {auth_user.get('username')}")
            if st.button("Logout", key="logout_btn"):
                state.reset_user_state()
                st.rerun()

        get_client()
