"""Gemini structured extraction for unstructured job descriptions."""

import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from models.job_profile import ExtractedJobProfile, JobProfile
from services.gemini_cv_extractor import DEFAULT_GEMINI_MODEL

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "job_description_extraction.txt"
)


class JobAnalysisError(RuntimeError):
    """Raised when a job description cannot be structured safely."""


class GeminiJobAnalyzer:
    """Extract a validated JobProfile with bounded retry behavior."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        client: Any | None = None,
        max_attempts: int = 2,
    ) -> None:
        if not api_key.strip():
            raise JobAnalysisError("Set GEMINI_API_KEY in jobpilot-ai/.env.")
        self._client = client or genai.Client(api_key=api_key)
        self._model = model
        self._max_attempts = max(1, max_attempts)

    def analyze(self, job_description: str) -> JobProfile:
        """Convert a job description to structured output and validate it."""
        description = job_description.strip()
        if len(description) < 80:
            raise JobAnalysisError("Paste a complete job description before analyzing.")
        prompt = PROMPT_PATH.read_text(encoding="utf-8").replace(
            "{{JOB_DESCRIPTION}}", description
        )
        last_error: Exception | None = None
        for _ in range(self._max_attempts):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ExtractedJobProfile,
                        temperature=0,
                        max_output_tokens=8192,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
                parsed = response.parsed
                if isinstance(parsed, ExtractedJobProfile):
                    extracted = parsed
                elif parsed is not None:
                    extracted = ExtractedJobProfile.model_validate(parsed)
                elif response.text:
                    extracted = ExtractedJobProfile.model_validate_json(response.text)
                else:
                    raise ValueError("Gemini returned an empty response.")
                if os.getenv("GEMINI_DEBUG_RESPONSE", "").lower() == "true":
                    print(
                        "[JobPilot] Gemini job response:\n"
                        + extracted.model_dump_json(indent=2),
                        flush=True,
                    )
                return JobProfile(
                    **extracted.model_dump(), raw_description=description
                )
            except (ValidationError, ValueError, TypeError) as exc:
                last_error = exc
                continue
            except Exception as exc:
                detail = " ".join(str(exc).split())[:500]
                raise JobAnalysisError(f"Gemini job analysis failed: {detail}") from exc
        raise JobAnalysisError(
            f"Gemini returned malformed structured data after {self._max_attempts} attempts."
        ) from last_error


def create_job_analyzer_from_env() -> GeminiJobAnalyzer:
    """Create the job analyzer from local environment settings."""
    return GeminiJobAnalyzer(
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    )
