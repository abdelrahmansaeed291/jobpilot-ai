"""Structured job-description and deterministic match result models."""

from typing import Literal

from pydantic import Field

from models.candidate_profile import ProfileModel


class ExperienceRequirement(ProfileModel):
    """Structured experience requirement extracted from a job description."""

    minimum_years: float | None = Field(default=None, ge=0, le=50)
    maximum_years: float | None = Field(default=None, ge=0, le=50)
    description: str = ""


class JobLanguageRequirement(ProfileModel):
    """A required or preferred language stated by an employer."""

    language: str
    proficiency: str = ""
    required: bool = True


class ExtractedJobProfile(ProfileModel):
    """Schema Gemini must return for an unstructured job description."""

    job_title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    work_mode: str = ""
    seniority: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    experience_requirements: ExperienceRequirement = Field(
        default_factory=ExperienceRequirement
    )
    language_requirements: list[JobLanguageRequirement] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    industry_domain: str = ""
    benefits: list[str] = Field(default_factory=list)


class JobProfile(ExtractedJobProfile):
    """Validated structured job data plus its original description."""

    raw_description: str = Field(default="", exclude=True)


Recommendation = Literal["Strong Apply", "Apply", "Consider", "Low Match"]


class MatchResult(ProfileModel):
    """Complete deterministic candidate-to-job match result."""

    overall_match: float = Field(ge=0, le=100)
    required_skills_score: float = Field(ge=0, le=100)
    preferred_skills_score: float = Field(ge=0, le=100)
    experience_score: float = Field(ge=0, le=100)
    education_score: float = Field(ge=0, le=100)
    language_score: float = Field(ge=0, le=100)
    responsibility_score: float = Field(ge=0, le=100)
    preference_score: float = Field(ge=0, le=100)
    recommendation: Recommendation
    strong_matches: list[str] = Field(default_factory=list)
    partial_matches: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    potential_deal_breakers: list[str] = Field(default_factory=list)
    nice_to_have_gaps: list[str] = Field(default_factory=list)
