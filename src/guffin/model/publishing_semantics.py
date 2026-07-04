"""The publishing-semantics vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Constants**: :data:`DEFAULT_PDF_RENDER` — the :class:`PdfRender` placement of an untagged
  PDF embed.
- **Enumerations**: :class:`PublishingSemantics` — the attributes Guffin recognizes (document metadata +
  the ``element-type``/``matter`` heading tags + the ``pdf-render`` PDF tag), each member a
  :class:`PublishingAttribute` in the :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`
  domain; :class:`Anchor` — the kind of vertex a Guffin attribute attaches to (page / heading / pdf),
  each carrying its :class:`~guffin.model.vertex.VertexType`; :class:`Matter` —
  the book division a part belongs to (front / body / back); :class:`StructuralElement` — a book's
  structural elements by name, each carrying its :class:`Matter` division (its organizational parts);
  :class:`PdfRender` — how an embedded PDF asset is placed in paginated output (inline / link).
- **Models**: :class:`PublishingAttribute` — an :class:`~guffin.model.attribute.Attribute` pinned to the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain and carrying a :class:`Anchor`.
- **Functions**: :func:`element_type_of` — read an ``element-type`` assignment's value as a
  :class:`StructuralElement` (raising if it is not one); :func:`matter_of` — read a ``matter``
  assignment's value as a :class:`Matter`; :func:`pdf_render_of` — read a ``pdf-render``
  assignment's value as a :class:`PdfRender`; :func:`find_publishing_attribute` — find a vertex's
  assignment for a :class:`PublishingSemantics` attribute (the Guffin domain supplied automatically);
  :func:`element_type_of_vertex` / :func:`matter_of_vertex` / :func:`pdf_render_of_vertex` —
  resolve a heading's ``element-type`` / bare ``matter`` tag, or a PDF embed's ``pdf-render`` tag,
  to its enum member, tolerating absent or illegal assignments (``None``,
  warning); :func:`resolved_matter` — a heading's resolved :class:`Matter` division (a bare
  ``matter`` tag overrides the element's conventional placement, logging any disagreement);
  :func:`has_parts` — return whether a :class:`~guffin.model.vertex_tree.VertexTree` structures its
  top level as parts (any render-visible level-1 heading — block-embed-transcluded headings
  included — tagged ``element-type:: part``);
  the :data:`~guffin.common.validation.Validator` functions :func:`all_attributes_anchored`
  (every recognised guffin attribute sits on its :class:`Anchor`'s vertex type),
  :func:`all_element_type_values_legal` (every ``element-type`` value is a
  :class:`StructuralElement`), :func:`all_matter_values_legal` (every ``matter`` value is a
  :class:`Matter`), :func:`all_pdf_render_values_legal` (every ``pdf-render`` value is a
  :class:`PdfRender`), and :func:`all_matter_tags_at_section_level` (every ``matter`` tag sits at
  the book's section level — level 1, or level 2 in a parts book);
  :func:`validate_semantics` — run every vocabulary validator over a
  :class:`~guffin.model.vertex_tree.VertexTree`, accumulating a
  :class:`~guffin.common.validation.ValidationResult`.

This module sits at the top of the ``model/`` conceptual stack: it may depend on the structural
primitives (:mod:`~guffin.model.attribute`, :mod:`~guffin.model.vertex`,
:mod:`~guffin.model.vertex_tree`), and none of them may depend on it.
"""

import enum
import logging
from collections.abc import Callable
from itertools import chain
from typing import Final, Self

from pydantic import ConfigDict, Field, field_validator, validate_call

from guffin.common.validation import ValidationError, ValidationResult, validate_all
from guffin.model.attribute import (
    Attribute,
    AttributeAssignment,
    AttributeDomain,
    verified_sole_value_text,
)
from guffin.model.vertex import HeadingVertex, PdfVertex, Vertex, VertexType, find_attribute_assignment
from guffin.model.vertex_tree import VertexTree, assignments_for, transcluded_vertices

logger = logging.getLogger(__name__)


class Anchor(enum.StrEnum):
    """The kind of vertex a Guffin attribute attaches to.

    Each member carries the :class:`~guffin.model.vertex.VertexType` it corresponds to — the type
    of vertex an attribute with this anchor may be declared on.

    Attributes:
        vertex_type: The :class:`~guffin.model.vertex.VertexType` this anchor corresponds to.
        PAGE: The attribute attaches to a page vertex (the whole document).
        HEADING: The attribute attaches to a heading vertex (a section).
        PDF: The attribute attaches to a PDF vertex (an embedded PDF asset).
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
    PDF = ("pdf", VertexType.PDF)


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


class PdfRender(enum.StrEnum):
    """How an embedded PDF asset is placed in paginated output — the values a ``pdf-render`` tag takes.

    Attributes:
        INLINE: Every page of the PDF renders in the document flow, in place of the embed.
        LINK: The PDF is represented by a hyperlink (the untagged default,
            :data:`DEFAULT_PDF_RENDER`).
    """

    INLINE = "inline"
    LINK = "link"


DEFAULT_PDF_RENDER: Final[PdfRender] = PdfRender.LINK
"""The :class:`PdfRender` placement of a PDF embed carrying no ``pdf-render`` tag."""


class PublishingAttribute(Attribute):
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
            raise ValueError(f"PublishingAttribute.domain is fixed to {AttributeDomain.GUFFIN!r}, got {value!r}")
        return value


class PublishingSemantics(enum.Enum):
    """The attributes Guffin recognizes, each a :class:`PublishingAttribute`.

    Each member's value is the :class:`PublishingAttribute` for that attribute.  Three kinds:

    - **Document metadata** (:attr:`Anchor.PAGE`) — bibliographic facts about the work as a whole:
      :attr:`TITLE`, :attr:`SUBTITLE`, :attr:`AUTHORS`, :attr:`DATE`, :attr:`PUBLISHER`,
      :attr:`RIGHTS`, :attr:`IDENTIFIER`.
    - **Heading tags** (:attr:`Anchor.HEADING`) — applied to an individual heading: :attr:`ELEMENT_TYPE`
      declares which :class:`StructuralElement` the heading is; :attr:`MATTER` declares its
      :class:`Matter` division directly, for a bespoke section with no specific element type.
    - **PDF tags** (:attr:`Anchor.PDF`) — applied to an individual embedded PDF asset:
      :attr:`PDF_RENDER` declares its :class:`PdfRender` placement in paginated output.

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
        PDF_RENDER: Tags an embedded PDF with its :class:`PdfRender` placement (inline pages vs a link).
    """

    _value_: PublishingAttribute

    TITLE = PublishingAttribute(name="title", anchor=Anchor.PAGE)
    SUBTITLE = PublishingAttribute(name="subtitle", anchor=Anchor.PAGE)
    AUTHORS = PublishingAttribute(name="authors", anchor=Anchor.PAGE)
    DATE = PublishingAttribute(name="date", anchor=Anchor.PAGE)
    PUBLISHER = PublishingAttribute(name="publisher", anchor=Anchor.PAGE)
    RIGHTS = PublishingAttribute(name="rights", anchor=Anchor.PAGE)
    IDENTIFIER = PublishingAttribute(name="identifier", anchor=Anchor.PAGE)
    ELEMENT_TYPE = PublishingAttribute(name="element-type", anchor=Anchor.HEADING)
    MATTER = PublishingAttribute(name="matter", anchor=Anchor.HEADING)
    PDF_RENDER = PublishingAttribute(name="pdf-render", anchor=Anchor.PDF)


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


@validate_call
def element_type_of(assignment: AttributeAssignment) -> StructuralElement:
    """Return the :class:`StructuralElement` that an ``element-type`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.ELEMENT_TYPE` attribute, then coerces its
    sole value to a :class:`StructuralElement` — the authoritative set of legal ``element-type`` values.

    Args:
        assignment: An :attr:`PublishingSemantics.ELEMENT_TYPE` attribute assignment (one value expected).

    Returns:
        The named :class:`StructuralElement`.

    Raises:
        ValueError: If *assignment* is not for the ``element-type`` attribute, does not carry exactly
            one value, or its value is not a recognised :class:`StructuralElement`.
    """
    return StructuralElement(verified_sole_value_text(assignment, PublishingSemantics.ELEMENT_TYPE.value))


@validate_call
def matter_of(assignment: AttributeAssignment) -> Matter:
    """Return the :class:`Matter` that a ``matter`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.MATTER` attribute, then coerces its sole
    value to a :class:`Matter` (``front-matter`` / ``body-matter`` / ``back-matter``).

    Args:
        assignment: A :attr:`PublishingSemantics.MATTER` attribute assignment (one value expected).

    Returns:
        The named :class:`Matter`.

    Raises:
        ValueError: If *assignment* is not for the ``matter`` attribute, does not carry exactly one
            value, or its value is not a recognised :class:`Matter`.
    """
    return Matter(verified_sole_value_text(assignment, PublishingSemantics.MATTER.value))


@validate_call
def pdf_render_of(assignment: AttributeAssignment) -> PdfRender:
    """Return the :class:`PdfRender` placement that a ``pdf-render`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.PDF_RENDER` attribute, then coerces
    its sole value to a :class:`PdfRender` (``inline`` / ``link``).

    Args:
        assignment: A :attr:`PublishingSemantics.PDF_RENDER` attribute assignment (one value expected).

    Returns:
        The named :class:`PdfRender`.

    Raises:
        ValueError: If *assignment* is not for the ``pdf-render`` attribute, does not carry exactly
            one value, or its value is not a recognised :class:`PdfRender`.
    """
    return PdfRender(verified_sole_value_text(assignment, PublishingSemantics.PDF_RENDER.value))


@validate_call(config=ConfigDict(strict=True))
def find_publishing_attribute(vertex: Vertex, attribute: PublishingSemantics) -> AttributeAssignment | None:
    """Return *vertex*'s assignment for the Guffin *attribute*, or ``None``.

    Convenience over :func:`~guffin.model.vertex.find_attribute_assignment` that passes the
    member's :class:`PublishingAttribute`, so callers neither restate nor risk mismatching its
    identity.  Validated strictly: *attribute* must be an actual :class:`PublishingSemantics`
    member — a bare :class:`~guffin.model.attribute.Attribute` carrying a member's identity is
    rejected rather than coerced by value.

    Args:
        vertex: The vertex whose folded attribute assignments are searched.
        attribute: The Guffin attribute to look up.

    Returns:
        The matching :class:`~guffin.model.attribute.AttributeAssignment`, or ``None`` when *vertex*
        has no such Guffin attribute.
    """
    return find_attribute_assignment(vertex, attribute.value)


@validate_call
def element_type_of_vertex(vertex: HeadingVertex) -> StructuralElement | None:
    """Resolve *vertex*'s ``element-type`` tag to a :class:`StructuralElement`, or ``None``.

    ``None`` when *vertex* carries no ``element-type`` assignment, or when the assignment does not
    coerce to a :class:`StructuralElement` (ignored with a warning).

    Args:
        vertex: The heading vertex whose tag to resolve.

    Returns:
        The named :class:`StructuralElement`, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.ELEMENT_TYPE)
    if assignment is None:
        return None
    try:
        return element_type_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring element-type on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def matter_of_vertex(vertex: HeadingVertex) -> Matter | None:
    """Resolve *vertex*'s bare ``matter`` tag to a :class:`Matter`, or ``None``.

    ``None`` when *vertex* carries no ``matter`` assignment, or when the assignment does not
    coerce to a :class:`Matter` (ignored with a warning).

    Args:
        vertex: The heading vertex whose tag to resolve.

    Returns:
        The named :class:`Matter`, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.MATTER)
    if assignment is None:
        return None
    try:
        return matter_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring matter on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def pdf_render_of_vertex(vertex: PdfVertex) -> PdfRender | None:
    """Resolve *vertex*'s ``pdf-render`` tag to a :class:`PdfRender`, or ``None``.

    ``None`` when *vertex* carries no ``pdf-render`` assignment, or when the assignment does not
    coerce to a :class:`PdfRender` (ignored with a warning).  An untagged embed's placement is
    :data:`DEFAULT_PDF_RENDER`.

    Args:
        vertex: The PDF vertex whose tag to resolve.

    Returns:
        The named :class:`PdfRender`, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.PDF_RENDER)
    if assignment is None:
        return None
    try:
        return pdf_render_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring pdf-render on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def resolved_matter(vertex: HeadingVertex) -> Matter | None:
    """Return *vertex*'s resolved :class:`Matter` division, or ``None`` when none applies.

    A bare ``matter`` tag takes precedence — letting an author override the default division for a
    non-standard placement — otherwise the matter is the ``element-type``'s
    :class:`StructuralElement` conventional placement.  When both are present and disagree, the
    ``matter`` tag wins and the override is logged.

    Args:
        vertex: The heading vertex whose division to resolve.

    Returns:
        The resolved :class:`Matter`, or ``None`` when *vertex* carries neither tag.
    """
    element: Final[StructuralElement | None] = element_type_of_vertex(vertex)
    override: Final[Matter | None] = matter_of_vertex(vertex)
    if element is not None and override is not None and override is not element.matter:
        logger.warning(
            "heading uid=%r: matter %r overrides its element-type %r (%s matter)",
            vertex.uid,
            override.value,
            element.value,
            element.matter.value,
        )
    if override is not None:
        return override
    return element.matter if element is not None else None


def _is_part_heading(heading: HeadingVertex) -> bool:
    """Return whether *heading* is a level-1 heading tagged ``element-type:: part``.

    An assignment whose value is not a recognised :class:`StructuralElement` is ignored with a
    warning.

    Args:
        heading: The heading vertex to check.

    Returns:
        ``True`` when *heading* declares itself a part, else ``False``.
    """
    return heading.heading_level == 1 and element_type_of_vertex(heading) is StructuralElement.PART


@validate_call
def has_parts(tree: VertexTree) -> bool:
    """Return whether *tree* structures its top level as parts.

    ``True`` when any render-visible level-1 :class:`~guffin.model.vertex.HeadingVertex` carries
    an ``element-type`` assignment naming :attr:`StructuralElement.PART` — the content's own
    declaration that its level-1 headings are parts (so its chapters live at level 2).  The
    render-visible headings (per :func:`~guffin.model.vertex_tree.transcluded_vertices`) include
    those transcluded through block embeds, since an embedded part heading structures the rendered
    document exactly as an in-tree one does; a part heading that is merely *referenced* (rendered
    inline as text) does not count.  Assignments whose value is not a recognised
    :class:`StructuralElement` are ignored with a warning.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to inspect.

    Returns:
        ``True`` when a render-visible level-1 heading is tagged as a part, else ``False``.
    """
    return any(_is_part_heading(vertex) for vertex in transcluded_vertices(tree) if isinstance(vertex, HeadingVertex))


_SEMANTICS_BY_NAME: Final[dict[str, PublishingSemantics]] = {
    member.value.name: member for member in PublishingSemantics
}
"""Maps each recognised guffin attribute name to its :class:`PublishingSemantics` member."""


def _anchor_violation(vertex: Vertex, assignment: AttributeAssignment) -> str | None:
    """Describe how *assignment* violates the anchor invariant on *vertex*, or ``None``.

    ``None`` when *assignment* is outside the vocabulary (non-guffin domain, or a name matching no
    :class:`PublishingSemantics` member) or when it sits on its anchor's vertex type; otherwise a
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
    member: Final[PublishingSemantics | None] = _SEMANTICS_BY_NAME.get(assignment_attribute.name)
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

    Each :class:`PublishingSemantics` member's :class:`PublishingAttribute` carries an :class:`Anchor`
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


def _illegal_value_violations(
    tree: VertexTree,
    attribute: PublishingSemantics,
    value_coercer: Callable[[AttributeAssignment], StructuralElement | Matter | PdfRender],
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
    for vertex, assignment in assignments_for(tree, attribute.value):
        try:
            value_coercer(assignment)
        except ValueError as exc:
            violations.append(f"on vertex uid={vertex.uid!r}: {exc}")
    return violations


@validate_call
def all_element_type_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``element-type`` values.

    Every :attr:`PublishingSemantics.ELEMENT_TYPE` assignment in *tree* must carry exactly one value,
    and that value must name a :class:`StructuralElement` member — the authoritative set of legal
    ``element-type`` values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``element-type`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.ELEMENT_TYPE, element_type_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal element-type values: " + "; ".join(violations),
        validator=all_element_type_values_legal,
    )


@validate_call
def all_matter_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``matter`` values.

    Every :attr:`PublishingSemantics.MATTER` assignment in *tree* must carry exactly one value, and
    that value must name a :class:`Matter` member — the authoritative set of legal ``matter``
    values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``matter`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.MATTER, matter_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal matter values: " + "; ".join(violations),
        validator=all_matter_values_legal,
    )


@validate_call
def all_pdf_render_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``pdf-render`` values.

    Every :attr:`PublishingSemantics.PDF_RENDER` assignment in *tree* must carry exactly one value,
    and that value must name a :class:`PdfRender` member — the authoritative set of legal
    ``pdf-render`` values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``pdf-render`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.PDF_RENDER, pdf_render_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal pdf-render values: " + "; ".join(violations),
        validator=all_pdf_render_values_legal,
    )


@validate_call
def all_matter_tags_at_section_level(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every ``matter`` tag to sit at the section level.

    A ``matter`` tag declares a bespoke section's book division, and sections sit at the book's
    *section level* — the heading level where chapter-shaped divisions live: level 1 in a chapters
    book, level 2 when the tree structures its top level as parts (see :func:`has_parts`).
    Non-heading hosts are not this validator's concern — they are already reported by
    :func:`all_attributes_anchored`.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``matter`` tag sits at the section level; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    parts: Final[bool] = has_parts(tree)
    section_level: Final[int] = 2 if parts else 1
    shape: Final[str] = "a parts book (sections at level 2)" if parts else "a chapters book (sections at level 1)"
    violations: Final[list[str]] = [
        f"'matter' tag on a level-{vertex.heading_level} heading (uid={vertex.uid!r}); this tree is {shape}"
        for vertex, _assignment in assignments_for(tree, PublishingSemantics.MATTER.value)
        if isinstance(vertex, HeadingVertex) and vertex.heading_level != section_level
    ]
    if not violations:
        return None
    return ValidationError(
        message="misplaced matter tags: " + "; ".join(violations),
        validator=all_matter_tags_at_section_level,
    )


@validate_call
def validate_semantics(tree: VertexTree) -> ValidationResult:
    """Return a :class:`~guffin.common.validation.ValidationResult` for the vocabulary invariants on *tree*.

    Runs every vocabulary validator — :func:`all_attributes_anchored`,
    :func:`all_element_type_values_legal`, :func:`all_matter_values_legal`,
    :func:`all_pdf_render_values_legal`, and
    :func:`all_matter_tags_at_section_level` — via :func:`~guffin.common.validation.validate_all`.  Every
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
            all_pdf_render_values_legal,
            all_matter_tags_at_section_level,
        ],
    )
