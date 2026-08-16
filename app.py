"""Streamlit entry point for JobPilot AI."""

import streamlit as st

from components.navigation import build_navigation
from utils.config import load_environment


def main() -> None:
    """Configure the application and run the selected Streamlit page."""
    st.set_page_config(
        page_title="JobPilot AI",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_environment()

    st.sidebar.title("JobPilot AI")
    st.sidebar.caption("Your personal job-search copilot")
    build_navigation().run()


if __name__ == "__main__":
    main()
