"""Tests for the persistent profile workflow."""

from datetime import UTC, datetime
from uuid import UUID

from models.candidate_profile import CandidateProfile
from services.profile_service import ProfileService


class FakeParser:
    """Predictable parser used to verify orchestration."""

    calls = 0
    structure_calls = 0

    def parse(self, pdf_bytes: bytes) -> CandidateProfile:
        self.calls += 1
        return CandidateProfile(
            name="New Name",
            email="new@example.com",
            parsed_cv_text="new parsed text",
        )

    def structure_text(self, text: str) -> CandidateProfile:
        self.structure_calls += 1
        return CandidateProfile(
            name="Gemini Name",
            location="Munich, Germany",
            parsed_cv_text=text,
            extraction_method="gemini",
        )


class FakeRepository:
    """In-memory persistence adapter for service tests."""

    def __init__(self, profile: CandidateProfile | None = None) -> None:
        self.profile = profile
        self.upload_calls = 0

    def get_profile(self, profile_id: UUID) -> CandidateProfile | None:
        return self.profile

    def save_profile(self, profile: CandidateProfile) -> CandidateProfile:
        self.profile = profile.model_copy(
            update={"updated_at": datetime.now(UTC)}
        )
        return self.profile

    def upload_cv(
        self, pdf_bytes: bytes, original_filename: str, profile_id: UUID
    ) -> str:
        self.upload_calls += 1
        return f"profiles/{profile_id}/cv.pdf"


def test_loading_saved_profile_does_not_parse_or_upload() -> None:
    """Application startup should only read the structured database row."""
    parser = FakeParser()
    repository = FakeRepository(CandidateProfile(name="Saved Name"))
    service = ProfileService(repository, parser)  # type: ignore[arg-type]

    loaded = service.load_profile()

    assert loaded is not None
    assert loaded.name == "Saved Name"
    assert parser.calls == 0
    assert repository.upload_calls == 0


def test_replacing_cv_parses_uploads_and_preserves_unextracted_manual_data() -> None:
    """A replacement should run once and retain fields the extractor leaves blank."""
    parser = FakeParser()
    repository = FakeRepository()
    service = ProfileService(repository, parser)  # type: ignore[arg-type]
    existing = CandidateProfile(
        name="Old Name",
        location="Berlin",
        professional_summary="Manually maintained summary",
    )

    saved = service.replace_cv(b"pdf", "resume.pdf", existing)

    assert parser.calls == 1
    assert repository.upload_calls == 1
    assert saved.name == "New Name"
    assert saved.location == "Berlin"
    assert saved.professional_summary == "Manually maintained summary"
    assert saved.parsed_cv_text == "new parsed text"
    assert saved.cv_file_path is not None


def test_reextracting_saved_text_does_not_parse_or_upload_pdf() -> None:
    """Gemini can enrich an existing profile without another CV upload."""
    parser = FakeParser()
    repository = FakeRepository()
    service = ProfileService(repository, parser)  # type: ignore[arg-type]
    existing = CandidateProfile(
        name="Basic Name",
        parsed_cv_text="already extracted CV text",
        cv_file_path="profiles/profile-id/cv.pdf",
    )

    saved = service.reextract_saved_cv(existing)

    assert parser.calls == 0
    assert parser.structure_calls == 1
    assert repository.upload_calls == 0
    assert saved.name == "Gemini Name"
    assert saved.location == "Munich, Germany"
    assert saved.cv_file_path == "profiles/profile-id/cv.pdf"
    assert saved.extraction_method == "gemini"
