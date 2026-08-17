"""Editable Streamlit form for structured candidate profile fields."""

from typing import TypeVar

import pandas as pd
import streamlit as st
from pydantic import BaseModel

from models.candidate_profile import (
    CandidateProfile,
    CertificationEntry,
    EducationEntry,
    LanguageEntry,
    ProjectEntry,
    WorkExperienceEntry,
)

EntryModel = TypeVar("EntryModel", bound=BaseModel)


def _frame(entries: list[BaseModel], columns: list[str]) -> pd.DataFrame:
    """Create an editor-ready DataFrame, including columns for an empty list."""
    records = [entry.model_dump() for entry in entries]
    for record in records:
        if "technologies" in record:
            record["technologies"] = ", ".join(record["technologies"])
    return pd.DataFrame(records, columns=columns)


def _clean_cell(value: object) -> str:
    """Convert a data-editor cell into a normalized string."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _entries(
    frame: pd.DataFrame,
    model_type: type[EntryModel],
    list_fields: tuple[str, ...] = (),
) -> list[EntryModel]:
    """Convert non-empty editor rows into validated Pydantic models."""
    results: list[EntryModel] = []
    for raw_record in frame.to_dict(orient="records"):
        record: dict[str, object] = {
            key: _clean_cell(value) for key, value in raw_record.items()
        }
        for field in list_fields:
            record[field] = [
                item.strip()
                for item in str(record.get(field, "")).split(",")
                if item.strip()
            ]
        if any(value for value in record.values()):
            results.append(model_type.model_validate(record))
    return results


def _parse_skills(value: str) -> list[str]:
    """Parse newline- or comma-separated skills while preserving order."""
    skills = [item.strip() for item in value.replace(",", "\n").splitlines()]
    return list(dict.fromkeys(skill for skill in skills if skill))


def render_profile_editor(profile: CandidateProfile) -> CandidateProfile | None:
    """Render the profile form and return edits only when it is submitted."""
    with st.form("candidate-profile-editor"):
        overview_tab, education_tab, experience_tab, more_tab = st.tabs(
            ["👤 Overview", "🎓 Education", "💼 Experience", "✨ More"]
        )

        with overview_tab:
            st.caption("Your core contact details and professional positioning.")
            contact_left, contact_middle, contact_right = st.columns(3)
            name = contact_left.text_input("Name", value=profile.name)
            email = contact_middle.text_input("Email", value=profile.email)
            location = contact_right.text_input("Location", value=profile.location)
            summary = st.text_area(
                "Professional summary",
                value=profile.professional_summary,
                height=150,
            )
            skills = st.text_area(
                "Technical skills",
                value="\n".join(profile.technical_skills),
                help="Enter one skill per line or separate skills with commas.",
                height=180,
            )

        with education_tab:
            st.caption("Add, remove, or update your education history.")
            education_frame = st.data_editor(
                _frame(
                    profile.education,
                    [
                        "institution",
                        "degree",
                        "field_of_study",
                        "start_date",
                        "end_date",
                        "description",
                    ],
                ),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="profile-education",
            )

        with experience_tab:
            st.caption("Keep your roles and impact statements accurate and current.")
            work_frame = st.data_editor(
                _frame(
                    profile.work_experience,
                    [
                        "company",
                        "job_title",
                        "location",
                        "start_date",
                        "end_date",
                        "description",
                    ],
                ),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="profile-work-experience",
            )

        with more_tab:
            st.markdown("#### Languages")
            language_frame = st.data_editor(
                _frame(profile.languages, ["name", "proficiency"]),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="profile-languages",
            )

            st.markdown("#### Certifications")
            certification_frame = st.data_editor(
                _frame(
                    profile.certifications,
                    ["name", "issuer", "date", "credential_url"],
                ),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="profile-certifications",
            )

            st.markdown("#### Projects")
            project_frame = st.data_editor(
                _frame(
                    profile.projects,
                    ["name", "description", "technologies", "url"],
                ),
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="profile-projects",
            )

        submitted = st.form_submit_button(
            "Save profile", type="primary", use_container_width=True
        )

    if not submitted:
        return None

    return profile.model_copy(
        update={
            "name": name.strip(),
            "email": email.strip(),
            "location": location.strip(),
            "professional_summary": summary.strip(),
            "technical_skills": _parse_skills(skills),
            "education": _entries(education_frame, EducationEntry),
            "work_experience": _entries(work_frame, WorkExperienceEntry),
            "languages": _entries(language_frame, LanguageEntry),
            "certifications": _entries(
                certification_frame, CertificationEntry
            ),
            "projects": _entries(
                project_frame, ProjectEntry, list_fields=("technologies",)
            ),
        }
    )
