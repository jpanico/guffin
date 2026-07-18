"""Tests for the guffin.common.line_range module."""

import pytest
from pydantic import ValidationError

from guffin.common.line_range import LineRange, sliced_line_range

_FILE_TEXT: str = "line one\nline two\nline three\nline four\n"


class TestLineRange:
    """LineRange is an inclusive 1-based range whose end never precedes its start."""

    def test_single_line_range(self) -> None:
        """A degenerate range holds one line: start == end."""
        line_range = LineRange(start=12, end=12)
        assert line_range.start == line_range.end == 12

    def test_rejects_end_before_start(self) -> None:
        """A range ending before it starts is rejected."""
        with pytest.raises(ValidationError, match="precedes start"):
            LineRange(start=40, end=10)

    def test_rejects_zero_start(self) -> None:
        """Lines are 1-based; line 0 does not exist."""
        with pytest.raises(ValidationError):
            LineRange(start=0, end=5)


class TestSlicedLineRange:
    """sliced_line_range() selects an inclusive 1-based range, rejecting out-of-range ends."""

    def test_none_returns_whole_text(self) -> None:
        """No range selects the whole text unchanged."""
        assert sliced_line_range(_FILE_TEXT, None) == _FILE_TEXT

    def test_selects_inclusive_range(self) -> None:
        """A range selects its lines, both ends inclusive."""
        assert sliced_line_range(_FILE_TEXT, LineRange(start=2, end=3)) == "line two\nline three"

    def test_single_line_range(self) -> None:
        """A degenerate range selects exactly one line."""
        assert sliced_line_range(_FILE_TEXT, LineRange(start=4, end=4)) == "line four"

    def test_out_of_range_end_rejected(self) -> None:
        """A range ending beyond the text's last line raises."""
        with pytest.raises(ValueError, match="exceeds"):
            sliced_line_range("one\ntwo", LineRange(start=1, end=99))
