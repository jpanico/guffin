"""Validation of the publishing-semantics vocabulary — every invariant checked over a tree.

Public symbols:

- **Functions**: the vocabulary :data:`~guffin.common.validation.Validator` functions
  :func:`all_attributes_anchored` (every recognised guffin attribute satisfies its
  :class:`~guffin.model.attribute_anchor.AttributeAnchor` — one of its vertex types, at its tree
  position), :func:`all_element_type_values_legal` (every ``element-type`` value is a
  :class:`~guffin.model.chicago_structure.StructuralElement`), :func:`all_matter_values_legal`
  (every ``matter`` value is a :class:`~guffin.model.chicago_structure.Matter`),
  :func:`all_page_break_values_legal` (every ``page-break`` value is a
  :class:`~guffin.model.publishing_semantics.PageBreak`),
  :func:`all_pdf_render_values_legal` (every ``pdf-render`` value is a
  :class:`~guffin.model.publishing_semantics.PdfRenderPlacement`), :func:`all_code_language_values_legal`
  (every ``code-language`` value names a language in the canonical vocabulary),
  :func:`all_code_source_values_legal` (every ``code-source`` value is a legal URL/SHA/date
  triple), :func:`all_publish_values_legal` (every ``publish`` value is a boolean literal),
  :func:`all_date_values_legal` (every ``date`` value is a W3CDTF reduced-precision date),
  :func:`all_cover_image_values_legal` (every ``cover-image`` value is a block reference
  resolving to an image vertex in the tree), and :func:`all_matter_tags_at_section_level`
  (every ``matter`` tag sits at the book's section level — level 1, or level 2 in a parts book);
  the internal-element-numbering :data:`~guffin.common.validation.Validator` functions over the
  render-visible headings (see :mod:`~guffin.model.element_number` — the numbers are the author's
  source of truth for the elements' logical order, and validation detects placement drift):
  :func:`all_element_numbers_well_formed` (a number-shaped heading lead must parse as a
  well-formed element number), :func:`all_element_numbers_in_headings_only` (no number-shaped
  lead on a text vertex), :func:`all_element_number_matters_legal` (every leading segment names a
  :class:`~guffin.model.chicago_structure.Matter`), :func:`all_element_number_matters_agree` (a
  number's matter agrees with the heading's resolved tags), :func:`all_element_numbers_unique`
  (no duplicates), :func:`all_element_numbers_ordered` (document order is strictly increasing
  number order), and :func:`all_element_numbers_nested` (a number under a numbered ancestor
  extends it as a strict prefix);
  :func:`validate_semantics` — run every vocabulary validator over a
  :class:`~guffin.model.vertex_tree.VertexTree`, accumulating a
  :class:`~guffin.common.validation.ValidationResult`.

This module sits at the very top of the ``model/`` conceptual stack, directly above
:mod:`~guffin.model.publishing_semantics`: it judges a tree against the vocabulary that module
defines — its attribute members, strict value readers, and tree queries — so it may depend on
the vocabulary and on everything the vocabulary may depend on, and nothing in ``model/`` may
depend on it.
"""

from collections.abc import Callable
from typing import Final

from pydantic import validate_call

from guffin.common.programming_language import CodeLanguageId
from guffin.common.validation import ValidationError, ValidationResult, validate_all
from guffin.common.w3cdtf_date import W3cdtfDate
from guffin.model.attribute import Attribute, AttributeDomain
from guffin.model.attribute_anchor import AttributeAnchor, TreePosition
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.chicago_structure import Matter, StructuralElement
from guffin.model.code_source import CodeSource
from guffin.model.element_number import (
    ElementNumber,
    leads_with_dotted_element_number_shape,
    leads_with_element_number_shape,
    parse_element_number,
)
from guffin.model.primitives import Uid
from guffin.model.publishing_semantics import (
    PageBreak,
    PdfRenderPlacement,
    PublishingAttribute,
    PublishingSemantics,
    code_language_of,
    code_source_of,
    cover_image_of,
    date_of,
    element_type_of,
    has_parts,
    matter_of,
    page_break_of,
    pdf_render_of,
    publish_of,
    resolved_matter,
)
from guffin.model.vertex import HeadingVertex, ImageVertex, TextVertex, Vertex, is_embed_vertex
from guffin.model.vertex_tree import (
    VertexTree,
    assignments_for,
    root_vertex,
    standalone_link_target,
    transcluded_vertices,
)

_SEMANTICS_BY_NAME: Final[dict[str, PublishingSemantics]] = {
    member.value.name: member for member in PublishingSemantics
}
"""Maps each recognised guffin attribute name to its :class:`PublishingSemantics` member."""


def _satisfies_type_through_link(anchor: AttributeAnchor, vertex: Vertex, tree: VertexTree) -> bool:
    """Return whether *vertex* satisfies *anchor*'s type constraint through its standalone vertex link.

    Only an anchor declaring :attr:`~AttributeAnchor.through_standalone_links` may be satisfied this
    way: *vertex* must be a standalone vertex link (per
    :func:`~guffin.model.vertex_tree.standalone_link_target`) whose target's type is among the
    anchor's :attr:`~AttributeAnchor.vertex_types` — the attribute then tags the referenced vertex
    at its reference site.

    Args:
        anchor: The anchor whose type constraint to check.
        vertex: The vertex the attribute is declared on.
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` resolving the link target.

    Returns:
        ``True`` when the anchor sees through standalone links and *vertex*'s link target
        satisfies the type constraint, else ``False``.
    """
    if not anchor.through_standalone_links:
        return False
    target: Final[Vertex | None] = standalone_link_target(vertex, tree)
    return target is not None and target.vertex_type in anchor.vertex_types


def _anchor_mismatch(attribute: PublishingAttribute, vertex: Vertex, root_uid: Uid, tree: VertexTree) -> str | None:
    """Describe how *vertex* fails *attribute*'s anchor, or ``None`` when it satisfies it.

    A host vertex must satisfy every anchor axis: its type must be among the anchor's
    :attr:`~AttributeAnchor.vertex_types` (or, for an anchor declaring
    :attr:`~AttributeAnchor.through_standalone_links`, its standalone vertex link must resolve to
    such a vertex — see :func:`_satisfies_type_through_link`), and its position must match the
    anchor's :attr:`~AttributeAnchor.tree_position` (:attr:`TreePosition.ROOT` requires the vertex
    to be the tree's root, identified by *root_uid*).

    Args:
        attribute: The publishing attribute whose anchor to check.
        vertex: The vertex the attribute is declared on.
        root_uid: The uid of the tree's root vertex.
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` resolving standalone link targets.

    Returns:
        The mismatch description, or ``None`` when *vertex* satisfies the anchor.
    """
    anchor: Final[AttributeAnchor] = attribute.anchor
    if vertex.vertex_type not in anchor.vertex_types and not _satisfies_type_through_link(anchor, vertex, tree):
        return (
            f"{attribute.name!r} is {anchor.value}-anchored but declared on a "
            f"{vertex.vertex_type.value!r} vertex (uid={vertex.uid!r})"
        )
    if anchor.tree_position is TreePosition.ROOT and vertex.uid != root_uid:
        return (
            f"{attribute.name!r} is {anchor.value}-anchored but declared on a " f"non-root vertex (uid={vertex.uid!r})"
        )
    return None


def _anchor_violation(vertex: Vertex, assignment: AttributeAssignment, root_uid: Uid, tree: VertexTree) -> str | None:
    """Describe how *assignment* violates the anchor invariant on *vertex*, or ``None``.

    ``None`` when *assignment* is outside the vocabulary (non-guffin domain, or a name matching no
    :class:`PublishingSemantics` member) or when *vertex* satisfies the attribute's anchor (see
    :func:`_anchor_mismatch`); otherwise a description naming the attribute, its expected anchor,
    the offending placement, and the vertex uid.

    Args:
        vertex: The vertex the assignment is declared on.
        assignment: The attribute assignment to check.
        root_uid: The uid of the tree's root vertex.
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` resolving standalone link targets.

    Returns:
        The violation description, or ``None`` when there is no violation.
    """
    assignment_attribute: Final[Attribute] = assignment.attribute.definition
    if assignment_attribute.domain is not AttributeDomain.GUFFIN:
        return None
    member: Final[PublishingSemantics | None] = _SEMANTICS_BY_NAME.get(assignment_attribute.name)
    if member is None:
        return None
    return _anchor_mismatch(member.value, vertex, root_uid, tree)


@validate_call
def all_attributes_anchored(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring every guffin attribute to sit on its anchor.

    Each :class:`PublishingSemantics` member's :class:`PublishingAttribute` carries an :class:`AttributeAnchor`
    naming the :class:`~guffin.model.vertex.VertexType` set and :class:`TreePosition` it attaches
    to; this validator enforces that invariant across *tree*'s render-visible document — the vertices
    returned by :func:`~guffin.model.vertex_tree.transcluded_vertices` (the tree vertices plus
    embed-transcluded content): every guffin-domain assignment whose name is a recognised member must
    be declared on a vertex of one of the anchor's types, at the anchor's tree position (a
    root-positioned anchor accepts only the tree's root vertex).  An anchor declaring
    :attr:`~AttributeAnchor.through_standalone_links` (the pdf anchor) also accepts a host whose
    standalone vertex link resolves to a vertex of the anchor's types — the attribute tags the
    referenced vertex at its reference site.  A vertex reached only by *mention*
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
        if (violation := _anchor_violation(vertex, assignment, root_uid, tree)) is not None
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
    value_coercer: Callable[
        [AttributeAssignment],
        StructuralElement | Matter | PageBreak | PdfRenderPlacement | bool | W3cdtfDate | CodeLanguageId | CodeSource,
    ],
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
def all_page_break_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``page-break`` values.

    Every :attr:`PublishingSemantics.PAGE_BREAK` assignment in *tree* must carry exactly one
    value, and that value must name a :class:`PageBreak` member — the authoritative set of legal
    ``page-break`` values.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``page-break`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.PAGE_BREAK, page_break_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal page-break values: " + "; ".join(violations),
        validator=all_page_break_values_legal,
    )


@validate_call
def all_pdf_render_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``pdf-render`` values.

    Every :attr:`PublishingSemantics.PDF_RENDER` assignment in *tree* must carry exactly one value,
    and that value must name a :class:`PdfRenderPlacement` member — the authoritative set of legal
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
def all_code_source_values_legal(tree: VertexTree) -> ValidationError | None:
    """:data:`~guffin.common.validation.Validator` requiring legal ``code-source`` values.

    Every :attr:`PublishingSemantics.CODE_SOURCE` assignment in *tree* must carry exactly three
    ordered values — a parseable ``github.com`` blob URL, a full 40-hex commit SHA,
    and a fetch date at full ``YYYY-MM-DD`` precision (see
    :class:`~guffin.model.code_source.CodeSource`).

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to validate.

    Returns:
        ``None`` when every ``code-source`` value is legal; a
        :class:`~guffin.common.validation.ValidationError` listing every violation otherwise.
    """
    violations: Final[list[str]] = _illegal_value_violations(tree, PublishingSemantics.CODE_SOURCE, code_source_of)
    if not violations:
        return None
    return ValidationError(
        message="illegal code-source values: " + "; ".join(violations),
        validator=all_code_source_values_legal,
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
    value; that value must be wholly a block reference ``((<uid>))``; the referenced UID
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
    :func:`all_page_break_values_legal`,
    :func:`all_pdf_render_values_legal`, :func:`all_code_source_values_legal`,
    :func:`all_publish_values_legal`,
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
            all_page_break_values_legal,
            all_pdf_render_values_legal,
            all_code_language_values_legal,
            all_code_source_values_legal,
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
