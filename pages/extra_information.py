"""Unified CV extraction, profile editing, and extra-information workspace."""

from datetime import datetime

import pandas as pd
import streamlit as st

from components.app_theme import render_feature_hero
from components.profile_editor import render_profile_editor
from components.profile_theme import render_profile_styles, render_status_card
from database.context_repository import (
    CandidateContextRepositoryError,
    SupabaseCandidateContextRepository,
)
from database.profile_repository import ProfileRepositoryError, SupabaseProfileRepository
from database.supabase_client import (
    SupabaseConfigurationError,
    create_supabase_client_from_env,
)
from models.candidate_context import (
    AdditionalCertification,
    AdditionalExperience,
    AdditionalProject,
    CandidateExtraInformation,
    CandidateSkill,
    SkillProficiency,
    SkillSource,
)
from models.candidate_profile import CandidateProfile
from services.cv_parser import CVParsingError
from services.gemini_cv_extractor import gemini_is_configured
from services.profile_service import ProfileService

_PROFILE_STATE_KEY = "candidate-profile"
_PROFILE_LOADED_KEY = "candidate-profile-loaded"
_PROFILE_FLASH_KEY = "candidate-profile-flash"
_PROFILE_WARNING_KEY = "candidate-profile-warning"
_EXTRA_STATE_KEY = "extra-information-value"
_EXTRA_LOADED_KEY = "extra-information-loaded"


@st.cache_resource
def _services() -> tuple[ProfileService, SupabaseCandidateContextRepository]:
    """Create reusable profile and context services for this Streamlit process."""
    client = create_supabase_client_from_env()
    return (
        ProfileService(SupabaseProfileRepository(client)),
        SupabaseCandidateContextRepository(client),
    )


def _format_date(value: datetime | None) -> str:
    """Format a timestamp as a simple local date."""
    return value.astimezone().strftime("%d %b %Y") if value else "Not saved"


def _set_profile(profile: CandidateProfile, message: str) -> None:
    """Refresh session state after a successful profile write."""
    st.session_state[_PROFILE_STATE_KEY] = profile
    st.session_state[_PROFILE_LOADED_KEY] = True
    st.session_state[_PROFILE_FLASH_KEY] = message
    if profile.extraction_warning:
        st.session_state[_PROFILE_WARNING_KEY] = profile.extraction_warning


def _load_profile(service: ProfileService) -> CandidateProfile | None:
    """Load structured profile data once without downloading or reparsing its CV."""
    if not st.session_state.get(_PROFILE_LOADED_KEY, False):
        st.session_state[_PROFILE_STATE_KEY] = service.load_profile()
        st.session_state[_PROFILE_LOADED_KEY] = True
    return st.session_state.get(_PROFILE_STATE_KEY)


def _frame(items: list[object], columns: list[str]) -> pd.DataFrame:
    """Convert Pydantic entries to editable rows."""
    records: list[dict[str, object]] = []
    for item in items:
        record = item.model_dump(mode="json")  # type: ignore[attr-defined]
        if "technologies" in record:
            record["technologies"] = ", ".join(record["technologies"])
        records.append(record)
    return pd.DataFrame(records, columns=columns)


def _clean(value: object) -> str:
    """Normalize an editable-grid value to a stripped string."""
    return "" if value is None or pd.isna(value) else str(value).strip()


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Return non-empty normalized records from an editable grid."""
    return [
        {key: _clean(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
        if any(_clean(value) for value in row.values())
    ]


def _technology_list(value: object) -> list[str]:
    """Parse comma-separated technologies while removing blanks."""
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _seed_extra(profile: CandidateProfile) -> CandidateExtraInformation:
    """Seed CV-derived skills when no manual context row exists yet."""
    return CandidateExtraInformation(
        skills=[
            CandidateSkill(
                skill_name=skill,
                proficiency_level=SkillProficiency.INTERMEDIATE,
                source=SkillSource.CV,
            )
            for skill in profile.technical_skills
        ]
    )


def _render_cv_workspace(
    service: ProfileService,
    profile: CandidateProfile,
    saved_profile: CandidateProfile | None,
) -> None:
    """Render CV upload, replacement, re-extraction, and extraction diagnostics."""
    with st.container(border=True):
        st.markdown("### Upload and extract your CV")
        st.caption(
            "Your original PDF is kept privately in Supabase. It is parsed only when "
            "you upload, replace, or explicitly re-extract it."
        )
        if gemini_is_configured():
            st.success("Gemini structured extraction is configured and ready.")
        else:
            st.warning(
                "GEMINI_API_KEY is not configured. Uploads will use the limited local extractor."
            )

        uploaded_cv = st.file_uploader(
            "Upload or replace CV",
            type=("pdf",),
            help="PDF only, maximum 10 MB.",
        )
        reextract_column, upload_column = st.columns(2)
        with reextract_column:
            reextract_clicked = st.button(
                "✨ Re-extract saved CV",
                disabled=not profile.parsed_cv_text or not gemini_is_configured(),
                use_container_width=True,
            )
        with upload_column:
            upload_clicked = st.button(
                "Process and save CV" if not profile.cv_file_path else "↻ Replace CV",
                type="primary",
                disabled=uploaded_cv is None,
                use_container_width=True,
            )

        if reextract_clicked:
            try:
                with st.spinner("Structuring the saved CV text with Gemini..."):
                    updated = service.reextract_saved_cv(profile)
                _set_profile(updated, "Saved CV text re-extracted and profile updated.")
                st.rerun()
            except (CVParsingError, ProfileRepositoryError) as exc:
                st.error(str(exc))

        if upload_clicked and uploaded_cv is not None:
            try:
                with st.spinner("Extracting, structuring, and saving your CV..."):
                    updated = service.replace_cv(
                        uploaded_cv.getvalue(),
                        uploaded_cv.name,
                        saved_profile,
                    )
                _set_profile(updated, "CV and extracted profile saved to Supabase.")
                st.rerun()
            except (CVParsingError, ProfileRepositoryError) as exc:
                st.error(str(exc))

    if profile.parsed_cv_text:
        with st.expander("View extraction output and parsed text"):
            json_tab, text_tab = st.tabs(["Structured JSON", "Parsed CV text"])
            with json_tab:
                st.json(
                    profile.model_dump(
                        mode="json",
                        exclude={
                            "id",
                            "cv_file_path",
                            "parsed_cv_text",
                            "updated_at",
                            "extraction_method",
                            "extraction_warning",
                        },
                    )
                )
            with text_tab:
                st.text_area(
                    "Parsed CV text",
                    value=profile.parsed_cv_text,
                    height=340,
                    disabled=True,
                    label_visibility="collapsed",
                )


def _render_extracted_profile_editor(
    service: ProfileService, profile: CandidateProfile
) -> None:
    """Render manual correction controls for Gemini-extracted profile fields."""
    st.info(
        "Review Gemini's extraction here. Your changes are saved to Supabase and "
        "immediately appear in the read-only My Profile portfolio."
    )
    edited_profile = render_profile_editor(profile)
    if edited_profile is None:
        return
    try:
        with st.spinner("Saving corrected profile..."):
            saved = service.save_profile(edited_profile)
        _set_profile(saved, "Extracted profile changes saved.")
        st.rerun()
    except ProfileRepositoryError as exc:
        st.error(str(exc))


def _render_extra_editor(
    repository: SupabaseCandidateContextRepository,
    profile: CandidateProfile,
) -> None:
    """Render fields for useful candidate details not captured by the CV."""
    try:
        if not st.session_state.get(_EXTRA_LOADED_KEY, False):
            st.session_state[_EXTRA_STATE_KEY] = (
                repository.get_extra_information() or _seed_extra(profile)
            )
            st.session_state[_EXTRA_LOADED_KEY] = True
    except CandidateContextRepositoryError as exc:
        st.error(str(exc))
        return

    value: CandidateExtraInformation = st.session_state[_EXTRA_STATE_KEY]
    summary_left, summary_middle, summary_right = st.columns(3)
    summary_left.metric("Manual skills", len(value.skills))
    summary_middle.metric("Extra experiences", len(value.additional_experience))
    summary_right.metric("Last updated", _format_date(value.updated_at))

    with st.form("extra-information-form"):
        skills_tab, experience_tab, projects_tab, other_tab = st.tabs(
            ["⚡ Skills", "🧭 Experience", "🚀 Projects", "📝 More"]
        )
        with skills_tab:
            st.caption("Add rows, edit cells, or remove rows you no longer need.")
            skills_frame = st.data_editor(
                _frame(
                    value.skills,
                    ["skill_name", "proficiency_level", "source", "notes"],
                ),
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "skill_name": "Skill",
                    "proficiency_level": st.column_config.SelectboxColumn(
                        "Proficiency", options=[item.value for item in SkillProficiency]
                    ),
                    "source": st.column_config.SelectboxColumn(
                        "Source", options=[item.value for item in SkillSource]
                    ),
                    "notes": "Notes",
                },
            )
        with experience_tab:
            experience_frame = st.data_editor(
                _frame(
                    value.additional_experience,
                    ["title", "description", "technologies", "date"],
                ),
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                column_config={"technologies": "Technologies (comma separated)"},
            )
        with projects_tab:
            projects_frame = st.data_editor(
                _frame(
                    value.projects,
                    ["project_name", "description", "technologies", "url", "github_url"],
                ),
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "project_name": "Project",
                    "technologies": "Technologies (comma separated)",
                    "github_url": "GitHub URL",
                },
            )
        with other_tab:
            st.markdown("#### Certifications")
            certifications_frame = st.data_editor(
                _frame(value.certifications, ["name", "issuer", "date"]),
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
            )
            st.markdown("#### Other information")
            other_information = st.text_area(
                "Facts, constraints, achievements, or stories the AI may use later",
                value=value.other_information,
                height=220,
            )
        submitted = st.form_submit_button(
            "Save additional information", type="primary", use_container_width=True
        )

    if not submitted:
        return
    try:
        skills = [CandidateSkill.model_validate(row) for row in _records(skills_frame)]
        experiences: list[AdditionalExperience] = []
        for row in _records(experience_frame):
            row["technologies"] = _technology_list(row.get("technologies", ""))
            experiences.append(AdditionalExperience.model_validate(row))
        projects: list[AdditionalProject] = []
        for row in _records(projects_frame):
            row["technologies"] = _technology_list(row.get("technologies", ""))
            projects.append(AdditionalProject.model_validate(row))
        certifications = [
            AdditionalCertification.model_validate(row)
            for row in _records(certifications_frame)
        ]
        saved = repository.save_extra_information(
            value.model_copy(
                update={
                    "skills": skills,
                    "additional_experience": experiences,
                    "projects": projects,
                    "certifications": certifications,
                    "other_information": other_information.strip(),
                }
            )
        )
        st.session_state[_EXTRA_STATE_KEY] = saved
        st.success("Additional information saved to Supabase.")
        st.rerun()
    except (ValueError, CandidateContextRepositoryError) as exc:
        st.error(f"Could not save extra information: {exc}")


def render() -> None:
    """Render the single workspace for all candidate-profile changes."""
    render_profile_styles()
    render_feature_hero(
        "Profile studio",
        "CV & Extra Information",
        "Upload and extract your CV, correct its structured data, and add everything the CV leaves out.",
        "✨",
        ("#0f766e", "#7c3aed"),
    )

    if message := st.session_state.pop(_PROFILE_FLASH_KEY, None):
        st.success(message)
    if warning := st.session_state.pop(_PROFILE_WARNING_KEY, None):
        st.warning(warning)

    try:
        profile_service, context_repository = _services()
        saved_profile = _load_profile(profile_service)
    except SupabaseConfigurationError as exc:
        st.warning(str(exc))
        return
    except ProfileRepositoryError as exc:
        st.error(str(exc))
        if st.button("Retry connection", use_container_width=True):
            st.session_state[_PROFILE_LOADED_KEY] = False
            st.rerun()
        return

    profile = saved_profile or CandidateProfile()
    status, updated, cv = st.columns(3)
    with status:
        render_status_card("✨", "Profile", "Ready" if saved_profile else "Not saved")
    with updated:
        render_status_card("📅", "Last updated", _format_date(profile.updated_at))
    with cv:
        render_status_card("📄", "CV", "Stored" if profile.cv_file_path else "Not uploaded")

    cv_tab, profile_tab, extras_tab = st.tabs(
        ["📄 CV & Extraction", "✏️ Edit Extracted Profile", "➕ Additional Information"]
    )
    with cv_tab:
        _render_cv_workspace(profile_service, profile, saved_profile)
    with profile_tab:
        _render_extracted_profile_editor(profile_service, profile)
    with extras_tab:
        _render_extra_editor(context_repository, profile)
