"""Safe links into native job-portal searches without scraping their pages."""

from dataclasses import dataclass
from urllib.parse import urlencode

from models.candidate_context import EmploymentType, NormalizedCandidateProfile

LINKEDIN_JOB_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
_LINKEDIN_JOB_TYPES = {
    EmploymentType.FULL_TIME: "F",
    EmploymentType.PART_TIME: "P",
    EmploymentType.INTERNSHIP: "I",
}
_LINKEDIN_TYPE_LABELS = {
    "Full-time": "F",
    "Part-time": "P",
    "Internship": "I",
    # LinkedIn has no dedicated Working Student type; part-time is the closest
    # native filter and the exact phrase is added to the keyword query below.
    "Working Student": "P",
}


@dataclass(frozen=True)
class JobPortalSearchLink:
    """One human-opened native job-portal search."""

    label: str
    role: str
    location: str
    url: str


def build_configured_linkedin_search_link(
    *,
    country: str,
    category: str,
    keywords: str,
    employment_types: list[str],
) -> JobPortalSearchLink:
    """Build one exact native LinkedIn URL from an external search definition."""
    # Keep the visible LinkedIn keyword field category-only. Employment type is
    # represented exclusively through LinkedIn's native f_JT filter.
    query_keywords = category
    type_codes = list(
        dict.fromkeys(
            _LINKEDIN_TYPE_LABELS[value]
            for value in employment_types
            if value in _LINKEDIN_TYPE_LABELS
        )
    )
    parameters = {
        "keywords": query_keywords,
        "location": country,
        "f_TPR": "r86400",
        "sortBy": "DD",
    }
    if type_codes:
        parameters["f_JT"] = ",".join(type_codes)
    types_label = ", ".join(employment_types)
    return JobPortalSearchLink(
        label=f"{category} · {types_label}",
        role=keywords,
        location=country,
        url=f"{LINKEDIN_JOB_SEARCH_URL}?{urlencode(parameters)}",
    )


def build_linkedin_search_links(
    candidate: NormalizedCandidateProfile,
) -> list[JobPortalSearchLink]:
    """Build LinkedIn searches with supported native filters already applied.

    Working Student is a keyword search because LinkedIn does not expose it as a
    standard employment-type filter. Work mode is left unrestricted when all three
    modes are accepted, which is equivalent to selecting Remote, Hybrid, and Onsite.
    """
    preferences = candidate.job_preferences
    roles = preferences.target_job_titles or ["Software Engineer"]
    locations = preferences.preferred_locations or [
        preferences.country or candidate.location or "Germany"
    ]
    job_type_codes = [
        code
        for employment_type, code in _LINKEDIN_JOB_TYPES.items()
        if employment_type in preferences.employment_types
    ]

    links: list[JobPortalSearchLink] = []
    for location in locations:
        for role in roles:
            parameters = {
                "keywords": role,
                "location": location,
                "f_TPR": "r86400",
                "sortBy": "DD",
            }
            if job_type_codes:
                parameters["f_JT"] = ",".join(job_type_codes)
            links.append(
                JobPortalSearchLink(
                    label=f"{role} · {location}",
                    role=role,
                    location=location,
                    url=f"{LINKEDIN_JOB_SEARCH_URL}?{urlencode(parameters)}",
                )
            )

        if EmploymentType.WORKING_STUDENT in preferences.employment_types:
            working_student_keywords = (
                '"Working Student" ("Computer Science" OR "Data Science" '
                'OR "Software Engineering")'
            )
            parameters = {
                "keywords": working_student_keywords,
                "location": location,
                "f_TPR": "r86400",
                "f_JT": "P,I",
                "sortBy": "DD",
            }
            links.append(
                JobPortalSearchLink(
                    label=f"Working Student · {location}",
                    role="Working Student",
                    location=location,
                    url=f"{LINKEDIN_JOB_SEARCH_URL}?{urlencode(parameters)}",
                )
            )
    return links
