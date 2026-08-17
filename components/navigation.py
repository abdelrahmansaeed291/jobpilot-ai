"""Application navigation configuration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import streamlit as st

from pages.analyze_job import render as render_analyze_job
from pages.application_assistant import render as render_application_assistant
from pages.dashboard import render as render_dashboard
from pages.extra_information import render as render_extra_information
from pages.find_jobs import render as render_find_jobs
from pages.interview_preparation import render as render_interview_preparation
from pages.job_preferences import render as render_job_preferences
from pages.my_applications import render as render_my_applications
from pages.my_profile import render as render_my_profile


@dataclass(frozen=True)
class PageSpec:
    """Metadata needed to register one application page."""

    title: str
    url_path: str
    render: Callable[[], None]
    icon: str


class NavigationController(Protocol):
    """Minimal interface returned by Streamlit's navigation builder."""

    def run(self) -> None:
        """Render the page selected by the user."""
        ...


PAGE_SPECS: tuple[PageSpec, ...] = (
    PageSpec("Dashboard", "dashboard", render_dashboard, "🏠"),
    PageSpec("My Profile", "my-profile", render_my_profile, "👤"),
    PageSpec(
        "CV & Extra Information", "extra-information", render_extra_information, "✨"
    ),
    PageSpec("Job Preferences", "job-preferences", render_job_preferences, "🎯"),
    PageSpec("Find Jobs", "find-jobs", render_find_jobs, "🔎"),
    PageSpec("Analyze Job", "analyze-job", render_analyze_job, "🧠"),
    PageSpec(
        "Application Assistant",
        "application-assistant",
        render_application_assistant,
        "📝",
    ),
    PageSpec(
        "Interview Preparation",
        "interview-preparation",
        render_interview_preparation,
        "🎤",
    ),
    PageSpec("My Applications", "my-applications", render_my_applications, "📋"),
)


def build_navigation() -> NavigationController:
    """Build and return the sidebar navigation controller."""
    pages = [
        st.Page(
            spec.render,
            title=spec.title,
            url_path=spec.url_path,
            icon=spec.icon,
        )
        for spec in PAGE_SPECS
    ]
    return st.navigation(pages, position="sidebar")
