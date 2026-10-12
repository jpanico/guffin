"""Tests for the guffin.roam.blockquote regex constant and callout parser."""

from typing import Final

import pytest
from pydantic import ValidationError

from guffin.roam.blockquote import (
    CALLOUT_RE,
    CalloutType,
    RoamBlockQuote,
    RoamCallout,
    is_quote_block,
    parse_block_quote,
    parse_callout,
    parse_epigraph,
    parse_pull_quote,
)

_FIREBASE_STORAGE_URL: Final[str] = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING: Final[str] = f"![A flower]({_FIREBASE_STORAGE_URL})"

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

    def test_single_line_quotation(self) -> None:
        """A single-line pull quote returns its quotation."""
        assert parse_pull_quote("[[>]] [[!QUOTE]] The quotation") == "The quotation"

    def test_every_line_is_quotation(self) -> None:
        """A pull quote carries no attribution: every line after the marker is quotation."""
        assert parse_pull_quote("[[>]] [[!QUOTE]] Q\nline 1\nline 2") == "Q\nline 1\nline 2"

    def test_dash_led_paragraph_is_still_quotation(self) -> None:
        """Even a dash-led final paragraph is quotation in a pull quote — only a block quote is attributed."""
        assert parse_pull_quote("[[>]] [[!QUOTE]] The quotation\n\n— Someone") == "The quotation\n\n— Someone"

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


class TestParseBlockQuote:
    """Tests for parse_block_quote() — a plain block quote and its dash-led attribution paragraph."""

    @pytest.mark.parametrize(
        ("block_string", "expected"),
        [
            pytest.param(
                "[[>]] I wish to God these calculations had been executed by steam!\n\n— __Charles Babbage__, c. 1821",
                RoamBlockQuote(
                    quote="I wish to God these calculations had been executed by steam!",
                    attribution="__Charles Babbage__, c. 1821",
                ),
                id="em-dash-credit",
            ),
            pytest.param(
                "> Go thou and slay.\n\n– The Old Man",
                RoamBlockQuote(quote="Go thou and slay.", attribution="The Old Man"),
                id="en-dash-credit-markdown-marker",
            ),
            pytest.param(
                "[[>]] Quote.\n\n—   Author Name,\n*Work Title*\n",
                RoamBlockQuote(quote="Quote.", attribution="Author Name,\n*Work Title*"),
                id="multi-line-credit",
            ),
            pytest.param(
                "[[>]] A quote with no credit.\nsecond line",
                RoamBlockQuote(quote="A quote with no credit.\nsecond line"),
                id="no-credit",
            ),
            pytest.param(
                "[[>]] Verse line one\n— a dash-led verse line",
                RoamBlockQuote(quote="Verse line one\n— a dash-led verse line"),
                id="dash-line-without-blank-line-is-quotation",
            ),
            pytest.param(
                "[[>]] Para one.\n\n— an inner dash paragraph\n\nPara three ends it.",
                RoamBlockQuote(quote="Para one.\n\n— an inner dash paragraph\n\nPara three ends it."),
                id="dash-paragraph-not-last-is-quotation",
            ),
        ],
    )
    def test_parses(self, block_string: str, expected: RoamBlockQuote) -> None:
        """The quotation and attribution split only at a dash-led final paragraph after a blank line."""
        assert parse_block_quote(block_string) == expected

    @pytest.mark.parametrize(
        "block_string",
        [
            "[[>]] [[!QUOTE]] A pull quote\n\n— Someone",
            "[[>]] [[!EPIGRAPH]]\nAn epigraph\n\n— Someone",
            "[[>]] [[!INFO]] a callout",
            "plain text",
        ],
    )
    def test_none_for_anything_but_a_plain_block_quote(self, block_string: str) -> None:
        """A pull quote, an epigraph, a callout, or ordinary text is not a plain block quote."""
        assert parse_block_quote(block_string) is None


class TestParseEpigraph:
    """Tests for parse_epigraph() — a [[>]] [[!EPIGRAPH]] quotation and its dash-led attribution paragraph."""

    @pytest.mark.parametrize(
        ("block_string", "expected"),
        [
            pytest.param(
                "[[>]] [[!EPIGRAPH]]\nThe medium is the message.\n\n— Marshall McLuhan",
                RoamBlockQuote(quote="The medium is the message.", attribution="Marshall McLuhan"),
                id="credit-after-blank-line",
            ),
            pytest.param(
                "[[>]] [[!EPIGRAPH]] On the marker line.\n\n– __Someone__, *A Work*",
                RoamBlockQuote(quote="On the marker line.", attribution="__Someone__, *A Work*"),
                id="quotation-on-marker-line-en-dash-credit",
            ),
            pytest.param(
                "[[>]] [[!EPIGRAPH]]\nVerse line one\nverse line two",
                RoamBlockQuote(quote="Verse line one\nverse line two"),
                id="no-credit",
            ),
            pytest.param(
                "[[>]] [[!EPIGRAPH]]\nA line\n— a dash-led verse line",
                RoamBlockQuote(quote="A line\n— a dash-led verse line"),
                id="dash-line-without-blank-line-is-quotation",
            ),
            pytest.param("[[>]] [[!EPIGRAPH]]", RoamBlockQuote(quote=""), id="marker-only"),
        ],
    )
    def test_parses(self, block_string: str, expected: RoamBlockQuote) -> None:
        """Everything after the marker is content, split at a dash-led final paragraph after a blank line."""
        assert parse_epigraph(block_string) == expected

    @pytest.mark.parametrize(
        "block_string",
        [
            "[[>]] a plain block quote",
            "> a plain block quote",
            "[[>]] [[!QUOTE]] A pull quote",
            "[[>]] [[!INFO]] a callout",
            "[[>]] [[!epigraph]] lowercase keyword",
            "plain text",
        ],
    )
    def test_none_for_anything_but_an_epigraph(self, block_string: str) -> None:
        """Only the uppercase [[>]] [[!EPIGRAPH]] marker makes an epigraph."""
        assert parse_epigraph(block_string) is None

    def test_is_a_quote_block(self) -> None:
        """An epigraph is a quote block, not a callout."""
        assert is_quote_block("[[>]] [[!EPIGRAPH]]\nAn epigraph")
        assert CALLOUT_RE.match("[[>]] [[!EPIGRAPH]]\nAn epigraph") is None

    def test_raises_validation_error_for_null_input(self) -> None:
        """Raises ValidationError when None is passed."""
        with pytest.raises(ValidationError):
            parse_epigraph(None)  # type: ignore[arg-type]
