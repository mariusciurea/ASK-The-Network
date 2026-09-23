"""Session state keys and the resets that go with them.

Streamlit keeps everything in one flat dictionary, so the keys were spelled out
by hand in several places and the "clear everything" block was copy-pasted three
times - one forgotten key there means a user sees the previous user's cached
conversation after a logout. Both live here now.
"""

from typing import Any

import streamlit as st


# --- keys -------------------------------------------------------------------

ACCEPTED_TERMS = "accepted_terms"

AUTH_TOKEN = "auth_token"
AUTH_USER = "auth_user"

ADK_CLIENT = "adk_client"

CURRENT_SESSION_ID = "current_session_id"
PENDING_SESSION_ID = "pending_session_selector_id"
SESSION_SELECTOR = "session_selector"
ALL_SESSION_IDS = "all_session_ids"
ALL_SESSION_LABELS = "all_session_conversations"
SESSIONS_LOADED = "sessions_loaded"

CACHED_CONVERSATION = "cached_conversation"
CACHED_CONVERSATION_SESSION_ID = "cached_session_id"
CACHED_ARTIFACT_NAMES = "cached_artifact_names"
CACHED_ARTIFACTS_SESSION_ID = "cached_artifacts_session_id"
LOADED_ARTIFACT = "loaded_artifact"

# Everything that belongs to one conversation. Cleared when the session
# changes, when a message is sent, and on logout.
_SESSION_SCOPED: dict[str, Any] = {
    CURRENT_SESSION_ID: None,
    PENDING_SESSION_ID: None,
    ALL_SESSION_IDS: [],
    ALL_SESSION_LABELS: [],
    SESSIONS_LOADED: False,
    CACHED_CONVERSATION: None,
    CACHED_CONVERSATION_SESSION_ID: None,
    CACHED_ARTIFACT_NAMES: None,
    CACHED_ARTIFACTS_SESSION_ID: None,
    LOADED_ARTIFACT: None,
}

# Everything that identifies the user.
_AUTH_SCOPED: dict[str, Any] = {
    AUTH_TOKEN: None,
    AUTH_USER: None,
    ADK_CLIENT: None,
}


def init_state() -> None:
    """Create every key the app reads, so no component has to guess."""

    st.session_state.setdefault(ACCEPTED_TERMS, None)

    for key, default in {**_AUTH_SCOPED, **_SESSION_SCOPED}.items():
        st.session_state.setdefault(key, default)


def reset_conversation_state() -> None:
    """Forget the selected conversation and everything cached about it."""

    for key, default in _SESSION_SCOPED.items():
        st.session_state[key] = default

    # the selectbox keeps its own widget key
    st.session_state.pop(SESSION_SELECTOR, None)


def reset_user_state() -> None:
    """Forget the user. Used on login, logout and auth failures."""

    for key, default in _AUTH_SCOPED.items():
        st.session_state[key] = default

    reset_conversation_state()


def invalidate_caches() -> None:
    """Drop cached conversation and artifacts after the data changed."""

    st.session_state[CACHED_CONVERSATION] = None
    st.session_state[CACHED_CONVERSATION_SESSION_ID] = None
    st.session_state[CACHED_ARTIFACT_NAMES] = None
    st.session_state[CACHED_ARTIFACTS_SESSION_ID] = None
    st.session_state[LOADED_ARTIFACT] = None
