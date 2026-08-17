"""Read-only candidate portfolio page."""

import streamlit as st

from components.profile_view import render_candidate_portfolio
from database.context_repository import (
    CandidateContextRepositoryError,
    SupabaseCandidateContextRepository,
)
from database.profile_repository import ProfileRepositoryError, SupabaseProfileRepository
from database.supabase_client import (
    SupabaseConfigurationError,
    create_supabase_client_from_env,
)
from models.candidate_context import CandidateExtraInformation


@st.cache_resource
def _repositories() -> tuple[
    SupabaseProfileRepository, SupabaseCandidateContextRepository
]:
    """Create reusable Supabase repositories for portfolio data."""
    client = create_supabase_client_from_env()
    return SupabaseProfileRepository(client), SupabaseCandidateContextRepository(client)


def render() -> None:
    """Render persisted candidate data as a polished, non-editable portfolio."""
    try:
        profile_repository, context_repository = _repositories()
        profile = profile_repository.get_profile()
    except SupabaseConfigurationError as exc:
        st.warning(str(exc))
        return
    except ProfileRepositoryError as exc:
        st.error(str(exc))
        if st.button("Retry connection", use_container_width=True):
            st.rerun()
        return

    if profile is None:
        st.info(
            "Your portfolio is waiting for its first CV. Open **CV & Extra Information** "
            "from the sidebar to upload and extract it."
        )
        return

    try:
        extra = context_repository.get_extra_information() or CandidateExtraInformation()
    except CandidateContextRepositoryError as exc:
        st.warning(
            "Your CV profile is available, but manual additions could not be loaded: "
            f"{exc}"
        )
        extra = CandidateExtraInformation()

    render_candidate_portfolio(profile, extra)
    st.info(
        "This page is your read-only portfolio. To update anything, use "
        "**CV & Extra Information** in the sidebar."
    )
