"""Job preferences page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the job preferences placeholder."""
    render_page_header(
        "Job Preferences",
        "Define your target roles, locations, work style, and other priorities.",
    )
