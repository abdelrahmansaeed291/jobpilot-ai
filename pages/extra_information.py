"""Extra candidate information page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the extra information placeholder."""
    render_page_header(
        "Extra Information",
        "Store relevant achievements, stories, links, and supporting details here.",
    )
