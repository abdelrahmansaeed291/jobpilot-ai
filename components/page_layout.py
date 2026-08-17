"""Shared layout helpers for application pages."""

from components.app_theme import render_feature_hero


def render_page_header(title: str, description: str) -> None:
    """Render a consistent colorful header for standard application pages."""
    render_feature_hero("JobPilot AI", title, description, "✦")
