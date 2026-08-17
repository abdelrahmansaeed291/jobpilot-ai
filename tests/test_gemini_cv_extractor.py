"""Tests for schema-constrained Gemini CV extraction."""

from types import SimpleNamespace

from models.candidate_profile import ExtractedCandidateProfile
from services.cv_parser import (
    BasicStructuredCVExtractor,
    FallbackStructuredCVExtractor,
)
from services.gemini_cv_extractor import (
    GeminiStructuredCVExtractor,
    StructuredExtractionError,
)


class FakeModels:
    """Return a predictable parsed response from the Gemini SDK surface."""

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        assert kwargs["model"] == "test-model"
        return SimpleNamespace(
            parsed=ExtractedCandidateProfile(
                name="Abdelrahman Abdelgawad",
                email="candidate@example.com",
                location="Munich, Germany",
                technical_skills=["Python", "PyTorch"],
            ),
            text=None,
        )


class FailingExtractor:
    """Represent an unavailable LLM provider."""

    def extract(self, text: str) -> ExtractedCandidateProfile:
        raise StructuredExtractionError("provider unavailable")


def test_gemini_extractor_returns_validated_candidate_profile() -> None:
    """Parsed SDK output should become a CandidateProfile with provenance."""
    client = SimpleNamespace(models=FakeModels())
    extractor = GeminiStructuredCVExtractor(
        api_key="test-key", model="test-model", client=client
    )

    profile = extractor.extract("candidate CV")

    assert profile.name == "Abdelrahman Abdelgawad"
    assert profile.location == "Munich, Germany"
    assert profile.extraction_method == "gemini"


def test_failed_gemini_request_falls_back_with_warning() -> None:
    """Provider failures should retain a usable local profile and warn the UI."""
    extractor = FallbackStructuredCVExtractor(
        FailingExtractor(), BasicStructuredCVExtractor()
    )

    profile = extractor.extract("Ada Lovelace\nada@example.com\nPython")

    assert profile.name == "Ada Lovelace"
    assert profile.extraction_method == "basic"
    assert profile.extraction_warning is not None
