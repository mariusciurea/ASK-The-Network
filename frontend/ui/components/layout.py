"""Layout manager."""

from typing import Sequence

import streamlit as st

from frontend.ui.components.base import BaseComponent


class Layout:
    """Main layout manager for the application"""

    @staticmethod
    def render(components: Sequence[BaseComponent]) -> None:
        """Render every component in its section, sidebar first."""

        sidebar_components = [c for c in components if c.is_sidebar]
        main_components = [c for c in components if not c.is_sidebar]

        with st.sidebar:
            for component in sidebar_components:
                component.render()

        for component in main_components:
            component.render()
