"""Tests for safe native job-portal search links."""

from urllib.parse import parse_qs, urlparse

from models.candidate_context import (
    EmploymentType,
    JobPreferences,
    NormalizedCandidateProfile,
    SearchRecency,
    WorkMode,
)
from services.job_portal_links import (
    build_configured_linkedin_search_link,
    build_linkedin_search_links,
)


def test_linkedin_links_apply_saved_native_filters() -> None:
    candidate = NormalizedCandidateProfile(
        job_preferences=JobPreferences(
            target_job_titles=["Software Engineer"],
            preferred_locations=["Germany", "Egypt"],
            employment_types=[
                EmploymentType.FULL_TIME,
                EmploymentType.PART_TIME,
                EmploymentType.WORKING_STUDENT,
                EmploymentType.INTERNSHIP,
            ],
            work_modes=[WorkMode.REMOTE, WorkMode.HYBRID, WorkMode.ONSITE],
            search_recency=SearchRecency.HOURS_24,
        )
    )

    links = build_linkedin_search_links(candidate)

    assert len(links) == 4
    standard = parse_qs(urlparse(links[0].url).query)
    assert standard["keywords"] == ["Software Engineer"]
    assert standard["location"] == ["Germany"]
    assert standard["f_TPR"] == ["r86400"]
    assert standard["f_JT"] == ["F,P,I"]
    assert standard["sortBy"] == ["DD"]
    assert any(link.role == "Working Student" for link in links)


def test_configured_linkedin_student_search_applies_exact_native_filters() -> None:
    link = build_configured_linkedin_search_link(
        country="Germany",
        category="Data Science",
        keywords="Data Science Engineer",
        employment_types=["Internship", "Working Student"],
    )
    parameters = parse_qs(urlparse(link.url).query)
    assert parameters["location"] == ["Germany"]
    assert parameters["f_TPR"] == ["r86400"]
    assert parameters["sortBy"] == ["DD"]
    assert parameters["f_JT"] == ["I,P"]
    assert parameters["keywords"] == ["Data Science"]
    assert "Working Student" not in parameters["keywords"][0]
    assert "Internship" not in parameters["keywords"][0]
