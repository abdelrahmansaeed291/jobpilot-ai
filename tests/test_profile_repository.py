"""Tests for Supabase profile persistence edge cases."""

from typing import Self

from database.profile_repository import SupabaseProfileRepository


class EmptyProfileQuery:
    """Mimic the fluent query returned by Supabase for an empty table."""

    def select(self, columns: str) -> Self:
        return self

    def eq(self, column: str, value: str) -> Self:
        return self

    def maybe_single(self) -> Self:
        return self

    def execute(self) -> None:
        return None


class EmptyProfileClient:
    """Provide the minimal client interface needed by the repository."""

    def table(self, name: str) -> EmptyProfileQuery:
        return EmptyProfileQuery()


def test_missing_profile_can_be_returned_as_none_response() -> None:
    """An empty Supabase table should be treated as no saved profile."""
    repository = SupabaseProfileRepository(EmptyProfileClient())  # type: ignore[arg-type]

    assert repository.get_profile() is None
