"""Job analysis page."""

from components.page_layout import render_page_header


def render() -> None:
    """Render the job analysis placeholder."""
    render_page_header(
        "Analyze Job",
        "Compare a job description with your profile and identify important gaps.",
    )
