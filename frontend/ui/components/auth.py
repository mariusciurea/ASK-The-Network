"""Login and registration."""

import logging

import requests
import streamlit as st

from frontend import state
from frontend.services.adk_service import describe_http_error
from frontend.settings import settings
from frontend.ui.components.base import BaseComponent


logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


class AuthComponent(BaseComponent):
    """Login and registration component."""

    def __init__(self):
        super().__init__("auth")
        self.is_sidebar = False

    def render(self):
        if st.session_state.get(state.AUTH_TOKEN):
            return

        st.subheader("Account")
        login_tab, register_tab = st.tabs(["Login", "Register"])

        with login_tab:
            self._render_login()

        with register_tab:
            self._render_register()

    def _render_login(self):
        with st.form("login_form"):
            username = st.text_input("Username or email", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

        if submitted:
            self._authenticate(
                "/auth/login",
                {"username": username, "password": password},
                "Logged in successfully",
            )

    def _render_register(self):
        with st.form("register_form"):
            username = st.text_input("Username", key="register_username")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            confirm_password = st.text_input(
                "Confirm password",
                type="password",
                key="register_confirm_password",
            )
            submitted = st.form_submit_button("Register")

        if not submitted:
            return

        if password != confirm_password:
            st.error("Passwords do not match")
            return

        if len(password) < MIN_PASSWORD_LENGTH:
            st.error(f"The password must have at least {MIN_PASSWORD_LENGTH} characters")
            return

        self._authenticate(
            "/auth/register",
            {"username": username, "email": email, "password": password},
            "Account created successfully",
        )

    @staticmethod
    def _authenticate(endpoint: str, payload: dict[str, str], success_message: str):
        """Call an auth endpoint and store the JWT."""

        try:
            response = requests.post(
                f"{settings.BASE_URL}{endpoint}",
                json=payload,
                timeout=(settings.CONNECT_TIMEOUT_SECONDS, settings.REQUEST_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            auth_data = response.json()
        except requests.HTTPError as error:
            # Never log the payload: it carries the password.
            logger.warning("Authentication failed on %s", endpoint)
            st.error(describe_http_error(error))
            return
        except requests.RequestException as error:
            logger.warning("Authentication request to %s failed: %s", endpoint, error)
            st.error("Could not reach the backend. Please try again.")
            return

        # A fresh identity starts from a clean slate - no cached conversation,
        # no artifacts and no client bound to the previous token.
        state.reset_user_state()
        st.session_state[state.AUTH_TOKEN] = auth_data["access_token"]
        st.session_state[state.AUTH_USER] = auth_data["user"]

        st.success(success_message)
        st.rerun()
