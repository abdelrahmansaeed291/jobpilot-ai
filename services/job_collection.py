"""Configuration-driven, provider-based job collection without relevance filtering."""

import json
import logging
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import parse_qs, urlparse

from pydantic import Field

from models.candidate_context import NormalizedCandidateProfile
from models.candidate_profile import ProfileModel
from models.job_discovery import JobCollectionReport, JobSearchResult
from services.job_discovery import SearchClient, normalize_search_result
from services.job_matching import normalize_skill

logger = logging.getLogger(__name__)

_COUNTRY_LOCATION_TERMS = {
    "germany": {
        "germany", "deutschland", "berlin", "munich", "munchen", "hamburg",
        "frankfurt", "cologne", "koln", "stuttgart", "dusseldorf", "leipzig",
        "dortmund", "dresden", "nuremberg", "nurnberg", "hanover", "hannover",
        "bremen", "essen", "bonn", "aachen", "karlsruhe", "mannheim", "potsdam",
        "bavaria", "bayern", "hesse", "hessen", "baden wurttemberg",
    },
    "egypt": {
        "egypt", "cairo", "giza", "alexandria", "nasr city", "new cairo",
        "maadi", "heliopolis", "mansoura", "tanta", "aswan", "luxor",
        "smart village", "6th of october", "sixth of october",
    },
}

DEFAULT_SEARCH_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "job_searches.json"
)


class JobSearchDefinition(ProfileModel):
    """One independently executed search from the external configuration."""

    country: str
    category: str
    keywords: str
    employment_types: list[str] = Field(default_factory=list)
    date_posted: Literal["24h"] = "24h"

    @property
    def label(self) -> str:
        """Return a concise log and UI label for this search."""
        types = ", ".join(self.employment_types) or "All types"
        return f"{self.country} · {self.category} · {types}"


class JobSearchConfiguration(ProfileModel):
    """Validated provider and search definitions loaded from JSON."""

    provider: Literal["linkedin"] = "linkedin"
    sort: Literal["newest"] = "newest"
    searches: list[JobSearchDefinition]


class JobSourceProvider(Protocol):
    """Pluggable source provider for independently configured searches."""

    name: str

    def search(self, definition: JobSearchDefinition) -> list[Mapping[str, Any]]:
        """Return raw public-index results for one configured search."""
        ...


def load_job_search_configuration(
    path: Path = DEFAULT_SEARCH_CONFIG_PATH,
) -> JobSearchConfiguration:
    """Load and validate the separate job-search configuration file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return JobSearchConfiguration.model_validate(payload)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Could not load job search configuration: {exc}") from exc


class TavilyLinkedInProvider:
    """Collect LinkedIn-only results through Tavily's public search index."""

    name = "LinkedIn"

    def __init__(self, client: SearchClient, max_results: int = 20) -> None:
        self._client = client
        self._max_results = max(1, min(20, max_results))

    def search(self, definition: JobSearchDefinition) -> list[Mapping[str, Any]]:
        """Run one source-restricted, 24-hour search without scraping LinkedIn."""
        query = (
            f'site:linkedin.com/jobs/view \"{definition.category}\" '
            f'\"{definition.country}\"'
        )
        response = self._client.search(
            query,
            search_depth="basic",
            topic="general",
            time_range="day",
            max_results=self._max_results,
            include_answer=False,
            include_raw_content=False,
            auto_parameters=False,
        )
        return [
            value
            for value in response.get("results", [])
            if isinstance(value, Mapping)
        ]


def extract_linkedin_job_id(url: str) -> str:
    """Extract LinkedIn's numeric job ID from common public job URLs."""
    parsed = urlparse(url)
    path_match = re.search(r"/jobs/view/(?:[^/?]*-)?(\d+)(?:/|$)", parsed.path)
    if path_match:
        return path_match.group(1)
    query = parse_qs(parsed.query)
    for key in ("currentJobId", "jobId"):
        if values := query.get(key):
            if values[0].isdigit():
                return values[0]
    return ""


def _linkedin_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").casefold()
    return hostname == "linkedin.com" or hostname.endswith(".linkedin.com")


def matches_configured_country(text: str, country: str) -> bool:
    """Require explicit country or known-city evidence in the result itself."""
    transliterated = text.casefold().translate(
        str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})
    )
    normalized = f" {normalize_skill(transliterated)} "
    terms = _COUNTRY_LOCATION_TERMS.get(normalize_skill(country), {normalize_skill(country)})
    return any(f" {term} " in normalized for term in terms if term)


def posted_age_hours(value: str, collected_at: datetime) -> float | None:
    """Parse a LinkedIn relative or ISO posting date into an age in hours."""
    text = value.casefold().strip()
    if text in {"today", "just now"}:
        return 0.0
    relative = re.search(
        r"(?P<value>\d+|an?|one)\s+(?P<unit>minute|hour|day|week)s?\s+ago",
        text,
    )
    if relative:
        raw_value = relative.group("value")
        amount = 1 if raw_value in {"a", "an", "one"} else int(raw_value)
        multiplier = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168}
        return amount * multiplier[relative.group("unit")]
    try:
        posted_at = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        return max(0.0, (collected_at - posted_at.astimezone(timezone.utc)).total_seconds() / 3600)
    except ValueError:
        return None


def matching_employment_types(
    text: str, configured_types: list[str]
) -> list[str]:
    """Validate job types from result text instead of putting them in keywords."""
    normalized = f" {normalize_skill(text)} "
    patterns = {
        "Full-time": (" full time ", " fulltime "),
        "Part-time": (" part time ", " parttime "),
        "Internship": (" internship ", " intern ", " trainee "),
        "Working Student": (
            " working student ",
            " werkstudent ",
            " student assistant ",
            " studentische hilfskraft ",
        ),
    }
    return [
        employment_type
        for employment_type in configured_types
        if any(pattern in normalized for pattern in patterns.get(employment_type, ()))
    ]


def _normalize_collected_job(
    raw: Mapping[str, Any],
    definition: JobSearchDefinition,
    candidate: NormalizedCandidateProfile,
    collected_at: datetime,
) -> JobSearchResult | None:
    job = normalize_search_result(raw, candidate)
    if job is None or not _linkedin_url(job.url):
        return None
    evidence = " ".join(
        (
            str(raw.get("title") or ""),
            str(raw.get("content") or raw.get("snippet") or ""),
            job.location,
        )
    )
    if not matches_configured_country(evidence, definition.country):
        logger.info(
            "Job rejected: country not proven (%s, %s)",
            definition.country,
            job.url,
        )
        return None
    age_hours = posted_age_hours(job.posted_date, collected_at)
    if age_hours is None or age_hours > 24:
        logger.info(
            "Job rejected: posting age is unknown or older than 24h (%s, %s)",
            job.posted_date,
            job.url,
        )
        return None
    matched_types = matching_employment_types(
        evidence, definition.employment_types
    )
    if definition.employment_types and not matched_types:
        logger.info(
            "Job rejected: employment type not proven (%s, %s)",
            ", ".join(definition.employment_types),
            job.url,
        )
        return None
    return job.model_copy(
        update={
            "country": definition.country,
            "location": (
                definition.country
                if job.location == "Not specified"
                else job.location
            ),
            "employment_type": ", ".join(matched_types)
            or "Not specified",
            "search_category": definition.category,
            "search_keyword": definition.category,
            "collected_at": collected_at,
            "source_job_id": extract_linkedin_job_id(job.url),
        }
    )


def _fallback_key(job: JobSearchResult) -> str:
    return "|".join(
        (
            normalize_skill(job.company),
            normalize_skill(job.title),
            normalize_skill(job.location),
        )
    )


def deduplicate_collected_jobs(
    jobs: list[JobSearchResult],
) -> list[JobSearchResult]:
    """Remove duplicates by LinkedIn ID, then company/title/location fallback."""
    seen_ids: set[str] = set()
    seen_fallbacks: set[str] = set()
    unique: list[JobSearchResult] = []
    for job in jobs:
        fallback = _fallback_key(job)
        if job.source_job_id and job.source_job_id in seen_ids:
            continue
        if fallback in seen_fallbacks:
            continue
        if job.source_job_id:
            seen_ids.add(job.source_job_id)
        seen_fallbacks.add(fallback)
        unique.append(job)
    return unique


def _freshness_key(job: JobSearchResult) -> tuple[int, float]:
    """Sort recognizable relative/ISO dates first while preserving stable order."""
    text = job.posted_date.casefold().strip()
    relative = re.search(r"(\d+)\s+(hour|day|week)s?\s+ago", text)
    if relative:
        value = int(relative.group(1))
        multiplier = {"hour": 1, "day": 24, "week": 168}[relative.group(2)]
        return (0, float(value * multiplier))
    try:
        timestamp = datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        return (0, -timestamp)
    except ValueError:
        return (1, 0.0)


class JobCollectionService:
    """Execute every configured search and return all unique collected jobs."""

    def __init__(self, provider: JobSourceProvider) -> None:
        self._provider = provider

    def collect(
        self,
        candidate: NormalizedCandidateProfile,
        configuration: JobSearchConfiguration,
    ) -> JobCollectionReport:
        """Collect all results without match, keyword, or preference filtering."""
        collected: list[JobSearchResult] = []
        failures: list[str] = []
        successful = 0
        criteria_rejected = 0
        for definition in configuration.searches:
            logger.info("Job search started: %s", definition.label)
            try:
                raw_results = self._provider.search(definition)
                collected_at = datetime.now(timezone.utc)
                normalized: list[JobSearchResult] = []
                for raw in raw_results:
                    job = _normalize_collected_job(
                        raw, definition, candidate, collected_at
                    )
                    if job is None:
                        criteria_rejected += 1
                    else:
                        normalized.append(job)
                collected.extend(normalized)
                successful += 1
                logger.info(
                    "Job search succeeded: %s (%d results)",
                    definition.label,
                    len(normalized),
                )
            except Exception as exc:
                failures.append(definition.label)
                logger.warning("Job search failed: %s (%s)", definition.label, exc)

        unique = deduplicate_collected_jobs(collected)
        unique.sort(key=_freshness_key)
        return JobCollectionReport(
            searches_attempted=len(configuration.searches),
            searches_succeeded=successful,
            searches_failed=failures,
            discovered_count=len(collected),
            criteria_rejected=criteria_rejected,
            duplicates_removed=len(collected) - len(unique),
            results=unique,
        )
