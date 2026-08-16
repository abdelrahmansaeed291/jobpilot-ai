"""Job discovery page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the job discovery placeholder."""
    render_page_header(
        "Find Jobs",
        "Search for relevant opportunities and review potential matches here.",
    )
