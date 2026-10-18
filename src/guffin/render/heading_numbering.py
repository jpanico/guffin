"""Heading numbers in a parts book, by the Chicago convention.

*The Chicago Manual of Style* numbers a book's chapters consecutively from the first to the last,
whatever parts group them, and numbers the parts on their own, so chapter 13 of Part II is
chapter 30 of a book whose Part I holds seventeen.  A section within a chapter carries the
chapter's number (30.1).  The writers number a parts book's headings as a hierarchy instead (2.13,
2.13.1), restarting the chapters in each part, so in a parts book Guffin numbers the headings
itself: one pass over the built document stamps each numbered heading with its number, which each
format then displays.  The same count numbers the floats, so a table in chapter 30 is Table 30.1.

A heading the build marks ``unnumbered`` (front and back matter, generated headings) takes no
number and counts for nothing; a part's number is a roman numeral, so it never reads as a
chapter's.

Public symbols:

- **Constants**: :data:`HEADING_NUMBER_ATTRIBUTE` — the attribute a numbered heading carries its
  number in; :data:`HEADING_NUMBER_CLASS` — the class of the span a heading's number is displayed
  in.
- **Functions**: :func:`roman_numeral` — a positive integer as an upper-case roman numeral;
  :func:`number_parts_book_headings` — stamp every numbered heading of a parts book with its
  number; :func:`insert_heading_number_spans` — display each stamped number as a span leading its
  heading's text.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so its symbols are typed as Unknown by pyright; the
# document edits below are plain panflute attribute writes.

from typing import Final

import panflute as pf  # type: ignore[import-untyped]
from pydantic import ConfigDict, PositiveInt, validate_call

HEADING_NUMBER_ATTRIBUTE: Final[str] = "data-guffin-heading-number"
"""The attribute a numbered heading carries its number in, as display text (``II``, ``30``, ``30.1``)."""

HEADING_NUMBER_CLASS: Final[str] = "header-section-number"
"""The class of the span a heading's number is displayed in: the class Pandoc gives its own numbers."""

_UNNUMBERED_CLASS: Final[str] = "unnumbered"

_ROMAN_NUMERALS: Final[tuple[tuple[int, str], ...]] = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


@validate_call
def roman_numeral(value: PositiveInt) -> str:
    """Return *value* as an upper-case roman numeral (``4`` → ``IV``).

    Args:
        value: The number to spell.

    Returns:
        The roman numeral.
    """
    remaining: int = value
    digits: Final[list[str]] = []
    for magnitude, numeral in _ROMAN_NUMERALS:
        count, remaining = divmod(remaining, magnitude)
        digits.append(numeral * count)
    return "".join(digits)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def number_parts_book_headings(doc: pf.Doc) -> None:
    """Stamp every numbered heading of the parts book *doc* with its Chicago number, in place.

    Headings are met in document order.  A level-1 heading is a part, numbered with a roman
    numeral; a level-2 heading is a chapter, numbered consecutively through the whole book; a
    deeper heading is a section of the chapter it follows, numbered under it (``30.1``,
    ``30.1.2``).  A heading classed ``unnumbered`` takes no number; a section under no numbered
    chapter — after a part's opening heading, or in front or back matter — takes none either.

    Args:
        doc: The built document of a book whose top-level division is the part.
    """
    parts: int = 0
    chapters: int = 0
    chapter: str | None = None
    sections: list[int] = []

    def _number(elem: pf.Element, _doc: pf.Doc) -> None:
        nonlocal parts, chapters, chapter, sections
        if not isinstance(elem, pf.Header):
            return
        numbered: Final[bool] = _UNNUMBERED_CLASS not in elem.classes
        if elem.level <= 2:
            chapter = None
            sections = []
        if not numbered:
            return
        if elem.level == 1:
            parts += 1
            elem.attributes[HEADING_NUMBER_ATTRIBUTE] = roman_numeral(parts)
            return
        if elem.level == 2:
            chapters += 1
            chapter = str(chapters)
            elem.attributes[HEADING_NUMBER_ATTRIBUTE] = chapter
            return
        if chapter is None:
            return
        depth: Final[int] = elem.level - 2
        sections = [*sections[:depth], *([0] * (depth - len(sections)))]
        sections[depth - 1] += 1
        elem.attributes[HEADING_NUMBER_ATTRIBUTE] = ".".join([chapter, *map(str, sections)])

    doc.walk(_number)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def insert_heading_number_spans(doc: pf.Doc) -> None:
    """Display each stamped heading number in *doc* as a span leading the heading's text, in place.

    Each heading carrying :data:`HEADING_NUMBER_ATTRIBUTE` loses the attribute and gains, ahead of
    its text, a :data:`HEADING_NUMBER_CLASS` span holding the number and a space — the markup a
    writer's own section numbering produces, so the number is styled alike.

    Args:
        doc: The document whose stamped headings to display.
    """

    def _display(elem: pf.Element, _doc: pf.Doc) -> None:
        if not isinstance(elem, pf.Header) or HEADING_NUMBER_ATTRIBUTE not in elem.attributes:
            return
        number: Final[str] = elem.attributes.pop(HEADING_NUMBER_ATTRIBUTE)
        elem.content = pf.ListContainer(
            pf.Span(pf.Str(number), classes=[HEADING_NUMBER_CLASS]), pf.Space(), *elem.content
        )

    doc.walk(_display)
