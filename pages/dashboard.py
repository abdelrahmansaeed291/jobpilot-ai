"""Dashboard page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the dashboard placeholder."""
    render_page_header(
        "Dashboard",
        "Your job-search overview, activity, and next actions will appear here.",
    )
