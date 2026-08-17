"""Tests for CV parsing and basic structured extraction."""

import pymupdf
import pytest

from services.cv_parser import CVParser, CVParsingError


def _pdf_with_text(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def test_parser_extracts_text_and_conservative_profile_fields() -> None:
    """A text PDF should produce reusable text and reliable basic fields."""
    profile = CVParser().parse(
        _pdf_with_text("Ada Lovelace\nada@example.com\nPython SQL PostgreSQL")
    )

    assert profile.name == "Ada Lovelace"
    assert profile.email == "ada@example.com"
    assert profile.technical_skills == ["Python", "SQL", "PostgreSQL"]
    assert "Ada Lovelace" in profile.parsed_cv_text


def test_parser_rejects_invalid_pdf() -> None:
    """Invalid uploads should produce a user-safe parsing error."""
    with pytest.raises(CVParsingError, match="valid PDF"):
        CVParser().parse(b"not a pdf")
