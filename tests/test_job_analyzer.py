"""Tests for safe structured job extraction retries."""

from types import SimpleNamespace

from models.job_profile import ExtractedJobProfile
from services.job_analyzer import GeminiJobAnalyzer


class RetryModels:
    """Return malformed data once and valid structured data next."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(parsed=None, text="{invalid json")
        return SimpleNamespace(
            parsed=ExtractedJobProfile(
                job_title="AI Engineer",
                company="Example GmbH",
                required_skills=["Python"],
            ),
            text=None,
        )


def test_analyzer_retries_malformed_json_and_returns_valid_profile() -> None:
    """Malformed provider output should receive one bounded retry."""
    models = RetryModels()
    analyzer = GeminiJobAnalyzer(
        api_key="test",
        model="test-model",
        client=SimpleNamespace(models=models),
        max_attempts=2,
    )

    profile = analyzer.analyze("Complete job description " * 10)

    assert models.calls == 2
    assert profile.job_title == "AI Engineer"
    assert profile.required_skills == ["Python"]
    assert profile.raw_description.startswith("Complete job description")
