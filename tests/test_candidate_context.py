"""Tests for normalized candidate context assembly."""

from models.candidate_context import (
    AdditionalProject,
    CandidateExtraInformation,
    CandidateSkill,
    JobPreferences,
    SkillSource,
)
from models.candidate_profile import CandidateProfile, ProjectEntry
from services.candidate_context_service import build_normalized_candidate_profile


def test_normalizer_combines_cv_extra_information_and_preferences() -> None:
    """Agents should receive one CandidateProfile-compatible enriched object."""
    cv = CandidateProfile(
        name="Candidate",
        technical_skills=["Python"],
        projects=[ProjectEntry(name="CV Project", technologies=["Python"])],
    )
    extra = CandidateExtraInformation(
        skills=[CandidateSkill(skill_name="Rust", source=SkillSource.MANUAL)],
        projects=[AdditionalProject(project_name="Manual Project", github_url="https://example.com")],
        other_information="Open-source contributor",
    )
    preferences = JobPreferences(target_job_titles=["AI Engineer"])

    normalized = build_normalized_candidate_profile(cv, extra, preferences)

    assert isinstance(normalized, CandidateProfile)
    assert normalized.technical_skills == ["Rust"]
    assert [project.name for project in normalized.projects] == [
        "CV Project",
        "Manual Project",
    ]
    assert normalized.other_information == "Open-source contributor"
    assert normalized.job_preferences.target_job_titles == ["AI Engineer"]


def test_normalizer_uses_cv_skills_when_extra_record_does_not_exist() -> None:
    """A profile remains usable before the user saves Extra Information."""
    normalized = build_normalized_candidate_profile(
        CandidateProfile(technical_skills=["Python", "SQL"]), None, None
    )

    assert normalized.technical_skills == ["Python", "SQL"]
    assert all(skill.source == SkillSource.CV for skill in normalized.skill_details)
