"""Terms and conditions gate."""

import streamlit as st

from frontend import state
from frontend.helpers.terms import terms_and_conditions
from frontend.ui.components.base import BaseComponent


class TermsModal(BaseComponent):
    """Blocking modal shown until the user accepts or declines the terms."""

    def __init__(self):
        super().__init__("terms_modal")
        self.is_sidebar = False

    @st.dialog("Terms and conditions")
    def _modal(self):
        st.markdown(terms_and_conditions)
        accept_column, decline_column = st.columns(2)

        with accept_column:
            if st.button("Yes, I accept"):
                st.session_state[state.ACCEPTED_TERMS] = True
                st.rerun()

        with decline_column:
            if st.button("No, I do not accept"):
                st.session_state[state.ACCEPTED_TERMS] = False
                st.rerun()

    def render(self):
        """If no decision has been taken yet, render the modal."""

        if st.session_state.get(state.ACCEPTED_TERMS) is None:
            self._modal()
