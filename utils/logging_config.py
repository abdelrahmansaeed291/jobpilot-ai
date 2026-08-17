"""Application logging configuration."""

import logging
import os


def configure_logging() -> None:
    """Enable concise terminal logs, including LangGraph node execution."""
    level_name = os.getenv("JOBPILOT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=False,
    )
