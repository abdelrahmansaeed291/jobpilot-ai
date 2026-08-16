"""Application tracking page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the application tracking placeholder."""
    render_page_header(
        "My Applications",
        "Track applications, statuses, deadlines, and follow-up actions here.",
    )
