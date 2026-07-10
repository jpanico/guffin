"""Tests for the guffin.common.date module."""

import pytest
from pydantic import TypeAdapter, ValidationError

from guffin.common.date import (
    ENGLISH_MONTH_ABBREVIATIONS,
    ENGLISH_MONTHS,
    W3cdtfDate,
    ordinal_suffix,
    verified_w3cdtf_date,
)


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


class TestVerifiedW3cdtfDate:
    """verified_w3cdtf_date() verifies a W3CDTF reduced-precision date, calendar validity included."""

    @pytest.mark.parametrize("date_text", ["1298", "1298-07", "1298-07-10", "2026-12-31", "2024-02-29"])
    def test_legal_dates_pass_through(self, date_text: str) -> None:
        """Each reduced-precision form (leap day included) is returned unchanged."""
        assert verified_w3cdtf_date(date_text) == date_text

    def test_rejects_prose_date(self) -> None:
        """A spelled-out date is rejected."""
        with pytest.raises(ValueError, match="W3CDTF"):
            verified_w3cdtf_date("July 10, 1298")

    def test_rejects_day_first_date(self) -> None:
        """A DD-MM-YYYY date (year not first) is rejected."""
        with pytest.raises(ValueError, match="W3CDTF"):
            verified_w3cdtf_date("10-07-1298")

    def test_rejects_short_year(self) -> None:
        """A two-digit year is rejected."""
        with pytest.raises(ValueError, match="W3CDTF"):
            verified_w3cdtf_date("98")

    def test_rejects_trailing_content(self) -> None:
        """A date embedded in a longer string is rejected (fullmatch, not search)."""
        with pytest.raises(ValueError, match="W3CDTF"):
            verified_w3cdtf_date("1298-07-10T12:00:00Z")

    def test_rejects_month_out_of_range(self) -> None:
        """A month outside 1-12 is rejected."""
        with pytest.raises(ValueError, match="outside 1-12"):
            verified_w3cdtf_date("1298-13")

    def test_rejects_impossible_calendar_day(self) -> None:
        """A day that does not exist in its month is rejected."""
        with pytest.raises(ValueError, match="not a valid calendar date"):
            verified_w3cdtf_date("1298-02-30")

    def test_rejects_non_leap_february_29(self) -> None:
        """February 29 in a non-leap year is rejected."""
        with pytest.raises(ValueError, match="not a valid calendar date"):
            verified_w3cdtf_date("2026-02-29")


class TestW3cdtfDateType:
    """The W3cdtfDate annotation itself enforces the full check at Pydantic boundaries."""

    _ADAPTER = TypeAdapter[W3cdtfDate](W3cdtfDate)

    def test_legal_date_validates(self) -> None:
        """A reduced-precision date passes through the annotation unchanged."""
        assert self._ADAPTER.validate_python("1298") == "1298"

    def test_wrong_shape_is_rejected(self) -> None:
        """A non-W3CDTF string fails validation at the type boundary."""
        with pytest.raises(ValidationError, match="W3CDTF"):
            self._ADAPTER.validate_python("July 10, 1298")

    def test_calendar_validity_is_enforced(self) -> None:
        """The annotation carries the calendar check, not just the shape."""
        with pytest.raises(ValidationError, match="not a valid calendar date"):
            self._ADAPTER.validate_python("1298-02-30")
