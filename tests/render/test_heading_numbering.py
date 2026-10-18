"""Tests for guffin.render.heading_numbering (Chicago heading numbers in a parts book) and its Typst filter."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
import pytest

import guffin.render.pdf_rendering as pdf_rendering_module
from guffin.render.heading_numbering import (
    HEADING_NUMBER_ATTRIBUTE,
    HEADING_NUMBER_CLASS,
    insert_heading_number_spans,
    number_parts_book_headings,
    roman_numeral,
)
from guffin.render.pandoc_ast import pandoc_to_json

_TYPST_HEADING_NUMBER_FILTER: Final[Path] = (
    Path(pdf_rendering_module.__file__).parent / "typst_resources" / "typst_heading_number.lua"
)


def _header(level: int, text: str, *classes: str) -> pf.Header:
    return pf.Header(pf.Str(text), level=level, identifier=f"h-{text.lower()}", classes=list(classes))


def _numbers(doc: pf.Doc) -> dict[str, str | None]:
    """Each header's text mapped to its stamped number, or None."""
    return {
        pf.stringify(block): block.attributes.get(HEADING_NUMBER_ATTRIBUTE)
        for block in doc.content
        if isinstance(block, pf.Header)
    }


def _parts_book() -> pf.Doc:
    """Front matter, two parts of two and one chapters (one with sections), and back matter."""
    return pf.Doc(
        _header(1, "Preface", "unnumbered"),
        _header(1, "PartOne"),
        _header(2, "Alpha"),
        _header(3, "AlphaSecOne"),
        _header(4, "AlphaSubOne"),
        _header(3, "AlphaSecTwo"),
        _header(2, "Beta"),
        _header(1, "PartTwo"),
        _header(3, "PartTwoOpening"),
        _header(2, "Gamma"),
        _header(3, "GammaSecOne"),
        _header(1, "Notes", "unnumbered"),
        _header(2, "NotesGroup", "unnumbered"),
        _header(3, "AfterNotes"),
    )


class TestRomanNumeral:
    """roman_numeral spells a positive integer in upper-case roman numerals."""

    @pytest.mark.parametrize(
        ("value", "expected"), [(1, "I"), (2, "II"), (4, "IV"), (9, "IX"), (14, "XIV"), (40, "XL"), (1994, "MCMXCIV")]
    )
    def test_spelling(self, value: int, expected: str) -> None:
        """The subtractive pairs (IV, IX, XL, CM) are used."""
        assert roman_numeral(value) == expected


class TestNumberPartsBookHeadings:
    """number_parts_book_headings numbers parts in roman, chapters straight through, sections under them."""

    def test_chicago_numbers(self) -> None:
        """Chapters continue across parts; sections carry their chapter; unnumbered headings take none."""
        doc: Final[pf.Doc] = _parts_book()
        number_parts_book_headings(doc)
        assert _numbers(doc) == {
            "Preface": None,
            "PartOne": "I",
            "Alpha": "1",
            "AlphaSecOne": "1.1",
            "AlphaSubOne": "1.1.1",
            "AlphaSecTwo": "1.2",
            "Beta": "2",
            "PartTwo": "II",
            "PartTwoOpening": None,
            "Gamma": "3",
            "GammaSecOne": "3.1",
            "Notes": None,
            "NotesGroup": None,
            "AfterNotes": None,
        }

    def test_headings_nested_in_divs_count_in_document_order(self) -> None:
        """A heading inside a Div is met where it stands in the document."""
        doc: Final[pf.Doc] = pf.Doc(
            _header(1, "PartOne"), pf.Div(_header(2, "Alpha")), _header(2, "Beta"), pf.Div(pf.Div(_header(2, "Gamma")))
        )
        number_parts_book_headings(doc)
        headers: Final[list[pf.Header]] = []
        doc.walk(lambda elem, _doc: headers.append(elem) if isinstance(elem, pf.Header) else None)
        assert [header.attributes.get(HEADING_NUMBER_ATTRIBUTE) for header in headers] == ["I", "1", "2", "3"]


class TestInsertHeadingNumberSpans:
    """insert_heading_number_spans displays each stamped number as a leading section-number span."""

    def test_span_leads_and_attribute_goes(self) -> None:
        """The number becomes a span and a space ahead of the text; the stamp attribute is removed."""
        doc: Final[pf.Doc] = pf.Doc(_header(1, "PartOne"), _header(2, "Alpha"), _header(1, "Notes", "unnumbered"))
        number_parts_book_headings(doc)
        insert_heading_number_spans(doc)
        part, chapter, notes = doc.content
        assert isinstance(part.content[0], pf.Span)
        assert part.content[0].classes == [HEADING_NUMBER_CLASS]
        assert pf.stringify(part) == "I PartOne"
        assert pf.stringify(chapter) == "1 Alpha"
        assert HEADING_NUMBER_ATTRIBUTE not in chapter.attributes
        assert pf.stringify(notes) == "Notes"


@pytest.mark.pandoc
class TestTypstHeadingNumberFilter:
    """typst_heading_number.lua writes a stamped heading as a Typst heading with a constant numbering."""

    @staticmethod
    def _typst(doc: pf.Doc) -> str:
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc), "typst", format="json", extra_args=[f"--lua-filter={_TYPST_HEADING_NUMBER_FILTER}"]
        )

    def test_stamped_heading_carries_its_number_and_label(self) -> None:
        """The chapter is a level-2 heading numbered 30, its text and label kept."""
        header: Final[pf.Header] = pf.Header(
            pf.Strong(pf.Str("Bark")), pf.Space(), pf.Str("Money"), level=2, identifier="vertex-chap00030"
        )
        header.attributes[HEADING_NUMBER_ATTRIBUTE] = "30"
        typst: Final[str] = self._typst(pf.Doc(header))
        assert '#heading(level: 2, numbering: (..nums) => "30")[#strong[Bark] Money]' in typst
        assert "<vertex-chap00030>" in typst

    def test_unstamped_heading_is_left_to_the_writer(self) -> None:
        """A heading without a number is written as Pandoc writes it."""
        typst: Final[str] = self._typst(pf.Doc(pf.Header(pf.Str("Notes"), level=1, classes=["unnumbered"])))
        assert "#heading(level: 1, numbering: none)[Notes]" in typst
