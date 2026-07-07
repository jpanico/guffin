"""Tests for the guffin.common.date module."""

import pytest

from guffin.common.date import ENGLISH_MONTH_ABBREVIATIONS, ENGLISH_MONTHS, ordinal_suffix


class TestEnglishMonths:
    """ENGLISH_MONTHS is the twelve month names in calendar order, 0-indexed at January."""

    def test_has_twelve_months_january_first(self) -> None:
        """There are twelve names, January at index 0 and December at index 11."""
        assert len(ENGLISH_MONTHS) == 12
        assert ENGLISH_MONTHS[0] == "January"
        assert ENGLISH_MONTHS[11] == "December"

    def test_month_number_indexing(self) -> None:
        """ENGLISH_MONTHS[month - 1] names the given 1-based month number."""
        assert ENGLISH_MONTHS[8 - 1] == "August"


class TestEnglishMonthAbbreviations:
    """ENGLISH_MONTH_ABBREVIATIONS is the twelve month abbreviations in calendar order."""

    def test_has_twelve_three_letter_abbreviations_january_first(self) -> None:
        """There are twelve three-letter abbreviations, Jan at index 0 and Dec at index 11."""
        assert len(ENGLISH_MONTH_ABBREVIATIONS) == 12
        assert all(len(abbreviation) == 3 for abbreviation in ENGLISH_MONTH_ABBREVIATIONS)
        assert ENGLISH_MONTH_ABBREVIATIONS[0] == "Jan"
        assert ENGLISH_MONTH_ABBREVIATIONS[11] == "Dec"

    def test_month_number_indexing(self) -> None:
        """ENGLISH_MONTH_ABBREVIATIONS[month - 1] abbreviates the given 1-based month number."""
        assert ENGLISH_MONTH_ABBREVIATIONS[9 - 1] == "Sep"


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
