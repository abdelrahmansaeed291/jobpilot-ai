"""Business workflow for persistent candidate profiles."""

from typing import Protocol
from uuid import UUID

from models.candidate_profile import CandidateProfile, DEFAULT_PROFILE_ID
from services.cv_parser import CVParser


class CandidateProfileRepository(Protocol):
    """Persistence operations required by the profile workflow."""

    def get_profile(self, profile_id: UUID) -> CandidateProfile | None:
        """Return a saved profile, if it exists."""
        ...

    def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Persist and return a profile."""
        ...

    def upload_cv(
        self, pdf_bytes: bytes, original_filename: str, profile_id: UUID
    ) -> str:
        """Store the original CV and return its path."""
        ...


class ProfileService:
    """Coordinate profile loading, editing, CV parsing, and persistence."""

    def __init__(
        self,
        repository: CandidateProfileRepository,
        parser: CVParser | None = None,
    ) -> None:
        self._repository = repository
        self._parser = parser or CVParser()

    def load_profile(self) -> CandidateProfile | None:
        """Load structured data only; never download or reparse the stored CV."""
        return self._repository.get_profile(DEFAULT_PROFILE_ID)

    def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Persist manual edits without touching or reparsing the CV."""
        return self._repository.save_profile(profile)

    def replace_cv(
        self,
        pdf_bytes: bytes,
        original_filename: str,
        existing_profile: CandidateProfile | None,
    ) -> CandidateProfile:
        """Parse, upload, and persist a new or replacement CV exactly once."""
        extracted = self._parser.parse(pdf_bytes)
        merged = self._merge_extracted(existing_profile, extracted)
        storage_path = self._repository.upload_cv(
            pdf_bytes,
            original_filename,
            DEFAULT_PROFILE_ID,
        )
        merged = merged.model_copy(
            update={
                "id": DEFAULT_PROFILE_ID,
                "cv_file_path": storage_path,
                "parsed_cv_text": extracted.parsed_cv_text,
            }
        )
        return self._save_with_extraction_metadata(merged)

    def reextract_saved_cv(self, existing: CandidateProfile) -> CandidateProfile:
        """Restructure saved text without reparsing or re-uploading the PDF."""
        extracted = self._parser.structure_text(existing.parsed_cv_text)
        merged = self._merge_extracted(existing, extracted).model_copy(
            update={
                "id": existing.id,
                "cv_file_path": existing.cv_file_path,
                "parsed_cv_text": existing.parsed_cv_text,
            }
        )
        return self._save_with_extraction_metadata(merged)

    def _save_with_extraction_metadata(
        self, profile: CandidateProfile
    ) -> CandidateProfile:
        """Persist profile fields while retaining transient extraction status."""
        saved = self._repository.save_profile(profile)
        return saved.model_copy(
            update={
                "extraction_method": profile.extraction_method,
                "extraction_warning": profile.extraction_warning,
            }
        )

    @staticmethod
    def _merge_extracted(
        existing: CandidateProfile | None,
        extracted: CandidateProfile,
    ) -> CandidateProfile:
        """Keep manual data when the basic extractor cannot infer a field."""
        if existing is None:
            return extracted

        scalar_fields = ("name", "email", "location", "professional_summary")
        list_fields = (
            "education",
            "work_experience",
            "technical_skills",
            "languages",
            "certifications",
            "projects",
        )
        updates = {
            field: getattr(extracted, field) or getattr(existing, field)
            for field in (*scalar_fields, *list_fields)
        }
        updates.update(
            extraction_method=extracted.extraction_method,
            extraction_warning=extracted.extraction_warning,
        )
        return existing.model_copy(update=updates)
