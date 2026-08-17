"""Tests for the application page registry."""

from components.navigation import PAGE_SPECS


def test_all_expected_pages_are_registered() -> None:
    """The navigation should expose every page in the product outline."""
    assert [page.title for page in PAGE_SPECS] == [
        "Dashboard",
        "My Profile",
        "CV & Extra Information",
        "Job Preferences",
        "Find Jobs",
        "Analyze Job",
        "Application Assistant",
        "Interview Preparation",
        "My Applications",
    ]


def test_page_paths_are_unique() -> None:
    """Each page needs an unambiguous URL path."""
    paths = [page.url_path for page in PAGE_SPECS]
    assert len(paths) == len(set(paths))
