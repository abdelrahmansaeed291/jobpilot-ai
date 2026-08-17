"""Persistent job-search preferences page."""

from datetime import datetime

import pandas as pd
import streamlit as st

from components.app_theme import render_feature_hero
from database.context_repository import (
    CandidateContextRepositoryError,
    SupabaseCandidateContextRepository,
)
from database.supabase_client import (
    SupabaseConfigurationError,
    create_supabase_client_from_env,
)
from models.candidate_context import (
    EmploymentType,
    JobPreferences,
    LanguageRequirement,
    SearchRecency,
    WorkMode,
)

_STATE_KEY = "job-preferences-value"
_LOADED_KEY = "job-preferences-loaded"


@st.cache_resource
def _repository() -> SupabaseCandidateContextRepository:
    """Create the reusable Supabase repository."""
    return SupabaseCandidateContextRepository(create_supabase_client_from_env())


def _lines(values: list[str]) -> str:
    return "\n".join(values)


def _parse_lines(value: str) -> list[str]:
    items = [item.strip() for item in value.replace(",", "\n").splitlines()]
    return list(dict.fromkeys(item for item in items if item))


def _date(value: datetime | None) -> str:
    return value.astimezone().strftime("%d %b %Y") if value else "Not saved"


def _languages_frame(values: list[LanguageRequirement]) -> pd.DataFrame:
    return pd.DataFrame(
        [item.model_dump() for item in values],
        columns=["language", "proficiency"],
    )


def render() -> None:
    """Render and persist job discovery and matching preferences."""
    render_feature_hero(
        "Search strategy",
        "Job Preferences",
        "Define what a great opportunity looks like before JobPilot starts matching.",
        "◎",
        ("#4338ca", "#db2777"),
    )
    try:
        repository = _repository()
        if not st.session_state.get(_LOADED_KEY):
            st.session_state[_STATE_KEY] = (
                repository.get_job_preferences() or JobPreferences()
            )
            st.session_state[_LOADED_KEY] = True
    except (SupabaseConfigurationError, CandidateContextRepositoryError) as exc:
        st.error(str(exc))
        return

    value: JobPreferences = st.session_state[_STATE_KEY]
    status_left, status_middle, status_right = st.columns(3)
    status_left.metric("Target roles", len(value.target_job_titles))
    status_middle.metric("Minimum match", f"{value.minimum_match_score}%")
    status_right.metric("Last updated", _date(value.updated_at))

    with st.form("job-preferences-form"):
        targets_tab, work_tab, filters_tab, limits_tab = st.tabs(
            ["🎯 Targets", "🏢 Work style", "🔎 Filters", "⚙️ Limits"]
        )
        with targets_tab:
            left, right = st.columns(2)
            target_titles = left.text_area(
                "Target job titles",
                value=_lines(value.target_job_titles),
                height=180,
                help="One title per line.",
            )
            preferred_locations = right.text_area(
                "Preferred locations",
                value=_lines(value.preferred_locations),
                height=180,
                help="One city or region per line.",
            )
            country = st.text_input("Country", value=value.country)

        with work_tab:
            work_modes = st.multiselect(
                "Work arrangement",
                options=[item.value for item in WorkMode],
                default=[item.value for item in value.work_modes],
            )
            employment_types = st.multiselect(
                "Employment type",
                options=[item.value for item in EmploymentType],
                default=[item.value for item in value.employment_types],
            )
            preferred_companies = st.text_area(
                "Preferred companies",
                value=_lines(value.preferred_companies),
                height=130,
            )
            excluded_companies = st.text_area(
                "Excluded companies",
                value=_lines(value.excluded_companies),
                height=130,
            )

        with filters_tab:
            industry_left, industry_right = st.columns(2)
            preferred_industries = industry_left.text_area(
                "Preferred industries",
                value=_lines(value.preferred_industries),
                height=160,
            )
            excluded_industries = industry_right.text_area(
                "Excluded industries",
                value=_lines(value.excluded_industries),
                height=160,
            )
            st.markdown("#### Language requirements")
            language_frame = st.data_editor(
                _languages_frame(value.language_requirements),
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
            )

        with limits_tab:
            minimum_match_score = st.slider(
                "Minimum match score",
                min_value=0,
                max_value=100,
                value=value.minimum_match_score,
                step=5,
            )
            maximum_experience = st.number_input(
                "Maximum acceptable required experience (years)",
                min_value=0.0,
                max_value=50.0,
                value=float(value.maximum_required_experience),
                step=0.5,
            )
            search_recency = st.select_slider(
                "Search recency",
                options=[item.value for item in SearchRecency],
                value=value.search_recency.value,
            )

        submitted = st.form_submit_button(
            "Save job preferences", type="primary", use_container_width=True
        )

    if not submitted:
        return
    language_requirements = []
    for row in language_frame.to_dict(orient="records"):
        language = "" if pd.isna(row.get("language")) else str(row["language"]).strip()
        proficiency = (
            "" if pd.isna(row.get("proficiency")) else str(row["proficiency"]).strip()
        )
        if language:
            language_requirements.append(
                LanguageRequirement(language=language, proficiency=proficiency)
            )
    try:
        saved = repository.save_job_preferences(
            value.model_copy(
                update={
                    "target_job_titles": _parse_lines(target_titles),
                    "preferred_locations": _parse_lines(preferred_locations),
                    "country": country.strip(),
                    "work_modes": [WorkMode(item) for item in work_modes],
                    "employment_types": [EmploymentType(item) for item in employment_types],
                    "minimum_match_score": minimum_match_score,
                    "preferred_industries": _parse_lines(preferred_industries),
                    "excluded_industries": _parse_lines(excluded_industries),
                    "preferred_companies": _parse_lines(preferred_companies),
                    "excluded_companies": _parse_lines(excluded_companies),
                    "language_requirements": language_requirements,
                    "maximum_required_experience": maximum_experience,
                    "search_recency": SearchRecency(search_recency),
                }
            )
        )
        st.session_state[_STATE_KEY] = saved
        st.success("Job preferences saved to Supabase.")
        st.rerun()
    except (ValueError, CandidateContextRepositoryError) as exc:
        st.error(f"Could not save job preferences: {exc}")
