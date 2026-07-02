import streamlit as st
from frontend.ui.components.layout import Layout
from settings import settings
from frontend.ui.components.components import (
    AuthComponent,
    SidebarComponent,
    ChatComponent,
    SessionManagerComponent,
    TermsModal,
)


st.set_page_config(
    page_title=f"Ask The Network {settings.APP_VERSION}",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """Main app function"""

    layout = Layout()

    terms = TermsModal()
    terms.render()

    if st.session_state.accepted_terms is True:
        auth = AuthComponent()
        if not st.session_state.auth_token:
            auth.render()
            st.stop()

        sidebar = SidebarComponent()
        session_manager = SessionManagerComponent()
        chat = ChatComponent()

        layout.render([sidebar, session_manager, chat])

    elif st.session_state.accepted_terms is False:
        st.error("You have not accepted the terms and conditions. "
                 "If you want to run the application please accept the terms and conditions")
        st.stop()


if __name__ == "__main__":
    main()
