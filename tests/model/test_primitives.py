"""Tests for the guffin.model.primitives module."""

from typing import Final

import pytest
import regex
from pydantic import TypeAdapter, ValidationError

from guffin.model.primitives import (
    ANCHORED_UID_PATTERN,
    ANCHORED_UID_RE,
    DAILY_NOTE_UID_PATTERN,
    SYNTHETIC_UID_PATTERN,
    UID_PATTERN,
    UID_RE,
    Uid,
    is_daily_note_uid,
)

_VALID_UID: Final[str] = "abc123xyz"
_VALID_DAILY_NOTE_UID: Final[str] = "08-24-2026"
_UID_ADAPTER: Final[TypeAdapter[str]] = TypeAdapter(Uid)


# ---------------------------------------------------------------------------
# TestUidPatterns
# ---------------------------------------------------------------------------


class TestUidPatterns:
    """Tests for the SYNTHETIC_UID_PATTERN / DAILY_NOTE_UID_PATTERN / UID_PATTERN / *ANCHORED* constants."""

    def test_synthetic_pattern_matches_nine_char_uid(self) -> None:
        """Test that SYNTHETIC_UID_PATTERN fully matches a bare nine-character UID."""
        assert regex.fullmatch(SYNTHETIC_UID_PATTERN, _VALID_UID) is not None

    def test_daily_note_pattern_matches_date_uid(self) -> None:
        """Test that DAILY_NOTE_UID_PATTERN fully matches an MM-DD-YYYY UID."""
        assert regex.fullmatch(DAILY_NOTE_UID_PATTERN, _VALID_DAILY_NOTE_UID) is not None

    def test_uid_pattern_composes_both_forms(self) -> None:
        """Test that UID_PATTERN fully matches either a synthetic or a daily-note UID."""
        assert regex.fullmatch(UID_PATTERN, _VALID_UID) is not None
        assert regex.fullmatch(UID_PATTERN, _VALID_DAILY_NOTE_UID) is not None

    def test_anchored_pattern_wraps_unanchored(self) -> None:
        """Test that ANCHORED_UID_PATTERN is UID_PATTERN bracketed by ^ and $."""
        assert ANCHORED_UID_PATTERN == f"^{UID_PATTERN}$"

    def test_uid_re_finds_full_daily_note_uid(self) -> None:
        """Test that UID_RE captures a whole MM-DD-YYYY UID, not just its first nine characters."""
        match: Final[regex.Match[str] | None] = UID_RE.search(f"see {_VALID_DAILY_NOTE_UID} here")
        assert match is not None
        assert match.group() == _VALID_DAILY_NOTE_UID

    def test_anchored_uid_re_matches_daily_note_uid(self) -> None:
        """Test that ANCHORED_UID_RE matches a string that is exactly a daily-note UID."""
        assert ANCHORED_UID_RE.match(_VALID_DAILY_NOTE_UID) is not None


# ---------------------------------------------------------------------------
# TestUidType
# ---------------------------------------------------------------------------


class TestUidType:
    """Tests for the Uid annotated type's pattern validation."""

    def test_accepts_valid_uid(self) -> None:
        """Test that a well-formed nine-character UID validates."""
        assert _UID_ADAPTER.validate_python(_VALID_UID) == _VALID_UID

    def test_accepts_daily_note_uid(self) -> None:
        """Test that a well-formed MM-DD-YYYY daily-note UID validates."""
        assert _UID_ADAPTER.validate_python(_VALID_DAILY_NOTE_UID) == _VALID_DAILY_NOTE_UID

    def test_rejects_too_short(self) -> None:
        """Test that an under-length UID is rejected."""
        with pytest.raises(ValidationError):
            _UID_ADAPTER.validate_python("abc12")

    def test_rejects_embedded_uid(self) -> None:
        """Test that a string merely containing a UID is rejected (anchoring is load-bearing)."""
        with pytest.raises(ValidationError):
            _UID_ADAPTER.validate_python("xxabc123xyzyy")


# ---------------------------------------------------------------------------
# TestIsDailyNoteUid
# ---------------------------------------------------------------------------


class TestIsDailyNoteUid:
    """Tests for the is_daily_note_uid classifier."""

    def test_true_for_daily_note_uid(self) -> None:
        """Test that an MM-DD-YYYY UID is classified as a daily-note UID."""
        assert is_daily_note_uid(_VALID_DAILY_NOTE_UID) is True

    def test_false_for_synthetic_uid(self) -> None:
        """Test that a synthetic nine-character UID is not classified as a daily-note UID."""
        assert is_daily_note_uid(_VALID_UID) is False
