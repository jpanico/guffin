"""Tests for the guffin.roam.markdown regex constants and callout parser."""

from typing import Final

import pytest
from pydantic import ValidationError

from guffin.roam.markdown import (
    ATTRIBUTE_ASSIGNMENT_RE,
    BLOCK_EMBED_RE,
    BLOCK_REF_RE,
    CALLOUT_RE,
    PAGE_REF_RE,
    TAG_RE,
    CalloutType,
    RoamCallout,
    firestore_url_file_name,
    image_link_alt_text,
    image_link_url,
    parse_callout,
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
# TestTagRE
# ---------------------------------------------------------------------------


class TestTagRE:
    """Tests for TAG_RE — a tag is ``#`` followed by a bracketed page reference or a bare page name."""

    # --- bare page-name form (bare_page_name): letters + digits only ---

    def test_bare_full_match(self) -> None:
        """A bare tag is consumed whole, including the leading '#'."""
        m = TAG_RE.search("#Guffin")
        assert m is not None
        assert m.group(0) == "#Guffin"
        assert m.group("bare_page_name") == "Guffin"
        assert m.group("page_ref") is None
        assert m.group("page_name") is None

    def test_bare_stops_at_punctuation(self) -> None:
        """The bare form admits no punctuation, so it stops at a comma."""
        m = TAG_RE.search("#Guffin,more")
        assert m is not None
        assert m.group(0) == "#Guffin"
        assert m.group("bare_page_name") == "Guffin"

    def test_bare_stops_at_dot(self) -> None:
        """A dot is punctuation outside the allowed connectors, so the bare form stops before it."""
        m = TAG_RE.search("#a.b")
        assert m is not None
        assert m.group("bare_page_name") == "a"

    def test_bare_stops_at_whitespace(self) -> None:
        """A bare tag terminates at the first whitespace character."""
        m = TAG_RE.search("#Guffin is great")
        assert m is not None
        assert m.group("bare_page_name") == "Guffin"

    @pytest.mark.parametrize(
        "name",
        [
            "Guffin",  # capitalized
            "todo",  # lowercase
            "v01",  # letters + digits
            "café",  # non-ASCII letters allowed
            "2024",  # all digits
            "some-tag",  # hyphen allowed
            "a_b_c",  # underscore allowed
            "a—b",  # em-dash allowed
        ],
    )
    def test_valid_bare_characters(self, name: str) -> None:
        """Letters, digits, and the connectors underscore/hyphen/em-dash are accepted."""
        m = TAG_RE.search(f"#{name} ")
        assert m is not None
        assert m.group("bare_page_name") == name

    def test_bare_at_max_length(self) -> None:
        """A 45-character bare name is matched whole (upper bound)."""
        name = "a" * 45
        m = TAG_RE.search(f"#{name}")
        assert m is not None
        assert m.group("bare_page_name") == name

    def test_bare_over_max_length_truncated(self) -> None:
        """A bare name longer than 45 chars matches only its first 45 characters."""
        m = TAG_RE.search("#" + "a" * 46)
        assert m is not None
        assert m.group("bare_page_name") == "a" * 45

    # --- bracketed page-reference form (page_ref / page_name): permissive ---

    def test_page_ref_full_match(self) -> None:
        """A bracketed tag is consumed whole, exposing page_ref and page_name."""
        m = TAG_RE.search("#[[Better Bullets]]")
        assert m is not None
        assert m.group(0) == "#[[Better Bullets]]"
        assert m.group("page_ref") == "[[Better Bullets]]"
        assert m.group("page_name") == "Better Bullets"
        assert m.group("bare_page_name") is None

    def test_page_ref_compound_nested(self) -> None:
        """A bracketed tag may reference a compound page name containing a nested reference."""
        m = TAG_RE.search("#[[a [[b]] c]]")
        assert m is not None
        assert m.group(0) == "#[[a [[b]] c]]"
        assert m.group("page_name") == "a [[b]] c"

    def test_page_ref_allows_punctuation(self) -> None:
        """A bracketed page name is permissive — it may contain punctuation such as a colon."""
        m = TAG_RE.search("#[[Chapter 7: intro]]")
        assert m is not None
        assert m.group("page_name") == "Chapter 7: intro"

    def test_no_match_page_ref_across_newline(self) -> None:
        """A bracketed page name spanning a newline does not match."""
        assert TAG_RE.search("#[[foo\nbar]]") is None

    # --- no-match cases ---

    def test_no_match_plain_text(self) -> None:
        """Text without a '#' does not match."""
        assert TAG_RE.search("no tags here") is None

    def test_no_match_hash_then_whitespace(self) -> None:
        """A '#' immediately followed by whitespace does not start a tag."""
        assert TAG_RE.search("# spaced") is None

    def test_no_match_hash_then_punctuation(self) -> None:
        """A '#' immediately followed by punctuation is neither a bracketed nor a bare tag."""
        assert TAG_RE.search("#,") is None

    def test_no_match_unterminated_page_ref(self) -> None:
        """A '#[[' with no closing ']]' is not a tag."""
        assert TAG_RE.search("#[[unclosed") is None


# ---------------------------------------------------------------------------
# TestAttributeAssignmentRE
# ---------------------------------------------------------------------------


class TestAttributeAssignmentRE:
    """Tests for ATTRIBUTE_ASSIGNMENT_RE — ``<attribute>:: <value>[, <value>]…``."""

    # --- fixture-derived examples ---

    def test_attribute1_example(self) -> None:
        """The fixture 'attribute1' assignment: a slug value and two tag values."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("attribute1:: 5, #[[callouts demo]], #v01")
        assert m is not None
        assert m.group("attribute") == "attribute1"
        assert m.group("values") == "5, #[[callouts demo]], #v01"
        assert m.captures("value") == ["5", "#[[callouts demo]]", "#v01"]

    def test_tags_example(self) -> None:
        """The fixture 'tags' assignment: two tag values, no spaces around the comma."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("tags:: #Guffin,#[[Better Bullets]]")
        assert m is not None
        assert m.group("attribute") == "tags"
        assert m.captures("value") == ["#Guffin", "#[[Better Bullets]]"]

    # --- structure ---

    def test_single_slug_value(self) -> None:
        """A single bare-slug value is captured."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("status:: done")
        assert m is not None
        assert m.group("attribute") == "status"
        assert m.captures("value") == ["done"]

    def test_single_bare_tag_value(self) -> None:
        """A single bare-tag value is captured."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("topic:: #Guffin")
        assert m is not None
        assert m.captures("value") == ["#Guffin"]

    def test_no_space_after_separator(self) -> None:
        """The separator need not be followed by whitespace."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("k::a")
        assert m is not None
        assert m.group("attribute") == "k"
        assert m.captures("value") == ["a"]

    def test_leading_whitespace_after_separator_excluded(self) -> None:
        """Whitespace between '::' and the first value is not part of 'values'."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("k::   v")
        assert m is not None
        assert m.group("values") == "v"

    def test_value_with_nested_page_ref(self) -> None:
        """A tag value may reference a compound (nested) page name."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("k:: #[[a [[b]] c]], z")
        assert m is not None
        assert m.captures("value") == ["#[[a [[b]] c]]", "z"]

    def test_match_on_inner_line(self) -> None:
        """MULTILINE: an assignment on a later line of a block string still matches."""
        m = ATTRIBUTE_ASSIGNMENT_RE.search("intro text\ntags:: #Guffin")
        assert m is not None
        assert m.group("attribute") == "tags"
        assert m.captures("value") == ["#Guffin"]

    # --- no-match cases ---

    def test_no_match_missing_separator(self) -> None:
        """A line without '::' is not an assignment."""
        assert ATTRIBUTE_ASSIGNMENT_RE.search("tags #Guffin") is None

    def test_no_match_not_line_anchored(self) -> None:
        """An assignment not at the start of a line does not match."""
        assert ATTRIBUTE_ASSIGNMENT_RE.search("prefix tags:: #Guffin") is None

    def test_no_match_empty_values(self) -> None:
        """An assignment with no value after '::' does not match."""
        assert ATTRIBUTE_ASSIGNMENT_RE.search("tags:: ") is None

    def test_no_match_punctuation_attribute(self) -> None:
        """An attribute name with disallowed punctuation does not match."""
        assert ATTRIBUTE_ASSIGNMENT_RE.search("a.b:: x") is None


# ---------------------------------------------------------------------------
# TestBlockRefRE
# ---------------------------------------------------------------------------


class TestBlockRefRE:
    """Tests for BLOCK_REF_RE — the Roam block reference ((<uid>)) regex."""

    # --- match cases ---

    def test_basic_match_full_string(self) -> None:
        """Full string is consumed by a single match."""
        m = BLOCK_REF_RE.search("((wdMgyBiP9))")
        assert m is not None
        assert m.group(0) == "((wdMgyBiP9))"

    def test_uid_group(self) -> None:
        """Named group 'uid' captures just the nine-character UID."""
        m = BLOCK_REF_RE.search("((wdMgyBiP9))")
        assert m is not None
        assert m.group("uid") == "wdMgyBiP9"

    @pytest.mark.parametrize(
        "uid",
        [
            "abc123xyz",  # all lowercase alphanumeric
            "ABCDEFGHI",  # all uppercase
            "123456789",  # all digits
            "abc_23xyz",  # underscore allowed
            "abc-23xyz",  # dash allowed
            "A1b2C3d4E",  # mixed case + digits
        ],
    )
    def test_valid_uid_characters(self, uid: str) -> None:
        """All characters permitted by UID_PATTERN are accepted."""
        m = BLOCK_REF_RE.search(f"(({uid}))")
        assert m is not None
        assert m.group("uid") == uid

    def test_inline_reference(self) -> None:
        """A reference embedded in surrounding prose is captured."""
        m = BLOCK_REF_RE.search("see ((wdMgyBiP9)) here")
        assert m is not None
        assert m.group(0) == "((wdMgyBiP9))"
        assert m.group("uid") == "wdMgyBiP9"

    def test_multiple_refs_via_finditer(self) -> None:
        """Adjacent block references are matched separately."""
        uids = [m.group("uid") for m in BLOCK_REF_RE.finditer("((abc123xyz)) and ((wdMgyBiP9))")]
        assert uids == ["abc123xyz", "wdMgyBiP9"]

    # --- no-match cases ---

    def test_no_match_plain_text(self) -> None:
        """Plain text without double-parens does not match."""
        assert BLOCK_REF_RE.search("no refs here") is None

    def test_no_match_single_parens(self) -> None:
        """Single-paren wrapping (uid) is not a block reference."""
        assert BLOCK_REF_RE.search("(wdMgyBiP9)") is None

    def test_no_match_empty_parens(self) -> None:
        """Empty (()) does not match — a UID is required."""
        assert BLOCK_REF_RE.search("(())") is None

    def test_no_match_uid_too_short(self) -> None:
        """A UID shorter than nine characters does not match."""
        assert BLOCK_REF_RE.search("((abc1234))") is None

    def test_no_match_uid_too_long(self) -> None:
        """A UID longer than nine characters does not match."""
        assert BLOCK_REF_RE.search("((abc123xyz0))") is None

    def test_no_match_space_in_uid(self) -> None:
        """A space inside the UID position is rejected."""
        assert BLOCK_REF_RE.search("((abc 3xyz))") is None

    def test_no_match_bang_in_uid(self) -> None:
        """A punctuation character (!) inside the UID position is rejected."""
        assert BLOCK_REF_RE.search("((abc!23xyz))") is None

    def test_no_match_unclosed(self) -> None:
        """An unclosed ((uid) reference does not match."""
        assert BLOCK_REF_RE.search("((wdMgyBiP9)") is None

    def test_no_match_page_ref_syntax(self) -> None:
        """Square-bracket [[uid]] page-ref syntax is not a block reference."""
        assert BLOCK_REF_RE.search("[[wdMgyBiP9]]") is None


# ---------------------------------------------------------------------------
# TestBlockEmbedRE
# ---------------------------------------------------------------------------


class TestBlockEmbedRE:
    """Tests for BLOCK_EMBED_RE — the Roam block embed {{embed: ((<uid>))}} regex."""

    # --- match cases ---

    def test_basic_match_full_string(self) -> None:
        """Full embed string is consumed by a single match."""
        m = BLOCK_EMBED_RE.search("{{embed: ((wdMgyBiP9))}}")
        assert m is not None
        assert m.group(0) == "{{embed: ((wdMgyBiP9))}}"

    def test_uid_group(self) -> None:
        """Named group 'uid' captures the embedded block's UID (carried through from BLOCK_REF_RE)."""
        m = BLOCK_EMBED_RE.search("{{embed: ((LfXmNr-tV))}}")
        assert m is not None
        assert m.group("uid") == "LfXmNr-tV"

    def test_inline_embed(self) -> None:
        """An embed surrounded by other text is captured."""
        m = BLOCK_EMBED_RE.search("see {{embed: ((wdMgyBiP9))}} here")
        assert m is not None
        assert m.group(0) == "{{embed: ((wdMgyBiP9))}}"
        assert m.group("uid") == "wdMgyBiP9"

    # --- no-match cases ---

    def test_no_match_bare_block_ref(self) -> None:
        """A bare block reference without the {{embed: }} wrapper does not match."""
        assert BLOCK_EMBED_RE.search("((wdMgyBiP9))") is None

    def test_no_match_missing_space(self) -> None:
        """The literal single space after 'embed:' is required."""
        assert BLOCK_EMBED_RE.search("{{embed:((wdMgyBiP9))}}") is None

    def test_no_match_uid_not_a_block_ref(self) -> None:
        """An embed whose target is a bare UID rather than a ((...)) reference does not match."""
        assert BLOCK_EMBED_RE.search("{{embed: wdMgyBiP9}}") is None

    def test_no_match_uid_too_short(self) -> None:
        """A UID shorter than nine characters does not match."""
        assert BLOCK_EMBED_RE.search("{{embed: ((abc1234))}}") is None


# ---------------------------------------------------------------------------
# TestImageLinkUrl
# ---------------------------------------------------------------------------


class TestImageLinkUrl:
    """Tests for image_link_url."""

    def test_extracts_url_from_image_link(self) -> None:
        """The Firestore URL is captured from a block string's image link."""
        assert image_link_url(_IMAGE_STRING) == _FIRESTORE_URL

    def test_extracts_url_embedded_in_surrounding_text(self) -> None:
        """The first image link's URL is found amid surrounding text."""
        assert image_link_url(f"see {_IMAGE_STRING} below") == _FIRESTORE_URL

    def test_none_when_no_image_link(self) -> None:
        """A string with no Firestore image link yields None."""
        assert image_link_url("just some plain text") is None

    def test_none_for_non_firestore_image(self) -> None:
        """A markdown image whose URL is not a Firestore URL is not matched."""
        assert image_link_url("![alt](https://example.com/photo.png)") is None


# ---------------------------------------------------------------------------
# TestImageLinkAltText
# ---------------------------------------------------------------------------


class TestImageLinkAltText:
    """Tests for image_link_alt_text."""

    def test_extracts_alt_text(self) -> None:
        """The alt text is captured from a block string's image link."""
        assert image_link_alt_text(_IMAGE_STRING) == "A flower"

    def test_strips_surrounding_whitespace(self) -> None:
        """Leading and trailing whitespace is stripped from the alt text."""
        assert image_link_alt_text(f"![  spaced  ]({_FIRESTORE_URL})") == "spaced"

    def test_none_when_alt_text_empty(self) -> None:
        """An image link with empty alt text yields None."""
        assert image_link_alt_text(f"![]({_FIRESTORE_URL})") is None

    def test_none_when_no_image_link(self) -> None:
        """A string with no Firestore image link yields None."""
        assert image_link_alt_text("just some plain text") is None


# ---------------------------------------------------------------------------
# TestFirestoreUrlFileName
# ---------------------------------------------------------------------------


class TestFirestoreUrlFileName:
    """Tests for firestore_url_file_name."""

    def test_decodes_filename_from_url(self) -> None:
        """The percent-encoded object path decodes to its last segment."""
        assert firestore_url_file_name(_FIRESTORE_URL) == "photo.jpeg"

    def test_none_when_no_object_path(self) -> None:
        """A URL without an /o/ object path segment yields None."""
        assert firestore_url_file_name("https://firebasestorage.googleapis.com/v0/b/test.appspot.com") is None
