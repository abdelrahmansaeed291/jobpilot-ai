"""Build the normalized candidate context consumed by every agent."""

import re

from models.candidate_context import (
    CandidateExtraInformation,
    CandidateSkill,
    JobPreferences,
    NormalizedCandidateProfile,
    SkillProficiency,
    SkillSource,
)
from models.candidate_profile import (
    CandidateProfile,
    CertificationEntry,
    ProjectEntry,
)


def _key(value: str) -> str:
    """Create a stable comparison key for names and labels."""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _unique_by_name(items: list[object], attribute: str) -> list[object]:
    """Deduplicate Pydantic entries by a named string attribute."""
    seen: set[str] = set()
    result: list[object] = []
    for item in items:
        item_key = _key(str(getattr(item, attribute, "")))
        if item_key and item_key not in seen:
            seen.add(item_key)
            result.append(item)
    return result


def build_normalized_candidate_profile(
    cv_profile: CandidateProfile,
    extra_information: CandidateExtraInformation | None,
    preferences: JobPreferences | None,
) -> NormalizedCandidateProfile:
    """Combine CV, manual information, and preferences into one agent profile."""
    if extra_information is None:
        skill_details = [
            CandidateSkill(
                skill_name=skill,
                proficiency_level=SkillProficiency.INTERMEDIATE,
                source=SkillSource.CV,
            )
            for skill in cv_profile.technical_skills
        ]
        extra_information = CandidateExtraInformation(skills=skill_details)
    else:
        skill_details = extra_information.skills

    manual_projects = [
        ProjectEntry(
            name=project.project_name,
            description=project.description,
            technologies=project.technologies,
            url=project.url or project.github_url,
        )
        for project in extra_information.projects
    ]
    manual_certifications = [
        CertificationEntry(
            name=certification.name,
            issuer=certification.issuer,
            date=certification.date,
        )
        for certification in extra_information.certifications
    ]
    projects = _unique_by_name(
        [*cv_profile.projects, *manual_projects], "name"
    )
    certifications = _unique_by_name(
        [*cv_profile.certifications, *manual_certifications], "name"
    )

    payload = cv_profile.model_dump()
    payload.update(
        technical_skills=list(
            dict.fromkeys(skill.skill_name for skill in skill_details)
        ),
        projects=projects,
        certifications=certifications,
        skill_details=skill_details,
        additional_experience=extra_information.additional_experience,
        other_information=extra_information.other_information,
        job_preferences=preferences or JobPreferences(),
    )
    return NormalizedCandidateProfile.model_validate(payload)
