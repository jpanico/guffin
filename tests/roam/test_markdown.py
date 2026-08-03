"""Tests for the guffin.roam.markdown regex constants."""

from typing import Final

import pytest

from guffin.roam.markdown import (
    ATTRIBUTE_ASSIGNMENT_RE,
    BLOCK_EMBED_RE,
    BLOCK_REF_RE,
    FIREBASE_STORAGE_URL_RE,
    PAGE_EMBED_RE,
    PAGE_REF_RE,
    PDF_EMBED_RE,
    TAG_RE,
    image_link_alt_text,
    image_link_url,
    pdf_embed_url,
)

_FIREBASE_STORAGE_URL: Final[str] = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING: Final[str] = f"![A flower]({_FIREBASE_STORAGE_URL})"

_FIREBASE_STORAGE_PDF_URL: Final[str] = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/pdfs%2Fpaper.pdf.enc?alt=media&token=abc123"
)
_PDF_STRING: Final[str] = f"{{{{pdf: {_FIREBASE_STORAGE_PDF_URL}}}}}"

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

    def test_page_reference_form_match(self) -> None:
        """The {{[[embed]]: ((<uid>))}} page-reference spelling is equivalent to the bare form."""
        m = BLOCK_EMBED_RE.search("{{[[embed]]: ((4SIo9hSEY))}}")
        assert m is not None
        assert m.group(0) == "{{[[embed]]: ((4SIo9hSEY))}}"
        assert m.group("uid") == "4SIo9hSEY"

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


class TestPageEmbedRE:
    """Tests for PAGE_EMBED_RE — the Roam page embed {{embed: [[<page_name>]]}} regex."""

    # --- match cases ---

    def test_basic_match_full_string(self) -> None:
        """Full page-embed string is consumed by a single match."""
        m = PAGE_EMBED_RE.search("{{embed: [[Some Page]]}}")
        assert m is not None
        assert m.group(0) == "{{embed: [[Some Page]]}}"

    def test_page_name_group(self) -> None:
        """Named group 'page_name' captures the embedded page's title (carried through from PAGE_REF_RE)."""
        m = PAGE_EMBED_RE.search("{{embed: [[CHAPTER XXXVI. Account of the City of Juju.]]}}")
        assert m is not None
        assert m.group("page_name") == "CHAPTER XXXVI. Account of the City of Juju."

    def test_nested_page_reference_in_name(self) -> None:
        """A page name containing a nested [[...]] reference is captured whole (recursive match)."""
        m = PAGE_EMBED_RE.fullmatch("{{embed: [[A [[nested]] page]]}}")
        assert m is not None
        assert m.group("page_name") == "A [[nested]] page"

    def test_inline_embed(self) -> None:
        """A page embed surrounded by other text is captured."""
        m = PAGE_EMBED_RE.search("see {{embed: [[Some Page]]}} here")
        assert m is not None
        assert m.group(0) == "{{embed: [[Some Page]]}}"
        assert m.group("page_name") == "Some Page"

    def test_page_reference_form_match(self) -> None:
        """The {{[[embed]]: [[<page_name>]]}} page-reference spelling is equivalent to the bare form."""
        m = PAGE_EMBED_RE.search("{{[[embed]]: [[Some Page]]}}")
        assert m is not None
        assert m.group(0) == "{{[[embed]]: [[Some Page]]}}"
        assert m.group("page_name") == "Some Page"

    # --- no-match cases ---

    def test_no_match_bare_page_ref(self) -> None:
        """A bare page reference without the {{embed: }} wrapper does not match."""
        assert PAGE_EMBED_RE.search("[[Some Page]]") is None

    def test_no_match_missing_space(self) -> None:
        """The literal single space after 'embed:' is required."""
        assert PAGE_EMBED_RE.search("{{embed:[[Some Page]]}}") is None

    def test_no_match_block_embed(self) -> None:
        """A block embed ({{embed: ((uid))}}) is not a page embed."""
        assert PAGE_EMBED_RE.search("{{embed: ((wdMgyBiP9))}}") is None


# ---------------------------------------------------------------------------
# TestFirebaseStorageUrlRE
# ---------------------------------------------------------------------------


class TestFirebaseStorageUrlRE:
    """Tests for FIREBASE_STORAGE_URL_RE — the canonical Firebase Storage URL regex."""

    # --- match cases ---

    def test_canonical_url_full_match(self) -> None:
        """A canonical Firebase Storage URL matches in full, with its anatomy captured."""
        m = FIREBASE_STORAGE_URL_RE.fullmatch(_FIREBASE_STORAGE_URL)
        assert m is not None
        assert m.group("bucket") == "test.appspot.com"
        assert m.group("object_path") == "imgs%2Fphoto.jpeg"
        assert m.group("query") == "alt=media&token=abc123"

    def test_nested_object_path(self) -> None:
        """A deeply nested percent-encoded object path (the live-graph shape) matches in full."""
        url = (
            "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com"
            "/o/imgs%2Fapp%2FSCFH%2FfJoSdh65Ry.pkpass.enc"
            "?alt=media&token=b756b61a-8d04-4f30-a887-3feac7bb9d6a"
        )
        m = FIREBASE_STORAGE_URL_RE.fullmatch(url)
        assert m is not None
        assert m.group("object_path") == "imgs%2Fapp%2FSCFH%2FfJoSdh65Ry.pkpass.enc"

    def test_self_terminates_before_delimiters(self) -> None:
        """The tight charset stops the match at a host construct's delimiter, not inside it."""
        m = FIREBASE_STORAGE_URL_RE.search(f"({_FIREBASE_STORAGE_URL})")
        assert m is not None
        assert m.group(0) == _FIREBASE_STORAGE_URL
        m2 = FIREBASE_STORAGE_URL_RE.search(f"{{{{pdf: {_FIREBASE_STORAGE_PDF_URL}}}}}")
        assert m2 is not None
        assert m2.group(0) == _FIREBASE_STORAGE_PDF_URL

    # --- no-match cases ---

    def test_no_match_other_host(self) -> None:
        """A URL on any other host is not a Firebase Storage URL."""
        assert FIREBASE_STORAGE_URL_RE.search("https://example.com/v0/b/x/o/y.png?alt=media") is None

    def test_no_match_missing_object_path(self) -> None:
        """A Firebase Storage-host URL without the /o/ object path does not match."""
        assert FIREBASE_STORAGE_URL_RE.search("https://firebasestorage.googleapis.com/v0/b/test.appspot.com") is None

    def test_no_match_missing_query(self) -> None:
        """A Firebase Storage URL without its access-parameter query string does not match."""
        assert (
            FIREBASE_STORAGE_URL_RE.fullmatch("https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/x.png")
            is None
        )


# ---------------------------------------------------------------------------
# TestPdfEmbedRE
# ---------------------------------------------------------------------------


class TestPdfEmbedRE:
    """Tests for PDF_EMBED_RE — the Roam PDF component {{pdf: <url>}} regex."""

    # --- match cases ---

    def test_bare_form_full_string(self) -> None:
        """The bare {{pdf: <url>}} form is consumed by a single match."""
        m = PDF_EMBED_RE.search(_PDF_STRING)
        assert m is not None
        assert m.group(0) == _PDF_STRING
        assert m.group("url") == _FIREBASE_STORAGE_PDF_URL

    def test_page_reference_form(self) -> None:
        """The page-reference {{[[pdf]]: <url>}} form is equivalent to the bare form."""
        m = PDF_EMBED_RE.search(f"{{{{[[pdf]]: {_FIREBASE_STORAGE_PDF_URL}}}}}")
        assert m is not None
        assert m.group("url") == _FIREBASE_STORAGE_PDF_URL

    def test_inline_component(self) -> None:
        """A PDF component embedded in surrounding prose is captured."""
        m = PDF_EMBED_RE.search(f"see {_PDF_STRING} here")
        assert m is not None
        assert m.group(0) == _PDF_STRING

    # --- no-match cases ---

    def test_no_match_non_firebase_storage_url(self) -> None:
        """A PDF component whose URL is not a Firebase Storage URL does not match."""
        assert PDF_EMBED_RE.search("{{pdf: https://example.com/paper.pdf}}") is None

    def test_no_match_missing_space(self) -> None:
        """The literal single space after the colon is required."""
        assert PDF_EMBED_RE.search(f"{{{{pdf:{_FIREBASE_STORAGE_PDF_URL}}}}}") is None

    def test_no_match_bare_url(self) -> None:
        """A naked Firebase Storage URL without the {{pdf: }} wrapper does not match."""
        assert PDF_EMBED_RE.search(_FIREBASE_STORAGE_PDF_URL) is None

    def test_no_match_other_component(self) -> None:
        """A different Roam component keyword does not match."""
        assert PDF_EMBED_RE.search(f"{{{{video: {_FIREBASE_STORAGE_PDF_URL}}}}}") is None


# ---------------------------------------------------------------------------
# TestPdfEmbedUrl
# ---------------------------------------------------------------------------


class TestPdfEmbedUrl:
    """Tests for pdf_embed_url."""

    def test_extracts_url_from_component(self) -> None:
        """The Firebase Storage URL is captured from a block string's PDF component."""
        assert pdf_embed_url(_PDF_STRING) == _FIREBASE_STORAGE_PDF_URL

    def test_extracts_url_from_page_reference_form(self) -> None:
        """The URL is captured from the {{[[pdf]]: <url>}} form."""
        assert pdf_embed_url(f"{{{{[[pdf]]: {_FIREBASE_STORAGE_PDF_URL}}}}}") == _FIREBASE_STORAGE_PDF_URL

    def test_none_when_no_component(self) -> None:
        """A string with no PDF component yields None."""
        assert pdf_embed_url("just some plain text") is None

    def test_none_for_non_firebase_storage_url(self) -> None:
        """A PDF component pointing outside Firebase Storage yields None."""
        assert pdf_embed_url("{{pdf: https://example.com/paper.pdf}}") is None


# ---------------------------------------------------------------------------
# TestImageLinkUrl
# ---------------------------------------------------------------------------


class TestImageLinkUrl:
    """Tests for image_link_url."""

    def test_extracts_url_from_image_link(self) -> None:
        """The Firebase Storage URL is captured from a block string's image link."""
        assert image_link_url(_IMAGE_STRING) == _FIREBASE_STORAGE_URL

    def test_extracts_url_embedded_in_surrounding_text(self) -> None:
        """The first image link's URL is found amid surrounding text."""
        assert image_link_url(f"see {_IMAGE_STRING} below") == _FIREBASE_STORAGE_URL

    def test_none_when_no_image_link(self) -> None:
        """A string with no Firebase Storage image link yields None."""
        assert image_link_url("just some plain text") is None

    def test_none_for_non_firebase_storage_image(self) -> None:
        """A markdown image whose URL is not a Firebase Storage URL is not matched."""
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
        assert image_link_alt_text(f"![  spaced  ]({_FIREBASE_STORAGE_URL})") == "spaced"

    def test_none_when_alt_text_empty(self) -> None:
        """An image link with empty alt text yields None."""
        assert image_link_alt_text(f"![]({_FIREBASE_STORAGE_URL})") is None

    def test_none_when_no_image_link(self) -> None:
        """A string with no Firebase Storage image link yields None."""
        assert image_link_alt_text("just some plain text") is None
