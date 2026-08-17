"""Cost-aware public job discovery, filtering, ranking, and detailed scoring."""

import logging
import os
import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import ValidationError

from models.candidate_context import NormalizedCandidateProfile, SearchRecency
from models.job_discovery import (
    JobDiscoveryReport,
    JobSearchResult,
    RankedJobResult,
)
from models.job_profile import JobProfile, MatchResult
from services.job_analyzer import JobAnalysisError
from services.job_matching import (
    JobMatchingEngine,
    SemanticSimilarity,
    SentenceTransformerSimilarity,
    normalize_skill,
)

logger = logging.getLogger(__name__)

_TRACKING_PARAMETERS = {
    "trk",
    "trackingid",
    "ref",
    "refid",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}
_JOB_WORDS = {
    "career",
    "developer",
    "engineer",
    "intern",
    "internship",
    "job",
    "manager",
    "scientist",
    "student",
    "vacancy",
}
_COMMON_TECHNOLOGIES = (
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "C#",
    "SQL",
    "PostgreSQL",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "PyTorch",
    "TensorFlow",
    "scikit-learn",
    "LangChain",
    "LangGraph",
    "Machine Learning",
    "Natural Language Processing",
    "LLM",
    "Generative AI",
    "REST API",
    "Git",
)
_SOURCE_NAMES = {
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "indeed.de": "Indeed",
    "xing.com": "XING",
    "stepstone.de": "StepStone",
    "stepstone.com": "StepStone",
    "glassdoor.com": "Glassdoor",
    "jobs.lever.co": "Lever",
    "boards.greenhouse.io": "Greenhouse",
    "job-boards.greenhouse.io": "Greenhouse",
    "jobs.ashbyhq.com": "Ashby",
}
_PRIORITY_SOURCE_SEARCHES = (
    ("LinkedIn", "site:linkedin.com/jobs"),
    ("StepStone", "site:stepstone.de"),
    ("Indeed", "(site:indeed.com OR site:indeed.de)"),
    ("XING", "site:xing.com/jobs"),
)
_PRIORITY_SOURCE_NAMES = {name for name, _ in _PRIORITY_SOURCE_SEARCHES}


class JobDiscoveryError(RuntimeError):
    """Raised when public job discovery cannot complete safely."""


class SearchClient(Protocol):
    """Small boundary around Tavily's search client for testing."""

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Return provider search results for one query."""
        ...


class StructuredJobAnalyzer(Protocol):
    """Boundary for the optional expensive job-description analyzer."""

    def analyze(self, job_description: str) -> JobProfile:
        """Return a validated structured job profile."""
        ...


def _deduplicate_text(values: list[str]) -> list[str]:
    """Remove blank and case-insensitive duplicate strings in stable order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join(value.split())
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def generate_search_queries(
    candidate: NormalizedCandidateProfile,
    max_queries: int = 6,
) -> list[str]:
    """Generate targeted, deterministic searches from saved preferences and skills."""
    preferences = candidate.job_preferences
    roles = _deduplicate_text(preferences.target_job_titles)
    if not roles:
        role_hint = candidate.professional_summary.split(".", maxsplit=1)[0].strip()
        roles = [role_hint] if 2 <= len(role_hint.split()) <= 10 else ["Software Engineer"]
    locations = _deduplicate_text(
        [*preferences.preferred_locations, preferences.country, candidate.location]
    ) or ["Remote"]
    employment_types = [item.value for item in preferences.employment_types]
    work_modes = [item.value for item in preferences.work_modes]
    skills = _deduplicate_text(candidate.technical_skills)[:4]

    role_clause = "(" + " OR ".join(f'\"{role}\"' for role in roles) + ")"
    location_clause = "(" + " OR ".join(f'\"{location}\"' for location in locations) + ")"
    type_clause = (
        "(" + " OR ".join(f'\"{value}\"' for value in employment_types) + ")"
        if employment_types
        else ""
    )
    mode_clause = (
        "(" + " OR ".join(f'\"{value}\"' for value in work_modes) + ")"
        if work_modes
        else ""
    )
    skill_clause = (
        "(" + " OR ".join(f'\"{value}\"' for value in skills[:3]) + ")"
        if skills
        else ""
    )

    queries: list[str] = [
        " ".join(
            part
            for part in (
                source_filter,
                role_clause,
                location_clause,
                type_clause,
                mode_clause,
                skill_clause,
                "jobs",
            )
            if part
        )
        for _, source_filter in _PRIORITY_SOURCE_SEARCHES
    ]
    for index, role in enumerate(roles):
        location = locations[index % len(locations)]
        job_type = employment_types[index % len(employment_types)] if employment_types else ""
        mode = "Remote" if "Remote" in work_modes else ""
        queries.append(
            " ".join(
                part
                for part in (f'"{role}"', location, job_type, mode, "jobs careers")
                if part
            )
        )
    for index, role in enumerate(roles):
        if not skills:
            break
        location = locations[index % len(locations)]
        queries.append(
            " ".join((f'"{role}"', location, *skills[:3], "hiring"))
        )
    if employment_types:
        queries.append(
            " ".join(
                (
                    employment_types[0],
                    roles[0],
                    locations[0],
                    *skills[:2],
                    "jobs",
                )
            )
        )
    return _deduplicate_text(queries)[: max(1, max_queries)]


def _source_from_url(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    hostname = hostname.casefold().removeprefix("www.")
    for domain, label in _SOURCE_NAMES.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return label
    root = hostname.split(".")[0].replace("-", " ")
    return root.title() if root else "Public web"


def _company_from_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold().removeprefix("www.")
    path_parts = [part for part in parsed.path.split("/") if part]
    if hostname in {"jobs.lever.co", "boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.ashbyhq.com"} and path_parts:
        return path_parts[0].replace("-", " ").title()
    root = hostname.split(".")[0]
    if root not in {"linkedin", "indeed", "xing", "stepstone", "glassdoor", "jobs", "careers"}:
        return root.replace("-", " ").title()
    return "Not specified"


def _extract_title_company(raw_title: str, url: str) -> tuple[str, str]:
    """Extract a useful role and company from common public result-title formats."""
    cleaned = re.sub(r"\s+", " ", raw_title).strip()
    linkedin = re.match(
        r"(?P<company>.+?)\s+hiring\s+(?P<title>.+?)(?:\s+in\s+.+?)?\s*\|\s*LinkedIn$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if linkedin:
        return linkedin.group("title").strip(), linkedin.group("company").strip()
    at_match = re.match(r"(?P<title>.+?)\s+(?:at|@)\s+(?P<company>.+?)(?:\s*[|–—]\s*.+)?$", cleaned, re.IGNORECASE)
    if at_match:
        return at_match.group("title").strip(), at_match.group("company").strip()
    parts = [part.strip() for part in re.split(r"\s+[|–—]\s+", cleaned) if part.strip()]
    source = _source_from_url(url)
    parts = [part for part in parts if normalize_skill(part) != normalize_skill(source)]
    title = parts[0] if parts else cleaned
    company = parts[1] if len(parts) > 1 else _company_from_url(url)
    return title or "Untitled opportunity", company or "Not specified"


def _extract_location(text: str, candidate: NormalizedCandidateProfile) -> str:
    targets = _deduplicate_text(
        [
            *candidate.job_preferences.preferred_locations,
            candidate.job_preferences.country,
            candidate.location,
        ]
    )
    lowered = text.casefold()
    for target in targets:
        if target.casefold() in lowered:
            return target
    if "remote" in lowered:
        return "Remote"
    match = re.search(
        r"(?:location|based in)\s*[:\-]?\s*([A-Z][A-Za-zÀ-ž .-]{2,40})",
        text,
    )
    return match.group(1).strip(" .-") if match else "Not specified"


def _extract_posted_date(result: Mapping[str, Any], text: str) -> str:
    relative = re.search(
        r"\b((?:\d+|an?|one)\s+(?:minute|hour|day|week)s?\s+ago)\b",
        text,
        re.IGNORECASE,
    )
    if relative:
        return relative.group(1)
    if re.search(r"\b(?:just now|today)\b", text, re.IGNORECASE):
        return "Today"
    for key in ("published_date", "publishedDate", "date"):
        if value := str(result.get(key) or "").strip():
            return value
    return "Not specified"


def normalize_search_result(
    raw: Mapping[str, Any], candidate: NormalizedCandidateProfile
) -> JobSearchResult | None:
    """Normalize one Tavily-style result without fetching or scraping its URL."""
    url = str(raw.get("url") or "").strip()
    title_text = str(raw.get("title") or "").strip()
    description = re.sub(
        r"\s+", " ", str(raw.get("content") or raw.get("snippet") or "")
    ).strip()[:6000]
    if not url or not title_text:
        return None
    title, company = _extract_title_company(title_text, url)
    combined = f"{title_text} {description}"
    try:
        return JobSearchResult(
            title=title,
            company=company,
            location=_extract_location(combined, candidate),
            source=_source_from_url(url),
            url=url,
            description=description,
            posted_date=_extract_posted_date(raw, combined),
        )
    except ValidationError:
        return None


def canonicalize_job_url(url: str) -> str:
    """Remove fragments and common tracking parameters for stable deduplication."""
    parsed = urlparse(url)
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=False)
            if key.casefold() not in _TRACKING_PARAMETERS
            and not key.casefold().startswith("utm_")
        )
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (parsed.scheme.casefold(), parsed.netloc.casefold(), path, "", query, "")
    )


def _fingerprint(value: JobSearchResult) -> str:
    title = normalize_skill(
        re.sub(r"\b(?:m/f/d|f/m/d|all genders|job|vacancy)\b", "", value.title, flags=re.IGNORECASE)
    )
    company = normalize_skill(value.company)
    if company and company != "not specified":
        return f"{title}|{company}"
    return f"{title}|{normalize_skill(value.location)}|{urlparse(value.url).hostname}"


def deduplicate_jobs(values: list[JobSearchResult]) -> list[JobSearchResult]:
    """Deduplicate canonical URLs and cross-site title/company repetitions."""
    by_key: dict[str, JobSearchResult] = {}
    seen_urls: set[str] = set()
    for value in values:
        canonical_url = canonicalize_job_url(value.url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)
        key = _fingerprint(value)
        existing = by_key.get(key)
        if existing is None or len(value.description) > len(existing.description):
            by_key[key] = value
    return list(by_key.values())


def _basic_filter(
    job: JobSearchResult, candidate: NormalizedCandidateProfile
) -> bool:
    text = normalize_skill(f"{job.title} {job.description}")
    title_tokens = set(normalize_skill(job.title).split())
    has_job_intent = bool(title_tokens & _JOB_WORDS) or "apply" in text or "hiring" in text
    if not has_job_intent:
        return False
    preferences = candidate.job_preferences
    company = normalize_skill(job.company)
    if any(normalize_skill(item) in company for item in preferences.excluded_companies):
        return False
    if any(normalize_skill(item) in text for item in preferences.excluded_industries):
        return False
    return True


def _preference_relevance(
    job: JobSearchResult, candidate: NormalizedCandidateProfile
) -> float:
    preferences = candidate.job_preferences
    checks: list[float] = []
    location_targets = [*preferences.preferred_locations, preferences.country]
    if location_targets:
        location = normalize_skill(job.location)
        checks.append(
            1.0
            if any(normalize_skill(target) in location for target in location_targets if target)
            else 0.25
        )
    if preferences.employment_types:
        text = normalize_skill(f"{job.title} {job.description}")
        checks.append(
            1.0
            if any(normalize_skill(item.value) in text for item in preferences.employment_types)
            else 0.4
        )
    return sum(checks) / len(checks) if checks else 1.0


def _preliminary_score(
    job: JobSearchResult,
    candidate: NormalizedCandidateProfile,
    semantic: SemanticSimilarity,
) -> float:
    preferences = candidate.job_preferences
    target_roles = preferences.target_job_titles or [candidate.professional_summary]
    search_intent = " ".join(
        [*target_roles, *candidate.technical_skills[:20], preferences.country]
    )
    job_text = f"{job.title}. {job.description}"
    semantic_score = semantic.similarity(search_intent, job_text)
    skill_keys = [normalize_skill(skill) for skill in candidate.technical_skills]
    normalized_job = normalize_skill(job_text)
    skill_hits = sum(1 for skill in skill_keys if skill and skill in normalized_job)
    skill_score = min(1.0, skill_hits / max(1, min(8, len(skill_keys))))
    title_score = max(
        (semantic.similarity(role, job.title) for role in target_roles if role.strip()),
        default=0.0,
    )
    preference_score = _preference_relevance(job, candidate)
    source_score = 1.0 if job.source in _PRIORITY_SOURCE_NAMES else 0.35
    score = (
        0.45 * semantic_score
        + 0.20 * skill_score
        + 0.15 * title_score
        + 0.10 * preference_score
        + 0.10 * source_score
    )
    return round(max(0.0, min(100.0, score * 100)), 1)


def _heuristic_job_profile(
    job: JobSearchResult, candidate: NormalizedCandidateProfile
) -> JobProfile:
    """Build a conservative profile when Gemini is unavailable or fails."""
    text = f"{job.title} {job.description}"
    technology_candidates = [*candidate.technical_skills, *_COMMON_TECHNOLOGIES]
    technologies = _deduplicate_text(
        [
            technology
            for technology in technology_candidates
            if normalize_skill(technology) in normalize_skill(text)
        ]
    )
    lowered = text.casefold()
    employment_type = next(
        (
            item.value
            for item in candidate.job_preferences.employment_types
            if item.value.casefold() in lowered
        ),
        "",
    )
    work_mode = next(
        (value for value in ("Remote", "Hybrid", "Onsite") if value.casefold() in lowered),
        "",
    )
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", job.description)
        if len(sentence.strip()) >= 20
    ]
    return JobProfile(
        job_title=job.title,
        company=job.company,
        location=job.location,
        employment_type=employment_type,
        work_mode=work_mode,
        responsibilities=sentences[:5],
        required_skills=technologies,
        technologies=technologies,
        raw_description=job.description,
    )


def _short_explanation(result: MatchResult) -> str:
    """Create a short deterministic explanation without another LLM call."""
    strengths = [item.removeprefix("Required skill: ") for item in result.strong_matches[:3]]
    gaps = [item.removeprefix("Required skill: ") for item in result.missing_requirements[:2]]
    parts = [result.recommendation]
    if strengths:
        parts.append(f"strong alignment in {', '.join(strengths)}")
    if gaps:
        parts.append(f"review gaps in {', '.join(gaps)}")
    if len(parts) == 1:
        parts.append("based on your skills, experience, and preferences")
    return ": ".join((parts[0], "; ".join(parts[1:]))) + "."


class JobDiscoveryService:
    """Discover many public results, then deeply analyze only the best candidates."""

    def __init__(
        self,
        search_client: SearchClient,
        semantic: SemanticSimilarity | None = None,
        analyzer: StructuredJobAnalyzer | None = None,
        matcher: JobMatchingEngine | None = None,
        today: date | None = None,
    ) -> None:
        self._search_client = search_client
        self._semantic = semantic or SentenceTransformerSimilarity()
        self._analyzer = analyzer
        self._matcher = matcher or JobMatchingEngine(self._semantic)
        self._today = today or date.today()

    def _search_options(
        self,
        candidate: NormalizedCandidateProfile,
        results_per_query: int,
    ) -> dict[str, Any]:
        recency = candidate.job_preferences.search_recency
        options: dict[str, Any] = {
            "search_depth": "basic",
            "topic": "general",
            "max_results": results_per_query,
            "include_answer": False,
            "include_raw_content": False,
            "auto_parameters": False,
        }
        if recency == SearchRecency.HOURS_24:
            options["time_range"] = "day"
        elif recency == SearchRecency.DAYS_3:
            options["start_date"] = (self._today - timedelta(days=3)).isoformat()
        else:
            options["time_range"] = "week"
        return options

    def discover(
        self,
        candidate: NormalizedCandidateProfile,
        *,
        max_queries: int = 6,
        results_per_query: int = 6,
        detailed_limit: int = 5,
    ) -> JobDiscoveryReport:
        """Run the complete discovery funnel and return only deeply scored top jobs."""
        queries = generate_search_queries(candidate, max_queries=max_queries)
        normalized: list[JobSearchResult] = []
        options = self._search_options(candidate, results_per_query)
        for query in queries:
            logger.info("Job discovery search query: %s", query)
            try:
                response = self._search_client.search(query, **options)
            except Exception as exc:
                logger.warning("Job search failed for query %r: %s", query, exc)
                continue
            for raw in response.get("results", []):
                if not isinstance(raw, Mapping):
                    continue
                if job := normalize_search_result(raw, candidate):
                    normalized.append(job)
        if not normalized:
            raise JobDiscoveryError(
                "No public job results were returned. Try broader roles, locations, or a longer recency window."
            )

        unique = deduplicate_jobs(normalized)
        filtered = [job for job in unique if _basic_filter(job, candidate)]
        preliminary = sorted(
            (
                (_preliminary_score(job, candidate, self._semantic), job)
                for job in filtered
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        shortlist = preliminary[: max(1, detailed_limit)]
        ranked: list[RankedJobResult] = []
        llm_count = 0
        for preliminary_score, job in shortlist:
            job_profile: JobProfile | None = None
            used_llm = False
            if self._analyzer is not None and len(job.description) >= 80:
                try:
                    job_profile = self._analyzer.analyze(
                        f"Job title: {job.title}\nCompany: {job.company}\n"
                        f"Location: {job.location}\n\n{job.description}"
                    )
                    used_llm = True
                    llm_count += 1
                except JobAnalysisError as exc:
                    logger.warning("Structured analysis failed for %s: %s", job.url, exc)
            job_profile = job_profile or _heuristic_job_profile(job, candidate)
            match = self._matcher.match(candidate, job_profile)
            ranked.append(
                RankedJobResult(
                    job=job,
                    preliminary_score=preliminary_score,
                    match_score=match.overall_match,
                    match_explanation=_short_explanation(match),
                    detailed_analysis=used_llm,
                    job_profile=job_profile,
                    match_result=match,
                )
            )
        ranked.sort(key=lambda value: value.match_score, reverse=True)
        return JobDiscoveryReport(
            queries=queries,
            discovered_count=len(normalized),
            filtered_count=len(filtered),
            jobs_analyzed_with_llm=llm_count,
            results=ranked,
        )


def create_tavily_client_from_env() -> SearchClient:
    """Create a Tavily client without exposing or hardcoding its API key."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise JobDiscoveryError("Set TAVILY_API_KEY in jobpilot-ai/.env to discover jobs.")
    from tavily import TavilyClient

    return TavilyClient(api_key=api_key)
