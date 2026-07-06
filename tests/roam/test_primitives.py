"""Tests for the guffin.roam.primitives module."""

from typing import Final

import pytest
import regex
from pydantic import TypeAdapter, ValidationError

from guffin.roam.primitives import (
    ANCHORED_UID_RE,
    DAILY_NOTE_UID_PATTERN,
    SYNTHETIC_UID_PATTERN,
    UID_PATTERN,
    UID_RE,
    Uid,
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

    def test_synthetic_pattern_rejects_daily_note_uid(self) -> None:
        """Test that SYNTHETIC_UID_PATTERN does not fully match an MM-DD-YYYY UID."""
        assert regex.fullmatch(SYNTHETIC_UID_PATTERN, _VALID_DAILY_NOTE_UID) is None

    def test_daily_note_pattern_matches_date_uid(self) -> None:
        """Test that DAILY_NOTE_UID_PATTERN fully matches an MM-DD-YYYY UID."""
        assert regex.fullmatch(DAILY_NOTE_UID_PATTERN, _VALID_DAILY_NOTE_UID) is not None

    def test_uid_pattern_composes_both_forms(self) -> None:
        """Test that UID_PATTERN fully matches either a synthetic or a daily-note UID."""
        assert regex.fullmatch(UID_PATTERN, _VALID_UID) is not None
        assert regex.fullmatch(UID_PATTERN, _VALID_DAILY_NOTE_UID) is not None

    def test_unanchored_pattern_has_no_anchors(self) -> None:
        """Test that the canonical UID_PATTERN carries no ^ or $ anchors."""
        assert "^" not in UID_PATTERN
        assert "$" not in UID_PATTERN

    def test_unanchored_pattern_is_embeddable(self) -> None:
        """Test that UID_PATTERN can match a UID embedded in surrounding text."""
        assert regex.search(UID_PATTERN, "see ((abc123xyz)) here") is not None

    def test_unanchored_pattern_fullmatches_bare_uid(self) -> None:
        """Test that UID_PATTERN fully matches a bare nine-character UID."""
        assert regex.fullmatch(UID_PATTERN, _VALID_UID) is not None

    def test_uid_re_finds_embedded_uid(self) -> None:
        """Test that the unanchored UID_RE finds a UID embedded in surrounding text."""
        assert UID_RE.search("see ((abc123xyz)) here") is not None

    def test_uid_re_matches_prefix_of_longer_string(self) -> None:
        """Test that the unanchored UID_RE matches the leading UID of a longer string."""
        assert UID_RE.match("abc123xyz0") is not None

    def test_anchored_uid_re_matches_exact_uid(self) -> None:
        """Test that ANCHORED_UID_RE matches a string that is exactly a UID."""
        assert ANCHORED_UID_RE.match(_VALID_UID) is not None

    def test_anchored_uid_re_rejects_too_long(self) -> None:
        """Test that ANCHORED_UID_RE rejects a string longer than nine characters."""
        assert ANCHORED_UID_RE.match("abc123xyz0") is None

    def test_anchored_uid_re_rejects_embedded_uid(self) -> None:
        """Test that ANCHORED_UID_RE does not match a UID surrounded by other characters."""
        assert ANCHORED_UID_RE.match("xxabc123xyz") is None

    def test_anchored_uid_re_matches_daily_note_uid(self) -> None:
        """Test that ANCHORED_UID_RE matches a string that is exactly a daily-note UID."""
        assert ANCHORED_UID_RE.match(_VALID_DAILY_NOTE_UID) is not None

    def test_uid_re_finds_full_daily_note_uid(self) -> None:
        """Test that UID_RE captures a whole MM-DD-YYYY UID, not just its first nine characters.

        The date alternative is listed first in UID_PATTERN precisely so that the
        nine-character synthetic branch cannot truncate a daily-note UID.
        """
        match: Final[regex.Match[str] | None] = UID_RE.search(f"see {_VALID_DAILY_NOTE_UID} here")
        assert match is not None
        assert match.group() == _VALID_DAILY_NOTE_UID


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

    def test_rejects_too_long(self) -> None:
        """Test that an over-length UID is rejected."""
        with pytest.raises(ValidationError):
            _UID_ADAPTER.validate_python("abc123xyz0")

    def test_rejects_embedded_uid(self) -> None:
        """Test that a string merely containing a UID is rejected (anchoring is load-bearing)."""
        with pytest.raises(ValidationError):
            _UID_ADAPTER.validate_python("xxabc123xyzyy")
