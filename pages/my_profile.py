"""Candidate profile page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the candidate profile placeholder."""
    render_page_header(
        "My Profile",
        "Build and maintain the professional profile used in your applications.",
    )
