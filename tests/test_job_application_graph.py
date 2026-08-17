"""Tests for LangGraph node execution and conditional routing."""

from agents.job_application_graph import (
    JobWorkflowDependencies,
    build_job_application_graph,
)
from models.candidate_context import JobPreferences, NormalizedCandidateProfile
from models.job_profile import JobProfile, MatchResult


class FakeAnalyzer:
    def analyze(self, job_description: str) -> JobProfile:
        return JobProfile(
            job_title="AI Engineer",
            company="Acme",
            location="Munich",
            required_skills=["Python"],
            raw_description=job_description,
        )


class FixedMatcher:
    def __init__(self, score: float) -> None:
        self.score = score

    def match(self, candidate: object, job: object) -> MatchResult:
        recommendation = "Apply" if self.score >= 70 else "Low Match"
        return MatchResult(
            overall_match=self.score,
            required_skills_score=self.score,
            preferred_skills_score=self.score,
            experience_score=self.score,
            education_score=self.score,
            language_score=self.score,
            responsibility_score=self.score,
            preference_score=self.score,
            recommendation=recommendation,
            strong_matches=["Required skill: Python"] if self.score >= 70 else [],
            missing_requirements=[] if self.score >= 70 else ["Required skill: Python"],
        )


def _profile() -> dict[str, object]:
    return NormalizedCandidateProfile(
        name="Candidate",
        technical_skills=["Python"],
        job_preferences=JobPreferences(minimum_match_score=70),
    ).model_dump(mode="json")


def test_weak_match_stops_before_expensive_nodes() -> None:
    calls = {"research": 0}

    def research(job: dict[str, object]) -> dict[str, object]:
        calls["research"] += 1
        return {"company": job.get("company")}

    graph = build_job_application_graph(
        JobWorkflowDependencies(
            profile_loader=_profile,
            job_analyzer=FakeAnalyzer(),
            match_engine=FixedMatcher(50),  # type: ignore[arg-type]
            company_researcher=research,
        )
    )
    result = graph.invoke(
        {"raw_job_description": "A complete AI Engineer job description " * 4, "messages": [], "execution_log": []}
    )

    assert calls["research"] == 0
    assert result["execution_log"] == [
        "profile_loader",
        "job_analyzer",
        "match_agent",
        "weak_match_explainer",
    ]


def test_strong_match_rewrites_then_routes_to_interview() -> None:
    writer_calls = {"count": 0}

    def writer(state: dict[str, object]) -> dict[str, object]:
        writer_calls["count"] += 1
        return {"attempt": writer_calls["count"], "claims": []}

    def critic(
        application: dict[str, object], candidate: dict[str, object]
    ) -> dict[str, object]:
        passed = application.get("attempt") == 2
        return {
            "passed": passed,
            "unsupported_claims": [] if passed else ["Unsupported draft claim"],
        }

    graph = build_job_application_graph(
        JobWorkflowDependencies(
            profile_loader=_profile,
            job_analyzer=FakeAnalyzer(),
            match_engine=FixedMatcher(80),  # type: ignore[arg-type]
            company_researcher=lambda job: {"company": job.get("company")},
            application_writer=writer,  # type: ignore[arg-type]
            critic=critic,
            interview_preparer=lambda state: {"questions": ["Why this role?"]},
            max_write_attempts=2,
        )
    )
    result = graph.invoke(
        {
            "raw_job_description": "A complete AI Engineer job description " * 4,
            "include_interview": True,
            "messages": [],
            "execution_log": [],
        }
    )

    assert writer_calls["count"] == 2
    assert result["validation_result"]["passed"] is True
    assert result["interview_content"]["questions"] == ["Why this role?"]
    assert result["execution_log"].count("application_writer_agent") == 2
    assert result["execution_log"][-1] == "interview_agent"
