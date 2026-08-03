"""Tests for the guffin.roam.blockquote regex constant and callout parser."""

from typing import Final

import pytest
from pydantic import ValidationError

from guffin.roam.blockquote import (
    CALLOUT_RE,
    CalloutType,
    RoamCallout,
    parse_callout,
    parse_pull_quote,
)

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
    def test_matches_all_eleven_types(self, callout_type: CalloutType) -> None:
        """Test that each of the eleven recognised callout type keywords matches."""
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
    def test_callout_type_group_all_eleven(self, callout_type: CalloutType) -> None:
        """Test that callout_type captures each of the eleven recognised type keywords."""
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
        """Returns None when block_string is a Firebase Storage image link."""
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
    def test_all_eleven_callout_types(self, callout_type: CalloutType) -> None:
        """All eleven callout type keywords are parsed to the correct CalloutType member."""
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


class TestParsePullQuote:
    """Tests for parse_pull_quote()."""

    def test_quote_only(self) -> None:
        """A single-line pull quote returns the quote with no attribution."""
        assert parse_pull_quote("[[>]] [[!QUOTE]] The quotation") == ("The quotation", None)

    def test_quote_and_attribution(self) -> None:
        """A pull quote's first line is the quote; the rest is the attribution."""
        assert parse_pull_quote("[[>]] [[!QUOTE]] The quotation\n— Someone") == ("The quotation", "— Someone")

    def test_multiline_attribution(self) -> None:
        """Attribution captures every line after the first, embedded newlines preserved."""
        assert parse_pull_quote("[[>]] [[!QUOTE]] Q\nline 1\nline 2") == ("Q", "line 1\nline 2")

    def test_none_for_plain_roam_block_quote(self) -> None:
        """A plain [[>]] block quote is not a pull quote."""
        assert parse_pull_quote("[[>]] a quotation") is None

    def test_none_for_standard_markdown_quote(self) -> None:
        """A standard Markdown > block quote is not a pull quote."""
        assert parse_pull_quote("> a quotation") is None

    def test_none_for_other_callout(self) -> None:
        """A non-QUOTE callout is not a pull quote."""
        assert parse_pull_quote("[[>]] [[!INFO]] a callout") is None

    def test_raises_validation_error_for_null_input(self) -> None:
        """Raises ValidationError when None is passed."""
        with pytest.raises(ValidationError):
            parse_pull_quote(None)  # type: ignore[arg-type]
