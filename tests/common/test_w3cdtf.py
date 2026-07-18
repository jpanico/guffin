"""Tests for the guffin.common.w3cdtf module."""

import pytest
from pydantic import TypeAdapter, ValidationError

from guffin.common.w3cdtf import DatePrecision, W3cdtfDate, verified_w3cdtf_date


class TestVerifiedW3cdtfDate:
    """verified_w3cdtf_date() parses a W3CDTF reduced-precision date, calendar validity included."""

    @pytest.mark.parametrize("date_text", ["1298", "1298-07", "1298-07-10", "2026-12-31", "2024-02-29"])
    def test_legal_dates_round_trip(self, date_text: str) -> None:
        """Each reduced-precision form (leap day included) parses and renders back unchanged."""
        assert str(verified_w3cdtf_date(date_text)) == date_text

    def test_parses_into_components(self) -> None:
        """The parsed model exposes the date's parts as integers."""
        parsed = verified_w3cdtf_date("1298-07-10")
        assert (parsed.year, parsed.month, parsed.day) == (1298, 7, 10)

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
        with pytest.raises(ValueError, match="less than or equal to 12"):
            verified_w3cdtf_date("1298-13")

    def test_rejects_impossible_calendar_day(self) -> None:
        """A day that does not exist in its month is rejected."""
        with pytest.raises(ValueError, match="not a valid calendar date"):
            verified_w3cdtf_date("1298-02-30")

    def test_rejects_non_leap_february_29(self) -> None:
        """February 29 in a non-leap year is rejected."""
        with pytest.raises(ValueError, match="not a valid calendar date"):
            verified_w3cdtf_date("2026-02-29")


class TestW3cdtfDateModel:
    """The W3cdtfDate model parses the string form at Pydantic boundaries and derives its precision."""

    _ADAPTER = TypeAdapter[W3cdtfDate](W3cdtfDate)

    @pytest.mark.parametrize(
        ("date_text", "precision"),
        [
            ("1298", DatePrecision.YEAR),
            ("1298-07", DatePrecision.MONTH),
            ("1298-07-10", DatePrecision.DAY),
        ],
    )
    def test_precision_is_derived_from_present_parts(self, date_text: str, precision: DatePrecision) -> None:
        """Precision is not stored; it falls out of which parts the date carries."""
        assert verified_w3cdtf_date(date_text).precision is precision

    def test_string_validates_at_type_boundary(self) -> None:
        """A W3CDTF string parses into the model wherever the annotation appears."""
        parsed = self._ADAPTER.validate_python("1298-07")
        assert (parsed.year, parsed.month, parsed.day) == (1298, 7, None)

    def test_wrong_shape_is_rejected(self) -> None:
        """A non-W3CDTF string fails validation at the type boundary."""
        with pytest.raises(ValidationError, match="W3CDTF"):
            self._ADAPTER.validate_python("July 10, 1298")

    def test_calendar_validity_is_enforced(self) -> None:
        """The model carries the calendar check, not just the shape."""
        with pytest.raises(ValidationError, match="not a valid calendar date"):
            self._ADAPTER.validate_python("1298-02-30")

    def test_day_without_month_is_rejected(self) -> None:
        """Constructing from parts cannot skip the month while carrying a day."""
        with pytest.raises(ValidationError, match="must also carry a month"):
            W3cdtfDate(year=1298, day=10)

    def test_serializes_to_canonical_string(self) -> None:
        """model_dump yields the canonical W3CDTF string, round-trippable through validation."""
        parsed = verified_w3cdtf_date("1298-07")
        assert parsed.model_dump() == "1298-07"
        assert self._ADAPTER.validate_python(parsed.model_dump()) == parsed

    def test_construction_from_parts_renders_zero_padded(self) -> None:
        """A model built from parts renders the padded canonical form."""
        assert str(W3cdtfDate(year=750, month=3)) == "0750-03"
