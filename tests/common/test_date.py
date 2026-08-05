"""Tests for the guffin.common.date module."""

import pytest

from guffin.common.date import (
    EnglishMonth,
    ordinal_suffix,
)


class TestEnglishMonth:
    """EnglishMonth is the twelve months valued 1-12, each carrying its English spellings."""

    def test_has_twelve_months_in_calendar_order(self) -> None:
        """There are twelve members, January valued 1 and December valued 12."""
        assert len(EnglishMonth) == 12
        assert EnglishMonth.JANUARY == 1
        assert EnglishMonth.DECEMBER == 12

    def test_month_number_lookup(self) -> None:
        """EnglishMonth(month) resolves a 1-based month number to its member."""
        assert EnglishMonth(8) is EnglishMonth.AUGUST

    @pytest.mark.parametrize("month_number", [0, 13])
    def test_month_number_lookup_rejects_out_of_range(self, month_number: int) -> None:
        """A number outside 1-12 is rejected rather than resolved to a month."""
        with pytest.raises(ValueError, match=str(month_number)):
            EnglishMonth(month_number)

    def test_full_name(self) -> None:
        """full_name is the month's English name."""
        assert EnglishMonth.JANUARY.full_name == "January"
        assert EnglishMonth.AUGUST.full_name == "August"
        assert EnglishMonth.DECEMBER.full_name == "December"

    def test_abbreviation(self) -> None:
        """Abbreviation is the month's three-letter English abbreviation."""
        assert EnglishMonth.JANUARY.abbreviation == "Jan"
        assert EnglishMonth.SEPTEMBER.abbreviation == "Sep"
        assert EnglishMonth.DECEMBER.abbreviation == "Dec"

    def test_every_abbreviation_is_three_letters(self) -> None:
        """Every member's abbreviation is exactly three letters (the truncation convention holds)."""
        assert all(len(month.abbreviation) == 3 for month in EnglishMonth)


class TestOrdinalSuffix:
    """ordinal_suffix() returns the English ordinal suffix, honoring the 11-13 exception."""

    @pytest.mark.parametrize(
        ("number", "suffix"),
        [
            (1, "st"),
            (2, "nd"),
            (3, "rd"),
            (4, "th"),
            (10, "th"),
            (11, "th"),
            (12, "th"),
            (13, "th"),
            (14, "th"),
            (20, "th"),
            (21, "st"),
            (22, "nd"),
            (23, "rd"),
            (24, "th"),
            (31, "st"),
            (111, "th"),
            (121, "st"),
        ],
    )
    def test_suffix(self, number: int, suffix: str) -> None:
        """Each number maps to its English ordinal suffix."""
        assert ordinal_suffix(number) == suffix
