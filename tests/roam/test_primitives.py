"""Tests for the guffin.roam.primitives module."""

from typing import Final

import pytest
import regex
from pydantic import TypeAdapter, ValidationError

from guffin.roam.primitives import ANCHORED_UID_PATTERN, ANCHORED_UID_RE, UID_PATTERN, UID_RE, Uid

_VALID_UID: Final[str] = "abc123xyz"
_UID_ADAPTER: Final[TypeAdapter[str]] = TypeAdapter(Uid)


# ---------------------------------------------------------------------------
# TestUidPatterns
# ---------------------------------------------------------------------------


class TestUidPatterns:
    """Tests for the UID_PATTERN / UID_RE / ANCHORED_UID_PATTERN / ANCHORED_UID_RE constants."""

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

    def test_anchored_pattern_wraps_unanchored(self) -> None:
        """Test that ANCHORED_UID_PATTERN is UID_PATTERN bracketed by ^ and $."""
        assert ANCHORED_UID_PATTERN == f"^{UID_PATTERN}$"

    def test_anchored_uid_re_matches_exact_uid(self) -> None:
        """Test that ANCHORED_UID_RE matches a string that is exactly a UID."""
        assert ANCHORED_UID_RE.match(_VALID_UID) is not None

    def test_anchored_uid_re_rejects_too_long(self) -> None:
        """Test that ANCHORED_UID_RE rejects a string longer than nine characters."""
        assert ANCHORED_UID_RE.match("abc123xyz0") is None

    def test_anchored_uid_re_rejects_embedded_uid(self) -> None:
        """Test that ANCHORED_UID_RE does not match a UID surrounded by other characters."""
        assert ANCHORED_UID_RE.match("xxabc123xyz") is None


# ---------------------------------------------------------------------------
# TestUidType
# ---------------------------------------------------------------------------


class TestUidType:
    """Tests for the Uid annotated type's pattern validation."""

    def test_accepts_valid_uid(self) -> None:
        """Test that a well-formed nine-character UID validates."""
        assert _UID_ADAPTER.validate_python(_VALID_UID) == _VALID_UID

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
