"""Pydantic models for the persistent candidate profile."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000001")


class ProfileModel(BaseModel):
    """Base model that tolerates future database columns."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class EducationEntry(ProfileModel):
    """One education record."""

    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class WorkExperienceEntry(ProfileModel):
    """One employment record."""

    company: str = ""
    job_title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class LanguageEntry(ProfileModel):
    """A spoken language and optional proficiency level."""

    name: str = ""
    proficiency: str = ""


class CertificationEntry(ProfileModel):
    """A professional certification or credential."""

    name: str = ""
    issuer: str = ""
    date: str = ""
    credential_url: str = ""


class ProjectEntry(ProfileModel):
    """A candidate project."""

    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    url: str = ""


class ExtractedCandidateProfile(ProfileModel):
    """Structured fields Gemini must extract from CV text."""

    name: str = ""
    email: str = ""
    location: str = ""
    professional_summary: str = ""
    education: list[EducationEntry] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)


class CandidateProfile(ExtractedCandidateProfile):
    """The reusable, persistently stored candidate profile."""

    id: UUID = DEFAULT_PROFILE_ID
    cv_file_path: str | None = None
    parsed_cv_text: str = ""
    updated_at: datetime | None = None
    extraction_method: Literal["basic", "gemini"] = Field(
        default="basic", exclude=True
    )
    extraction_warning: str | None = Field(default=None, exclude=True)
