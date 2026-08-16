"""Interview preparation page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the interview preparation placeholder."""
    render_page_header(
        "Interview Preparation",
        "Practice likely questions and organize job-specific interview notes here.",
    )
