"""Local environment configuration helpers."""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_environment() -> None:
    """Load local variables from ``.env`` without overriding the host environment."""
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)
