"""Deterministic candidate-to-job scoring with semantic support."""

import re
from dataclasses import dataclass
from datetime import date
from functools import cached_property, lru_cache
from typing import Protocol

import numpy as np

from models.candidate_context import NormalizedCandidateProfile
from models.candidate_profile import WorkExperienceEntry
from models.job_profile import JobProfile, MatchResult, Recommendation

SCORE_WEIGHTS = {
    "required_skills": 0.40,
    "preferred_skills": 0.15,
    "experience": 0.20,
    "education": 0.10,
    "languages": 0.05,
    "responsibility": 0.05,
    "preference": 0.05,
}

_SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "postgres": "postgresql",
    "postgre sql": "postgresql",
    "sklearn": "scikit learn",
    "scikit learn": "scikit learn",
    "huggingface": "hugging face",
    "nlp": "natural language processing",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "gcp": "google cloud",
    "aws ec2": "aws",
    "restful api": "rest api",
    "restful apis": "rest api",
    "rest apis": "rest api",
}


class SemanticSimilarity(Protocol):
    """Semantic text comparison boundary used by the scoring engine."""

    def similarity(self, left: str, right: str) -> float:
        """Return cosine similarity in the range zero to one."""
        ...


class SentenceTransformerSimilarity:
    """Cached all-MiniLM-L6-v2 semantic similarity implementation."""

    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> None:
        self._model_name = model_name

    @cached_property
    def _model(self):  # type: ignore[no-untyped-def]
        from sentence_transformers import SentenceTransformer

        try:
            # Avoid unnecessary Hugging Face network checks after the model has
            # already been downloaded into the local cache.
            return SentenceTransformer(self._model_name, local_files_only=True)
        except OSError:
            # A fresh installation still needs one normal download.
            return SentenceTransformer(self._model_name)

    @lru_cache(maxsize=4096)
    def _embedding(self, text: str) -> tuple[float, ...]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return tuple(float(value) for value in vector)

    def similarity(self, left: str, right: str) -> float:
        """Return a cached cosine similarity for two non-empty strings."""
        if not left.strip() or not right.strip():
            return 0.0
        left_vector = np.asarray(self._embedding(left.strip()), dtype=float)
        right_vector = np.asarray(self._embedding(right.strip()), dtype=float)
        return max(0.0, min(1.0, float(np.dot(left_vector, right_vector))))


@dataclass(frozen=True)
class SkillComparison:
    """Internal skill score and explainability details."""

    score: float
    strong: list[str]
    partial: list[str]
    missing: list[str]


def normalize_skill(skill: str) -> str:
    """Normalize common technology spelling and aliases for exact matching."""
    normalized = skill.casefold().strip()
    normalized = normalized.replace("c++", " cpp ").replace("c#", " csharp ")
    normalized = normalized.replace(".net", " dotnet ").replace("node.js", " nodejs ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return _SKILL_ALIASES.get(normalized, normalized)


def compare_skills(
    candidate_skills: list[str],
    requested_skills: list[str],
    semantic: SemanticSimilarity,
) -> SkillComparison:
    """Score exact, normalized, and semantic skill matches deterministically."""
    if not requested_skills:
        return SkillComparison(100.0, [], [], [])
    candidate_map = {
        normalize_skill(skill): skill for skill in candidate_skills if skill.strip()
    }
    strong: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    credits: list[float] = []
    for requested in requested_skills:
        requested_key = normalize_skill(requested)
        if requested_key in candidate_map:
            strong.append(requested)
            credits.append(1.0)
            continue
        best_skill = ""
        best_similarity = 0.0
        for candidate in candidate_skills:
            similarity = semantic.similarity(requested, candidate)
            if similarity > best_similarity:
                best_skill, best_similarity = candidate, similarity
        if best_similarity >= 0.82:
            partial.append(f"{requested} ≈ {best_skill}")
            credits.append(0.75)
        elif best_similarity >= 0.68:
            partial.append(f"{requested} ~ {best_skill}")
            credits.append(0.40)
        else:
            missing.append(requested)
            credits.append(0.0)
    return SkillComparison(round(100 * sum(credits) / len(credits), 1), strong, partial, missing)


def _parse_month(value: str, reference: date, end: bool = False) -> int | None:
    text = value.casefold().strip()
    if not text:
        return None
    if any(word in text for word in ("present", "current", "now")):
        return reference.year * 12 + reference.month - 1
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    if not year_match:
        return None
    year = int(year_match.group())
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    month = next((number for name, number in months.items() if name in text), None)
    month = month or (12 if end else 1)
    return year * 12 + month - 1


def calculate_experience_years(
    work_experience: list[WorkExperienceEntry],
    reference: date | None = None,
) -> float:
    """Calculate non-overlapping documented work months as years."""
    reference = reference or date.today()
    active_months: set[int] = set()
    for entry in work_experience:
        start = _parse_month(entry.start_date, reference)
        end = _parse_month(entry.end_date, reference, end=True)
        if start is None or end is None or end < start:
            continue
        active_months.update(range(start, end + 1))
    return round(len(active_months) / 12, 2)


def _best_similarity(
    query: str,
    candidate_texts: list[str],
    semantic: SemanticSimilarity,
) -> float:
    return max(
        (semantic.similarity(query, text) for text in candidate_texts if text.strip()),
        default=0.0,
    )


def _relevant_experience_score(
    candidate: NormalizedCandidateProfile,
    job: JobProfile,
    semantic: SemanticSimilarity,
) -> tuple[float, list[str], list[str]]:
    candidate_texts = [
        f"{entry.job_title} {entry.description}"
        for entry in candidate.work_experience
    ] + [
        f"{entry.title} {entry.description} {' '.join(entry.technologies)}"
        for entry in candidate.additional_experience
    ]
    query = " ".join(
        [*job.responsibilities, *job.required_skills, job.industry_domain]
    )
    relevance = _best_similarity(query, candidate_texts, semantic) * 100 if query else 100.0
    minimum_years = job.experience_requirements.minimum_years
    if minimum_years is None or minimum_years == 0:
        return round(relevance, 1), [], []
    candidate_years = calculate_experience_years(candidate.work_experience)
    year_coverage = min(1.0, candidate_years / minimum_years) * 100
    score = round(0.6 * year_coverage + 0.4 * relevance, 1)
    if candidate_years >= minimum_years:
        return score, [f"Experience: {candidate_years:g} years"], []
    return score, [], [
        f"Experience: {candidate_years:g} years documented; {minimum_years:g} required"
    ]


def _education_score(
    candidate: NormalizedCandidateProfile,
    job: JobProfile,
    semantic: SemanticSimilarity,
) -> tuple[float, list[str]]:
    if not job.education_requirements:
        return 100.0, []
    candidate_texts = [
        f"{entry.degree} {entry.field_of_study} {entry.institution}"
        for entry in candidate.education
    ]
    if not candidate_texts:
        return 0.0, list(job.education_requirements)
    scores: list[float] = []
    missing: list[str] = []
    for requirement in job.education_requirements:
        requirement_key = normalize_skill(requirement)
        degree_match = any(
            ("master" in requirement_key or "msc" in requirement_key)
            and ("master" in text.casefold() or "m.sc" in text.casefold())
            or ("bachelor" in requirement_key or "bsc" in requirement_key)
            and ("bachelor" in text.casefold() or "b.sc" in text.casefold())
            or "phd" in requirement_key
            and ("phd" in text.casefold() or "doctor" in text.casefold())
            for text in candidate_texts
        )
        similarity = _best_similarity(requirement, candidate_texts, semantic)
        score = max(0.9 if degree_match else 0.0, similarity)
        scores.append(score)
        if score < 0.6:
            missing.append(requirement)
    return round(100 * sum(scores) / len(scores), 1), missing


def _proficiency_level(value: str) -> int:
    text = value.casefold()
    if "native" in text or "mother" in text:
        return 4
    if "fluent" in text or "business" in text or "c1" in text or "c2" in text:
        return 3
    if "intermediate" in text or "conversational" in text or "b1" in text or "b2" in text:
        return 2
    if "basic" in text or "beginner" in text or "a1" in text or "a2" in text:
        return 1
    return 1 if text.strip() else 0


def _language_score(
    candidate: NormalizedCandidateProfile, job: JobProfile
) -> tuple[float, list[str], list[str]]:
    required_languages = [item for item in job.language_requirements if item.required]
    optional_languages = [item for item in job.language_requirements if not item.required]
    if not required_languages:
        score = 100.0
    else:
        score = 0.0
    candidate_languages = {
        normalize_skill(item.name): _proficiency_level(item.proficiency)
        for item in candidate.languages
    }
    credits: list[float] = []
    missing: list[str] = []
    for requirement in required_languages:
        available = candidate_languages.get(normalize_skill(requirement.language), 0)
        required = _proficiency_level(requirement.proficiency)
        if available == 0:
            credits.append(0.0)
            missing.append(f"Language: {requirement.language} {requirement.proficiency}")
        elif required == 0 or available >= required:
            credits.append(1.0)
        else:
            credits.append(0.5)
            missing.append(f"Language level: {requirement.language} {requirement.proficiency}")
    if credits:
        score = round(100 * sum(credits) / len(credits), 1)
    optional_gaps = [
        f"Preferred language: {requirement.language} {requirement.proficiency}".strip()
        for requirement in optional_languages
        if normalize_skill(requirement.language) not in candidate_languages
    ]
    return score, missing, optional_gaps


def _preference_score(
    candidate: NormalizedCandidateProfile,
    job: JobProfile,
    semantic: SemanticSimilarity,
) -> tuple[float, list[str]]:
    preferences = candidate.job_preferences
    checks: list[float] = []
    deal_breakers: list[str] = []
    company_key = normalize_skill(job.company)
    industry_key = normalize_skill(job.industry_domain)
    if any(normalize_skill(item) in company_key for item in preferences.excluded_companies):
        checks.append(0.0)
        deal_breakers.append(f"Excluded company: {job.company}")
    elif preferences.preferred_companies:
        checks.append(
            100.0 if any(normalize_skill(item) in company_key for item in preferences.preferred_companies) else 40.0
        )
    if any(normalize_skill(item) in industry_key for item in preferences.excluded_industries):
        checks.append(0.0)
        deal_breakers.append(f"Excluded industry: {job.industry_domain}")
    elif preferences.preferred_industries:
        checks.append(
            100.0 if any(normalize_skill(item) in industry_key for item in preferences.preferred_industries) else 40.0
        )
    if preferences.target_job_titles:
        title_similarity = max(
            semantic.similarity(job.job_title, title)
            for title in preferences.target_job_titles
        )
        checks.append(round(title_similarity * 100, 1))
    if preferences.preferred_locations or preferences.country:
        location_targets = [*preferences.preferred_locations, preferences.country]
        checks.append(
            100.0
            if any(normalize_skill(item) in normalize_skill(job.location) for item in location_targets if item)
            else 35.0
        )
    if preferences.work_modes and job.work_mode:
        checks.append(
            100.0
            if normalize_skill(job.work_mode)
            in {normalize_skill(item.value) for item in preferences.work_modes}
            else 0.0
        )
    if preferences.employment_types and job.employment_type:
        checks.append(
            100.0
            if normalize_skill(job.employment_type)
            in {normalize_skill(item.value) for item in preferences.employment_types}
            else 0.0
        )
    required_years = job.experience_requirements.minimum_years
    if required_years is not None and required_years > preferences.maximum_required_experience:
        deal_breakers.append(
            f"Requires {required_years:g} years; your maximum is {preferences.maximum_required_experience:g}"
        )
        checks.append(0.0)
    return (round(sum(checks) / len(checks), 1) if checks else 100.0), deal_breakers


def weighted_overall(scores: dict[str, float]) -> float:
    """Apply the fixed scoring formula without LLM involvement."""
    return round(sum(scores[name] * weight for name, weight in SCORE_WEIGHTS.items()), 1)


def classify_recommendation(score: float) -> Recommendation:
    """Map an overall deterministic score to the requested recommendation."""
    if score >= 85:
        return "Strong Apply"
    if score >= 70:
        return "Apply"
    if score >= 55:
        return "Consider"
    return "Low Match"


class JobMatchingEngine:
    """Calculate explainable match scores from normalized profile data."""

    def __init__(self, semantic: SemanticSimilarity | None = None) -> None:
        self._semantic = semantic or SentenceTransformerSimilarity()

    def match(
        self, candidate: NormalizedCandidateProfile, job: JobProfile
    ) -> MatchResult:
        """Return component scores, evidence, gaps, and a recommendation."""
        required = compare_skills(
            candidate.technical_skills, job.required_skills, self._semantic
        )
        preferred = compare_skills(
            candidate.technical_skills, job.preferred_skills, self._semantic
        )
        experience_score, experience_strong, experience_missing = (
            _relevant_experience_score(candidate, job, self._semantic)
        )
        education_score, education_missing = _education_score(
            candidate, job, self._semantic
        )
        language_score, language_missing, optional_language_gaps = _language_score(
            candidate, job
        )
        responsibility_query = " ".join(job.responsibilities)
        candidate_story = " ".join(
            [
                candidate.professional_summary,
                *[entry.description for entry in candidate.work_experience],
                *[entry.description for entry in candidate.projects],
                *[entry.description for entry in candidate.additional_experience],
                candidate.other_information,
            ]
        )
        responsibility_score = (
            round(self._semantic.similarity(responsibility_query, candidate_story) * 100, 1)
            if responsibility_query
            else 100.0
        )
        preference_score, deal_breakers = _preference_score(
            candidate, job, self._semantic
        )
        component_scores = {
            "required_skills": required.score,
            "preferred_skills": preferred.score,
            "experience": experience_score,
            "education": education_score,
            "languages": language_score,
            "responsibility": responsibility_score,
            "preference": preference_score,
        }
        overall = weighted_overall(component_scores)
        if overall < candidate.job_preferences.minimum_match_score:
            deal_breakers.append(
                f"Below your minimum match score of {candidate.job_preferences.minimum_match_score}%"
            )
        if job.required_skills and len(required.missing) / len(job.required_skills) >= 0.5:
            deal_breakers.append("At least half of the required skills are missing")
        strong_matches = [
            *[f"Required skill: {item}" for item in required.strong],
            *[f"Preferred skill: {item}" for item in preferred.strong],
            *experience_strong,
        ]
        if education_score >= 80 and job.education_requirements:
            strong_matches.append("Education requirements")
        if language_score >= 80 and job.language_requirements:
            strong_matches.append("Language requirements")
        return MatchResult(
            overall_match=overall,
            required_skills_score=required.score,
            preferred_skills_score=preferred.score,
            experience_score=experience_score,
            education_score=education_score,
            language_score=language_score,
            responsibility_score=responsibility_score,
            preference_score=preference_score,
            recommendation=classify_recommendation(overall),
            strong_matches=strong_matches,
            partial_matches=[*required.partial, *preferred.partial],
            missing_requirements=[
                *[f"Required skill: {item}" for item in required.missing],
                *experience_missing,
                *[f"Education: {item}" for item in education_missing],
                *language_missing,
            ],
            potential_deal_breakers=list(dict.fromkeys(deal_breakers)),
            nice_to_have_gaps=[
                *[f"Preferred skill: {item}" for item in preferred.missing],
                *optional_language_gaps,
            ],
        )
