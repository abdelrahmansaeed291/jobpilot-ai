"""Supabase repositories for extra information and job preferences."""

from typing import Any, TypeVar

from pydantic import BaseModel
from supabase import Client

from models.candidate_context import CandidateExtraInformation, JobPreferences

EXTRA_INFORMATION_TABLE = "candidate_extra_information"
JOB_PREFERENCES_TABLE = "job_preferences"
ContextModel = TypeVar("ContextModel", bound=BaseModel)


class CandidateContextRepositoryError(RuntimeError):
    """Raised when extra information or preference persistence fails."""


class SupabaseCandidateContextRepository:
    """Persist personal candidate context in Supabase singleton rows."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def get_extra_information(self) -> CandidateExtraInformation | None:
        """Load manually curated candidate information."""
        return self._get(
            EXTRA_INFORMATION_TABLE,
            CandidateExtraInformation,
            "extra information",
        )

    def save_extra_information(
        self, value: CandidateExtraInformation
    ) -> CandidateExtraInformation:
        """Persist manually curated candidate information."""
        return self._save(EXTRA_INFORMATION_TABLE, value, CandidateExtraInformation)

    def get_job_preferences(self) -> JobPreferences | None:
        """Load persistent job preferences."""
        return self._get(JOB_PREFERENCES_TABLE, JobPreferences, "job preferences")

    def save_job_preferences(self, value: JobPreferences) -> JobPreferences:
        """Persist job preferences."""
        return self._save(JOB_PREFERENCES_TABLE, value, JobPreferences)

    def _get(
        self,
        table: str,
        model_type: type[ContextModel],
        label: str,
    ) -> ContextModel | None:
        try:
            response = (
                self._client.table(table)
                .select("*")
                .eq("id", "00000000-0000-0000-0000-000000000001")
                .maybe_single()
                .execute()
            )
            if response is None or not response.data:
                return None
            return model_type.model_validate(response.data)
        except Exception as exc:
            raise CandidateContextRepositoryError(
                f"Could not load {label} from Supabase. Apply migration 002 and retry."
            ) from exc

    def _save(
        self,
        table: str,
        value: ContextModel,
        model_type: type[ContextModel],
    ) -> ContextModel:
        payload = value.model_dump(mode="json", exclude={"updated_at"})
        try:
            response = self._client.table(table).upsert(payload, on_conflict="id").execute()
            data: Any = response.data
            row = data[0] if isinstance(data, list) and data else data
            if not row:
                raise RuntimeError("Supabase returned no saved row.")
            return model_type.model_validate(row)
        except Exception as exc:
            raise CandidateContextRepositoryError(
                "Could not save the information to Supabase. Your form is unchanged."
            ) from exc
