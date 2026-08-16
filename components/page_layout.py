"""Shared layout helpers for application pages."""

import streamlit as st


def render_page_header(title: str, description: str) -> None:
    """Render a consistent title and temporary page description."""
    st.title(title)
    st.info(description)
