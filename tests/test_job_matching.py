"""Unit tests for deterministic job scoring functions."""

from models.candidate_context import JobPreferences, NormalizedCandidateProfile
from models.candidate_profile import EducationEntry, LanguageEntry, WorkExperienceEntry
from models.job_profile import (
    ExperienceRequirement,
    JobLanguageRequirement,
    JobProfile,
)
from services.job_matching import (
    JobMatchingEngine,
    calculate_experience_years,
    classify_recommendation,
    compare_skills,
    normalize_skill,
    weighted_overall,
)


class TokenSimilarity:
    """Fast deterministic semantic stand-in for unit tests."""

    def similarity(self, left: str, right: str) -> float:
        left_tokens = set(normalize_skill(left).split())
        right_tokens = set(normalize_skill(right).split())
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def test_skill_normalization_and_exact_alias_matching() -> None:
    """Common aliases should count as exact rather than LLM-inferred matches."""
    comparison = compare_skills(
        ["PostgreSQL", "JavaScript"], ["Postgres", "JS"], TokenSimilarity()
    )

    assert normalize_skill("C++") == "cpp"
    assert comparison.score == 100
    assert comparison.strong == ["Postgres", "JS"]


def test_experience_months_are_not_double_counted() -> None:
    """Overlapping roles should not inflate total documented experience."""
    years = calculate_experience_years(
        [
            WorkExperienceEntry(start_date="Jan 2020", end_date="Dec 2021"),
            WorkExperienceEntry(start_date="Jan 2021", end_date="Dec 2022"),
        ]
    )

    assert years == 3.0


def test_weighting_and_recommendation_boundaries() -> None:
    """The published component weights and thresholds must remain stable."""
    overall = weighted_overall(
        {
            "required_skills": 100,
            "preferred_skills": 80,
            "experience": 75,
            "education": 100,
            "languages": 100,
            "responsibility": 60,
            "preference": 80,
        }
    )

    assert overall == 89.0
    assert classify_recommendation(85) == "Strong Apply"
    assert classify_recommendation(70) == "Apply"
    assert classify_recommendation(55) == "Consider"
    assert classify_recommendation(54.9) == "Low Match"


def test_matching_engine_reports_missing_required_skills_deterministically() -> None:
    """Missing requirements should lower the score and remain explainable."""
    candidate = NormalizedCandidateProfile(
        technical_skills=["Python", "PostgreSQL"],
        education=[EducationEntry(degree="M.Sc.", field_of_study="Data Science")],
        languages=[LanguageEntry(name="English", proficiency="Fluent")],
        work_experience=[
            WorkExperienceEntry(
                job_title="AI Engineer",
                start_date="Jan 2022",
                end_date="Dec 2024",
                description="Built Python machine learning services",
            )
        ],
        job_preferences=JobPreferences(minimum_match_score=0),
    )
    job = JobProfile(
        job_title="AI Engineer",
        required_skills=["Python", "Kubernetes"],
        preferred_skills=["PostgreSQL"],
        experience_requirements=ExperienceRequirement(minimum_years=2),
        responsibilities=["Build Python machine learning services"],
        education_requirements=["Master degree in Data Science"],
        language_requirements=[
            JobLanguageRequirement(language="English", proficiency="Fluent"),
            JobLanguageRequirement(
                language="German", proficiency="Basic", required=False
            ),
        ],
    )

    result = JobMatchingEngine(TokenSimilarity()).match(candidate, job)

    assert result.required_skills_score == 50
    assert "Required skill: Kubernetes" in result.missing_requirements
    assert result.preferred_skills_score == 100
    assert result.language_score == 100
    assert "Preferred language: German Basic" in result.nice_to_have_gaps
    assert result.overall_match == weighted_overall(
        {
            "required_skills": result.required_skills_score,
            "preferred_skills": result.preferred_skills_score,
            "experience": result.experience_score,
            "education": result.education_score,
            "languages": result.language_score,
            "responsibility": result.responsibility_score,
            "preference": result.preference_score,
        }
    )
