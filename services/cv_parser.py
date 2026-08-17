"""CV text parsing and structured extraction boundaries."""

import re
import sys
from typing import Protocol

import pymupdf

from models.candidate_profile import CandidateProfile

MAX_CV_SIZE_BYTES = 10 * 1024 * 1024


class CVParsingError(ValueError):
    """Raised when an uploaded CV cannot be parsed safely."""


class StructuredCVExtractor(Protocol):
    """Interface for converting CV text into structured profile fields.

    A Gemini-backed implementation can replace the basic extractor later without
    changing the PDF, persistence, or Streamlit layers.
    """

    def extract(self, text: str) -> CandidateProfile:
        """Extract a candidate profile from plain CV text."""
        ...


class PyMuPDFTextExtractor:
    """Extract plain text from an in-memory PDF with PyMuPDF."""

    def extract(self, pdf_bytes: bytes) -> str:
        """Return normalized text for every page in the PDF."""
        if not pdf_bytes:
            raise CVParsingError("The uploaded PDF is empty.")
        if len(pdf_bytes) > MAX_CV_SIZE_BYTES:
            raise CVParsingError("The CV must be 10 MB or smaller.")

        try:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
                if document.page_count == 0:
                    raise CVParsingError("The PDF does not contain any pages.")
                text = "\n".join(page.get_text("text") for page in document)
        except CVParsingError:
            raise
        except Exception as exc:
            raise CVParsingError(
                "The file could not be read as a valid PDF."
            ) from exc

        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if not normalized:
            raise CVParsingError(
                "No selectable text was found. Scanned-image CVs are not supported yet."
            )
        return normalized


class BasicStructuredCVExtractor:
    """Perform conservative local extraction until Gemini extraction is added."""

    _EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
    _KNOWN_SKILLS = (
        "Python",
        "Java",
        "JavaScript",
        "TypeScript",
        "SQL",
        "React",
        "Streamlit",
        "FastAPI",
        "Django",
        "Flask",
        "PostgreSQL",
        "Supabase",
        "Docker",
        "Kubernetes",
        "Git",
        "AWS",
        "Azure",
        "Google Cloud",
        "Machine Learning",
        "Natural Language Processing",
        "LangChain",
        "LangGraph",
    )

    def extract(self, text: str) -> CandidateProfile:
        """Extract reliable fields and leave ambiguous fields for manual editing."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        email_match = self._EMAIL_PATTERN.search(text)
        name = self._find_likely_name(lines)
        skills = [
            skill
            for skill in self._KNOWN_SKILLS
            if re.search(rf"\b{re.escape(skill)}\b", text, flags=re.IGNORECASE)
        ]
        return CandidateProfile(
            name=name,
            email=email_match.group(0) if email_match else "",
            technical_skills=skills,
            parsed_cv_text=text,
            extraction_method="basic",
        )

    @staticmethod
    def _find_likely_name(lines: list[str]) -> str:
        """Return a conservative name candidate from the beginning of the CV."""
        for line in lines[:5]:
            if (
                1 < len(line.split()) <= 6
                and len(line) <= 80
                and "@" not in line
                and not any(character.isdigit() for character in line)
            ):
                return line
        return ""


class FallbackStructuredCVExtractor:
    """Use a local extractor when the configured LLM request fails."""

    def __init__(
        self,
        primary: StructuredCVExtractor,
        fallback: StructuredCVExtractor | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or BasicStructuredCVExtractor()

    def extract(self, text: str) -> CandidateProfile:
        """Try the primary extractor and attach a user-visible fallback warning."""
        try:
            return self._primary.extract(text)
        except Exception as exc:
            print(f"[JobPilot] {exc}", file=sys.stderr, flush=True)
            profile = self._fallback.extract(text)
            return profile.model_copy(
                update={
                    "extraction_warning": (
                        f"{exc} JobPilot used the basic local extractor instead. "
                        "Review and complete the fields manually."
                    )
                }
            )


def create_structured_extractor() -> StructuredCVExtractor:
    """Select Gemini when configured, otherwise use the local extractor."""
    from services.gemini_cv_extractor import (
        create_gemini_extractor_from_env,
        gemini_is_configured,
    )

    if not gemini_is_configured():
        return BasicStructuredCVExtractor()
    return FallbackStructuredCVExtractor(create_gemini_extractor_from_env())


class CVParser:
    """Coordinate PDF text extraction and structured profile extraction."""

    def __init__(
        self,
        text_extractor: PyMuPDFTextExtractor | None = None,
        structured_extractor: StructuredCVExtractor | None = None,
    ) -> None:
        self._text_extractor = text_extractor or PyMuPDFTextExtractor()
        self._structured_extractor = structured_extractor or create_structured_extractor()

    def parse(self, pdf_bytes: bytes) -> CandidateProfile:
        """Parse a PDF once and return its structured candidate profile."""
        text = self._text_extractor.extract(pdf_bytes)
        return self.structure_text(text)

    def structure_text(self, text: str) -> CandidateProfile:
        """Structure previously parsed text without reopening or uploading a PDF."""
        if not text.strip():
            raise CVParsingError("There is no saved CV text to structure.")
        profile = self._structured_extractor.extract(text)
        return profile.model_copy(update={"parsed_cv_text": text})
