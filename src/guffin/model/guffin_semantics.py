"""Guffin's own attribute vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Enumerations**: :class:`GuffinSemantics` — the attributes Guffin recognizes (document metadata +
  the ``element-type`` heading tag), each member a :class:`GuffinAttribute` in the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`
  domain; :class:`Anchor` — the kind of vertex a Guffin attribute attaches to (page / heading), each
  carrying its :class:`~guffin.model.vertex.VertexType`; :class:`Matter` —
  the book division a part belongs to (front / body / back); :class:`StructuralElement` — a book's
  structural elements by name, each carrying its :class:`Matter` division (its organizational parts).
- **Models**: :class:`GuffinAttribute` — an :class:`~guffin.model.attribute.Attribute` pinned to the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain and carrying a :class:`Anchor`.
- **Functions**: :func:`element_type_of` — read an ``element-type`` assignment's value as a
  :class:`StructuralElement` (raising if it is not one); :func:`matter_of` — read a ``matter``
  assignment's value as a :class:`Matter`; :func:`find_guffin_attribute` — find a vertex's
  assignment for a :class:`GuffinSemantics` attribute (the Guffin domain supplied automatically);
  :func:`has_parts` — return whether a :class:`~guffin.model.vertex_tree.VertexTree` structures its
  top level as parts (any level-1 heading tagged ``element-type:: part``);
  the :data:`~guffin.common.validation.Validator` functions :func:`all_attributes_anchored`
  (every recognised guffin attribute sits on its :class:`Anchor`'s vertex type),
  :func:`all_element_type_values_legal` (every ``element-type`` value is a
  :class:`StructuralElement`), :func:`all_matter_values_legal` (every ``matter`` value is a
  :class:`Matter`), and :func:`all_matter_tags_level_1` (every ``matter`` tag sits on a level-1
  heading); :func:`validate_semantics` — run every vocabulary validator over a
  :class:`~guffin.model.vertex_tree.VertexTree`, accumulating a
  :class:`~guffin.common.validation.ValidationResult`.

This module sits at the top of the ``model/`` conceptual stack: it may depend on the structural
primitives (:mod:`~guffin.model.attribute`, :mod:`~guffin.model.vertex`,
:mod:`~guffin.model.vertex_tree`), and none of them may depend on it.
"""

import enum
import logging
from collections.abc import Callable, Iterator
from itertools import chain
from typing import Final, Self

from pydantic import Field, field_validator, validate_call

from guffin.common.validation import ValidationError, ValidationResult, validate_all
from guffin.model.attribute import Attribute, AttributeAssignment, AttributeDomain, sole_value_text
from guffin.model.vertex import HeadingVertex, Vertex, VertexType, find_attribute_assignment
from guffin.model.vertex_tree import VertexTree, heading_vertices

logger = logging.getLogger(__name__)


class Anchor(enum.StrEnum):
    """The kind of vertex a Guffin attribute attaches to.

    Each member carries the :class:`~guffin.model.vertex.VertexType` it corresponds to — the type
    of vertex an attribute with this anchor may be declared on.

    Attributes:
        vertex_type: The :class:`~guffin.model.vertex.VertexType` this anchor corresponds to.
        PAGE: The attribute attaches to a page vertex (the whole document).
        HEADING: The attribute attaches to a heading vertex (a section).
    """

    def __new__(cls, value: str, vertex_type: VertexType) -> Self:
        """Create a member whose string value is *value* and that carries *vertex_type*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.vertex_type = vertex_type
        return member

    vertex_type: VertexType

    PAGE = ("page", VertexType.PAGE)
    HEADING = ("heading", VertexType.HEADING)


class Matter(enum.StrEnum):
    """A top-level division of a book — the publishing-standard grouping its parts belong to.

    Attributes:
        FRONT: Front matter — material preceding the main text (title page, foreword, preface, …).
        BODY: Body matter — the main text (parts, chapters).
        BACK: Back matter — material following the main text (appendices, glossary, colophon, …).
    """

    FRONT = "front-matter"
    BODY = "body-matter"
    BACK = "back-matter"


class GuffinAttribute(Attribute):
    """A Guffin-domain :class:`~guffin.model.attribute.Attribute` that also carries a :class:`Anchor`.

    Specializes :class:`~guffin.model.attribute.Attribute` by pinning :attr:`domain` to
    :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` (any other value is rejected) and adding a
    required :attr:`anchor`.

    Attributes:
        domain: Always :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`.
        anchor: The kind of vertex this attribute attaches to.
    """

    domain: AttributeDomain = Field(default=AttributeDomain.GUFFIN, description="Always the guffin domain.")
    anchor: Anchor = Field(..., description="The kind of vertex this attribute attaches to.")

    @field_validator("domain")
    @classmethod
    def _domain_must_be_guffin(cls, value: AttributeDomain) -> AttributeDomain:
        """Reject any domain other than :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`."""
        if value is not AttributeDomain.GUFFIN:
            raise ValueError(f"GuffinAttribute.domain is fixed to {AttributeDomain.GUFFIN!r}, got {value!r}")
        return value


class GuffinSemantics(enum.Enum):
    """The attributes Guffin recognizes, each a :class:`GuffinAttribute`.

    Each member's value is the :class:`GuffinAttribute` for that attribute.  Two kinds:

    - **Document metadata** (:attr:`Anchor.PAGE`) — bibliographic facts about the work as a whole:
      :attr:`TITLE`, :attr:`SUBTITLE`, :attr:`AUTHORS`, :attr:`DATE`, :attr:`PUBLISHER`,
      :attr:`RIGHTS`, :attr:`IDENTIFIER`.
    - **Heading tags** (:attr:`Anchor.HEADING`) — applied to an individual heading: :attr:`ELEMENT_TYPE`
      declares which :class:`StructuralElement` the heading is; :attr:`MATTER` declares its
      :class:`Matter` division directly, for a bespoke section with no specific element type.

    Attributes:
        TITLE: The document title.
        SUBTITLE: The document subtitle.
        AUTHORS: The document author(s).
        DATE: The document date.
        PUBLISHER: The publisher of the work.
        RIGHTS: The rights statement for the work (e.g. a copyright line).
        IDENTIFIER: The document identifier.
        ELEMENT_TYPE: Tags a heading with its :class:`StructuralElement` (the book part it is).
        MATTER: Tags a heading with its :class:`Matter` division (for a section with no element type).
    """

    _value_: GuffinAttribute

    TITLE = GuffinAttribute(name="title", anchor=Anchor.PAGE)
    SUBTITLE = GuffinAttribute(name="subtitle", anchor=Anchor.PAGE)
    AUTHORS = GuffinAttribute(name="authors", anchor=Anchor.PAGE)
    DATE = GuffinAttribute(name="date", anchor=Anchor.PAGE)
    PUBLISHER = GuffinAttribute(name="publisher", anchor=Anchor.PAGE)
    RIGHTS = GuffinAttribute(name="rights", anchor=Anchor.PAGE)
    IDENTIFIER = GuffinAttribute(name="identifier", anchor=Anchor.PAGE)
    ELEMENT_TYPE = GuffinAttribute(name="element-type", anchor=Anchor.HEADING)
    MATTER = GuffinAttribute(name="matter", anchor=Anchor.HEADING)


class StructuralElement(enum.StrEnum):
    """The structural elements of a book — its organizational parts, each in a :class:`Matter` division.

    The reusable section types an author tags a heading with, from :attr:`TITLE_PAGE` through
    :attr:`COLOPHON` — title page, foreword, preface, parts and chapters, appendices, glossary, index,
    colophon, and so on.  Member names follow publishing conventions; each member's value is that name,
    and :attr:`matter` is the front/body/back-matter division it conventionally belongs to.

    :attr:`matter` is aligned with the Chicago Manual of Style (CMOS), the de facto US book-publishing
    standard — this is the *conventional* placement, independent of any output format.  How a specific
    format's toolchain happens to divide these parts is a separate, format-specific concern resolved
    where that format is rendered.

    Only the book's **interior** is classified by matter, so there is no ``cover`` member: per CMOS the
    cover (and jacket) is the exterior, outside the front/body/back-matter division.  In practice a
    cover is supplied as document metadata / a cover image, not authored as a tagged content section.

    Attributes:
        matter: The :class:`Matter` division this element conventionally belongs to, per CMOS.
    """

    def __new__(cls, value: str, matter: Matter) -> Self:
        """Create a member whose string value is *value* and that carries *matter*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.matter = matter
        return member

    matter: Matter

    TITLE_PAGE = ("title-page", Matter.FRONT)
    COPYRIGHT_PAGE = ("copyright-page", Matter.FRONT)
    EPIGRAPH = ("epigraph", Matter.FRONT)
    ACKNOWLEDGMENTS = ("acknowledgments", Matter.FRONT)
    FOREWORD = ("foreword", Matter.FRONT)
    PREFACE = ("preface", Matter.FRONT)
    INTRODUCTION = ("introduction", Matter.FRONT)
    TABLE_OF_CONTENTS = ("table-of-contents", Matter.FRONT)
    LIST_OF_ILLUSTRATIONS = ("list-of-illustrations", Matter.FRONT)
    PROLOGUE = ("prologue", Matter.BODY)
    PART = ("part", Matter.BODY)
    CHAPTER = ("chapter", Matter.BODY)
    SECTION = ("section", Matter.BODY)
    SUB_SECTION = ("sub-section", Matter.BODY)
    SUB_SUB_SECTION = ("sub-sub-section", Matter.BODY)
    # Conclusion and epilogue close the text proper (per CMOS): end of the body matter, not back
    # matter.  An afterword, being commentary *about* the text, opens the back matter instead.
    CONCLUSION = ("conclusion", Matter.BODY)
    EPILOGUE = ("epilogue", Matter.BODY)
    AFTERWORD = ("afterword", Matter.BACK)
    APPENDIX = ("appendix", Matter.BACK)
    GLOSSARY = ("glossary", Matter.BACK)
    ENDNOTES = ("endnotes", Matter.BACK)
    BIBLIOGRAPHY = ("bibliography", Matter.BACK)
    INDEX = ("index", Matter.BACK)
    ABOUT_THE_AUTHOR = ("about-the-author", Matter.BACK)
    COLOPHON = ("colophon", Matter.BACK)


def _is_assignment_for(assignment: AttributeAssignment, attribute: GuffinSemantics) -> bool:
    """Return whether *assignment* is for the Guffin *attribute* (by name and domain).

    Args:
        assignment: The attribute assignment to test.
        attribute: The :class:`GuffinSemantics` member to match against.

    Returns:
        ``True`` when the assignment's attribute name and domain equal the member's
        :class:`GuffinAttribute`, else ``False``.
    """
    expected: Final[GuffinAttribute] = attribute.value
    assignment_attribute: Final[Attribute] = assignment.attribute.definition
    return assignment_attribute.name == expected.name and assignment_attribute.domain == expected.domain


def _verified_sole_value(assignment: AttributeAssignment, attribute: GuffinSemantics) -> str:
    """Verify *assignment* is for the Guffin *attribute* and return its sole value's text.

    Args:
        assignment: The attribute assignment to verify (one value expected).
        attribute: The :class:`GuffinSemantics` member the assignment must be for.

    Returns:
        The text of the assignment's sole value.

    Raises:
        ValueError: If *assignment* is not for *attribute* (by name and domain), or does not carry
            exactly one value.
    """
    if not _is_assignment_for(assignment, attribute):
        expected: Final[GuffinAttribute] = attribute.value
        assignment_attribute: Final[Attribute] = assignment.attribute.definition
        raise ValueError(
            f"expected an assignment of {expected.name!r} in the {expected.domain} domain, "
            f"got {assignment_attribute.name!r} in {assignment_attribute.domain}"
        )
    return sole_value_text(assignment)


@validate_call
def element_type_of(assignment: AttributeAssignment) -> StructuralElement:
    """Return the :class:`StructuralElement` that an ``element-type`` assignment names.

    Verifies *assignment* is for the :attr:`GuffinSemantics.ELEMENT_TYPE` attribute, then coerces its
    sole value to a :class:`StructuralElement` — the authoritative set of legal ``element-type`` values.

    Args:
        assignment: An :attr:`GuffinSemantics.ELEMENT_TYPE` attribute assignment (one value expected).

    Returns:
        The named :class:`StructuralElement`.

    Raises:
        ValueError: If *assignment* is not for the ``element-type`` attribute, does not carry exactly
            one value, or its value is not a recognised :class:`StructuralElement`.
    """
    return StructuralElement(_verified_sole_value(assignment, GuffinSemantics.ELEMENT_TYPE))


@validate_call
def matter_of(assignment: AttributeAssignment) -> Matter:
    """Return the :class:`Matter` that a ``matter`` assignment names.

    Verifies *assignment* is for the :attr:`GuffinSemantics.MATTER` attribute, then coerces its sole
    value to a :class:`Matter` (``front-matter`` / ``body-matter`` / ``back-matter``).

    Args:
        assignment: A :attr:`GuffinSemantics.MATTER` attribute assignment (one value expected).

    Returns:
        The named :class:`Matter`.

    Raises:
        ValueError: If *assignment* is not for the ``matter`` attribute, does not carry exactly one
            value, or its value is not a recognised :class:`Matter`.
    """
    return Matter(_verified_sole_value(assignment, GuffinSemantics.MATTER))


@validate_call
def find_guffin_attribute(vertex: Vertex, attribute: GuffinSemantics) -> AttributeAssignment | None:
    """Return *vertex*'s assignment for the Guffin *attribute*, or ``None``.

    Convenience over :func:`~guffin.model.vertex.find_attribute_assignment` that reads the name and
    domain from the member's :class:`GuffinAttribute`, so callers neither restate nor risk
    mismatching them.

    Args:
        vertex: The vertex whose folded attribute assignments are searched.
        attribute: The Guffin attribute to look up.

    Returns:
        The matching :class:`~guffin.model.attribute.AttributeAssignment`, or ``None`` when *vertex*
        has no such Guffin attribute.
    """
    return find_attribute_assignment(vertex, attribute.value.name, attribute.value.domain)


def _is_part_heading(heading: HeadingVertex) -> bool:
    """Return whether *heading* is a level-1 heading tagged ``element-type:: part``.

    An assignment whose value is not a recognised :class:`StructuralElement` is ignored with a
    warning.

    Args:
        heading: The heading vertex to check.

    Returns:
        ``True`` when *heading* declares itself a part, else ``False``.
    """
    if heading.heading_level != 1:
        return False
    assignment: Final[AttributeAssignment | None] = find_guffin_attribute(heading, GuffinSemantics.ELEMENT_TYPE)
    if assignment is None:
        return False
    try:
        element: Final[StructuralElement] = element_type_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring element-type on vertex uid=%r: %s", heading.uid, exc)
        return False
    return element is StructuralElement.PART


@validate_call
def has_parts(tree: VertexTree) -> bool:
    """Return whether *tree* structures its top level as parts.

    ``True`` when any level-1 :class:`~guffin.model.vertex.HeadingVertex` carries an
    ``element-type`` assignment naming :attr:`StructuralElement.PART` — the content's own
    declaration that its level-1 headings are parts (so its chapters live at level 2).
    Assignments whose value is not a recognised :class:`StructuralElement` are ignored with a
    warning.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to inspect.

    Returns:
        ``True`` when a level-1 heading is tagged as a part, else ``False``.
    """
    return any(_is_part_heading(heading) for heading in heading_vertices(tree))


_SEMANTICS_BY_NAME: Final[dict[str, GuffinSemantics]] = {member.value.name: member for member in GuffinSemantics}
"""Maps each recognised guffin attribute name to its :class:`GuffinSemantics` member."""


def _anchor_violation(vertex: Vertex, assignment: AttributeAssignment) -> str | None:
    """Describe how *assignment* violates the anchor invariant on *vertex*, or ``None``.

    ``None`` when *assignment* is outside the vocabulary (non-guffin domain, or a name matching no
    :class:`GuffinSemantics` member) or when it sits on its anchor's vertex type; otherwise a
    description naming the attribute, its expected anchor, the actual vertex type, and the vertex
    uid.

    Args:
        vertex: The vertex the assignment is declared on.
        assignment: The attribute assignment to check.

    Returns:
        The violation description, or ``None`` when there is no violation.
    """
    assignment_attribute: Final[Attribute] = assignment.attribute.definition
    if assignment_attribute.domain is not AttributeDomain.GUFFIN:
        return None
    member: Final[GuffinSemantics | None] = _SEMANTICS_BY_NAME.get(assignment_attribute.name)
    if member is None:
        return None
    anchor: Final[Anchor] = member.value.anchor
    if vertex.vertex_type is anchor.vertex_type:
        return None
    return (
        f"{assignment_attribute.name!r} is {anchor.value}-anchored but declared on a "
        f"{vertex.vertex_type.value!r} vertex (uid={vertex.uid!r})"
    )


@validate_call
def all_attributes_anchored(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every guffin attribute to sit on its anchor.

    Each :class:`GuffinSemantics` member's :class:`GuffinAttribute` carries an :class:`Anchor`
    naming the :class:`~guffin.model.vertex.VertexType` it attaches to; this validator enforces
    that invariant across *tree* — both its tree vertices and its referenced-vertex stubs
    (:attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`): every guffin-domain assignment
    whose name is a recognised member must be declared on a vertex of the anchor's type.
    Default-domain assignments and unrecognised guffin-domain names are outside the vocabulary and
    pass through unchecked.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every recognised guffin attribute is correctly anchored; a
        :class:`~guffin.common.validation.ValidationError` listing every misanchored assignment
        (attribute name, expected anchor, actual vertex type, and vertex uid) otherwise.
    """
    violations: Final[list[str]] = [
        violation
        for vertex in chain(tree.tree_vertices, tree.ref_vertices)
        for assignment in vertex.attribute_assignments or ()
        if (violation := _anchor_violation(vertex, assignment)) is not None
    ]
    if not violations:
        return None
    return ValidationError(
        message="misanchored guffin attributes: " + "; ".join(violations),
        validator=all_attributes_anchored,
    )


def _tagged_assignments(tree: VertexTree, attribute: GuffinSemantics) -> Iterator[tuple[Vertex, AttributeAssignment]]:
    """Return every ``(vertex, assignment)`` pair in *tree* whose assignment is for *attribute*.

    An assignment matches when its name and domain equal the member's :class:`GuffinAttribute`.
    Both the tree vertices and the referenced-vertex stubs
    (:attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`) are walked.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to walk.
        attribute: The Guffin attribute whose assignments to return.

    Returns:
        A lazy iterator of each matching assignment, paired with the vertex it is declared on.
    """
    return (
        (vertex, assignment)
        for vertex in chain(tree.tree_vertices, tree.ref_vertices)
        for assignment in vertex.attribute_assignments or ()
        if _is_assignment_for(assignment, attribute)
    )


def _illegal_value_violations(
    tree: VertexTree,
    attribute: GuffinSemantics,
    value_coercer: Callable[[AttributeAssignment], StructuralElement | Matter],
) -> list[str]:
    """Collect a violation description for each *attribute* assignment in *tree* that *value_coercer* rejects.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to walk.
        attribute: The Guffin attribute whose assignments to check.
        value_coercer: The value coercer for the attribute (e.g. :func:`element_type_of`); a
            :exc:`ValueError` from it marks the assignment as a violation.

    Returns:
        One description per rejected assignment (the vertex uid and the coercion error); empty
        when every assignment coerces.
    """
    violations: Final[list[str]] = []
    for vertex, assignment in _tagged_assignments(tree, attribute):
        try:
            value_coercer(assignment)
        except ValueError as exc:
            violations.append(f"on vertex uid={vertex.uid!r}: {exc}")
    return violations


@validate_call
def all_element_type_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``element-type`` values.

    Every :attr:`GuffinSemantics.ELEMENT_TYPE` assignment in *tree* must carry exactly one value,
    and that value must name a :class:`StructuralElement` member — the authoritative set of legal
    ``element-type`` values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``element-type`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, GuffinSemantics.ELEMENT_TYPE, element_type_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal element-type values: " + "; ".join(violations),
        validator=all_element_type_values_legal,
    )


@validate_call
def all_matter_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``matter`` values.

    Every :attr:`GuffinSemantics.MATTER` assignment in *tree* must carry exactly one value, and
    that value must name a :class:`Matter` member — the authoritative set of legal ``matter``
    values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``matter`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, GuffinSemantics.MATTER, matter_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal matter values: " + "; ".join(violations),
        validator=all_matter_values_legal,
    )


@validate_call
def all_matter_tags_level_1(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every ``matter`` tag to sit on a level-1 heading.

    A ``matter`` tag declares a heading's top-level book division, so it applies to level-1
    headings only.  Non-heading hosts are not this validator's concern — they are already
    reported by :func:`all_attributes_anchored`.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``matter`` tag sits on a level-1 heading; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = [
        f"'matter' tag on a level-{vertex.heading_level} heading (uid={vertex.uid!r}); "
        "'matter' applies to level-1 headings only"
        for vertex, _assignment in _tagged_assignments(tree, GuffinSemantics.MATTER)
        if isinstance(vertex, HeadingVertex) and vertex.heading_level != 1
    ]
    if not violations:
        return None
    return ValidationError(
        message="misplaced matter tags: " + "; ".join(violations),
        validator=all_matter_tags_level_1,
    )


@validate_call
def validate_semantics(tree: VertexTree) -> ValidationResult:
    """Return a :class:`~guffin.common.validation.ValidationResult` for the vocabulary invariants on *tree*.

    Runs every vocabulary validator — :func:`all_attributes_anchored`,
    :func:`all_element_type_values_legal`, :func:`all_matter_values_legal`, and
    :func:`all_matter_tags_level_1` — via :func:`~guffin.common.validation.validate_all`.  Every
    validator covers both the tree vertices and the referenced-vertex stubs
    (:attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`).  All validators run regardless of
    prior failures; the result accumulates every error found.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        A :class:`~guffin.common.validation.ValidationResult` that is valid when *tree* satisfies
        every vocabulary invariant, or contains one
        :class:`~guffin.common.validation.ValidationError` per failed validator otherwise.
    """
    return validate_all(
        tree,
        [
            all_attributes_anchored,
            all_element_type_values_legal,
            all_matter_values_legal,
            all_matter_tags_level_1,
        ],
    )
