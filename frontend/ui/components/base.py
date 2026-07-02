from abc import ABC, abstractmethod
import streamlit as st


class BaseComponent(ABC):
    """Base class for all UI components"""

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.initialize_state()

    def initialize_state(self):
        """Initialize component-specific session state"""
        pass

    @abstractmethod
    def render(self):
        """Render the component"""
        pass

    def get_state(self, key: str, default=None):
        """Get value from session state"""
        return st.session_state.get(f"{self.name}_{key}", default)

    def set_state(self, key: str, value):
        """Set value in session state"""
        st.session_state[f"{self.name}_{key}"] = value