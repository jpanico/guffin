"""Tests for the guffin.roam.primitives module."""

from typing import Final

import pytest
import regex
from pydantic import TypeAdapter, ValidationError

from guffin.roam.markdown import CALLOUT_RE, PAGE_REF_RE, CalloutType, RoamCallout, parse_callout
from guffin.roam.primitives import ANCHORED_UID_PATTERN, ANCHORED_UID_RE, UID_PATTERN, UID_RE, Uid

_VALID_UID: Final[str] = "abc123xyz"
_UID_ADAPTER: Final[TypeAdapter[str]] = TypeAdapter(Uid)

_FIRESTORE_URL: Final[str] = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING: Final[str] = f"![A flower]({_FIRESTORE_URL})"

# ---------------------------------------------------------------------------
# TestCalloutRE
# ---------------------------------------------------------------------------


class TestCalloutRE:
    """Tests for CALLOUT_RE — the full callout block string regex."""

    # --- full RE match ---

    def test_matches_marker_only(self) -> None:
        """Test that a bare callout marker with no title or body matches."""
        assert CALLOUT_RE.match("[[>]] [[!INFO]]") is not None

    def test_matches_marker_with_title(self) -> None:
        """Test that a callout marker followed by a title matches."""
        assert CALLOUT_RE.match("[[>]] [[!NOTE]] This is the title") is not None

    def test_matches_marker_with_title_and_body(self) -> None:
        """Test that a callout marker with a title and a single body line matches."""
        assert CALLOUT_RE.match("[[>]] [[!WARNING]] Title\nBody line") is not None

    def test_matches_marker_with_multiline_body(self) -> None:
        """Test that a callout marker with a title and multiple body lines matches."""
        assert CALLOUT_RE.match("[[>]] [[!INFO]] Title\nLine 1\nLine 2\nLine 3") is not None

    @pytest.mark.parametrize("callout_type", list(CalloutType))
    def test_matches_all_twelve_types(self, callout_type: CalloutType) -> None:
        """Test that each of the twelve recognised callout type keywords matches."""
        assert CALLOUT_RE.match(f"[[>]] [[!{callout_type}]] Title") is not None

    def test_no_match_plain_string(self) -> None:
        """Test that a plain string without the callout prefix does not match."""
        assert CALLOUT_RE.match("Just some text") is None

    def test_no_match_empty_string(self) -> None:
        """Test that an empty string does not match."""
        assert CALLOUT_RE.match("") is None

    def test_no_match_prefix_only(self) -> None:
        """Test that the bare [[>]] prefix without a type block does not match."""
        assert CALLOUT_RE.match("[[>]]") is None

    def test_no_match_invalid_type(self) -> None:
        """Test that an unrecognised callout type keyword does not match."""
        assert CALLOUT_RE.match("[[>]] [[!INVALID]] title") is None

    def test_no_match_lowercase_type(self) -> None:
        """Test that a lowercase callout type keyword does not match."""
        assert CALLOUT_RE.match("[[>]] [[!info]] title") is None

    def test_no_match_missing_type_brackets(self) -> None:
        """Test that a malformed marker without the [[!...]] brackets does not match."""
        assert CALLOUT_RE.match("[[>]] !INFO title") is None

    # --- named capture groups ---

    def test_prefix_group(self) -> None:
        """Test that the prefix group captures '[[>]]'."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title")
        assert m is not None
        assert m.group("prefix") == "[[>]]"

    def test_callout_type_group(self) -> None:
        """Test that the callout_type group captures the type keyword."""
        m = CALLOUT_RE.match("[[>]] [[!WARNING]] Title")
        assert m is not None
        assert m.group("callout_type") == "WARNING"

    @pytest.mark.parametrize("callout_type", list(CalloutType))
    def test_callout_type_group_all_twelve(self, callout_type: CalloutType) -> None:
        """Test that callout_type captures each of the twelve recognised type keywords."""
        m = CALLOUT_RE.match(f"[[>]] [[!{callout_type}]] Title")
        assert m is not None
        assert m.group("callout_type") == callout_type

    def test_title_group_with_text(self) -> None:
        """Test that the title group captures all text on the first line after the marker."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] This is the title")
        assert m is not None
        assert m.group("title") == "This is the title"

    def test_title_group_empty_when_marker_only(self) -> None:
        """Test that the title group is an empty string when nothing follows the marker."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]]")
        assert m is not None
        assert m.group("title") == ""

    def test_title_group_strips_leading_whitespace(self) -> None:
        r"""Test that leading whitespace between the marker and title text is consumed by \s*."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]]  Two spaces before title")
        assert m is not None
        assert m.group("title") == "Two spaces before title"

    def test_title_group_is_first_line_only(self) -> None:
        """Test that the title group stops at the first newline."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Only the first line\nNot in title")
        assert m is not None
        assert m.group("title") == "Only the first line"

    def test_body_group_none_when_no_newline(self) -> None:
        """Test that the body group is None when the string contains no newline."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title only")
        assert m is not None
        assert m.group("body") is None

    def test_body_group_single_line(self) -> None:
        """Test that the body group captures a single line after the first newline."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title\nBody text here")
        assert m is not None
        assert m.group("body") == "Body text here"

    def test_body_group_multiline(self) -> None:
        """Test that the body group captures all lines after the first newline, preserving embedded newlines."""
        m = CALLOUT_RE.match("[[>]] [[!INFO]] Title\nLine 1\nLine 2\nLine 3")
        assert m is not None
        assert m.group("body") == "Line 1\nLine 2\nLine 3"

    def test_body_group_preserves_blank_lines(self) -> None:
        """Test that blank lines within the body are preserved by the DOTALL body group."""
        body: Final[str] = "- item one\n- item two\n\nA paragraph"
        m = CALLOUT_RE.match(f"[[>]] [[!NOTE]] Title\n{body}")
        assert m is not None
        assert m.group("body") == body


# ---------------------------------------------------------------------------
# TestCallout
# ---------------------------------------------------------------------------


class TestCallout:
    """Tests for the callout() function."""

    # --- returns None ---

    def test_returns_none_for_empty_string(self) -> None:
        """Returns None for an empty string."""
        assert parse_callout("") is None

    def test_returns_none_for_plain_text(self) -> None:
        """Returns None when block_string does not start with ROAM_BLOCK_QUOTE_PREFIX."""
        assert parse_callout("Some plain text") is None

    def test_returns_none_for_image_link(self) -> None:
        """Returns None when block_string is a Firestore image link."""
        assert parse_callout(_IMAGE_STRING) is None

    # --- returns RoamCallout ---

    def test_returns_roam_callout_instance(self) -> None:
        """Returns a RoamCallout instance for a valid callout string."""
        assert isinstance(parse_callout("[[>]] [[!INFO]]"), RoamCallout)

    def test_callout_type_field(self) -> None:
        """callout_type matches the marker keyword as a CalloutType member."""
        result = parse_callout("[[>]] [[!WARNING]]")
        assert result is not None
        assert result.callout_type is CalloutType.WARNING

    @pytest.mark.parametrize("callout_type", list(CalloutType))
    def test_all_twelve_callout_types(self, callout_type: CalloutType) -> None:
        """All twelve callout type keywords are parsed to the correct CalloutType member."""
        result = parse_callout(f"[[>]] [[!{callout_type}]]")
        assert result is not None
        assert result.callout_type is CalloutType(callout_type)

    def test_title_with_text(self) -> None:
        """Title captures the text on the first line after the marker."""
        result = parse_callout("[[>]] [[!INFO]] This is the title")
        assert result is not None
        assert result.title == "This is the title"

    def test_title_empty_when_marker_only(self) -> None:
        """Title is an empty string when nothing follows the marker."""
        result = parse_callout("[[>]] [[!INFO]]")
        assert result is not None
        assert result.title == ""

    def test_body_empty_when_no_newline(self) -> None:
        """Body is an empty string when the block string contains no newline."""
        result = parse_callout("[[>]] [[!INFO]] Title only")
        assert result is not None
        assert result.body == ""

    def test_body_single_line(self) -> None:
        """Body captures the single line after the first newline."""
        result = parse_callout("[[>]] [[!INFO]] Title\nBody line")
        assert result is not None
        assert result.body == "Body line"

    def test_body_multiline(self) -> None:
        """Body captures all lines after the first newline, preserving embedded newlines."""
        result = parse_callout("[[>]] [[!INFO]] Title\nLine 1\nLine 2\nLine 3")
        assert result is not None
        assert result.body == "Line 1\nLine 2\nLine 3"

    # --- error cases ---

    def test_raises_value_error_for_malformed_marker(self) -> None:
        """Raises ValueError when block_string starts with ROAM_BLOCK_QUOTE_PREFIX but has a malformed marker."""
        with pytest.raises(ValueError, match="does not match callout pattern"):
            parse_callout("[[>]] [[!INVALID]]")

    def test_raises_validation_error_for_null_input(self) -> None:
        """Raises ValidationError when None is passed."""
        with pytest.raises(ValidationError):
            parse_callout(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestPageRefRE
# ---------------------------------------------------------------------------


class TestPageRefRE:
    """Tests for PAGE_REF_RE — the recursive Roam page reference [[<page_name>]] regex."""

    @pytest.mark.parametrize(
        "text, page_name",
        [
            ("[[Test Article]]", "Test Article"),
            ("[[[[Test Article]] 0]]", "[[Test Article]] 0"),
            ("[[0.2 Introduction [[v01]]]]", "0.2 Introduction [[v01]]"),
            (
                "[[1.2.2 Chapter 7: [[What You See is What it Means]] [[v01]]]]",
                "1.2.2 Chapter 7: [[What You See is What it Means]] [[v01]]",
            ),
            ("[[[[[[Illustration]] Brief]] -- Draft]]", "[[[[Illustration]] Brief]] -- Draft"),
        ],
    )
    def test_balanced_page_name(self, text: str, page_name: str) -> None:
        """Test that page_name captures the content between the outermost balanced brackets."""
        m = PAGE_REF_RE.search(text)
        assert m is not None
        assert m.group(0) == text
        assert m.group("page_name") == page_name

    def test_inline_reference(self) -> None:
        """Test that a reference embedded in surrounding text is captured."""
        m = PAGE_REF_RE.search("see [[My Page]] here")
        assert m is not None
        assert m.group(0) == "[[My Page]]"
        assert m.group("page_name") == "My Page"

    def test_multiple_top_level_refs(self) -> None:
        """Test that adjacent top-level references are matched separately."""
        names = [m.group("page_name") for m in PAGE_REF_RE.finditer("[[a]] and [[b]]")]
        assert names == ["a", "b"]

    def test_multiple_refs_with_nesting(self) -> None:
        """Test that finditer enumerates top-level refs while preserving nested page names."""
        names = [m.group("page_name") for m in PAGE_REF_RE.finditer("[[a [[b]] c]] and [[d]]")]
        assert names == ["a [[b]] c", "d"]

    def test_hashtag_reference(self) -> None:
        """Test that the [[...]] portion of a #[[tag]] hashtag reference matches."""
        m = PAGE_REF_RE.search("#[[tag]]")
        assert m is not None
        assert m.group("page_name") == "tag"

    def test_page_name_with_punctuation(self) -> None:
        """Test that a page name containing spaces and punctuation is captured whole."""
        m = PAGE_REF_RE.search("[[A/B & C!]]")
        assert m is not None
        assert m.group("page_name") == "A/B & C!"

    def test_no_match_plain_text(self) -> None:
        """Test that text without a reference does not match."""
        assert PAGE_REF_RE.search("no refs here") is None

    def test_no_match_single_brackets(self) -> None:
        """Test that single-bracket [text] is not a page reference."""
        assert PAGE_REF_RE.search("[not a ref]") is None

    def test_no_match_empty_reference(self) -> None:
        """Test that an empty [[]] reference does not match."""
        assert PAGE_REF_RE.search("[[]]") is None

    def test_no_match_unclosed(self) -> None:
        """Test that an unclosed [[ reference does not match."""
        assert PAGE_REF_RE.search("[[unclosed") is None

    def test_no_match_across_newline(self) -> None:
        """Test that a reference whose name spans a newline does not match."""
        assert PAGE_REF_RE.search("[[foo\nbar]]") is None


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
