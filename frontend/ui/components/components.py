import streamlit as st
import base64
import json
import requests
from urllib.parse import quote

from typing import Any
from frontend.ui.components.base import BaseComponent
from frontend.services.adk_service import ADKService
from frontend.helpers.get_conversation import get_conversations, get_first_user_question
from frontend.helpers.terms import terms_and_conditions
from frontend.settings import settings


class SidebarComponent(BaseComponent):
    """Sidebar component for server configuration"""

    def __init__(self):
        super().__init__("sidebar")
        self.is_sidebar = True

    def initialize_state(self):
        if 'adk_client' not in st.session_state:
            st.session_state.adk_client = None

    def render(self):
        st.title("Ask The Network")
        auth_user = st.session_state.get("auth_user")
        if auth_user:
            st.caption(f"Logged in as {auth_user.get('username')}")
            if st.button("Logout", key="logout_btn"):
                st.session_state.auth_token = None
                st.session_state.auth_user = None
                st.session_state.adk_client = None
                st.session_state.current_session_id = None
                st.session_state.pending_session_selector_id = None
                st.session_state.all_session_ids = []
                st.session_state.all_session_conversations = []
                st.session_state.sessions_loaded = False
                st.session_state.cached_conversation = None
                st.session_state.cached_session_id = None
                st.session_state.cached_artifact_names = None
                st.session_state.cached_artifacts_session_id = None
                st.session_state.loaded_artifact = None
                st.rerun()

        try:
            if st.session_state.adk_client is None:
                st.session_state.adk_client = ADKService()
                self.set_state("client_initialized", True)
        except Exception as e:
            self.set_state("client_initialized", False)


class AuthComponent(BaseComponent):
    """Login and registration component."""

    def __init__(self):
        super().__init__("auth")
        self.is_sidebar = False

    def initialize_state(self):
        if 'auth_token' not in st.session_state:
            st.session_state.auth_token = None
        if 'auth_user' not in st.session_state:
            st.session_state.auth_user = None

    def render(self):
        if st.session_state.auth_token:
            return

        st.subheader("Account")
        login_tab, register_tab = st.tabs(["Login", "Register"])

        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username or email", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login")

            if submitted:
                self._authenticate(
                    "/auth/login",
                    {
                        "username": username,
                        "password": password,
                    },
                    "Logged in successfully",
                )

        with register_tab:
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

            if submitted:
                if password != confirm_password:
                    st.error("Passwords do not match")
                    return

                self._authenticate(
                    "/auth/register",
                    {
                        "username": username,
                        "email": email,
                        "password": password,
                    },
                    "Account created successfully",
                )

    @staticmethod
    def _authenticate(endpoint: str, payload: dict[str, str], success_message: str):
        """Call an auth endpoint and store the JWT."""
        try:
            response = requests.post(
                f"{settings.BASE_URL.rstrip('/')}{endpoint}",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            auth_data = response.json()
        except requests.HTTPError as e:
            detail = str(e)
            if e.response is not None:
                try:
                    detail = e.response.json().get("detail", detail)
                except ValueError:
                    detail = e.response.text or detail
            st.error(detail)
            return
        except requests.RequestException as e:
            st.error(f"Authentication request failed: {e}")
            return

        st.session_state.auth_token = auth_data["access_token"]
        st.session_state.auth_user = auth_data["user"]
        st.session_state.current_session_id = None
        st.session_state.pending_session_selector_id = None
        st.session_state.all_session_ids = []
        st.session_state.all_session_conversations = []
        st.session_state.sessions_loaded = False
        st.session_state.cached_conversation = None
        st.session_state.cached_session_id = None
        st.session_state.cached_artifact_names = None
        st.session_state.cached_artifacts_session_id = None
        st.session_state.loaded_artifact = None
        if st.session_state.get("adk_client"):
            st.session_state.adk_client.session.headers.update({
                "Authorization": f"Bearer {auth_data['access_token']}"
            })
        st.success(success_message)
        st.rerun()


class SessionManagerComponent(BaseComponent):
    """Component for managing conversation sessions"""

    def __init__(self):
        super().__init__("session_manager")
        self.is_sidebar = True

    def initialize_state(self):
        if 'current_session_id' not in st.session_state:
            st.session_state.current_session_id = None

        if 'all_session_ids' not in st.session_state:
            st.session_state.all_session_ids = []

        if 'all_session_conversations' not in st.session_state:
            st.session_state.all_session_conversations = []
        
        if 'sessions_loaded' not in st.session_state:
            st.session_state.sessions_loaded = False

        if 'pending_session_selector_id' not in st.session_state:
            st.session_state.pending_session_selector_id = None

    def render(self):
        if not st.session_state.adk_client:
            st.warning("Please configure server connection first")
            return

        #  get sessions if needed
        if not st.session_state.sessions_loaded or st.button("🔄 Refresh Sessions", key="refresh_sessions"):
            self._load_sessions()
            st.session_state.sessions_loaded = True

        if not st.session_state.all_session_ids:
            st.info("No sessions available")
            if st.button("Create First Session", key="create_first_session"):
                self._create_new_session()
            return

        # default index
        if st.session_state.current_session_id and st.session_state.current_session_id in st.session_state.all_session_ids:
            default_index = st.session_state.all_session_ids.index(st.session_state.current_session_id)
        else:
            default_index = 0

        session_label_by_id = dict(zip(
            st.session_state.all_session_ids,
            st.session_state.all_session_conversations,
        ))
        selected_session_is_available = st.session_state.current_session_id in st.session_state.all_session_ids
        pending_session_id = st.session_state.pending_session_selector_id

        if pending_session_id and pending_session_id in st.session_state.all_session_ids:
            st.session_state.current_session_id = pending_session_id
            st.session_state.session_selector = pending_session_id
            st.session_state.pending_session_selector_id = None
        elif "session_selector" not in st.session_state and selected_session_is_available:
            st.session_state.session_selector = st.session_state.current_session_id
        elif st.session_state.get("session_selector") not in st.session_state.all_session_ids:
            st.session_state.session_selector = (
                st.session_state.current_session_id
                if selected_session_is_available
                else None
            )

        selected_session_id = st.selectbox(
            "Please select the session",
            options=st.session_state.all_session_ids,
            format_func=lambda session_id: session_label_by_id.get(session_id, "Choose an option"),
            key="session_selector",
            index=default_index,
        )

        # update if selection changed
        if selected_session_id != st.session_state.current_session_id:
            st.session_state.current_session_id = selected_session_id

        col1, col2 = st.columns(2)
        with col1:
            if st.button("New Session", key="new_session_btn"):
                self._create_new_session()

        with col2:
            if st.button("Delete Session", key="delete_session_btn",
                         disabled=not st.session_state.current_session_id):
                self._delete_session()

    @staticmethod
    def _load_sessions():
        """Load all sessions from the service"""
        try:
            sessions = st.session_state.adk_client.get_sessions()
            session_ids = [session["id"] for session in sessions]

            all_sessions = [st.session_state.adk_client.get_session_by_id(session["id"]) for session in sessions]
            current_session_id = st.session_state.current_session_id
            if current_session_id and current_session_id not in session_ids:
                current_session = st.session_state.adk_client.get_session_by_id(current_session_id)
                if current_session:
                    session_ids.append(current_session_id)
                    all_sessions.append(current_session)

            session_conversations = [
                get_first_user_question(session) or f"New session {session['id'][:8]}..." 
                for session in all_sessions
            ]

            session_ids.insert(0, None)
            session_conversations.insert(0, "Choose an option")

            st.session_state.all_session_ids = session_ids
            st.session_state.all_session_conversations = session_conversations
        except Exception as e:
            st.error(f"Error loading sessions: {e}")

    @staticmethod
    def _create_new_session():
        """Create a new conversation session"""
        try:
            session = st.session_state.adk_client.create_session()
            session_id = session["id"]
            st.session_state.current_session_id = session_id
            st.session_state.pending_session_selector_id = session_id
            st.session_state.sessions_loaded = False  # Mark for reload
            st.success(f"Created new session: {session_id[:8]}...")
            st.rerun()
        except Exception as e:
            st.error(f"Error creating session: {e}")

    @staticmethod
    def _delete_session():
        """Delete the current session"""
        try:
            if st.session_state.current_session_id:
                session_id = st.session_state.current_session_id
                st.session_state.adk_client.delete_session(session_id=session_id)
                st.session_state.current_session_id = None
                st.session_state.pending_session_selector_id = None
                st.session_state.sessions_loaded = False  # Mark for reload
                st.rerun()
        except Exception as e:
            st.error(f"Error deleting session: {e}")


class ChatComponent(BaseComponent):
    """Main chat interface component"""

    def __init__(self):
        super().__init__("chat")
        self.is_sidebar = False

    def initialize_state(self):
        if 'cached_conversation' not in st.session_state:
            st.session_state.cached_conversation = None
        if 'cached_session_id' not in st.session_state:
            st.session_state.cached_session_id = None
        if 'cached_artifacts_session_id' not in st.session_state:
            st.session_state.cached_artifacts_session_id = None
        if 'cached_artifact_names' not in st.session_state:
            st.session_state.cached_artifact_names = None
        if 'loaded_artifact' not in st.session_state:
            st.session_state.loaded_artifact = None

    def render(self):
        if not st.session_state.adk_client:
            st.info("Please configure server connection in the sidebar")
            return

        if st.session_state.current_session_id:
            self._render_conversation()
            self._render_artifacts()
        else:
            st.info("Please select or create a session to start chatting")

        self._render_chat_input()

    @staticmethod
    def _render_conversation():
        """Render the current conversation with caching"""
        session_id = st.session_state.current_session_id
        
        # get conversation if session changed or cache is empty
        if (st.session_state.cached_session_id != session_id or 
            st.session_state.cached_conversation is None):

            selected_session = st.session_state.adk_client.get_session_by_id(session_id)
            conversations = get_conversations(selected_session)
            
            st.session_state.cached_conversation = conversations
            st.session_state.cached_session_id = session_id
        else:
            conversations = st.session_state.cached_conversation

        if conversations:
            st.subheader("Current Conversation")
            turn_count = 0
            for turn in conversations.values():
                if "user" in turn:
                    with st.chat_message("user"):
                        st.write(turn["user"])
                    turn_count += 1

                if "model" in turn:
                    with st.chat_message("assistant"):
                        st.write(turn["model"])
        else:
            st.info("There is no conversation within this session")

    @staticmethod
    def _artifact_url(session_id: str, artifact_name: str, suffix: str = "") -> str:
        """Build an ADK artifact endpoint URL."""
        encoded_artifact_name = quote(artifact_name, safe="")
        artifact_path = (
            "/artifacts"
            if not encoded_artifact_name
            else f"/artifacts/{encoded_artifact_name}{suffix}"
        )
        return (
            f"{st.session_state.adk_client.base_url}/apps/{settings.APP_NAME}"
            f"/users/{st.session_state.adk_client.encoded_user_id}/sessions/{session_id}"
            f"{artifact_path}"
        )

    @staticmethod
    def _request_json(url: str) -> Any:
        """Request JSON using the existing ADK service HTTP session."""
        response = st.session_state.adk_client.session.get(url)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _load_artifact_names(session_id: str, force_refresh: bool = False) -> list[str]:
        """Load artifact names for the current session."""
        cache_matches_session = st.session_state.cached_artifacts_session_id == session_id
        has_cache = st.session_state.cached_artifact_names is not None

        if cache_matches_session and has_cache and not force_refresh:
            return st.session_state.cached_artifact_names

        artifact_names = ChatComponent._request_json(
            ChatComponent._artifact_url(session_id, "")
        )

        st.session_state.cached_artifacts_session_id = session_id
        st.session_state.cached_artifact_names = artifact_names
        return artifact_names

    @staticmethod
    def _load_artifact_versions_metadata(
        session_id: str,
        artifact_name: str,
    ) -> list[dict[str, Any]]:
        """Load metadata for all artifact versions."""
        return ChatComponent._request_json(
            ChatComponent._artifact_url(
                session_id,
                artifact_name,
                "/versions/metadata",
            )
        )

    @staticmethod
    def _load_artifact_version(
        session_id: str,
        artifact_name: str,
        version: int | str,
    ) -> dict[str, Any]:
        """Load a specific artifact version."""
        return ChatComponent._request_json(
            ChatComponent._artifact_url(
                session_id,
                artifact_name,
                f"/versions/{version}",
            )
        )

    @staticmethod
    def _extract_artifact_data(artifact: dict[str, Any]) -> tuple[Any, bytes, str]:
        """Extract display data, raw bytes, and MIME type from an ADK Part."""
        inline_data = artifact.get("inlineData") or artifact.get("inline_data")
        if inline_data:
            mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or ""
            raw_data = base64.b64decode(inline_data.get("data", ""))

            # Binary formats - return raw bytes without text decoding
            binary_types = ("image/", "application/vnd.", "application/octet-stream",
                           "application/pdf", "application/zip")
            if any(mime_type.startswith(bt) for bt in binary_types):
                return raw_data, raw_data, mime_type

            text_data = raw_data.decode("utf-8")

            if "json" in mime_type:
                return json.loads(text_data), raw_data, mime_type

            return text_data, raw_data, mime_type

        if "text" in artifact:
            text_data = artifact["text"]
            raw_data = text_data.encode("utf-8")
            try:
                return json.loads(text_data), raw_data, "application/json"
            except json.JSONDecodeError:
                return text_data, raw_data, "text/plain"

        raw_data = json.dumps(artifact, indent=2).encode("utf-8")
        return artifact, raw_data, "application/json"

    @staticmethod
    def _render_artifact_payload(payload: Any, mime_type: str = ""):
        """Render artifact content in the most useful available format."""
        # Handle binary image data
        if isinstance(payload, bytes) and mime_type.startswith("image/"):
            st.image(payload, use_container_width=True)
            return

        # Handle binary Excel/other files - just show info (download button is separate)
        if isinstance(payload, bytes):
            st.info(f"Binary artifact ({len(payload)} bytes, type: {mime_type}). Use the download button above.")
            return

        if isinstance(payload, list):
            st.caption(f"{len(payload)} rows")
            if all(isinstance(item, dict) for item in payload):
                st.dataframe(payload, use_container_width=True)
            else:
                st.json(payload)
            return

        if isinstance(payload, dict):
            st.json(payload)
            return

        st.code(str(payload))

    @staticmethod
    def _render_artifacts():
        """Render artifacts attached to the current session."""
        session_id = st.session_state.current_session_id
        if not session_id:
            return

        with st.expander("Artifacts", expanded=False):
            refresh = st.button("Refresh Artifacts", key=f"refresh_artifacts_{session_id}")

            try:
                artifact_names = ChatComponent._load_artifact_names(
                    session_id,
                    force_refresh=refresh,
                )
            except Exception as e:
                st.warning(f"Could not load artifacts: {e}")
                return

            if not artifact_names:
                st.info("No artifacts saved for this session yet")
                return

            preferred_artifact = "sql_command_output.json"
            default_artifact_index = (
                artifact_names.index(preferred_artifact)
                if preferred_artifact in artifact_names
                else 0
            )

            artifact_name = st.selectbox(
                "Artifact",
                options=artifact_names,
                index=default_artifact_index,
                key=f"artifact_selector_{session_id}",
            )

            try:
                versions_metadata = ChatComponent._load_artifact_versions_metadata(
                    session_id,
                    artifact_name,
                )
            except Exception as e:
                st.warning(f"Could not load artifact versions: {e}")
                return

            if not versions_metadata:
                st.info("No versions available for this artifact")
                return

            version_options = [
                metadata.get("version")
                for metadata in sorted(
                    versions_metadata,
                    key=lambda item: item.get("version", 0),
                    reverse=True,
                )
            ]

            selected_version = st.selectbox(
                "Version",
                options=version_options,
                key=f"artifact_version_selector_{session_id}_{artifact_name}",
            )

            selected_metadata = next(
                (
                    metadata
                    for metadata in versions_metadata
                    if metadata.get("version") == selected_version
                ),
                {},
            )
            mime_type = selected_metadata.get("mimeType") or selected_metadata.get("mime_type")
            if mime_type:
                st.caption(f"Type: {mime_type}")

            if st.button(
                "Load Artifact",
                key=f"load_artifact_{session_id}_{artifact_name}_{selected_version}",
            ):
                try:
                    artifact = ChatComponent._load_artifact_version(
                        session_id,
                        artifact_name,
                        selected_version,
                    )
                    payload, raw_data, loaded_mime_type = ChatComponent._extract_artifact_data(
                        artifact
                    )
                except Exception as e:
                    st.error(f"Could not load artifact: {e}")
                    return

                st.session_state.loaded_artifact = {
                    "session_id": session_id,
                    "artifact_name": artifact_name,
                    "version": selected_version,
                    "payload": payload,
                    "raw_data": raw_data,
                    "mime_type": loaded_mime_type,
                }

            loaded_artifact = st.session_state.loaded_artifact
            if not loaded_artifact:
                return

            loaded_artifact_matches_selection = (
                loaded_artifact["session_id"] == session_id
                and loaded_artifact["artifact_name"] == artifact_name
                and loaded_artifact["version"] == selected_version
            )
            if loaded_artifact_matches_selection:
                st.download_button(
                    label="Download Artifact",
                    data=loaded_artifact["raw_data"],
                    file_name=artifact_name,
                    mime=loaded_artifact["mime_type"] or "application/octet-stream",
                    key=f"download_artifact_{session_id}_{artifact_name}_{selected_version}",
                )
                ChatComponent._render_artifact_payload(
                    loaded_artifact["payload"], loaded_artifact["mime_type"]
                )

    def _render_chat_input(self):
        """Render the chat input field"""
        prompt = st.chat_input("Ask me anything...")
        if prompt:
            self._handle_user_message(prompt)

    @staticmethod
    def _extract_text_from_adk_event(event: dict[str, Any]) -> str:
        """Extract displayable text from an ADK event."""
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

    @staticmethod
    def _handle_user_message(message: str):
        """Handle user message and get response"""
    
        if not st.session_state.current_session_id:
            try:
                session = st.session_state.adk_client.create_session()
                st.session_state.current_session_id = session["id"]
                st.session_state.pending_session_selector_id = session["id"]
                st.session_state.sessions_loaded = False
            except Exception as e:
                st.error(f"Error creating session: {e}")
                return

        session_id = st.session_state.current_session_id

        # user message
        with st.chat_message("user"):
            st.write(message)

        # agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response_placeholder = st.empty()
                    streamed_text = ""
                    final_text = ""

                    # /run endpoint
                    response = st.session_state.adk_client.send_message(
                        session_id,
                        message
                    )
                    if response:
                        print(response)
                        if "text" in response[0]["content"]["parts"][0]:
                            st.write(response[0]["content"]["parts"][0]["text"])

                    # /run_sse endpoint
                    # for event in st.session_state.adk_client.send_message_sse(
                    #     session_id,
                    #     message,
                    # ):
                    #     if "error" in event:
                    #         st.error(event["error"])
                    #         return
                    #
                    #     event_text = ChatComponent._extract_text_from_adk_event(event)
                    #     if not event_text:
                    #         continue
                    #
                    #     if event.get("partial"):
                    #         streamed_text += event_text
                    #         response_placeholder.write(streamed_text)
                    #     else:
                    #         final_text = event_text
                    #         if not streamed_text:
                    #             response_placeholder.write(final_text)

                    st.session_state.cached_conversation = None
                    st.session_state.cached_artifact_names = None
                    st.session_state.loaded_artifact = None

                    if streamed_text and final_text and final_text != streamed_text:
                        response_placeholder.write(final_text)

                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error processing query: {e}")


class TermsModal(BaseComponent):
    def __init__(self):
        super().__init__("terms_modal")
        self.is_sidebar = False

    def initialize_state(self):
        if 'accepted_terms' not in st.session_state:
            st.session_state.accepted_terms = None

    @st.dialog("Terms and conditions")
    def _modal(self):
        st.markdown(terms_and_conditions)
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Yes, I accept"):
                st.session_state.accepted_terms = True
                st.rerun()

        with col2:
            if st.button("No, I do not accept"):
                st.session_state.accepted_terms = False
                st.rerun()

    def render(self):
        """If no decision render the modal"""
        if st.session_state.get("accepted_terms") is None:
            self._modal()
