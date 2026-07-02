import streamlit as st
from typing import List
from frontend.ui.components.base import BaseComponent


class Layout:
    """Main layout manager for the application"""

    def __init__(self):
        self.sidebar_components = []
        self.main_components = []

    def render(self, components: List[BaseComponent]):
        """Render all components in their appropriate sections"""

        for component in components:
            if hasattr(component, 'is_sidebar') and component.is_sidebar:
                self.sidebar_components.append(component)
            else:
                self.main_components.append(component)

        # sidebar components
        with st.sidebar:
            for component in self.sidebar_components:
                component.render()

        # main components
        for component in self.main_components:
            component.render()