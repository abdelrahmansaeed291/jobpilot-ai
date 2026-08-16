"""Application assistant page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the application assistant placeholder."""
    render_page_header(
        "Application Assistant",
        "Prepare tailored application materials with guided AI assistance here.",
    )
