"""The publishing-semantics vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Constants**: :data:`DEFAULT_PDF_RENDER` — the :class:`PdfRender` placement of an untagged
  PDF embed; :data:`DEFAULT_PUBLISH` — the publication state of an untagged vertex.
- **Enumerations**: :class:`PublishingSemantics` — the attributes Guffin recognizes (document metadata +
  the ``element-type``/``matter`` heading tags + the ``pdf-render`` PDF tag + the ``publish``
  block tag), each member a
  :class:`PublishingAttribute` in the :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`
  domain; :class:`PdfRender` — how an embedded PDF asset is placed in paginated output (inline /
  link).  The anchoring affordances an attribute declares
  (:class:`~guffin.model.attribute_anchor.AttributeAnchor`,
  :class:`~guffin.model.attribute_anchor.TreePosition`) live in
  :mod:`~guffin.model.attribute_anchor`; the CMOS-aligned structural taxonomy the ``element-type`` and
  ``matter`` tags take their values from (:class:`~guffin.model.chicago_structure.Matter`,
  :class:`~guffin.model.chicago_structure.StructuralElement`) lives in
  :mod:`~guffin.model.chicago_structure`.
- **Models**: :class:`PublishingAttribute` — an :class:`~guffin.model.attribute.Attribute` pinned to the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain and carrying a :class:`AttributeAnchor`.
- **Functions**: :func:`element_type_of` — read an ``element-type`` assignment's value as a
  :class:`StructuralElement` (raising if it is not one); :func:`matter_of` — read a ``matter``
  assignment's value as a :class:`Matter`; :func:`pdf_render_of` — read a ``pdf-render``
  assignment's value as a :class:`PdfRender`; :func:`code_language_of` — read a
  ``code-language`` assignment's value as a canonical
  :data:`~guffin.common.programming_language.CodeLanguageId` (any vocabulary name or alias,
  case-insensitively); :func:`publish_of` — read a ``publish``
  assignment's value as a boolean; :func:`date_of` — read a ``date`` assignment's value as a
  :data:`~guffin.common.date.W3cdtfDate` (``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``);
  :func:`cover_image_of` — read a ``cover-image`` assignment's value as the referenced image
  block's :data:`~guffin.model.primitives.Uid` (the value is a Roam block reference
  ``((<uid>))``); :func:`cover_image_vertex` — resolve a tree's cover to the
  :class:`~guffin.model.vertex.ImageVertex` its root references, tolerating absent or
  unresolvable assignments (``None``, warning);
  :func:`illustrators_of_vertex` — a vertex's declared illustrator names, in source order
  (empty tuple when none);
  :func:`find_publishing_attribute` — find a vertex's
  assignment for a :class:`PublishingSemantics` attribute (the Guffin domain supplied automatically);
  :func:`element_type_of_vertex` / :func:`matter_of_vertex` / :func:`pdf_render_of_vertex` /
  :func:`code_language_of_vertex` / :func:`publish_of_vertex` —
  resolve a heading's ``element-type`` / bare ``matter`` tag, a PDF embed's ``pdf-render`` tag,
  a code block's ``code-language`` tag,
  or any block's ``publish`` tag, to its value, tolerating absent or illegal assignments (``None``,
  warning); :func:`resolved_matter` — a heading's resolved :class:`Matter` division (a bare
  ``matter`` tag overrides the element's conventional placement, logging any disagreement);
  :func:`has_parts` — return whether a :class:`~guffin.model.vertex_tree.VertexTree` structures its
  top level as parts (any render-visible level-1 heading — embed-transcluded headings
  included — tagged ``element-type:: part``);
  :func:`has_element_type` — return whether any render-visible heading in a
  :class:`~guffin.model.vertex_tree.VertexTree` is tagged with a given :class:`StructuralElement`;
  :func:`drop_unpublished` — prune every ``publish:: false`` subtree (embeds of pruned
  content vanishing with it) from a :class:`~guffin.model.vertex_tree.VertexTree`;
  :func:`strip_element_numbers` — remove every heading's internal element number (the
  well-formed leading marker) from a :class:`~guffin.model.vertex_tree.VertexTree`;
  the :data:`~guffin.common.validation.Validator` functions :func:`all_attributes_anchored`
  (every recognised guffin attribute satisfies its :class:`AttributeAnchor` — one of its vertex types, at
  its tree position),
  :func:`all_element_type_values_legal` (every ``element-type`` value is a
  :class:`StructuralElement`), :func:`all_matter_values_legal` (every ``matter`` value is a
  :class:`Matter`), :func:`all_pdf_render_values_legal` (every ``pdf-render`` value is a
  :class:`PdfRender`), :func:`all_code_language_values_legal` (every ``code-language`` value
  names a language in the canonical vocabulary),
  :func:`all_publish_values_legal` (every ``publish`` value is a boolean
  literal), :func:`all_date_values_legal` (every ``date`` value is a W3CDTF
  reduced-precision date), :func:`all_cover_image_values_legal` (every ``cover-image`` value
  is a block reference resolving to an image vertex in the tree), and
  :func:`all_matter_tags_at_section_level` (every ``matter`` tag sits at
  the book's section level — level 1, or level 2 in a parts book);
  the internal-element-numbering :data:`~guffin.common.validation.Validator` functions over the
  render-visible headings (see :mod:`~guffin.model.element_number` — the numbers are the author's
  source of truth for the elements' logical order, and validation detects placement drift):
  :func:`all_element_numbers_well_formed` (a number-shaped heading lead must parse as a
  well-formed element number), :func:`all_element_numbers_in_headings_only` (no number-shaped
  lead on a text vertex), :func:`all_element_number_matters_legal` (every leading segment names a
  :class:`Matter`), :func:`all_element_number_matters_agree` (a number's matter agrees with the
  heading's resolved tags), :func:`all_element_numbers_unique` (no duplicates),
  :func:`all_element_numbers_ordered` (document order is strictly increasing number order), and
  :func:`all_element_numbers_nested` (a number under a numbered ancestor extends it as a strict
  prefix);
  :func:`validate_semantics` — run every vocabulary validator over a
  :class:`~guffin.model.vertex_tree.VertexTree`, accumulating a
  :class:`~guffin.common.validation.ValidationResult`.

This module sits at the top of the ``model/`` conceptual stack: it may depend on the structural
primitives (:mod:`~guffin.model.attribute`, :mod:`~guffin.model.vertex`,
:mod:`~guffin.model.vertex_tree`), the :mod:`~guffin.model.attribute_anchor` affordances, the
:mod:`~guffin.model.chicago_structure` taxonomy, and the :mod:`~guffin.model.element_number`
numbering primitive, and none of them may depend on it.
"""

import enum
import logging
from collections.abc import Callable
from typing import Final

import regex
from pydantic import ConfigDict, Field, field_validator, validate_call

from guffin.common.date import W3cdtfDate, verified_w3cdtf_date
from guffin.common.programming_language import CodeLanguageId, canonical_language_id
from guffin.common.validation import ValidationError, ValidationResult, validate_all
from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    attribute_value_text,
)
from guffin.model.attribute_anchor import AttributeAnchor, TreePosition
from guffin.model.attribute_assignment import AttributeAssignment, verified_sole_value_text
from guffin.model.chicago_structure import Matter, StructuralElement
from guffin.model.element_number import (
    ElementNumber,
    leads_with_dotted_element_number_shape,
    leads_with_element_number_shape,
    parse_element_number,
    stripped_element_number,
)
from guffin.model.primitives import UID_PATTERN, Uid
from guffin.model.vertex import (
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PdfVertex,
    TextVertex,
    Vertex,
    find_attribute_assignment,
    is_embed_vertex,
)
from guffin.model.vertex_tree import VertexTree, assignments_for, map_vertices, root_vertex, transcluded_vertices

logger = logging.getLogger(__name__)


class PdfRender(enum.StrEnum):
    """How an embedded PDF asset is placed in paginated output — the values a ``pdf-render`` tag takes.

    Attributes:
        INLINE: Every page of the PDF renders in the document flow, in place of the embed.
        LINK: The PDF is represented as a reference rather than its rendered pages (the untagged
            default, :data:`DEFAULT_PDF_RENDER`); how that reference is presented is format-specific
            (e.g. a bundled-file link in Markdown, plain filename text in PDF).
    """

    INLINE = "inline"
    LINK = "link"


DEFAULT_PDF_RENDER: Final[PdfRender] = PdfRender.LINK
"""The :class:`PdfRender` placement of a PDF embed carrying no ``pdf-render`` tag."""

DEFAULT_PUBLISH: Final[bool] = True
"""The publication state of a vertex carrying no ``publish`` tag."""

_PUBLISH_LITERALS: Final[dict[str, bool]] = {"true": True, "false": False}
"""Maps each legal ``publish`` value literal to the publication state it names."""


class PublishingAttribute(Attribute):
    """A Guffin-domain :class:`~guffin.model.attribute.Attribute` that also carries a :class:`AttributeAnchor`.

    Specializes :class:`~guffin.model.attribute.Attribute` by pinning :attr:`domain` to
    :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` (any other value is rejected) and adding a
    required :attr:`anchor`.

    Attributes:
        domain: Always :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`.
        anchor: The kind of vertex this attribute attaches to.
    """

    domain: AttributeDomain = Field(default=AttributeDomain.GUFFIN, description="Always the guffin domain.")
    anchor: AttributeAnchor = Field(..., description="The kind of vertex this attribute attaches to.")

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

    - **Document metadata** (:attr:`AttributeAnchor.ROOT`) — bibliographic facts about the work as a
      whole, so they attach only to the tree's root vertex (the export target itself, whatever
      its type): :attr:`TITLE`, :attr:`SUBTITLE`, :attr:`AUTHORS`, :attr:`ILLUSTRATORS`,
      :attr:`DATE`, :attr:`PUBLISHER`, :attr:`RIGHTS`, :attr:`IDENTIFIER`, :attr:`LANGUAGE`,
      :attr:`DESCRIPTION`, :attr:`REVISION`, :attr:`COVER_IMAGE`.  The cover is
      metadata rather than an :class:`~guffin.model.chicago_structure.StructuralElement` because
      per CMOS only the book *interior* is matter-classified — the cover is exterior.
    - **Heading tags** (:attr:`AttributeAnchor.HEADING`) — applied to an individual heading: :attr:`ELEMENT_TYPE`
      declares which :class:`StructuralElement` the heading is; :attr:`MATTER` declares its
      :class:`Matter` division directly, for a bespoke section with no specific element type.
    - **PDF tags** (:attr:`AttributeAnchor.PDF`) — applied to an individual embedded PDF asset:
      :attr:`PDF_RENDER` declares its :class:`PdfRender` placement in paginated output.
    - **Code-block tags** (:attr:`AttributeAnchor.CODE_BLOCK`) — applied to an individual fenced
      code listing: :attr:`CODE_LANGUAGE` declares the listing's language, overriding the closed
      vocabulary the Roam UI embeds in the fence.
    - **Block tags** (:attr:`AttributeAnchor.BLOCK`) — applied to any block vertex: :attr:`PUBLISH`
      declares whether the block, with its entire subtree, appears in rendered output.

    Attributes:
        TITLE: The document title.
        SUBTITLE: The document subtitle.
        AUTHORS: The document author(s) — the work's primary creators.
        ILLUSTRATORS: The work's illustrator(s) — supportive contributors, not co-creators
            (bibliographically secondary to :attr:`AUTHORS`).
        DATE: The document date.
        PUBLISHER: The publisher of the work.
        RIGHTS: The rights statement for the work (e.g. a copyright line).
        IDENTIFIER: The document identifier.
        LANGUAGE: The main language of the work, as an IETF BCP 47 language tag (e.g. ``en-US``).
        DESCRIPTION: A prose description of the work (e.g. a catalog blurb or abstract).
        REVISION: An author-declared revision label for the content (free text — e.g. a draft
            name or version string), carried into the export's content
            :class:`~guffin.common.revision.Revision` record.
        COVER_IMAGE: The work's cover image — the value is a Roam block reference
            ``((<uid>))`` to an image block, keeping the cover ordinary, reusable Roam content.
        ELEMENT_TYPE: Tags a heading with its :class:`StructuralElement` (the book part it is).
        MATTER: Tags a heading with its :class:`Matter` division (for a section with no element type).
        PDF_RENDER: Tags an embedded PDF with its :class:`PdfRender` placement (inline pages vs a link).
        CODE_LANGUAGE: Tags a fenced code listing with its language — any name or alias of the
            canonical vocabulary (:mod:`~guffin.common.programming_language`) — overriding the
            closed language set the Roam UI offers (which lacks e.g. Fortran).
        PUBLISH: Tags a block with its publication state; ``false`` omits the block and every
            descendant from all rendered output (absent, :data:`DEFAULT_PUBLISH` applies).
    """

    _value_: PublishingAttribute

    TITLE = PublishingAttribute(name="title", anchor=AttributeAnchor.ROOT)
    SUBTITLE = PublishingAttribute(name="subtitle", anchor=AttributeAnchor.ROOT)
    AUTHORS = PublishingAttribute(name="authors", anchor=AttributeAnchor.ROOT)
    ILLUSTRATORS = PublishingAttribute(name="illustrators", anchor=AttributeAnchor.ROOT)
    DATE = PublishingAttribute(name="date", anchor=AttributeAnchor.ROOT)
    PUBLISHER = PublishingAttribute(name="publisher", anchor=AttributeAnchor.ROOT)
    RIGHTS = PublishingAttribute(name="rights", anchor=AttributeAnchor.ROOT)
    IDENTIFIER = PublishingAttribute(name="identifier", anchor=AttributeAnchor.ROOT)
    LANGUAGE = PublishingAttribute(name="language", anchor=AttributeAnchor.ROOT)
    DESCRIPTION = PublishingAttribute(name="description", anchor=AttributeAnchor.ROOT)
    REVISION = PublishingAttribute(name="revision", anchor=AttributeAnchor.ROOT)
    COVER_IMAGE = PublishingAttribute(name="cover-image", anchor=AttributeAnchor.ROOT)
    ELEMENT_TYPE = PublishingAttribute(name="element-type", anchor=AttributeAnchor.HEADING)
    MATTER = PublishingAttribute(name="matter", anchor=AttributeAnchor.HEADING)
    PDF_RENDER = PublishingAttribute(name="pdf-render", anchor=AttributeAnchor.PDF)
    CODE_LANGUAGE = PublishingAttribute(name="code-language", anchor=AttributeAnchor.CODE_BLOCK)
    PUBLISH = PublishingAttribute(name="publish", anchor=AttributeAnchor.BLOCK)


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


@validate_call
def code_language_of(assignment: AttributeAssignment) -> CodeLanguageId:
    """Return the canonical language id that a ``code-language`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.CODE_LANGUAGE` attribute, then
    resolves its sole value — any language name or alias of the canonical vocabulary,
    case-insensitively — to its canonical id via
    :func:`~guffin.common.programming_language.canonical_language_id` (``FORTRAN`` →
    ``fortran``).

    Args:
        assignment: A :attr:`PublishingSemantics.CODE_LANGUAGE` attribute assignment (one value
            expected).

    Returns:
        The canonical language id.

    Raises:
        ValueError: If *assignment* is not for the ``code-language`` attribute, does not carry
            exactly one value, or its value names no language in the canonical vocabulary.
    """
    value_text: Final[str] = verified_sole_value_text(assignment, PublishingSemantics.CODE_LANGUAGE.value)
    resolved: Final[str | None] = canonical_language_id(value_text)
    if resolved is None:
        raise ValueError(f"code-language value {value_text!r} names no language in the canonical vocabulary")
    return resolved


@validate_call
def publish_of(assignment: AttributeAssignment) -> bool:
    """Return the publication state that a ``publish`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.PUBLISH` attribute, then coerces
    its sole value to a boolean (``true`` / ``false``).

    Args:
        assignment: A :attr:`PublishingSemantics.PUBLISH` attribute assignment (one value expected).

    Returns:
        The named publication state.

    Raises:
        ValueError: If *assignment* is not for the ``publish`` attribute, does not carry exactly
            one value, or its value is neither ``true`` nor ``false``.
    """
    literal: Final[str] = verified_sole_value_text(assignment, PublishingSemantics.PUBLISH.value)
    published: Final[bool | None] = _PUBLISH_LITERALS.get(literal)
    if published is None:
        raise ValueError(f"'publish' value must be 'true' or 'false'; got {literal!r}")
    return published


@validate_call
def date_of(assignment: AttributeAssignment) -> W3cdtfDate:
    """Return the :data:`~guffin.common.date.W3cdtfDate` that a ``date`` assignment carries.

    Verifies *assignment* is for the :attr:`PublishingSemantics.DATE` attribute, then checks its
    sole value is a W3CDTF reduced-precision date — ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``
    (year first), with a real calendar month and day when present — via
    :func:`~guffin.common.date.verified_w3cdtf_date`.

    Args:
        assignment: A :attr:`PublishingSemantics.DATE` attribute assignment (one value expected).

    Returns:
        The assignment's value as a :data:`~guffin.common.date.W3cdtfDate`, unchanged.

    Raises:
        ValueError: If *assignment* is not for the ``date`` attribute, does not carry exactly one
            value, or its value is not a W3CDTF reduced-precision date (wrong shape, month outside
            1–12, or a day invalid for its month).
    """
    return verified_w3cdtf_date(verified_sole_value_text(assignment, PublishingSemantics.DATE.value))


_BLOCK_REF_VALUE_RE: Final[regex.Pattern[str]] = regex.compile(rf"\(\((?P<uid>{UID_PATTERN})\)\)")
"""A Roam block reference ``((<uid>))`` as an attribute-value token (fullmatch-anchored at use).

Built from the model's own :data:`~guffin.model.primitives.UID_PATTERN`, so the vocabulary stays
free of any ``roam/`` dependency.
"""


@validate_call
def cover_image_of(assignment: AttributeAssignment) -> Uid:
    """Return the UID of the image block that a ``cover-image`` assignment references.

    Verifies *assignment* is for the :attr:`PublishingSemantics.COVER_IMAGE` attribute, then
    coerces its sole value to the referenced block's UID: the value must be wholly a Roam block
    reference ``((<uid>))`` pointing at an image block.  Referencing a block (rather than
    carrying a raw image URL) keeps the cover an ordinary piece of Roam content — reusable,
    and editable in place.

    Args:
        assignment: A :attr:`PublishingSemantics.COVER_IMAGE` attribute assignment (one value
            expected).

    Returns:
        The referenced block's UID.  Whether that block is actually an image vertex present in
        the tree is a tree-level question (see :func:`cover_image_vertex` and
        :func:`all_cover_image_values_legal`).

    Raises:
        ValueError: If *assignment* is not for the ``cover-image`` attribute, does not carry
            exactly one value, or its value is not wholly a Roam block reference.
    """
    text: Final[str] = verified_sole_value_text(assignment, PublishingSemantics.COVER_IMAGE.value)
    ref_match: Final[regex.Match[str] | None] = _BLOCK_REF_VALUE_RE.fullmatch(text)
    if ref_match is None:
        raise ValueError(f"'cover-image' value must be a block reference ((<uid>)); got {text!r}")
    return ref_match.group("uid")


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
        The matching :class:`~guffin.model.attribute_assignment.AttributeAssignment`, or ``None`` when *vertex*
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
def code_language_of_vertex(vertex: CodeBlockVertex) -> CodeLanguageId | None:
    """Resolve *vertex*'s ``code-language`` tag to a canonical language id, or ``None``.

    ``None`` when *vertex* carries no ``code-language`` assignment, or when the assignment does
    not resolve against the canonical vocabulary (ignored with a warning).  An untagged code
    block's language is whatever the Roam fence embeds.

    Args:
        vertex: The code-block vertex whose tag to resolve.

    Returns:
        The canonical language id, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.CODE_LANGUAGE)
    if assignment is None:
        return None
    try:
        return code_language_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring code-language on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def publish_of_vertex(vertex: Vertex) -> bool | None:
    """Resolve *vertex*'s ``publish`` tag to its publication state, or ``None``.

    ``None`` when *vertex* carries no ``publish`` assignment, or when the assignment does not
    coerce to a boolean (ignored with a warning).  An untagged vertex's state is
    :data:`DEFAULT_PUBLISH`.

    Args:
        vertex: The vertex whose tag to resolve.

    Returns:
        The named publication state, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.PUBLISH)
    if assignment is None:
        return None
    try:
        return publish_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring publish on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def cover_image_vertex(tree: VertexTree) -> ImageVertex | None:
    """Resolve *tree*'s cover image to the :class:`~guffin.model.vertex.ImageVertex` it references, or ``None``.

    Reads the ``cover-image`` block reference off *tree*'s root vertex and follows it to the
    referenced vertex.  ``None`` when the root carries no ``cover-image`` assignment (silent),
    or — with a warning — when the assignment does not coerce to a block reference, the
    referenced UID is absent from the tree, or the referenced vertex is not an image.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` whose cover to resolve.

    Returns:
        The referenced :class:`~guffin.model.vertex.ImageVertex`, or ``None``.
    """
    root: Final[Vertex] = root_vertex(tree)
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(root, PublishingSemantics.COVER_IMAGE)
    if assignment is None:
        return None
    try:
        target_uid: Final[Uid] = cover_image_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring cover-image on root vertex uid=%r: %s", root.uid, exc)
        return None
    target: Final[Vertex | None] = tree.uid_map.get(target_uid)
    if target is None:
        logger.warning("cover-image references uid=%r, which is absent from the tree", target_uid)
        return None
    if not isinstance(target, ImageVertex):
        logger.warning(
            "cover-image references uid=%r, which is not an image (vertex_type=%s)", target_uid, target.vertex_type
        )
        return None
    return target


@validate_call
def revision_of(assignment: AttributeAssignment) -> str:
    """Return the revision label that a ``revision`` assignment carries.

    Verifies *assignment* is for the :attr:`PublishingSemantics.REVISION` attribute, then returns
    its sole value verbatim — the label is free text (a draft name, a version string, …).

    Args:
        assignment: A :attr:`PublishingSemantics.REVISION` attribute assignment (one value
            expected).

    Returns:
        The revision label.

    Raises:
        ValueError: If *assignment* is not for the ``revision`` attribute or does not carry
            exactly one value.
    """
    return verified_sole_value_text(assignment, PublishingSemantics.REVISION.value)


@validate_call
def revision_of_vertex(vertex: Vertex) -> str | None:
    """Resolve *vertex*'s ``revision`` attribute to its label, or ``None``.

    ``None`` when *vertex* carries no ``revision`` assignment, or when the assignment does not
    carry exactly one value (ignored with a warning).

    Args:
        vertex: The vertex whose attribute to resolve.

    Returns:
        The revision label, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.REVISION)
    if assignment is None:
        return None
    try:
        return revision_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring revision on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def illustrators_of_vertex(vertex: Vertex) -> tuple[str, ...]:
    """Return the illustrator names *vertex*'s ``illustrators`` assignment declares, or ``()``.

    The tolerant per-vertex reader: each of the assignment's values contributes its text (a
    literal token or a referenced page name), in source order; a vertex with no ``illustrators``
    assignment yields the empty tuple.

    Args:
        vertex: The vertex whose attribute to resolve.

    Returns:
        The illustrator names, in source order; empty when none are declared.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.ILLUSTRATORS)
    if assignment is None:
        return ()
    return tuple(attribute_value_text(value) for value in assignment.values)


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
    those transcluded through embeds, since an embedded part heading structures the rendered
    document exactly as an in-tree one does; a part heading that is merely *referenced* (rendered
    inline as text) does not count.  Assignments whose value is not a recognised
    :class:`StructuralElement` are ignored with a warning.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to inspect.

    Returns:
        ``True`` when a render-visible level-1 heading is tagged as a part, else ``False``.
    """
    return any(_is_part_heading(vertex) for vertex in transcluded_vertices(tree) if isinstance(vertex, HeadingVertex))


@validate_call
def has_element_type(tree: VertexTree, element: StructuralElement) -> bool:
    """Return whether any render-visible heading in *tree* is tagged ``element-type:: <element>``.

    The render-visible headings (per :func:`~guffin.model.vertex_tree.transcluded_vertices`)
    include those transcluded through embeds; a heading that is merely *referenced*
    (rendered inline as text) does not count.  Assignments whose value is not a recognised
    :class:`StructuralElement` are ignored with a warning.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to inspect.
        element: The :class:`StructuralElement` to look for.

    Returns:
        ``True`` when a render-visible heading declares itself *element*, else ``False``.
    """
    return any(
        element_type_of_vertex(vertex) is element
        for vertex in transcluded_vertices(tree)
        if isinstance(vertex, HeadingVertex)
    )


@validate_call
def drop_unpublished(tree: VertexTree) -> VertexTree:
    """Return a new :class:`VertexTree` without the unpublished subtrees.

    A vertex tagged ``publish:: false`` is unpublished: it is removed — together with every
    descendant — from both :attr:`~guffin.model.vertex_tree.VertexTree.tree_vertices` and
    :attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`, and its uid is stripped from every
    surviving vertex's children list.  The tag travels with the content: an
    :data:`~guffin.model.vertex.EmbedVertex` (block or page embed) whose transclusion target was
    removed is removed as well (applied to a fixpoint, so an embed of an embed of unpublished
    content also vanishes).  Assignments that do not coerce to a boolean are ignored with a warning (the
    vertex stays published).  The original *tree* is not modified; it passes through unchanged
    when nothing is tagged unpublished.

    Args:
        tree: The source :class:`~guffin.model.vertex_tree.VertexTree`.

    Returns:
        A new :class:`~guffin.model.vertex_tree.VertexTree` without the unpublished vertices, or
        *tree* itself when no prune applies.

    Raises:
        ValueError: If the tree's root vertex is itself unpublished — the export target cannot
            be omitted from its own output.
    """
    pending: list[Uid] = [vertex.uid for vertex in tree.uid_map.values() if publish_of_vertex(vertex) is False]
    if not pending:
        return tree
    removed: Final[set[Uid]] = set()
    while pending:
        # Close over descendants, then cascade to embeds whose target vanished; repeat to a fixpoint.
        while pending:
            uid = pending.pop()
            if uid in removed:
                continue
            removed.add(uid)
            vertex = tree.uid_map.get(uid)
            if vertex is not None and vertex.children:
                pending.extend(vertex.children)
        pending = [
            vertex.uid
            for vertex in tree.uid_map.values()
            if vertex.uid not in removed and is_embed_vertex(vertex) and vertex.vertex_link.uid in removed
        ]
    root_uid: Final[Uid] = root_vertex(tree).uid
    if root_uid in removed:
        raise ValueError(f"the export target itself (root vertex uid={root_uid!r}) is tagged 'publish:: false'")
    logger.info("dropping %d unpublished vertices (publish:: false)", len(removed))

    def _strip_children(vertex: Vertex) -> Vertex:
        if vertex.children and any(child_uid in removed for child_uid in vertex.children):
            return vertex.model_copy(
                update={"children": [child_uid for child_uid in vertex.children if child_uid not in removed]}
            )
        return vertex

    return VertexTree(
        tree_vertices=[_strip_children(v) for v in tree.tree_vertices if v.uid not in removed],
        ref_vertices=[_strip_children(v) for v in tree.ref_vertices if v.uid not in removed],
    )


@validate_call
def strip_element_numbers(tree: VertexTree) -> VertexTree:
    """Return a new :class:`VertexTree` with every heading's internal element number removed.

    Each :class:`~guffin.model.vertex.HeadingVertex` — tree and referenced vertices alike, so
    embed-transcluded headings are covered — has a well-formed leading marker stripped from its
    text (per :func:`~guffin.model.element_number.stripped_element_number`); the numbers are
    internal authoring bookkeeping, not content.  Headings with no marker, malformed leads, and
    every other vertex type pass through unchanged, and the original *tree* is not modified.

    Args:
        tree: The source :class:`~guffin.model.vertex_tree.VertexTree`.

    Returns:
        A new :class:`~guffin.model.vertex_tree.VertexTree` whose headings carry no element
        numbers.
    """

    def _strip(vertex: Vertex) -> Vertex:
        if not isinstance(vertex, HeadingVertex):
            return vertex
        stripped_text: Final[str] = stripped_element_number(vertex.text)
        if stripped_text == vertex.text:
            return vertex
        return vertex.model_copy(update={"text": stripped_text})

    return map_vertices(tree, _strip)


_SEMANTICS_BY_NAME: Final[dict[str, PublishingSemantics]] = {
    member.value.name: member for member in PublishingSemantics
}
"""Maps each recognised guffin attribute name to its :class:`PublishingSemantics` member."""


def _anchor_mismatch(attribute: PublishingAttribute, vertex: Vertex, root_uid: Uid) -> str | None:
    """Describe how *vertex* fails *attribute*'s anchor, or ``None`` when it satisfies it.

    A host vertex must satisfy both anchor axes: its type must be among the anchor's
    :attr:`~AttributeAnchor.vertex_types`, and its position must match the anchor's
    :attr:`~AttributeAnchor.tree_position` (:attr:`TreePosition.ROOT` requires the vertex to be the
    tree's root, identified by *root_uid*).

    Args:
        attribute: The publishing attribute whose anchor to check.
        vertex: The vertex the attribute is declared on.
        root_uid: The uid of the tree's root vertex.

    Returns:
        The mismatch description, or ``None`` when *vertex* satisfies the anchor.
    """
    anchor: Final[AttributeAnchor] = attribute.anchor
    if vertex.vertex_type not in anchor.vertex_types:
        return (
            f"{attribute.name!r} is {anchor.value}-anchored but declared on a "
            f"{vertex.vertex_type.value!r} vertex (uid={vertex.uid!r})"
        )
    if anchor.tree_position is TreePosition.ROOT and vertex.uid != root_uid:
        return (
            f"{attribute.name!r} is {anchor.value}-anchored but declared on a " f"non-root vertex (uid={vertex.uid!r})"
        )
    return None


def _anchor_violation(vertex: Vertex, assignment: AttributeAssignment, root_uid: Uid) -> str | None:
    """Describe how *assignment* violates the anchor invariant on *vertex*, or ``None``.

    ``None`` when *assignment* is outside the vocabulary (non-guffin domain, or a name matching no
    :class:`PublishingSemantics` member) or when *vertex* satisfies the attribute's anchor (see
    :func:`_anchor_mismatch`); otherwise a description naming the attribute, its expected anchor,
    the offending placement, and the vertex uid.

    Args:
        vertex: The vertex the assignment is declared on.
        assignment: The attribute assignment to check.
        root_uid: The uid of the tree's root vertex.

    Returns:
        The violation description, or ``None`` when there is no violation.
    """
    assignment_attribute: Final[Attribute] = assignment.attribute.definition
    if assignment_attribute.domain is not AttributeDomain.GUFFIN:
        return None
    member: Final[PublishingSemantics | None] = _SEMANTICS_BY_NAME.get(assignment_attribute.name)
    if member is None:
        return None
    return _anchor_mismatch(member.value, vertex, root_uid)


@validate_call
def all_attributes_anchored(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every guffin attribute to sit on its anchor.

    Each :class:`PublishingSemantics` member's :class:`PublishingAttribute` carries an :class:`AttributeAnchor`
    naming the :class:`~guffin.model.vertex.VertexType` set and :class:`TreePosition` it attaches
    to; this validator enforces that invariant across *tree*'s render-visible document — the vertices
    returned by :func:`~guffin.model.vertex_tree.transcluded_vertices` (the tree vertices plus
    embed-transcluded content): every guffin-domain assignment whose name is a recognised member must
    be declared on a vertex of one of the anchor's types, at the anchor's tree position (a
    root-positioned anchor accepts only the tree's root vertex).  A vertex reached only by *mention*
    (a page or block reference rendered inline as text) is not part of this document — it carries its
    own foreign page's guffin metadata — and is not checked.
    Default-domain assignments and unrecognised guffin-domain names are outside the vocabulary and
    pass through unchecked.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every recognised guffin attribute is correctly anchored; a
        :class:`~guffin.common.validation.ValidationError` listing every misanchored assignment
        (attribute name, expected anchor, actual vertex type, and vertex uid) otherwise.
    """
    root_uid: Final[Uid] = root_vertex(tree).uid
    violations: Final[list[str]] = [
        violation
        for vertex in transcluded_vertices(tree)
        for assignment in vertex.attribute_assignments or ()
        if (violation := _anchor_violation(vertex, assignment, root_uid)) is not None
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
    value_coercer: Callable[[AttributeAssignment], StructuralElement | Matter | PdfRender | bool | W3cdtfDate],
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
def all_code_language_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``code-language`` values.

    Every :attr:`PublishingSemantics.CODE_LANGUAGE` assignment in *tree* must carry exactly one
    value, and that value must name a language in the canonical vocabulary
    (:mod:`~guffin.common.programming_language`) by name or alias, case-insensitively.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``code-language`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.CODE_LANGUAGE, code_language_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal code-language values: " + "; ".join(violations),
        validator=all_code_language_values_legal,
    )


@validate_call
def all_publish_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``publish`` values.

    Every :attr:`PublishingSemantics.PUBLISH` assignment in *tree* must carry exactly one value,
    and that value must be ``true`` or ``false`` — the authoritative set of legal ``publish``
    values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``publish`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.PUBLISH, publish_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal publish values: " + "; ".join(violations),
        validator=all_publish_values_legal,
    )


@validate_call
def all_date_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``date`` values.

    Every :attr:`PublishingSemantics.DATE` assignment in *tree* must carry exactly one value, and
    that value must be a W3CDTF reduced-precision date — ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``
    — the year-first ISO 8601 profile that publishing metadata conventions build on.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``date`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.DATE, date_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal date values: " + "; ".join(violations),
        validator=all_date_values_legal,
    )


@validate_call
def all_cover_image_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal, resolvable ``cover-image`` values.

    Every :attr:`PublishingSemantics.COVER_IMAGE` assignment in *tree* must carry exactly one
    value; that value must be wholly a Roam block reference ``((<uid>))``; the referenced UID
    must be present in *tree*; and the referenced vertex must be an
    :class:`~guffin.model.vertex.ImageVertex` — the cover must resolve to an actual image.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``cover-image`` value resolves to an image vertex; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = []
    for vertex, assignment in assignments_for(tree, PublishingSemantics.COVER_IMAGE.value):
        try:
            target_uid: Uid = cover_image_of(assignment)
        except ValueError as exc:
            violations.append(f"on vertex uid={vertex.uid!r}: {exc}")
            continue
        target: Vertex | None = tree.uid_map.get(target_uid)
        if target is None:
            violations.append(f"on vertex uid={vertex.uid!r}: references uid={target_uid!r}, absent from the tree")
        elif not isinstance(target, ImageVertex):
            violations.append(
                f"on vertex uid={vertex.uid!r}: references uid={target_uid!r}, "
                f"which is not an image (vertex_type={target.vertex_type})"
            )
    if not violations:
        return None
    return ValidationError(
        message="illegal cover-image values: " + "; ".join(violations),
        validator=all_cover_image_values_legal,
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


type _NumberedHeading = tuple[HeadingVertex, ElementNumber, ElementNumber | None]
"""One numbered render-visible heading: the vertex, its number, and its nearest numbered ancestor's number."""


def _numbered_headings(tree: VertexTree) -> list[_NumberedHeading]:
    """Return every numbered render-visible heading in document order, with its numbered-ancestor context.

    Walks the rendered document pre-order: each vertex's children in order, with an embed's target
    subtree descending at the embed site — so a transcluded heading appears where it renders, and
    the nearest-numbered-ancestor context threads from the embed into the transclusion.  Each
    vertex is visited once (cycles terminate); embed targets absent from
    :attr:`~guffin.model.vertex_tree.VertexTree.uid_map` are skipped.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to walk.

    Returns:
        One :data:`_NumberedHeading` per numbered heading, in document order.
    """
    records: Final[list[_NumberedHeading]] = []
    seen: Final[set[Uid]] = set()
    stack: Final[list[tuple[Vertex, ElementNumber | None]]] = [(root_vertex(tree), None)]
    while stack:
        vertex, ancestor = stack.pop()
        if vertex.uid in seen:
            continue
        seen.add(vertex.uid)
        context: ElementNumber | None = ancestor
        if isinstance(vertex, HeadingVertex) and (number := parse_element_number(vertex.text)) is not None:
            records.append((vertex, number, ancestor))
            context = number
        frames: list[tuple[Vertex, ElementNumber | None]] = [
            (tree.uid_map[uid], context) for uid in vertex.children or () if uid in tree.uid_map
        ]
        if is_embed_vertex(vertex) and vertex.vertex_link.uid in tree.uid_map:
            frames.insert(0, (tree.uid_map[vertex.vertex_link.uid], context))
        stack.extend(reversed(frames))
    return records


@validate_call
def all_element_numbers_well_formed(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every number-shaped heading lead to parse.

    A render-visible heading whose text leads with a number-shaped marker (per
    :func:`~guffin.model.element_number.leads_with_element_number_shape`) must lead with a
    well-formed :class:`~guffin.model.element_number.ElementNumber` — two or more dot-separated
    integers with no leading zeros.  A malformed attempt (``[1]``, ``[1..2]``, ``[01.2]``) is a
    violation rather than silently passing as ordinary text.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every number-shaped heading lead parses; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = [
        f"heading uid={vertex.uid!r} leads with {vertex.text.strip()[:40]!r}, "
        "which is number-shaped but not a well-formed element number"
        for vertex in transcluded_vertices(tree)
        if isinstance(vertex, HeadingVertex)
        and leads_with_element_number_shape(vertex.text)
        and parse_element_number(vertex.text) is None
    ]
    if not violations:
        return None
    return ValidationError(
        message="malformed element numbers: " + "; ".join(violations),
        validator=all_element_numbers_well_formed,
    )


@validate_call
def all_element_numbers_in_headings_only(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring element numbers to appear only on headings.

    An internal element number is legal only as a heading's lead.  A render-visible
    :class:`~guffin.model.vertex.TextVertex` whose text leads with a *dotted* number-shaped marker
    (per :func:`~guffin.model.element_number.leads_with_dotted_element_number_shape`) is a
    violation — the probable authoring mistake of numbering a plain block that should be a
    heading.  The dotted restriction exempts running prose that leads with a bare bracketed
    integer, an ordinary footnote or citation label (``[1] See Letter of …``).  Other vertex
    types carry opaque or quoted content (code, block quotes, callouts) and are not this
    validator's concern.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when no text vertex leads with a dotted number-shaped marker; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = [
        f"text vertex uid={vertex.uid!r} leads with the element-number marker {vertex.text.strip()[:40]!r}"
        for vertex in transcluded_vertices(tree)
        if isinstance(vertex, TextVertex) and leads_with_dotted_element_number_shape(vertex.text)
    ]
    if not violations:
        return None
    return ValidationError(
        message="element numbers outside headings: " + "; ".join(violations),
        validator=all_element_numbers_in_headings_only,
    )


@validate_call
def all_element_number_matters_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every element number's leading segment to name a matter.

    The leading segment classifies the element's :class:`Matter` division per
    :data:`~guffin.model.element_number.MATTER_BY_LEADING_SEGMENT`: 0 front-matter, 1 body-matter,
    2 back-matter.  Any other leading segment is a violation.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every element number's matter is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = [
        f"heading uid={vertex.uid!r}: element number [{number}] has illegal leading segment "
        f"{number.segments[0]}; legal segments are 0 (front-matter), 1 (body-matter), 2 (back-matter)"
        for vertex, number, _ancestor in _numbered_headings(tree)
        if number.matter is None
    ]
    if not violations:
        return None
    return ValidationError(
        message="illegal element-number matters: " + "; ".join(violations),
        validator=all_element_number_matters_legal,
    )


@validate_call
def all_element_number_matters_agree(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring a number's matter to agree with the heading's tags.

    When a numbered heading also resolves a :class:`Matter` division from its
    ``element-type``/``matter`` tags (per :func:`resolved_matter`), the two classifications must
    agree; disagreement is a violation with no silent winner — the author reconciles the number or
    the tags.  A heading carrying only one of the two classifications has nothing to disagree
    with and passes.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every numbered, tagged heading's classifications agree; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = [
        f"heading uid={vertex.uid!r}: element number [{number}] declares {number.matter} "
        f"but its tags resolve to {tag_matter}"
        for vertex, number, _ancestor in _numbered_headings(tree)
        if number.matter is not None
        and (tag_matter := resolved_matter(vertex)) is not None
        and tag_matter is not number.matter
    ]
    if not violations:
        return None
    return ValidationError(
        message="element-number matter disagreements: " + "; ".join(violations),
        validator=all_element_number_matters_agree,
    )


@validate_call
def all_element_numbers_unique(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every element number to appear at most once.

    Each internal element number denotes one document element, so two render-visible headings
    carrying the same number are a violation.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every element number is unique; a
        :class:`~guffin.common.validation.ValidationError` listing every duplicate otherwise.
    """
    by_number: Final[dict[ElementNumber, list[HeadingVertex]]] = {}
    for vertex, number, _ancestor in _numbered_headings(tree):
        by_number.setdefault(number, []).append(vertex)
    violations: Final[list[str]] = [
        f"element number [{number}] appears on {len(vertices)} headings: "
        + ", ".join(f"uid={vertex.uid!r}" for vertex in vertices)
        for number, vertices in by_number.items()
        if len(vertices) > 1
    ]
    if not violations:
        return None
    return ValidationError(
        message="duplicate element numbers: " + "; ".join(violations),
        validator=all_element_numbers_unique,
    )


@validate_call
def all_element_numbers_ordered(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring document order to follow element-number order.

    The numbers are the author's source of truth for the elements' logical order; this validator
    detects *placement drift* — a numbered heading rendering before a lower-numbered one.  Every
    consecutive pair of numbered render-visible headings, in document order (embeds where they
    render), must be strictly increasing.  Unnumbered headings do not participate.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when the numbered headings render in strictly increasing number order; a
        :class:`~guffin.common.validation.ValidationError` listing every out-of-order pair otherwise.
    """
    records: Final[list[_NumberedHeading]] = _numbered_headings(tree)
    violations: Final[list[str]] = [
        f"heading uid={vertex.uid!r} [{number}] renders after uid={prev_vertex.uid!r} [{prev_number}]"
        for (prev_vertex, prev_number, _pa), (vertex, number, _a) in zip(records, records[1:], strict=False)
        if not prev_number < number
    ]
    if not violations:
        return None
    return ValidationError(
        message="element numbers out of document order: " + "; ".join(violations),
        validator=all_element_numbers_ordered,
    )


@validate_call
def all_element_numbers_nested(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring nesting to follow element-number prefixes.

    A numbered heading rendering beneath a numbered ancestor heading must carry the ancestor's
    number as a strict prefix (``[1.2.3]`` under ``[1.2]``) — anything else is placement drift, a
    logically foreign element nested inside the ancestor.  For transcluded content the ancestor
    context threads through the embed site.  A numbered heading with no numbered ancestor is
    unconstrained; heading levels and segment counts are deliberately not compared (the numbering
    is placement-independent).

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every nested number extends its numbered ancestor; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = [
        f"heading uid={vertex.uid!r} [{number}] sits under the numbered ancestor [{ancestor}], "
        "which is not a prefix of it"
        for vertex, number, ancestor in _numbered_headings(tree)
        if ancestor is not None and not ancestor.is_prefix_of(number)
    ]
    if not violations:
        return None
    return ValidationError(
        message="element numbers that break their ancestor nesting: " + "; ".join(violations),
        validator=all_element_numbers_nested,
    )


@validate_call
def validate_semantics(tree: VertexTree) -> ValidationResult:
    """Return a :class:`~guffin.common.validation.ValidationResult` for the vocabulary invariants on *tree*.

    Runs every vocabulary validator — :func:`all_attributes_anchored`,
    :func:`all_element_type_values_legal`, :func:`all_matter_values_legal`,
    :func:`all_pdf_render_values_legal`, :func:`all_publish_values_legal`,
    :func:`all_date_values_legal`, :func:`all_cover_image_values_legal`, and
    :func:`all_matter_tags_at_section_level` — and every internal-element-numbering validator —
    :func:`all_element_numbers_well_formed`, :func:`all_element_numbers_in_headings_only`,
    :func:`all_element_number_matters_legal`, :func:`all_element_number_matters_agree`,
    :func:`all_element_numbers_unique`, :func:`all_element_numbers_ordered`, and
    :func:`all_element_numbers_nested` — via :func:`~guffin.common.validation.validate_all`.  Every
    attribute validator covers both the tree vertices and the referenced-vertex stubs
    (:attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`); the numbering validators cover the
    render-visible vertices (embed-transcluded content included).  All validators run regardless of
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
            all_code_language_values_legal,
            all_publish_values_legal,
            all_date_values_legal,
            all_cover_image_values_legal,
            all_matter_tags_at_section_level,
            all_element_numbers_well_formed,
            all_element_numbers_in_headings_only,
            all_element_number_matters_legal,
            all_element_number_matters_agree,
            all_element_numbers_unique,
            all_element_numbers_ordered,
            all_element_numbers_nested,
        ],
    )
