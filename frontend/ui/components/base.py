"""Base class for UI components."""

from abc import ABC, abstractmethod
from typing import Any

import streamlit as st


class BaseComponent(ABC):
    """Base class for all UI components.

    State shared between components lives in `frontend.state`; `get_state` and
    `set_state` are for values that belong to one component only and are
    namespaced with its name to avoid key collisions.
    """

    #: Components with this flag are rendered inside the sidebar by Layout.
    is_sidebar: bool = False

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__
        self.initialize_state()

    def initialize_state(self) -> None:
        """Initialize component-specific session state"""

    @abstractmethod
    def render(self) -> None:
        """Render the component"""

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a component-scoped value from session state"""

        return st.session_state.get(f"{self.name}_{key}", default)

    def set_state(self, key: str, value: Any) -> None:
        """Set a component-scoped value in session state"""

        st.session_state[f"{self.name}_{key}"] = value
