"""Supabase persistence for candidate profiles and original CV files."""

from pathlib import Path
from typing import Any
from uuid import UUID

from supabase import Client

from models.candidate_profile import CandidateProfile, DEFAULT_PROFILE_ID

PROFILE_TABLE = "candidate_profiles"
CV_BUCKET = "candidate-cvs"


class ProfileRepositoryError(RuntimeError):
    """Raised when candidate profile persistence fails."""


class SupabaseProfileRepository:
    """Store and retrieve the single-user profile through Supabase."""

    def __init__(self, client: Client, bucket: str = CV_BUCKET) -> None:
        self._client = client
        self._bucket = bucket

    def get_profile(
        self, profile_id: UUID = DEFAULT_PROFILE_ID
    ) -> CandidateProfile | None:
        """Load the structured profile without downloading or parsing its CV."""
        try:
            response = (
                self._client.table(PROFILE_TABLE)
                .select("*")
                .eq("id", str(profile_id))
                .maybe_single()
                .execute()
            )
            if response is None or not response.data:
                return None
            return CandidateProfile.model_validate(response.data)
        except Exception as exc:
            raise ProfileRepositoryError(
                "The profile could not be loaded from Supabase. "
                "Check the connection, migration, and credentials."
            ) from exc

    def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Upsert the profile and return the database representation."""
        payload = profile.model_dump(mode="json", exclude={"updated_at"})
        try:
            response = (
                self._client.table(PROFILE_TABLE)
                .upsert(payload, on_conflict="id")
                .execute()
            )
            data: Any = response.data
            row = data[0] if isinstance(data, list) and data else data
            if not row:
                raise RuntimeError("Supabase returned no saved profile row.")
            return CandidateProfile.model_validate(row)
        except Exception as exc:
            raise ProfileRepositoryError(
                "The profile could not be saved to Supabase. "
                "Your current form values remain on this page."
            ) from exc

    def upload_cv(
        self,
        pdf_bytes: bytes,
        original_filename: str,
        profile_id: UUID = DEFAULT_PROFILE_ID,
    ) -> str:
        """Upload or replace the original CV and return its private storage path."""
        storage_path = f"profiles/{profile_id}/cv.pdf"
        safe_original_name = Path(original_filename).name
        try:
            self._client.storage.from_(self._bucket).upload(
                storage_path,
                pdf_bytes,
                file_options={
                    "content-type": "application/pdf",
                    "cache-control": "3600",
                    "upsert": "true",
                    "metadata": {"original_filename": safe_original_name},
                },
            )
            return storage_path
        except Exception as exc:
            raise ProfileRepositoryError(
                "The CV could not be uploaded to Supabase Storage. "
                "Check that the candidate-cvs bucket migration was applied."
            ) from exc
