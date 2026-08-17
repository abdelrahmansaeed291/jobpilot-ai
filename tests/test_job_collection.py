"""Tests for configuration-driven, unfiltered LinkedIn job collection."""

from datetime import datetime, timezone

from models.candidate_context import JobPreferences, NormalizedCandidateProfile
from services.job_collection import (
    JobCollectionService,
    JobSearchConfiguration,
    JobSearchDefinition,
    TavilyLinkedInProvider,
    deduplicate_collected_jobs,
    extract_linkedin_job_id,
    load_job_search_configuration,
    matching_employment_types,
    matches_configured_country,
    posted_age_hours,
)


class FakeLinkedInProvider:
    name = "LinkedIn"

    def search(self, definition: JobSearchDefinition) -> list[dict[str, str]]:
        if definition.category == "Failed Search":
            raise RuntimeError("provider unavailable")
        return [
            {
                "title": "Acme hiring Software Engineer in Berlin | LinkedIn",
                "url": "https://www.linkedin.com/jobs/view/software-engineer-123456",
                "content": "Posted 2 hours ago. Full-time role in Berlin, Germany.",
            },
            {
                "title": "Unexpected Accountant at Other Co | LinkedIn",
                "url": "https://www.linkedin.com/jobs/view/unexpected-accountant-987654",
                "content": "Posted 1 hour ago in Hamburg, Germany. Full-time position that intentionally does not match the configured role.",
            },
        ]


class MixedEligibilityProvider:
    name = "LinkedIn"

    def search(self, definition: JobSearchDefinition) -> list[dict[str, str]]:
        return [
            {
                "title": "Valid Engineer | LinkedIn",
                "url": "https://www.linkedin.com/jobs/view/valid-engineer-100001",
                "content": "Berlin, Germany · 3 hours ago · Full-time",
            },
            {
                "title": "Old Engineer | LinkedIn",
                "url": "https://www.linkedin.com/jobs/view/old-engineer-100002",
                "content": "Munich, Germany · 2 days ago · Full-time",
            },
            {
                "title": "Wrong Country Engineer | LinkedIn",
                "url": "https://www.linkedin.com/jobs/view/wrong-country-100003",
                "content": "Cairo, Egypt · 2 hours ago · Full-time",
            },
            {
                "title": "Unknown Age Engineer | LinkedIn",
                "url": "https://www.linkedin.com/jobs/view/unknown-age-100004",
                "content": "Hamburg, Germany · Full-time",
            },
        ]


class CapturingSearchClient:
    def __init__(self) -> None:
        self.query = ""
        self.options: dict[str, object] = {}

    def search(self, query: str, **kwargs: object) -> dict[str, object]:
        self.query = query
        self.options = kwargs
        return {"results": []}


def _candidate() -> NormalizedCandidateProfile:
    return NormalizedCandidateProfile(
        location="Germany",
        job_preferences=JobPreferences(
            target_job_titles=["Software Engineer"],
            preferred_locations=["Germany", "Egypt"],
        ),
    )


def test_default_configuration_contains_six_germany_and_three_egypt_searches() -> None:
    configuration = load_job_search_configuration()
    assert len(configuration.searches) == 9
    assert sum(item.country == "Germany" for item in configuration.searches) == 6
    assert sum(item.country == "Egypt" for item in configuration.searches) == 3
    assert all(item.date_posted == "24h" for item in configuration.searches)


def test_provider_search_text_contains_category_but_not_job_type() -> None:
    client = CapturingSearchClient()
    provider = TavilyLinkedInProvider(client)
    provider.search(
        JobSearchDefinition(
            country="Germany",
            category="Data Science",
            keywords="Data Science",
            employment_types=["Internship", "Working Student"],
        )
    )
    assert '"Data Science"' in client.query
    assert "Internship" not in client.query
    assert "Working Student" not in client.query
    assert client.options["time_range"] == "day"


def test_linkedin_job_id_is_used_for_deduplication() -> None:
    assert (
        extract_linkedin_job_id(
            "https://www.linkedin.com/jobs/view/software-engineer-123456?trackingId=x"
        )
        == "123456"
    )


def test_strict_country_and_posting_age_parsing() -> None:
    now = datetime(2026, 8, 16, 18, 0, tzinfo=timezone.utc)
    assert matches_configured_country("Software Engineer — München", "Germany")
    assert matches_configured_country("Data Scientist in New Cairo", "Egypt")
    assert not matches_configured_country("Software Engineer in London", "Germany")
    assert posted_age_hours("35 minutes ago", now) < 1
    assert posted_age_hours("24 hours ago", now) == 24
    assert posted_age_hours("2 days ago", now) == 48
    assert posted_age_hours("Not specified", now) is None
    assert matching_employment_types(
        "Werkstudent Data Science in Berlin", ["Internship", "Working Student"]
    ) == ["Working Student"]


def test_collection_keeps_nonmatching_jobs_and_only_removes_duplicates() -> None:
    configuration = JobSearchConfiguration(
        searches=[
            JobSearchDefinition(
                country="Germany",
                category="Software Engineering",
                keywords="Software Engineer",
                employment_types=["Full-time"],
            ),
            JobSearchDefinition(
                country="Germany",
                category="Data Science",
                keywords="Data Science Engineer",
                employment_types=["Full-time"],
            ),
            JobSearchDefinition(
                country="Egypt",
                category="Failed Search",
                keywords="Failure",
                employment_types=["Full-time"],
            ),
        ]
    )

    report = JobCollectionService(FakeLinkedInProvider()).collect(
        _candidate(), configuration
    )

    assert report.discovered_count == 4
    assert report.criteria_rejected == 0
    assert report.duplicates_removed == 2
    assert len(report.results) == 2
    assert any(job.title == "Unexpected Accountant" for job in report.results)
    assert report.searches_succeeded == 2
    assert report.searches_failed == ["Egypt · Failed Search · Full-time"]
    assert report.results[0].posted_date == "1 hour ago"


def test_collection_rejects_old_wrong_country_and_unknown_age_results() -> None:
    configuration = JobSearchConfiguration(
        searches=[
            JobSearchDefinition(
                country="Germany",
                category="Software Engineering",
                keywords="Software Engineer",
                employment_types=["Full-time"],
            )
        ]
    )

    report = JobCollectionService(MixedEligibilityProvider()).collect(
        _candidate(), configuration
    )

    assert [job.title for job in report.results] == ["Valid Engineer"]
    assert report.criteria_rejected == 3
    assert report.discovered_count == 1
