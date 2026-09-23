"""Entrypoint"""

import logging

import streamlit as st

from frontend import state
from frontend.settings import settings
from frontend.ui.components.auth import AuthComponent
from frontend.ui.components.chat import ChatComponent
from frontend.ui.components.layout import Layout
from frontend.ui.components.sessions import SessionManagerComponent
from frontend.ui.components.sidebar import SidebarComponent
from frontend.ui.components.terms import TermsModal


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

st.set_page_config(
    page_title=f"Ask The Network {settings.APP_VERSION}",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """Main app function"""

    state.init_state()

    TermsModal().render()

    if st.session_state[state.ACCEPTED_TERMS] is False:
        st.error("You have not accepted the terms and conditions. "
                 "If you want to run the application please accept the terms and conditions")
        st.stop()

    if st.session_state[state.ACCEPTED_TERMS] is not True:
        return

    if not st.session_state[state.AUTH_TOKEN]:
        AuthComponent().render()
        st.stop()

    Layout().render([
        SidebarComponent(),
        SessionManagerComponent(),
        ChatComponent(),
    ])


if __name__ == "__main__":
    main()
