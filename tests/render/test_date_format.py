"""Tests for guffin.render.date_format."""

import datetime

import pytest

from guffin.render.date_format import DateFormat, format_date


class TestFormatDate:
    """format_date renders a date per the chosen DateFormat."""

    @pytest.mark.parametrize(
        ("date_format", "expected"),
        [
            (DateFormat.ROAM_LONG, "January 1st, 2026"),
            (DateFormat.ISO, "2026-01-01"),
            (DateFormat.ABBREV_MONTH_DAY, "Jan 1"),
        ],
    )
    def test_formats(self, date_format: DateFormat, expected: str) -> None:
        """Each format renders the date as its canonical string."""
        assert format_date(datetime.date(2026, 1, 1), date_format) == expected

    def test_roam_long_matches_the_daily_note_title(self) -> None:
        """ROAM_LONG reproduces Roam's own daily-note title (the default, unchanged output)."""
        assert format_date(datetime.date(2026, 8, 24), DateFormat.ROAM_LONG) == "August 24th, 2026"

    def test_abbrev_month_day_omits_the_year(self) -> None:
        """ABBREV_MONTH_DAY renders the abbreviated month and day with no year and no ordinal."""
        assert format_date(datetime.date(2026, 12, 25), DateFormat.ABBREV_MONTH_DAY) == "Dec 25"
