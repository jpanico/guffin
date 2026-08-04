"""Tests for guffin.model.element_number."""

import pytest
from pydantic import ValidationError

from guffin.model.chicago_structure import Matter
from guffin.model.element_number import (
    MATTER_BY_LEADING_SEGMENT,
    ElementNumber,
    leads_with_dotted_element_number_shape,
    leads_with_element_number_shape,
    parse_element_number,
    stripped_element_number,
)


class TestParseElementNumber:
    """parse_element_number() reads a well-formed leading marker and rejects everything else."""

    def test_two_segments_parse(self) -> None:
        """A minimal two-segment marker parses into its integer segments."""
        number = parse_element_number("[1.2] Chapter Two")
        assert number is not None
        assert number.segments == (1, 2)

    def test_three_segments_parse(self) -> None:
        """A deeper marker parses every dot-separated segment."""
        number = parse_element_number("[1.2.10] Chapter Ten")
        assert number is not None
        assert number.segments == (1, 2, 10)

    def test_leading_whitespace_is_ignored(self) -> None:
        """The marker is the first text ignoring whitespace."""
        number = parse_element_number("  \t[0.3] An Epistle")
        assert number is not None
        assert number.segments == (0, 3)

    def test_zero_leading_segment_parses(self) -> None:
        """A single 0 is a legal segment (the front-matter classifier), not a leading zero."""
        number = parse_element_number("[0.1] Acknowledgments")
        assert number is not None
        assert number.segments == (0, 1)

    def test_plain_text_is_none(self) -> None:
        """Text with no marker parses to None."""
        assert parse_element_number("A.D. 1290.") is None

    def test_bare_single_segment_is_none(self) -> None:
        """A bare bracketed integer is not a well-formed element number (minimum two segments)."""
        assert parse_element_number("[1] Book I") is None

    def test_leading_zero_segment_is_none(self) -> None:
        """A padded segment is malformed."""
        assert parse_element_number("[01.2] Chapter") is None

    def test_consecutive_dots_are_none(self) -> None:
        """An empty segment is malformed."""
        assert parse_element_number("[1..2] Chapter") is None

    def test_marker_not_at_lead_is_none(self) -> None:
        """A marker after other text is not an element number."""
        assert parse_element_number("Chapter [1.2] Two") is None

    def test_page_reference_lead_is_none(self) -> None:
        """A page-reference lead (``[[…]]``) never reads as a marker."""
        assert parse_element_number("[[Acknowledgments]]") is None

    def test_markdown_link_lead_is_none(self) -> None:
        """A Markdown link lead is excluded by the lookahead for '('."""
        assert parse_element_number("[1.2](https://example.com) linked") is None

    def test_unclosed_bracket_is_none(self) -> None:
        """An unclosed bracket lead is ordinary text."""
        assert parse_element_number("[1.2 Chapter") is None


class TestLeadsWithElementNumberShape:
    """leads_with_element_number_shape() separates attempted markers from ordinary text."""

    def test_well_formed_marker_is_shaped(self) -> None:
        """A well-formed marker is also number-shaped."""
        assert leads_with_element_number_shape("[1.2] Chapter") is True

    def test_bare_single_segment_is_shaped(self) -> None:
        """A bare bracketed integer is number-shaped (a malformed attempt, not ordinary text)."""
        assert leads_with_element_number_shape("[1] Book I") is True

    def test_padded_segment_is_shaped(self) -> None:
        """A padded segment is number-shaped."""
        assert leads_with_element_number_shape("[01.2] Chapter") is True

    def test_consecutive_dots_are_shaped(self) -> None:
        """Empty segments are number-shaped."""
        assert leads_with_element_number_shape("[1..2] Chapter") is True

    def test_plain_text_is_not_shaped(self) -> None:
        """Text with no bracket lead is not number-shaped."""
        assert leads_with_element_number_shape("Chapter Two") is False

    def test_page_reference_lead_is_not_shaped(self) -> None:
        """A page-reference lead (``[[…]]``) is not number-shaped."""
        assert leads_with_element_number_shape("[[Acknowledgments]]") is False

    def test_markdown_link_lead_is_not_shaped(self) -> None:
        """A Markdown link lead is not number-shaped (lookahead for '(')."""
        assert leads_with_element_number_shape("[1](https://example.com) footnote link") is False

    def test_wordy_bracket_lead_is_not_shaped(self) -> None:
        """A bracket containing non-digits is not number-shaped."""
        assert leads_with_element_number_shape("[sic] quoted") is False


class TestLeadsWithDottedElementNumberShape:
    """leads_with_dotted_element_number_shape() additionally requires a dot in the marker."""

    def test_dotted_marker_is_shaped(self) -> None:
        """A dotted marker is dotted-number-shaped."""
        assert leads_with_dotted_element_number_shape("[1.2] stray") is True

    def test_malformed_dotted_marker_is_shaped(self) -> None:
        """A malformed but dotted marker is dotted-number-shaped."""
        assert leads_with_dotted_element_number_shape("[1..2] stray") is True

    def test_bare_single_segment_is_not_shaped(self) -> None:
        """A bare bracketed integer — a footnote or citation label in prose — is not."""
        assert leads_with_dotted_element_number_shape("[1] See Letter of Fr. Odoric") is False


class TestElementNumberModel:
    """ElementNumber enforces its shape and is immutable."""

    def test_single_segment_is_rejected(self) -> None:
        """A number needs at least two segments: the matter classifier plus an ordinal."""
        with pytest.raises(ValidationError):
            ElementNumber(segments=(1,))

    def test_negative_segment_is_rejected(self) -> None:
        """Segments are non-negative integers."""
        with pytest.raises(ValidationError):
            ElementNumber(segments=(1, -2))

    def test_frozen(self) -> None:
        """Instances are immutable."""
        number = ElementNumber(segments=(1, 2))
        with pytest.raises(ValidationError):
            number.segments = (2, 1)  # type: ignore[misc]

    def test_str_is_dotted_form(self) -> None:
        """str() renders the dotted form without brackets."""
        assert str(ElementNumber(segments=(1, 2, 10))) == "1.2.10"


class TestElementNumberOrdering:
    """ElementNumber is totally ordered by numeric tuple comparison."""

    def test_sibling_order(self) -> None:
        """Siblings order by their differing segment."""
        assert ElementNumber(segments=(1, 1)) < ElementNumber(segments=(1, 2))

    def test_prefix_orders_before_extension(self) -> None:
        """A number orders before every number it prefixes."""
        assert ElementNumber(segments=(1, 2)) < ElementNumber(segments=(1, 2, 1))

    def test_numeric_not_textual(self) -> None:
        """Comparison is numeric per segment, so 10 follows 9."""
        assert ElementNumber(segments=(1, 9)) < ElementNumber(segments=(1, 10))

    def test_equality_is_segment_equality(self) -> None:
        """Equal segments mean equal numbers."""
        assert ElementNumber(segments=(1, 2)) == ElementNumber(segments=(1, 2))

    def test_total_ordering_derives_ge(self) -> None:
        """The derived comparisons agree with __lt__ and equality."""
        assert ElementNumber(segments=(1, 2)) >= ElementNumber(segments=(1, 2))
        assert ElementNumber(segments=(1, 3)) > ElementNumber(segments=(1, 2))


class TestElementNumberMatter:
    """The leading segment classifies the matter division per the fixed convention."""

    def test_zero_is_front_matter(self) -> None:
        """Leading 0 is front-matter."""
        assert ElementNumber(segments=(0, 1)).matter is Matter.FRONT

    def test_one_is_body_matter(self) -> None:
        """Leading 1 is body-matter."""
        assert ElementNumber(segments=(1, 4)).matter is Matter.BODY

    def test_two_is_back_matter(self) -> None:
        """Leading 2 is back-matter."""
        assert ElementNumber(segments=(2, 1)).matter is Matter.BACK

    def test_other_leading_segment_has_no_matter(self) -> None:
        """A leading segment outside the convention resolves to None."""
        assert ElementNumber(segments=(3, 1)).matter is None

    def test_convention_covers_every_matter(self) -> None:
        """The fixed convention maps onto the full Matter enum, one division per legal segment."""
        assert set(MATTER_BY_LEADING_SEGMENT.values()) == set(Matter)


class TestIsPrefixOf:
    """is_prefix_of() tests strict prefixing."""

    def test_strict_prefix(self) -> None:
        """A number strictly prefixes its extensions."""
        assert ElementNumber(segments=(1, 2)).is_prefix_of(ElementNumber(segments=(1, 2, 3))) is True

    def test_equal_is_not_prefix(self) -> None:
        """A number is not a strict prefix of itself."""
        assert ElementNumber(segments=(1, 2)).is_prefix_of(ElementNumber(segments=(1, 2))) is False

    def test_textual_prefix_is_not_prefix(self) -> None:
        """Segment 2 does not prefix segment 20 — prefixing is by segment, not by text."""
        assert ElementNumber(segments=(1, 2)).is_prefix_of(ElementNumber(segments=(1, 20))) is False

    def test_diverging_number_is_not_prefix(self) -> None:
        """A number does not prefix a sibling branch."""
        assert ElementNumber(segments=(1, 2)).is_prefix_of(ElementNumber(segments=(1, 3, 1))) is False


class TestStrippedElementNumber:
    """stripped_element_number() removes a well-formed leading marker and nothing else."""

    def test_marker_is_stripped(self) -> None:
        """A well-formed marker and its separating whitespace are removed."""
        assert stripped_element_number("[1.2] Chapter Two") == "Chapter Two"

    def test_leading_whitespace_before_marker_is_stripped(self) -> None:
        """Whitespace around the marker goes with it."""
        assert stripped_element_number("  [0.3] An Epistle") == "An Epistle"

    def test_plain_text_is_unchanged(self) -> None:
        """Text with no marker passes through unchanged."""
        assert stripped_element_number("A.D. 1290.") == "A.D. 1290."

    def test_malformed_lead_is_unchanged(self) -> None:
        """A malformed number-shaped lead is not stripped (validation reports it instead)."""
        assert stripped_element_number("[1] Book I") == "[1] Book I"

    def test_markdown_link_lead_is_unchanged(self) -> None:
        """A Markdown link lead is not a marker."""
        assert stripped_element_number("[1.2](https://example.com) linked") == "[1.2](https://example.com) linked"

    def test_marker_only_text_strips_to_empty(self) -> None:
        """A heading that is nothing but its marker strips to the empty string."""
        assert stripped_element_number("[1.2]") == ""
