"""LinkedIn-focused, configuration-driven job collection page."""

import hashlib
import os
from html import escape

import streamlit as st

from components.app_theme import render_feature_hero
from database.context_repository import (
    CandidateContextRepositoryError,
    SupabaseCandidateContextRepository,
)
from database.job_repository import SavedJobRepositoryError, SupabaseSavedJobRepository
from database.profile_repository import ProfileRepositoryError, SupabaseProfileRepository
from database.supabase_client import (
    SupabaseConfigurationError,
    create_supabase_client_from_env,
)
from models.candidate_context import NormalizedCandidateProfile
from models.job_discovery import JobCollectionReport, JobSearchResult, SavedJob
from models.job_profile import JobProfile
from services.candidate_context_service import build_normalized_candidate_profile
from services.job_collection import (
    JobCollectionService,
    JobSearchConfiguration,
    TavilyLinkedInProvider,
    load_job_search_configuration,
)
from services.job_discovery import JobDiscoveryError, create_tavily_client_from_env
from services.job_portal_links import build_configured_linkedin_search_link

_REPORT_KEY = "job-collection-report-category-only-v3"


@st.cache_data(ttl=1800, show_spinner=False)
def _collect_cached(
    candidate_json: str, cache_version: str = "category-only-v3"
) -> dict[str, object]:
    """Cache identical nine-search collections for 30 minutes."""
    del cache_version
    candidate = NormalizedCandidateProfile.model_validate_json(candidate_json)
    configuration = load_job_search_configuration()
    provider = TavilyLinkedInProvider(create_tavily_client_from_env())
    report = JobCollectionService(provider).collect(candidate, configuration)
    return report.model_dump(mode="json")


def _load_candidate() -> NormalizedCandidateProfile:
    """Load normalized candidate data used only by result normalization and Analyze."""
    client = create_supabase_client_from_env()
    profile = SupabaseProfileRepository(client).get_profile()
    if profile is None:
        raise ProfileRepositoryError(
            "Upload and save your CV in CV & Extra Information before searching."
        )
    context = SupabaseCandidateContextRepository(client)
    return build_normalized_candidate_profile(
        profile,
        context.get_extra_information(),
        context.get_job_preferences(),
    )


def _render_styles() -> None:
    """Apply a clean card design to the unfiltered job dataset."""
    st.markdown(
        """
        <style>
        .collection-summary {display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1rem 0 1.25rem}
        .collection-stat {padding:.9rem 1rem;border:1px solid rgba(37,99,235,.14);border-radius:16px;background:linear-gradient(145deg,#fff,#eff6ff);box-shadow:0 8px 24px rgba(30,64,175,.06)}
        .collection-stat strong {display:block;color:#1e3a8a;font-size:1.3rem}
        .collection-stat span {color:#6b7280;font-size:.72rem;font-weight:750;text-transform:uppercase;letter-spacing:.06em}
        .source-badge {display:inline-flex;padding:.3rem .62rem;border-radius:999px;color:#1d4ed8;background:#dbeafe;font-size:.73rem;font-weight:800}
        .job-title {margin:.5rem 0 .15rem;color:#172554;font-size:1.2rem;font-weight:850}
        .job-company {color:#374151;font-size:.92rem;font-weight:650}
        .job-meta {margin:.55rem 0;color:#6b7280;font-size:.8rem;line-height:1.6}
        .category-chip {display:inline-flex;padding:.28rem .58rem;margin:.15rem .25rem .15rem 0;border-radius:999px;background:#f5f3ff;color:#6d28d9;font-size:.73rem;font-weight:700}
        @media(max-width:780px){.collection-summary{grid-template-columns:repeat(2,1fr)}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _save_job(job: JobSearchResult) -> None:
    """Persist an unscored job for later analysis."""
    client = create_supabase_client_from_env()
    SupabaseSavedJobRepository(client).save(SavedJob.from_search_result(job))


def _prepare_analysis(job: JobSearchResult) -> None:
    """Load a collected job into Analyze Job without calculating a hidden score."""
    st.session_state["analyzed-job-profile"] = JobProfile(
        job_title=job.title,
        company=job.company,
        location=job.location,
        employment_type=job.employment_type,
        raw_description=job.description,
    )
    st.session_state.pop("analyzed-job-match", None)


def _render_job_card(job: JobSearchResult) -> None:
    """Render all stored standardized fields for one unique job."""
    token = hashlib.sha1(job.url.encode("utf-8")).hexdigest()[:12]
    st.markdown(
        f'<span class="source-badge">LinkedIn</span>'
        f'<div class="job-title">{escape(job.title)}</div>'
        f'<div class="job-company">{escape(job.company)}</div>'
        f'<div class="job-meta">📍 {escape(job.location)} · {escape(job.country)}<br>'
        f'💼 {escape(job.employment_type)} · 🕒 {escape(job.posted_date)}</div>'
        f'<span class="category-chip">{escape(job.search_category)}</span>'
        f'<span class="category-chip">{escape(job.search_keyword)}</span>',
        unsafe_allow_html=True,
    )
    if job.description:
        with st.expander("Job description"):
            st.write(job.description)
    actions = st.columns(3)
    with actions[0]:
        if st.button("Analyze", key=f"analyze-{token}", use_container_width=True):
            _prepare_analysis(job)
            st.success("Loaded into Analyze Job. Open that page from the sidebar.")
    with actions[1]:
        if st.button("Save", key=f"save-{token}", use_container_width=True):
            try:
                _save_job(job)
                st.success(f"Saved {job.title}.")
            except (SavedJobRepositoryError, SupabaseConfigurationError) as exc:
                st.error(str(exc))
    with actions[2]:
        st.link_button("Open LinkedIn ↗", job.url, use_container_width=True)


def _render_configuration(configuration: JobSearchConfiguration) -> None:
    """Show one-click native LinkedIn searches without mixing country groups."""
    st.markdown("### Step 1 · Open the exact searches on LinkedIn")
    st.caption(
        "Each button opens LinkedIn Jobs with the keyword, country, employment type, "
        "past-24-hours, and newest-first filters already encoded."
    )
    germany_tab, egypt_tab = st.tabs(["Germany · 6 searches", "Egypt · 3 searches"])
    for country, tab in (("Germany", germany_tab), ("Egypt", egypt_tab)):
        with tab:
            columns = st.columns(2)
            country_searches = [
                definition
                for definition in configuration.searches
                if definition.country == country
            ]
            for index, definition in enumerate(country_searches):
                link = build_configured_linkedin_search_link(
                    country=definition.country,
                    category=definition.category,
                    keywords=definition.keywords,
                    employment_types=definition.employment_types,
                )
                with columns[index % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{definition.category}**")
                        st.caption(
                            f"{definition.keywords} · {', '.join(definition.employment_types)} · Last 24h"
                        )
                        st.link_button(
                            "Open filtered LinkedIn Jobs ↗",
                            link.url,
                            use_container_width=True,
                        )


def _render_report(report: JobCollectionReport) -> None:
    """Display every unique result, newest first and separated by country."""
    summary = (
        (str(report.discovered_count), "Collected"),
        (str(report.criteria_rejected), "Criteria rejected"),
        (str(report.duplicates_removed), "Duplicates removed"),
        (str(len(report.results)), "Unique jobs"),
    )
    cards = "".join(
        f'<div class="collection-stat"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'
        for value, label in summary
    )
    st.markdown(f'<div class="collection-summary">{cards}</div>', unsafe_allow_html=True)
    st.success(
        "Country and 24-hour eligibility were verified from each result. No match-score, "
        "keyword-relevance, preference, or semantic filters were applied."
    )
    st.caption(
        f"Searches succeeded: {report.searches_succeeded}/{report.searches_attempted}. "
        "Results with an unknown posting age, no explicit Germany/Egypt location, or "
        "no evidence of the configured employment type are excluded."
    )
    if report.searches_failed:
        with st.expander(f"⚠ {len(report.searches_failed)} searches failed"):
            for label in report.searches_failed:
                st.markdown(f"- {label}")

    country_names = ("Germany", "Egypt")
    country_tabs = st.tabs(
        [
            f"{country} ({sum(job.country == country for job in report.results)})"
            for country in country_names
        ]
    )
    for country, tab in zip(country_names, country_tabs, strict=True):
        with tab:
            jobs = [job for job in report.results if job.country == country]
            if not jobs:
                st.info(f"No LinkedIn jobs were returned for {country} in this run.")
                continue
            for job in jobs:
                with st.container(border=True):
                    _render_job_card(job)


def render() -> None:
    """Run nine configured LinkedIn searches and display all unique jobs."""
    _render_styles()
    render_feature_hero(
        "LinkedIn first · no hidden filtering",
        "Find Jobs",
        "Run nine focused 24-hour searches, combine the results, remove duplicates, and display every job.",
        "🔎",
        ("#0a66c2", "#4338ca"),
    )
    try:
        candidate = _load_candidate()
        configuration = load_job_search_configuration()
    except (
        SupabaseConfigurationError,
        ProfileRepositoryError,
        CandidateContextRepositoryError,
        RuntimeError,
    ) as exc:
        st.error(str(exc))
        return

    _render_configuration(configuration)
    st.divider()
    st.markdown("### Step 2 · Retrieve public results into JobPilot")
    st.caption(
        "LinkedIn is the only source in this configuration. Each search uses Tavily's "
        "public index with a 24-hour time window; JobPilot does not scrape LinkedIn."
    )
    if not os.getenv("TAVILY_API_KEY", "").strip():
        st.warning(
            "Automatic collection needs TAVILY_API_KEY in jobpilot-ai/.env. "
            "Without it, JobPilot cannot retrieve public search results."
        )
        return

    if st.button("Collect all LinkedIn jobs", type="primary", use_container_width=True):
        try:
            with st.spinner("Running all 9 searches and removing duplicates..."):
                st.session_state[_REPORT_KEY] = _collect_cached(
                    candidate.model_dump_json()
                )
        except (JobDiscoveryError, RuntimeError) as exc:
            st.error(str(exc))

    if payload := st.session_state.get(_REPORT_KEY):
        _render_report(JobCollectionReport.model_validate(payload))
