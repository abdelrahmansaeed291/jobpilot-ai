"""Supabase persistence for discovered jobs saved by the candidate."""

from typing import Any

from supabase import Client

from models.job_discovery import SavedJob

SAVED_JOBS_TABLE = "saved_jobs"


class SavedJobRepositoryError(RuntimeError):
    """Raised when a saved-job persistence operation fails."""


class SupabaseSavedJobRepository:
    """Persist shortlisted public jobs for the personal JobPilot user."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def save(self, job: SavedJob) -> SavedJob:
        """Upsert a job by original URL and return the stored row."""
        payload = job.model_dump(
            mode="json", exclude={"id", "saved_at"}, exclude_none=True
        )
        try:
            response = (
                self._client.table(SAVED_JOBS_TABLE)
                .upsert(payload, on_conflict="url")
                .execute()
            )
            data: Any = response.data
            row = data[0] if isinstance(data, list) and data else data
            if not row:
                raise RuntimeError("Supabase returned no saved job row.")
            return SavedJob.model_validate(row)
        except Exception as exc:
            raise SavedJobRepositoryError(
                "The job could not be saved. Apply migration 003 and retry."
            ) from exc

    def list_saved(self) -> list[SavedJob]:
        """List saved jobs from newest to oldest."""
        try:
            response = (
                self._client.table(SAVED_JOBS_TABLE)
                .select("*")
                .order("saved_at", desc=True)
                .execute()
            )
            return [SavedJob.model_validate(row) for row in (response.data or [])]
        except Exception as exc:
            raise SavedJobRepositoryError(
                "Saved jobs could not be loaded. Apply migration 003 and retry."
            ) from exc
