"""Gemini-backed structured extraction for parsed CV text."""

import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from models.candidate_profile import CandidateProfile, ExtractedCandidateProfile

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "cv_profile_extraction.txt"
)


class StructuredExtractionError(RuntimeError):
    """Raised when Gemini cannot return a valid structured candidate profile."""


class GeminiStructuredCVExtractor:
    """Extract a Pydantic-validated profile with Gemini structured output."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("A Gemini API key is required.")
        self._client = client or genai.Client(api_key=api_key)
        self._model = model

    def extract(self, text: str) -> CandidateProfile:
        """Return validated structured data without accepting free-form JSON."""
        prompt = PROMPT_PATH.read_text(encoding="utf-8").replace(
            "{{CV_TEXT}}", text
        )
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedCandidateProfile,
                    temperature=0,
                    max_output_tokens=8192,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
            parsed = response.parsed
            if isinstance(parsed, ExtractedCandidateProfile):
                extracted = parsed
            elif parsed is not None:
                extracted = ExtractedCandidateProfile.model_validate(parsed)
            elif response.text:
                extracted = ExtractedCandidateProfile.model_validate_json(
                    response.text
                )
            else:
                raise StructuredExtractionError(
                    "Gemini returned an empty structured response."
                )
            if os.getenv("GEMINI_DEBUG_RESPONSE", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }:
                print(
                    "[JobPilot] Gemini structured response:\n"
                    + extracted.model_dump_json(indent=2),
                    flush=True,
                )
            return CandidateProfile(
                **extracted.model_dump(), extraction_method="gemini"
            )
        except StructuredExtractionError:
            raise
        except Exception as exc:
            detail = " ".join(str(exc).split())[:500]
            raise StructuredExtractionError(
                f"Gemini structured extraction failed: {detail}"
            ) from exc


def gemini_is_configured() -> bool:
    """Return whether a Gemini API key is available without revealing it."""
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def create_gemini_extractor_from_env() -> GeminiStructuredCVExtractor:
    """Build the extractor from local environment configuration."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    return GeminiStructuredCVExtractor(api_key=api_key, model=model)
