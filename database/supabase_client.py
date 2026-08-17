"""Supabase client construction from local environment variables."""

import os

from supabase import Client, create_client


class SupabaseConfigurationError(RuntimeError):
    """Raised when required Supabase configuration is unavailable."""


def create_supabase_client_from_env() -> Client:
    """Create a Supabase client without embedding credentials in source code."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    if not url or not key:
        raise SupabaseConfigurationError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in jobpilot-ai/.env."
        )
    return create_client(url, key)
