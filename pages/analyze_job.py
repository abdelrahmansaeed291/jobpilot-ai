"""Structured job analysis and deterministic matching page."""

import os
from html import escape

import plotly.graph_objects as go
import streamlit as st

from components.app_theme import render_feature_hero
from database.context_repository import (
    CandidateContextRepositoryError,
    SupabaseCandidateContextRepository,
)
from database.profile_repository import ProfileRepositoryError, SupabaseProfileRepository
from database.supabase_client import create_supabase_client_from_env
from models.job_profile import JobProfile, MatchResult
from services.candidate_context_service import build_normalized_candidate_profile
from services.gemini_cv_extractor import DEFAULT_GEMINI_MODEL
from services.job_analyzer import GeminiJobAnalyzer, JobAnalysisError
from services.job_matching import JobMatchingEngine

_JOB_KEY = "analyzed-job-profile"
_MATCH_KEY = "analyzed-job-match"


@st.cache_data(ttl=3600, show_spinner=False)
def _analyze_cached(description: str, model: str) -> JobProfile:
    """Cache identical Gemini job extractions for one hour."""
    analyzer = GeminiJobAnalyzer(
        api_key=os.getenv("GEMINI_API_KEY", ""), model=model
    )
    return analyzer.analyze(description)


@st.cache_resource
def _matching_engine() -> JobMatchingEngine:
    """Load SentenceTransformer only once for the Streamlit process."""
    return JobMatchingEngine()


def _chips(values: list[str], empty_text: str = "None stated") -> None:
    """Render compact colorful value chips."""
    if not values:
        st.caption(empty_text)
        return
    chips = "".join(
        f'<span style="display:inline-block;padding:.32rem .68rem;margin:.2rem;'
        'border-radius:999px;background:linear-gradient(100deg,#ede9fe,#cffafe);'
        'color:#4338ca;font-size:.82rem;font-weight:700">'
        f"{escape(value)}</span>"
        for value in values
    )
    st.markdown(chips, unsafe_allow_html=True)


def _render_job_profile(job: JobProfile) -> None:
    """Show Gemini-extracted information before matching is available."""
    st.markdown("### ✦ Extracted job profile")
    title, company, location, employment = st.columns(4)
    title.metric("Role", job.job_title or "Not stated")
    company.metric("Company", job.company or "Not stated")
    location.metric("Location", job.location or "Not stated")
    employment.metric("Type", job.employment_type or "Not stated")

    responsibilities_tab, skills_tab, requirements_tab, details_tab = st.tabs(
        ["Responsibilities", "Skills", "Requirements", "Details"]
    )
    with responsibilities_tab:
        if job.responsibilities:
            for responsibility in job.responsibilities:
                st.markdown(f"- {responsibility}")
        else:
            st.caption("No explicit responsibilities found.")
    with skills_tab:
        st.markdown("**Required skills**")
        _chips(job.required_skills)
        st.markdown("**Preferred skills**")
        _chips(job.preferred_skills)
        st.markdown("**Technologies**")
        _chips(job.technologies)
    with requirements_tab:
        st.markdown("**Education**")
        _chips(job.education_requirements)
        experience = job.experience_requirements
        experience_text = experience.description or (
            f"{experience.minimum_years:g}+ years"
            if experience.minimum_years is not None
            else "Not stated"
        )
        st.markdown(f"**Experience:** {experience_text}")
        st.markdown("**Languages**")
        _chips(
            [
                f"{item.language} · {item.proficiency} · "
                f"{'Required' if item.required else 'Preferred'}"
                for item in job.language_requirements
            ]
        )
    with details_tab:
        detail_left, detail_right = st.columns(2)
        detail_left.markdown(f"**Seniority:** {job.seniority or 'Not stated'}")
        detail_left.markdown(f"**Work mode:** {job.work_mode or 'Not stated'}")
        detail_right.markdown(
            f"**Industry/domain:** {job.industry_domain or 'Not stated'}"
        )
        st.markdown("**Benefits**")
        _chips(job.benefits)


def _score_figure(result: MatchResult) -> go.Figure:
    labels = [
        "Required skills",
        "Preferred skills",
        "Experience",
        "Education",
        "Languages",
        "Responsibilities",
        "Preferences",
    ]
    values = [
        result.required_skills_score,
        result.preferred_skills_score,
        result.experience_score,
        result.education_score,
        result.language_score,
        result.responsibility_score,
        result.preference_score,
    ]
    colors = ["#4f46e5", "#7c3aed", "#0891b2", "#0d9488", "#16a34a", "#db2777", "#f59e0b"]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{value:.0f}%" for value in values],
            textposition="auto",
        )
    )
    figure.update_layout(
        height=390,
        margin=dict(l=10, r=20, t=15, b=10),
        xaxis=dict(range=[0, 100], showgrid=False, title=None),
        yaxis=dict(autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return figure


def _render_list_card(title: str, icon: str, values: list[str]) -> None:
    with st.container(border=True):
        st.markdown(f"#### {icon} {title}")
        if values:
            for value in values:
                st.markdown(f"- {value}")
        else:
            st.caption("Nothing identified.")


def _render_match(result: MatchResult) -> None:
    """Render the deterministic result and explainability evidence."""
    recommendation_colors = {
        "Strong Apply": ("#047857", "#10b981"),
        "Apply": ("#2563eb", "#7c3aed"),
        "Consider": ("#d97706", "#f59e0b"),
        "Low Match": ("#b91c1c", "#ef4444"),
    }
    start, end = recommendation_colors[result.recommendation]
    st.markdown(
        f"""
        <div style="padding:1.45rem 1.7rem;border-radius:20px;color:white;
          background:linear-gradient(110deg,{start},{end});
          box-shadow:0 14px 34px rgba(79,70,229,.18);margin:1.2rem 0">
          <div style="font-size:.75rem;font-weight:800;letter-spacing:.1em">DETERMINISTIC MATCH</div>
          <div style="font-size:3rem;font-weight:900;line-height:1.1">{result.overall_match:.0f}%</div>
          <div style="font-size:1.2rem;font-weight:750">{escape(result.recommendation)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "The percentage is calculated from fixed scoring functions. Gemini cannot modify it."
    )
    st.plotly_chart(_score_figure(result), use_container_width=True)
    left, right = st.columns(2)
    with left:
        _render_list_card("Strong matches", "✅", result.strong_matches)
        _render_list_card("Partial matches", "◐", result.partial_matches)
        _render_list_card("Nice-to-have gaps", "☆", result.nice_to_have_gaps)
    with right:
        _render_list_card("Missing requirements", "△", result.missing_requirements)
        _render_list_card(
            "Potential deal breakers", "⚠", result.potential_deal_breakers
        )


def _calculate_match(job: JobProfile) -> MatchResult:
    """Load fresh persistent context and run deterministic matching."""
    client = create_supabase_client_from_env()
    profile = SupabaseProfileRepository(client).get_profile()
    if profile is None:
        raise ProfileRepositoryError("Save your candidate profile before matching.")
    context_repository = SupabaseCandidateContextRepository(client)
    extra = context_repository.get_extra_information()
    preferences = context_repository.get_job_preferences()
    normalized = build_normalized_candidate_profile(profile, extra, preferences)
    return _matching_engine().match(normalized, job)


def render() -> None:
    """Render job extraction first, then deterministic candidate matching."""
    render_feature_hero(
        "Evidence-based matching",
        "Analyze a Job",
        "Turn any job description into structured requirements, then calculate an explainable match.",
        "✦",
        ("#312e81", "#0891b2"),
    )
    with st.container(border=True):
        job_description = st.text_area(
            "Paste the complete job description",
            height=330,
            placeholder="Paste the role, responsibilities, and requirements here…",
        )
        analyze_clicked = st.button(
            "Analyze job description",
            type="primary",
            use_container_width=True,
            disabled=len(job_description.strip()) < 80,
        )
    if analyze_clicked:
        try:
            with st.spinner("Gemini is structuring the job description..."):
                model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
                st.session_state[_JOB_KEY] = _analyze_cached(job_description, model)
                st.session_state.pop(_MATCH_KEY, None)
        except JobAnalysisError as exc:
            st.error(str(exc))

    job: JobProfile | None = st.session_state.get(_JOB_KEY)
    if job is None:
        return
    _render_job_profile(job)
    st.divider()
    if st.button(
        "Calculate deterministic match",
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("Comparing skills, experience, education, and preferences..."):
                st.session_state[_MATCH_KEY] = _calculate_match(job)
        except (
            ProfileRepositoryError,
            CandidateContextRepositoryError,
            RuntimeError,
        ) as exc:
            st.error(str(exc))
    result: MatchResult | None = st.session_state.get(_MATCH_KEY)
    if result is not None:
        _render_match(result)
