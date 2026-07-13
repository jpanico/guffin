"""Internal element numbering — the author-maintained logical ordering of a document's elements.

An internal element number is a bracketed, dot-separated marker leading a heading's text (first
text ignoring whitespace), e.g. ``[0.1]`` or ``[1.2.3]``.  It encodes the element's relative,
logical, hierarchical position in the document, independently of where the element actually sits
in the source hierarchy.  A fixed convention classifies the leading segment as the element's
:class:`~guffin.model.chicago_structure.Matter` division — ``0`` front-matter, ``1`` body-matter,
``2`` back-matter — so every number carries at least two segments: the matter classifier plus the
ordinal path within it (a bare ``[1]`` is not a well-formed element number).

Public symbols:

- **Pattern constants**: :data:`ELEMENT_NUMBER_PATTERN` / :data:`ELEMENT_NUMBER_RE` — a
  well-formed leading marker (two or more dot-separated integers, no leading zeros);
  :data:`ELEMENT_NUMBER_SHAPE_PATTERN` / :data:`ELEMENT_NUMBER_SHAPE_RE` — the looser
  *number-shaped* leading marker (bracketed digits and dots), matching both well-formed numbers
  and malformed attempts such as ``[1]`` or ``[1..2]``;
  :data:`ELEMENT_NUMBER_DOTTED_SHAPE_PATTERN` / :data:`ELEMENT_NUMBER_DOTTED_SHAPE_RE` — the
  number-shaped marker restricted to those containing a dot, the shape that reads distinctively as
  an element number in running text (a bare ``[1]`` is an ordinary footnote or citation label).
- **Constants**: :data:`MATTER_BY_LEADING_SEGMENT` — the fixed leading-segment →
  :class:`~guffin.model.chicago_structure.Matter` convention (the single source for the mapping).
- **Models**: :class:`ElementNumber` — an immutable, totally ordered element number.
- **Functions**: :func:`parse_element_number` — read a text's leading marker as an
  :class:`ElementNumber` (``None`` when the text does not lead with a well-formed marker);
  :func:`leads_with_element_number_shape` / :func:`leads_with_dotted_element_number_shape` —
  whether a text leads with a number-shaped (respectively dotted number-shaped) marker,
  well-formed or not.

Both patterns exempt non-marker bracket syntax: a ``[[page reference]]`` lead never matches
(its second character is ``[``), and a Markdown link lead such as ``[1](url)`` is excluded by a
negative lookahead for ``(``.  An unclosed bracket lead is ordinary text, not a marker.

Sits just above the structural taxonomy in the ``model/`` conceptual stack: it depends only on
:mod:`~guffin.model.chicago_structure`, and any vocabulary declared over the model may depend on it.
"""

from collections.abc import Mapping
from functools import total_ordering
from typing import Annotated, Final

import regex
from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.model.chicago_structure import Matter

_SEGMENT_PATTERN: Final[str] = r"(?:0|[1-9]\d*)"
"""One element-number segment: a non-negative integer with no leading zeros."""

ELEMENT_NUMBER_PATTERN: Final[str] = rf"^\s*\[(?P<segments>{_SEGMENT_PATTERN}(?:\.{_SEGMENT_PATTERN})+)\](?!\()"
"""A well-formed internal element number leading a text: ``[n.n(.n)*]``, two or more segments."""

ELEMENT_NUMBER_RE: Final[regex.Pattern[str]] = regex.compile(ELEMENT_NUMBER_PATTERN)
"""Compiled :data:`ELEMENT_NUMBER_PATTERN`."""

ELEMENT_NUMBER_SHAPE_PATTERN: Final[str] = r"^\s*\[[0-9.]+\](?!\()"
"""A number-*shaped* marker leading a text: a bracket containing only digits and dots.

Matches every well-formed element number and every malformed attempt (``[1]``, ``[1..2]``,
``[01.2]``), so a consumer can distinguish "attempted an element number" from "ordinary text".
"""

ELEMENT_NUMBER_SHAPE_RE: Final[regex.Pattern[str]] = regex.compile(ELEMENT_NUMBER_SHAPE_PATTERN)
"""Compiled :data:`ELEMENT_NUMBER_SHAPE_PATTERN`."""

ELEMENT_NUMBER_DOTTED_SHAPE_PATTERN: Final[str] = r"^\s*\[(?=[0-9.]*\.)[0-9.]+\](?!\()"
"""A *dotted* number-shaped marker leading a text: :data:`ELEMENT_NUMBER_SHAPE_PATTERN` with ≥ 1 dot.

The dot is what makes a bracketed number distinctively an element number: a bare bracketed
integer (``[1]``) is ordinary prose in running text — a footnote or citation label — and only the
dotted form (``[1.2]``, ``[1..2]``, ``[.1]``) reads as an element-number occurrence.
"""

ELEMENT_NUMBER_DOTTED_SHAPE_RE: Final[regex.Pattern[str]] = regex.compile(ELEMENT_NUMBER_DOTTED_SHAPE_PATTERN)
"""Compiled :data:`ELEMENT_NUMBER_DOTTED_SHAPE_PATTERN`."""

MATTER_BY_LEADING_SEGMENT: Final[Mapping[int, Matter]] = {
    0: Matter.FRONT,
    1: Matter.BODY,
    2: Matter.BACK,
}
"""The fixed convention classifying an element number's leading segment as a :class:`Matter` division."""


@total_ordering
class ElementNumber(BaseModel):
    """An internal element number: the dot-separated integer path of one document element.

    Immutable and totally ordered by numeric tuple comparison of :attr:`segments` — the order of
    the elements the numbers denote — so ``[1.2] < [1.2.1] < [1.10]`` (numeric, not textual).
    Equality is segment equality.

    Attributes:
        segments: The number's integer segments, in marker order.  At least two: the leading
            matter classifier plus the ordinal path within it.
    """

    model_config = ConfigDict(frozen=True)

    segments: tuple[Annotated[int, Field(ge=0)], ...] = Field(min_length=2)

    @property
    def matter(self) -> Matter | None:
        """The :class:`Matter` division the leading segment classifies, or ``None`` when illegal.

        Resolved through :data:`MATTER_BY_LEADING_SEGMENT`; a leading segment outside the
        convention (3 or greater) has no matter.
        """
        return MATTER_BY_LEADING_SEGMENT.get(self.segments[0])

    def is_prefix_of(self, other: ElementNumber) -> bool:
        """Return whether this number is a strict prefix of *other*.

        ``[1.2]`` is a strict prefix of ``[1.2.3]`` but not of itself or of ``[1.20]``.

        No ``@validate_call``: pydantic evaluates the decorated hints at decoration time, before
        ``ElementNumber`` is added to module globals, raising ``NameError``.

        Args:
            other: The number to test against.

        Returns:
            ``True`` when *other* extends this number by one or more segments.
        """
        return len(self.segments) < len(other.segments) and other.segments[: len(self.segments)] == self.segments

    def __lt__(self, other: ElementNumber) -> bool:
        """Return whether this number orders strictly before *other* (numeric tuple comparison)."""
        return self.segments < other.segments

    def __str__(self) -> str:
        """Return the dotted form without brackets, e.g. ``1.2.3``."""
        return ".".join(str(segment) for segment in self.segments)


@validate_call
def parse_element_number(text: str) -> ElementNumber | None:
    """Return the :class:`ElementNumber` leading *text*, or ``None`` when there is none.

    A marker must match :data:`ELEMENT_NUMBER_RE`: first text ignoring whitespace, bracketed,
    two or more dot-separated integers with no leading zeros.  A malformed number-shaped lead
    (e.g. ``[1]`` or ``[1..2]``) also returns ``None`` — use
    :func:`leads_with_element_number_shape` to distinguish it from ordinary text.

    Args:
        text: The text whose lead to parse (typically a heading's text).

    Returns:
        The parsed :class:`ElementNumber`, or ``None`` when *text* does not lead with a
        well-formed marker.
    """
    match: Final[regex.Match[str] | None] = ELEMENT_NUMBER_RE.match(text)
    if match is None:
        return None
    return ElementNumber(segments=tuple(int(segment) for segment in match.group("segments").split(".")))


@validate_call
def leads_with_element_number_shape(text: str) -> bool:
    """Return whether *text* leads with a number-shaped marker, well-formed or not.

    Matches :data:`ELEMENT_NUMBER_SHAPE_RE`: a leading bracket containing only digits and dots.
    Together with :func:`parse_element_number` this separates three cases — a well-formed number
    (both succeed), a malformed attempt (shape only), and ordinary text (neither).

    Args:
        text: The text whose lead to test.

    Returns:
        ``True`` when *text* leads with a number-shaped marker.
    """
    return ELEMENT_NUMBER_SHAPE_RE.match(text) is not None


@validate_call
def leads_with_dotted_element_number_shape(text: str) -> bool:
    """Return whether *text* leads with a *dotted* number-shaped marker, well-formed or not.

    Matches :data:`ELEMENT_NUMBER_DOTTED_SHAPE_RE`: like
    :func:`leads_with_element_number_shape`, but the marker must contain at least one dot — the
    shape that reads distinctively as an element number in running text, where a bare bracketed
    integer (``[1]``) is an ordinary footnote or citation label.

    Args:
        text: The text whose lead to test.

    Returns:
        ``True`` when *text* leads with a dotted number-shaped marker.
    """
    return ELEMENT_NUMBER_DOTTED_SHAPE_RE.match(text) is not None
