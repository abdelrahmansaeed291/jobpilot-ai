"""Tests for query generation, normalization, deduplication, and discovery costs."""

from datetime import date

from models.candidate_context import (
    EmploymentType,
    JobPreferences,
    NormalizedCandidateProfile,
    SearchRecency,
)
from models.job_profile import JobProfile
from services.job_discovery import (
    JobDiscoveryService,
    deduplicate_jobs,
    generate_search_queries,
    normalize_search_result,
)
from services.job_matching import JobMatchingEngine


class FakeSemantic:
    """Predictable similarity implementation that avoids loading an ML model."""

    def similarity(self, left: str, right: str) -> float:
        left_words = set(left.casefold().split())
        right_words = set(right.casefold().split())
        return 0.9 if left_words & right_words else 0.2


class FakeSearchClient:
    def __init__(self, results: list[dict[str, str]]) -> None:
        self.results = results
        self.calls: list[tuple[str, dict[str, object]]] = []

    def search(self, query: str, **kwargs: object) -> dict[str, object]:
        self.calls.append((query, kwargs))
        return {"results": self.results}


class FakeAnalyzer:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, job_description: str) -> JobProfile:
        self.calls += 1
        return JobProfile(
            job_title="AI Engineer",
            company="Acme",
            location="Munich, Germany",
            employment_type="Full-time",
            responsibilities=["Build Python machine learning systems"],
            required_skills=["Python"],
            preferred_skills=["Machine Learning"],
            raw_description=job_description,
        )


def _candidate() -> NormalizedCandidateProfile:
    return NormalizedCandidateProfile(
        name="Candidate",
        location="Munich, Germany",
        professional_summary="AI software engineer",
        technical_skills=["Python", "Machine Learning", "LangGraph"],
        job_preferences=JobPreferences(
            target_job_titles=["AI Engineer", "Machine Learning Engineer"],
            preferred_locations=["Munich"],
            country="Germany",
            employment_types=[EmploymentType.FULL_TIME],
            search_recency=SearchRecency.DAYS_3,
            minimum_match_score=60,
        ),
    )


def test_search_queries_use_roles_location_type_and_skills() -> None:
    queries = generate_search_queries(_candidate())
    combined = " ".join(queries)
    assert '"AI Engineer"' in combined
    assert "Munich" in combined
    assert "Full-time" in combined
    assert "Python" in combined
    assert "site:linkedin.com/jobs" in combined
    assert "site:stepstone.de" in combined
    assert "site:indeed.com" in combined
    assert "site:xing.com/jobs" in combined


def test_normalization_and_cross_site_deduplication() -> None:
    candidate = _candidate()
    linked_in = normalize_search_result(
        {
            "title": "Acme hiring AI Engineer in Munich | LinkedIn",
            "url": "https://linkedin.com/jobs/view/123?utm_source=test",
            "content": "Acme is hiring a Python AI engineer in Munich.",
        },
        candidate,
    )
    indeed = normalize_search_result(
        {
            "title": "AI Engineer at Acme | Indeed",
            "url": "https://indeed.de/viewjob?id=456",
            "content": "Full-time AI Engineer job using Python in Munich.",
        },
        candidate,
    )
    assert linked_in is not None and indeed is not None
    assert linked_in.title == "AI Engineer"
    assert linked_in.company == "Acme"
    assert len(deduplicate_jobs([linked_in, indeed])) == 1


def test_discovery_only_analyzes_semantic_shortlist() -> None:
    search = FakeSearchClient(
        [
            {
                "title": "AI Engineer at Acme | Careers",
                "url": "https://acme.example/jobs/ai-engineer",
                "content": "Join our AI engineering job in Munich. Build Python machine learning services and production APIs.",
            },
            {
                "title": "Machine Learning Engineer at Beta | Careers",
                "url": "https://beta.example/careers/ml-engineer",
                "content": "Machine learning engineer vacancy in Germany using Python, Docker, and cloud platforms.",
            },
            {
                "title": "Data Engineer at Gamma | Careers",
                "url": "https://gamma.example/jobs/data-engineer",
                "content": "Data engineer job working on SQL and Python pipelines in Germany with an international team.",
            },
        ]
    )
    analyzer = FakeAnalyzer()
    semantic = FakeSemantic()
    service = JobDiscoveryService(
        search_client=search,
        semantic=semantic,
        analyzer=analyzer,
        matcher=JobMatchingEngine(semantic),
        today=date(2026, 8, 16),
    )

    report = service.discover(
        _candidate(), max_queries=2, results_per_query=5, detailed_limit=2
    )

    assert report.discovered_count == 6
    assert len(report.results) == 2
    assert analyzer.calls == 2
    assert report.jobs_analyzed_with_llm == 2
    assert all(
        call[1]["start_date"] == "2026-08-13" for call in search.calls
    )
    assert report.results == sorted(
        report.results, key=lambda item: item.match_score, reverse=True
    )
