"""Serializable models for public job discovery and saved opportunities."""

from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import Field, field_validator

from models.candidate_profile import ProfileModel
from models.job_profile import JobProfile, MatchResult


class JobSearchResult(ProfileModel):
    """One normalized result returned by a public web search provider."""

    title: str
    company: str = "Not specified"
    location: str = "Not specified"
    source: str
    url: str
    description: str = ""
    posted_date: str = "Not specified"
    country: str = "Not specified"
    employment_type: str = "Not specified"
    search_category: str = ""
    search_keyword: str = ""
    collected_at: datetime | None = None
    source_job_id: str = ""

    @field_validator("url")
    @classmethod
    def require_public_web_url(cls, value: str) -> str:
        """Reject non-web URLs before they reach the UI or persistence layer."""
        cleaned = value.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("A job result must have a public HTTP(S) URL.")
        return cleaned


class RankedJobResult(ProfileModel):
    """A shortlisted job with deterministic relevance and detailed match data."""

    job: JobSearchResult
    preliminary_score: float = Field(ge=0, le=100)
    match_score: float = Field(ge=0, le=100)
    match_explanation: str
    detailed_analysis: bool = False
    job_profile: JobProfile | None = None
    match_result: MatchResult | None = None


class JobDiscoveryReport(ProfileModel):
    """Complete, serializable result of one discovery run."""

    queries: list[str] = Field(default_factory=list)
    discovered_count: int = Field(default=0, ge=0)
    filtered_count: int = Field(default=0, ge=0)
    jobs_analyzed_with_llm: int = Field(default=0, ge=0)
    results: list[RankedJobResult] = Field(default_factory=list)


class JobCollectionReport(ProfileModel):
    """Unfiltered job collection report with duplicates removed."""

    searches_attempted: int = Field(default=0, ge=0)
    searches_succeeded: int = Field(default=0, ge=0)
    searches_failed: list[str] = Field(default_factory=list)
    discovered_count: int = Field(default=0, ge=0)
    criteria_rejected: int = Field(default=0, ge=0)
    duplicates_removed: int = Field(default=0, ge=0)
    results: list[JobSearchResult] = Field(default_factory=list)


class SavedJob(ProfileModel):
    """A discovered job persisted for later review and application tracking."""

    id: UUID | None = None
    title: str
    company: str = "Not specified"
    location: str = "Not specified"
    source: str
    url: str
    description: str = ""
    posted_date: str = "Not specified"
    match_score: float = Field(ge=0, le=100)
    match_explanation: str = ""
    job_profile: dict[str, object] = Field(default_factory=dict)
    match_result: dict[str, object] = Field(default_factory=dict)
    saved_at: datetime | None = None

    @classmethod
    def from_ranked_result(cls, value: RankedJobResult) -> "SavedJob":
        """Build a persistence model from one ranked discovery result."""
        return cls(
            **value.job.model_dump(),
            match_score=value.match_score,
            match_explanation=value.match_explanation,
            job_profile=(
                value.job_profile.model_dump(mode="json") if value.job_profile else {}
            ),
            match_result=(
                value.match_result.model_dump(mode="json") if value.match_result else {}
            ),
        )

    @classmethod
    def from_search_result(cls, value: JobSearchResult) -> "SavedJob":
        """Save an unscored collected job for optional later analysis."""
        return cls(
            title=value.title,
            company=value.company,
            location=value.location,
            source=value.source,
            url=value.url,
            description=value.description,
            posted_date=value.posted_date,
            match_score=0,
            match_explanation="Not analyzed yet",
            job_profile={
                "job_title": value.title,
                "company": value.company,
                "location": value.location,
                "employment_type": value.employment_type,
                "raw_description": value.description,
            },
        )
