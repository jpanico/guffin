"""The publishing-semantics vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Constants**: :data:`PDF_RENDER_FALLBACK` — the :class:`PdfRenderPlacement` placement a format falls
  back to when it cannot honour the requested one; :data:`DEFAULT_PUBLISH` — the publication
  state of an untagged vertex.
- **Enumerations**: :class:`PublishingSemantics` — the attributes Guffin recognizes (document metadata +
  the ``element-type``/``matter``/``page-break`` heading tags + the ``pdf-render`` PDF tag + the
  ``publish`` block tag), each member a
  :class:`PublishingAttribute` in the :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`
  domain; :class:`PdfRenderPlacement` — how an embedded PDF asset is placed in output (reproduced at the
  embed or in an appendix, natively or as images; linked as a contained copy or an external URL;
  or named only); :class:`PageBreak` — where a page break is forced relative to the tagged heading
  (``before``).  The anchoring affordances an attribute declares
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
  assignment's value as a :class:`Matter`; :func:`page_break_of` — read a ``page-break``
  assignment's value as a :class:`PageBreak`; :func:`pdf_render_of` — read a ``pdf-render``
  assignment's value as a :class:`PdfRenderPlacement`; :func:`code_language_of` — read a
  ``code-language`` assignment's value as a canonical
  :data:`~guffin.common.programming_language.CodeLanguageId` (any vocabulary name or alias,
  case-insensitively); :func:`code_source_of` — read a ``code-source`` assignment's three
  ordered values (GitHub blob URL, commit SHA, fetch date) as a
  :class:`~guffin.model.code_source.CodeSource`; :func:`publish_of` — read a ``publish``
  assignment's value as a boolean; :func:`date_of` — read a ``date`` assignment's value as a
  parsed :class:`~guffin.common.w3cdtf_date.W3cdtfDate` (``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``);
  :func:`cover_image_of` — read a ``cover-image`` assignment's value as the referenced image
  block's :data:`~guffin.model.primitives.Uid` (the value is a block reference
  ``((<uid>))``); :func:`cover_image_vertex` — resolve a tree's cover to the
  :class:`~guffin.model.vertex.ImageVertex` its root references, tolerating absent or
  unresolvable assignments (``None``, warning);
  :func:`illustrators_of_vertex` — a vertex's declared illustrator names, in source order
  (empty tuple when none);
  :func:`effective_title` — a :class:`~guffin.model.vertex_tree.VertexTree`'s document title,
  derived from its root by a fixed precedence (a root ``title`` assignment, else a page root's
  ``title``, else a basis from the root's own content);
  :func:`find_publishing_attribute` — find a vertex's
  assignment for a :class:`PublishingSemantics` attribute (the Guffin domain supplied automatically);
  :func:`element_type_of_vertex` / :func:`matter_of_vertex` / :func:`page_break_of_vertex` /
  :func:`pdf_render_of_vertex` /
  :func:`code_language_of_vertex` / :func:`code_source_of_vertex` / :func:`publish_of_vertex` —
  resolve a heading's ``element-type`` / bare ``matter`` / ``page-break`` tag, a PDF embed's
  ``pdf-render`` tag (declared on the embed itself or on a standalone-link reference to it), a
  code block's ``code-language`` or ``code-source`` tag,
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
  :func:`drop_page_breaks` — remove every heading's ``page-break`` tag from a
  :class:`~guffin.model.vertex_tree.VertexTree`, so no authored page-break directive is honored;
  :func:`promote_non_body_sections` — promote every root-level heading of explicit
  front/back matter to heading level 1, so a linear rendering cannot nest it under a
  preceding part.

This module sits near the top of the ``model/`` conceptual stack: it may depend on the structural
primitives (:mod:`~guffin.model.attribute`, :mod:`~guffin.model.vertex`,
:mod:`~guffin.model.vertex_tree`), the :mod:`~guffin.model.attribute_anchor` affordances, the
:mod:`~guffin.model.chicago_structure` taxonomy, the :mod:`~guffin.model.code_source` value
model, and the :mod:`~guffin.model.element_number`
numbering primitive, and none of them may depend on it.
"""

import enum
import logging
from typing import Final

import regex
from pydantic import ConfigDict, Field, field_validator, validate_call

from guffin.common.filenames import url_file_name
from guffin.common.programming_language import CodeLanguageId, canonical_language_id
from guffin.common.w3cdtf_date import W3cdtfDate, verified_w3cdtf_date
from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    attribute_value_text,
)
from guffin.model.attribute_anchor import AttributeAnchor
from guffin.model.attribute_assignment import (
    AttributeAssignment,
    is_assignment_for,
    sole_value_text,
    verified_sole_value_text,
    verify_assignment_for,
)
from guffin.model.chicago_structure import Matter, StructuralElement
from guffin.model.code_source import CodeSource
from guffin.model.element_number import stripped_element_number
from guffin.model.primitives import UID_PATTERN, Uid
from guffin.model.vertex import (
    BlockEmbedVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageEmbedVertex,
    PageVertex,
    PdfVertex,
    QuoteBlockVertex,
    TableVertex,
    TextVertex,
    TodoVertex,
    Vertex,
    find_attribute_assignment,
    is_embed_vertex,
)
from guffin.model.vertex_tree import VertexTree, map_vertices, root_vertex, transcluded_vertices

logger = logging.getLogger(__name__)


class PdfRenderPlacement(enum.StrEnum):
    """How an embedded PDF asset is placed in output — the values a ``pdf-render`` tag takes.

    The vocabulary spans the whole space of placements an author might ask for, whether or not a
    given format can honour a given one: two axes for reproducing the document's pages (*where* —
    at the embed or at the back — and *at what fidelity* — the format's own content or page
    images), two for referencing the file instead of reproducing it (a copy carried inside the
    output, or the externally hosted original), one for naming it and nothing more, and one for
    omitting the occurrence entirely.  A format that cannot honour the requested placement falls
    back to :attr:`NAME_ONLY` with a warning rather than silently choosing something else — the
    author asks, and is told when the answer is no.

    Attributes:
        INLINE_NATIVE: The PDF's pages are reproduced at the embed, as the output format's own
            content.
        INLINE_IMAGE: The PDF's pages are reproduced at the embed, as images.
        APPENDIX_NATIVE: The PDF's pages are reproduced in an appendix at the back, linked from
            the embed, as the output format's own content.
        APPENDIX_IMAGE: The PDF's pages are reproduced in an appendix at the back, linked from
            the embed, as images.
        INTERNAL_LINK: The PDF file itself travels inside the output document, and the embed
            links to that contained copy.
        EXTERNAL_LINK: The embed links to the PDF where it is hosted, outside the output
            document, by ordinary URL.
        NAME_ONLY: The PDF is named in the text; it is neither reproduced nor linked.  The
            universal fallback, since every format can name a file.
        STRIP: The occurrence is omitted entirely — no pages, no link, no name; the output reads
            as though the embed were absent.
    """

    INLINE_NATIVE = "inline-native"
    INLINE_IMAGE = "inline-image"
    APPENDIX_NATIVE = "appendix-native"
    APPENDIX_IMAGE = "appendix-image"
    INTERNAL_LINK = "internal-link"
    EXTERNAL_LINK = "external-link"
    NAME_ONLY = "name-only"
    STRIP = "strip"


PDF_RENDER_FALLBACK: Final[PdfRenderPlacement] = PdfRenderPlacement.NAME_ONLY
"""The placement a format falls back to when it cannot honour the one an author asked for.

Deliberately a single fixed member rather than a ranked chain: a chain would have Guffin choose
which unasked-for placement is *closest* to the request, and that judgment is the author's to
make.  Every fallback is logged as a warning, so a request that could not be met is never silent.
"""


class PageBreak(enum.StrEnum):
    """Where a page break is forced relative to the tagged heading — the values a ``page-break`` tag takes.

    A directive about paginated output only; a format without pages expresses it as nothing.
    An untagged heading forces no break — there is no default member.

    Attributes:
        BEFORE: The tagged heading opens on a new page.
    """

    BEFORE = "before"


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
      :class:`Matter` division directly, for a bespoke section with no specific element type;
      :attr:`PAGE_BREAK` forces a :class:`PageBreak` in paginated output.
    - **PDF tags** (:attr:`AttributeAnchor.PDF`) — applied to an individual embedded PDF asset,
      directly or at a standalone-link reference site (the pdf anchor sees through standalone
      vertex links, so a reference to a PDF living on another page can be tagged where it is
      displayed): :attr:`PDF_RENDER` declares its :class:`PdfRenderPlacement` placement in paginated
      output.
    - **Code-block tags** (:attr:`AttributeAnchor.CODE_BLOCK`) — applied to an individual fenced
      code listing: :attr:`CODE_LANGUAGE` declares the listing's language, overriding whatever
      language the source's fence records.
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
        COVER_IMAGE: The work's cover image — the value is a block reference
            ``((<uid>))`` to an image block, keeping the cover ordinary, reusable graph content.
        ELEMENT_TYPE: Tags a heading with its :class:`StructuralElement` (the book part it is).
        MATTER: Tags a heading with its :class:`Matter` division (for a section with no element type).
        PAGE_BREAK: Tags a heading with a forced :class:`PageBreak` in paginated output
            (``before`` opens the heading on a new page).
        PDF_RENDER: Tags an embedded PDF with its :class:`PdfRenderPlacement` placement (inline pages vs a
            link); declared on the embed itself or on a standalone-link reference to it (the
            reference site's tag governing that reference).
        CODE_LANGUAGE: Tags a fenced code listing with its language — any name or alias of the
            canonical vocabulary (:mod:`~guffin.common.programming_language`) — overriding the
            language the source's fence records (a source's own language set may lack e.g. Fortran).
        CODE_SOURCE: Tags a fenced code listing with the provenance of its content — three
            ordered values: the GitHub blob URL naming its source, the full commit SHA
            actually fetched, and the fetch date (see
            :class:`~guffin.model.code_source.CodeSource`).
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
    PAGE_BREAK = PublishingAttribute(name="page-break", anchor=AttributeAnchor.HEADING)
    PDF_RENDER = PublishingAttribute(name="pdf-render", anchor=AttributeAnchor.PDF)
    CODE_LANGUAGE = PublishingAttribute(name="code-language", anchor=AttributeAnchor.CODE_BLOCK)
    CODE_SOURCE = PublishingAttribute(name="code-source", anchor=AttributeAnchor.CODE_BLOCK)
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
def page_break_of(assignment: AttributeAssignment) -> PageBreak:
    """Return the :class:`PageBreak` that a ``page-break`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.PAGE_BREAK` attribute, then coerces
    its sole value to a :class:`PageBreak` (``before``).

    Args:
        assignment: A :attr:`PublishingSemantics.PAGE_BREAK` attribute assignment (one value expected).

    Returns:
        The named :class:`PageBreak`.

    Raises:
        ValueError: If *assignment* is not for the ``page-break`` attribute, does not carry exactly
            one value, or its value is not a recognised :class:`PageBreak`.
    """
    return PageBreak(verified_sole_value_text(assignment, PublishingSemantics.PAGE_BREAK.value))


@validate_call
def pdf_render_of(assignment: AttributeAssignment) -> PdfRenderPlacement:
    """Return the :class:`PdfRenderPlacement` placement that a ``pdf-render`` assignment names.

    Verifies *assignment* is for the :attr:`PublishingSemantics.PDF_RENDER` attribute, then coerces
    its sole value to a :class:`PdfRenderPlacement` (``inline`` / ``link``).

    Args:
        assignment: A :attr:`PublishingSemantics.PDF_RENDER` attribute assignment (one value expected).

    Returns:
        The named :class:`PdfRenderPlacement`.

    Raises:
        ValueError: If *assignment* is not for the ``pdf-render`` attribute, does not carry exactly
            one value, or its value is not a recognised :class:`PdfRenderPlacement`.
    """
    return PdfRenderPlacement(verified_sole_value_text(assignment, PublishingSemantics.PDF_RENDER.value))


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
def code_source_of(assignment: AttributeAssignment) -> CodeSource:
    """Return the :class:`~guffin.model.code_source.CodeSource` that a ``code-source`` assignment describes.

    Verifies *assignment* is for the :attr:`PublishingSemantics.CODE_SOURCE` attribute, then reads
    its three ordered values — the GitHub blob URL naming the source, the full 40-hex
    commit SHA actually fetched, and the full-precision fetch date — into a
    :class:`~guffin.model.code_source.CodeSource`.

    Args:
        assignment: A :attr:`PublishingSemantics.CODE_SOURCE` attribute assignment (three ordered
            values expected: url, commit sha, fetched date).

    Returns:
        The described :class:`~guffin.model.code_source.CodeSource`.

    Raises:
        ValueError: If *assignment* is not for the ``code-source`` attribute, does not carry
            exactly three values, or any value is illegal — an unparseable GitHub blob URL, a
            SHA that is not full 40-hex, or a date not at full ``YYYY-MM-DD`` precision.
    """
    verify_assignment_for(assignment, PublishingSemantics.CODE_SOURCE.value)
    if len(assignment.values) != 3:
        raise ValueError(f"code-source expects 3 values (url, commit sha, fetched date); got {len(assignment.values)}")
    url_text, sha_text, date_text = (attribute_value_text(value) for value in assignment.values)
    return CodeSource.model_validate({"url": url_text, "commit_sha": sha_text, "fetched_date": date_text})


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
    """Return the :class:`~guffin.common.w3cdtf_date.W3cdtfDate` that a ``date`` assignment carries.

    Verifies *assignment* is for the :attr:`PublishingSemantics.DATE` attribute, then parses its
    sole value as a W3CDTF reduced-precision date — ``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``
    (year first), with a real calendar month and day when present — via
    :func:`~guffin.common.w3cdtf_date.verified_w3cdtf_date`.

    Args:
        assignment: A :attr:`PublishingSemantics.DATE` attribute assignment (one value expected).

    Returns:
        The assignment's value as a parsed :class:`~guffin.common.w3cdtf_date.W3cdtfDate`.

    Raises:
        ValueError: If *assignment* is not for the ``date`` attribute, does not carry exactly one
            value, or its value is not a W3CDTF reduced-precision date (wrong shape, month outside
            1–12, or a day invalid for its month).
    """
    return verified_w3cdtf_date(verified_sole_value_text(assignment, PublishingSemantics.DATE.value))


_BLOCK_REF_VALUE_RE: Final[regex.Pattern[str]] = regex.compile(rf"\(\((?P<uid>{UID_PATTERN})\)\)")
"""A block reference ``((<uid>))`` as an attribute-value token (fullmatch-anchored at use).

Built from the model's own :data:`~guffin.model.primitives.UID_PATTERN`, so the vocabulary stays
free of any source-package dependency.
"""


@validate_call
def cover_image_of(assignment: AttributeAssignment) -> Uid:
    """Return the UID of the image block that a ``cover-image`` assignment references.

    Verifies *assignment* is for the :attr:`PublishingSemantics.COVER_IMAGE` attribute, then
    coerces its sole value to the referenced block's UID: the value must be wholly a block
    reference ``((<uid>))`` pointing at an image block.  Referencing a block (rather than
    carrying a raw image URL) keeps the cover an ordinary piece of graph content — reusable,
    and editable in place.

    Args:
        assignment: A :attr:`PublishingSemantics.COVER_IMAGE` attribute assignment (one value
            expected).

    Returns:
        The referenced block's UID.  Whether that block is actually an image vertex present in
        the tree is a tree-level question (see :func:`cover_image_vertex`).

    Raises:
        ValueError: If *assignment* is not for the ``cover-image`` attribute, does not carry
            exactly one value, or its value is not wholly a block reference.
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
def page_break_of_vertex(vertex: HeadingVertex) -> PageBreak | None:
    """Resolve *vertex*'s ``page-break`` tag to a :class:`PageBreak`, or ``None``.

    ``None`` when *vertex* carries no ``page-break`` assignment, or when the assignment does not
    coerce to a :class:`PageBreak` (ignored with a warning).  An untagged heading forces no
    page break.

    Args:
        vertex: The heading vertex whose tag to resolve.

    Returns:
        The named :class:`PageBreak`, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.PAGE_BREAK)
    if assignment is None:
        return None
    try:
        return page_break_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring page-break on vertex uid=%r: %s", vertex.uid, exc)
        return None


@validate_call
def pdf_render_of_vertex(vertex: Vertex) -> PdfRenderPlacement | None:
    """Resolve *vertex*'s ``pdf-render`` tag to a :class:`PdfRenderPlacement`, or ``None``.

    The host may be the PDF embed itself, or — per the pdf anchor's
    :attr:`~guffin.model.attribute_anchor.AttributeAnchor.through_standalone_links` affordance — a
    vertex whose standalone vertex link references a PDF embed, tagging that embed at its
    reference site.  ``None`` when *vertex* carries no ``pdf-render`` assignment, or when the
    assignment does not coerce to a :class:`PdfRenderPlacement` (ignored with a warning).  An untagged
    embed's placement is :data:`DEFAULT_PDF_RENDER`.

    Args:
        vertex: The vertex whose tag to resolve.

    Returns:
        The named :class:`PdfRenderPlacement`, or ``None``.
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
    block's language is whatever the source's fence records.

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
def code_source_of_vertex(vertex: CodeBlockVertex) -> CodeSource | None:
    """Resolve *vertex*'s ``code-source`` tag to its :class:`~guffin.model.code_source.CodeSource`, or ``None``.

    ``None`` when *vertex* carries no ``code-source`` assignment, or when the assignment does
    not describe a legal source reference (ignored with a warning).  An untagged code block's
    content simply has no recorded provenance.

    Args:
        vertex: The code-block vertex whose tag to resolve.

    Returns:
        The described :class:`~guffin.model.code_source.CodeSource`, or ``None``.
    """
    assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.CODE_SOURCE)
    if assignment is None:
        return None
    try:
        return code_source_of(assignment)
    except ValueError as exc:
        logger.warning("ignoring code-source on vertex uid=%r: %s", vertex.uid, exc)
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


def _vertex_effective_title(vertex: Vertex, tree: VertexTree) -> str:
    """Return the effective title contributed by *vertex* (see :func:`effective_title`).

    A :attr:`PublishingSemantics.TITLE` assignment on *vertex* takes precedence; otherwise the
    title is drawn from the vertex's type.  For an :data:`~guffin.model.vertex.EmbedVertex` (block
    or page embed), recurses into the transcluded target resolved through *tree*'s ``uid_map``.
    """
    title_assignment: Final[AttributeAssignment | None] = find_publishing_attribute(vertex, PublishingSemantics.TITLE)
    if title_assignment is not None:
        return sole_value_text(title_assignment)
    match vertex:
        case PageVertex():
            return vertex.title
        case HeadingVertex() | TextVertex() | TodoVertex():
            return vertex.text
        case QuoteBlockVertex():
            return vertex.quote
        case ImageVertex():
            return vertex.alt_text or url_file_name(vertex.source) or str(vertex.source)
        case PdfVertex():
            return url_file_name(vertex.source) or str(vertex.source)
        case CalloutVertex():
            return vertex.title or vertex.body
        case CodeBlockVertex():
            return vertex.code
        case TableVertex():
            return "_".join(vertex.table.rows[0])
        case BlockEmbedVertex() | PageEmbedVertex():
            return _vertex_effective_title(tree.uid_map[vertex.vertex_link.uid], tree)


@validate_call
def effective_title(tree: VertexTree) -> str:
    """Return the effective document title of *tree*, derived from its root vertex.

    A :class:`~guffin.model.vertex_tree.VertexTree` always has a title, whatever its root's type.
    It is resolved by a fixed precedence:

    1. a :attr:`PublishingSemantics.TITLE` assignment on the root — its sole value's text (an
       author's explicit title, overriding everything below);
    2. otherwise, if the root is a :class:`~guffin.model.vertex.PageVertex`, its ``title``;
    3. otherwise, a basis drawn from the root's own content by type — block text, image
       alt-text/filename/source, callout title-or-body, code, or the first table row's cells
       joined by ``_`` — and, for an :data:`~guffin.model.vertex.EmbedVertex`, the effective
       title of the transcluded target.

    The returned text is raw: links are not unwrapped and length is not clipped, so a consumer
    that needs a filename or rendered inlines applies its own transform.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` whose title to derive.

    Returns:
        The effective title text.
    """
    return _vertex_effective_title(root_vertex(tree), tree)


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


@validate_call
def drop_page_breaks(tree: VertexTree) -> VertexTree:
    """Return a new :class:`~guffin.model.vertex_tree.VertexTree` with every heading's ``page-break`` tag removed.

    Each :class:`~guffin.model.vertex.HeadingVertex` — tree and referenced vertices alike, so
    embed-transcluded headings are covered — has its :attr:`PublishingSemantics.PAGE_BREAK`
    assignment removed, so no authored page-break directive remains to be honored; each removal
    is logged as a warning.  Headings with no such tag and every other vertex type pass through
    unchanged, and the original *tree* is not modified.

    Args:
        tree: The source :class:`~guffin.model.vertex_tree.VertexTree`.

    Returns:
        A new :class:`~guffin.model.vertex_tree.VertexTree` whose headings carry no ``page-break``
        tags.
    """

    def _drop(vertex: Vertex) -> Vertex:
        if not isinstance(vertex, HeadingVertex) or not vertex.attribute_assignments:
            return vertex
        kept: Final[list[AttributeAssignment]] = [
            assignment
            for assignment in vertex.attribute_assignments
            if not is_assignment_for(assignment, PublishingSemantics.PAGE_BREAK.value)
        ]
        if len(kept) == len(vertex.attribute_assignments):
            return vertex
        logger.warning(
            "dropping page-break tag on heading uid=%r: authored page breaks are not honored here", vertex.uid
        )
        return vertex.model_copy(update={"attribute_assignments": kept})

    return map_vertices(tree, _drop)


@validate_call
def promote_non_body_sections(tree: VertexTree) -> VertexTree:
    """Return a new :class:`~guffin.model.vertex_tree.VertexTree` with root-level non-body sections at heading level 1.

    Promotes every :class:`~guffin.model.vertex.HeadingVertex` that is (a) a **direct child of
    the root vertex** and (b) **explicitly non-body matter** (its :func:`resolved_matter` is
    :attr:`~guffin.model.chicago_structure.Matter.FRONT` or
    :attr:`~guffin.model.chicago_structure.Matter.BACK`) to ``heading_level`` 1.  Per CMOS, such
    sections stand outside every part — but a rendered document is a linear stream whose tables
    of contents nest by heading level alone, so a chapter-leveled section following a part would
    otherwise be adopted by it.  The two conditions keep the rule conservative: a non-body
    section genuinely nested *inside* a part is left alone (the hierarchy says it belongs
    there), as is an untagged or body-matter root child.  The original *tree* is not modified.

    Args:
        tree: The source :class:`~guffin.model.vertex_tree.VertexTree`.

    Returns:
        A new :class:`~guffin.model.vertex_tree.VertexTree` with the qualifying sections at
        heading level 1; *tree* unchanged in content when none qualify.
    """
    root: Final[Vertex] = root_vertex(tree)
    promoted_uids: Final[set[Uid]] = set()
    for child_uid in root.children or []:
        child: Vertex | None = tree.uid_map.get(child_uid)
        if not isinstance(child, HeadingVertex) or child.heading_level == 1:
            continue
        if resolved_matter(child) not in (Matter.FRONT, Matter.BACK):
            continue
        promoted_uids.add(child.uid)
    if not promoted_uids:
        return tree

    def _promote(vertex: Vertex) -> Vertex:
        if vertex.uid not in promoted_uids:
            return vertex
        return vertex.model_copy(update={"heading_level": 1})

    return map_vertices(tree, _promote)
