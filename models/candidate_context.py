"""Models for manually curated candidate context and job preferences."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from models.candidate_profile import CandidateProfile, ProfileModel


class SkillProficiency(StrEnum):
    """Supported skill proficiency levels."""

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class SkillSource(StrEnum):
    """Origin of a candidate skill."""

    CV = "CV"
    MANUAL = "Manual"


class WorkMode(StrEnum):
    """Supported workplace arrangements."""

    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "Onsite"


class EmploymentType(StrEnum):
    """Supported employment categories."""

    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    WORKING_STUDENT = "Working student"
    INTERNSHIP = "Internship"


class SearchRecency(StrEnum):
    """Maximum job-post age used during discovery."""

    HOURS_24 = "24 hours"
    DAYS_3 = "3 days"
    DAYS_7 = "7 days"


class CandidateSkill(ProfileModel):
    """A skill with provenance and self-assessed proficiency."""

    skill_name: str
    proficiency_level: SkillProficiency = SkillProficiency.INTERMEDIATE
    source: SkillSource = SkillSource.MANUAL
    notes: str = ""


class AdditionalExperience(ProfileModel):
    """Experience that does not appear in the CV."""

    title: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    date: str = ""


class AdditionalProject(ProfileModel):
    """A manually supplied project."""

    project_name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    url: str = ""
    github_url: str = ""


class AdditionalCertification(ProfileModel):
    """A manually supplied certification."""

    name: str
    issuer: str = ""
    date: str = ""


class LanguageRequirement(ProfileModel):
    """A language and requested proficiency."""

    language: str
    proficiency: str = ""


class CandidateExtraInformation(ProfileModel):
    """All manually maintained information beyond the CV."""

    id: str = "00000000-0000-0000-0000-000000000001"
    skills: list[CandidateSkill] = Field(default_factory=list)
    additional_experience: list[AdditionalExperience] = Field(default_factory=list)
    projects: list[AdditionalProject] = Field(default_factory=list)
    certifications: list[AdditionalCertification] = Field(default_factory=list)
    other_information: str = ""
    updated_at: datetime | None = None


class JobPreferences(ProfileModel):
    """Persistent constraints and priorities for job discovery and matching."""

    id: str = "00000000-0000-0000-0000-000000000001"
    target_job_titles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    country: str = ""
    work_modes: list[WorkMode] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    minimum_match_score: int = Field(default=70, ge=0, le=100)
    preferred_industries: list[str] = Field(default_factory=list)
    excluded_industries: list[str] = Field(default_factory=list)
    preferred_companies: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    language_requirements: list[LanguageRequirement] = Field(default_factory=list)
    maximum_required_experience: float = Field(default=5.0, ge=0, le=50)
    search_recency: SearchRecency = SearchRecency.DAYS_7
    updated_at: datetime | None = None

    @field_validator(
        "target_job_titles",
        "preferred_locations",
        "preferred_industries",
        "excluded_industries",
        "preferred_companies",
        "excluded_companies",
    )
    @classmethod
    def deduplicate_lists(cls, values: list[str]) -> list[str]:
        """Remove blank and duplicate preference values while preserving order."""
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class NormalizedCandidateProfile(CandidateProfile):
    """Agent-ready CandidateProfile enriched with manual context and preferences."""

    skill_details: list[CandidateSkill] = Field(default_factory=list, exclude=True)
    additional_experience: list[AdditionalExperience] = Field(
        default_factory=list, exclude=True
    )
    other_information: str = Field(default="", exclude=True)
    job_preferences: JobPreferences = Field(
        default_factory=JobPreferences, exclude=True
    )
