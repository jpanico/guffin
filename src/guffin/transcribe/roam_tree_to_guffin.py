"""Transcribe a Roam `NodeTree` into the guffin render model.

The two `NodeTree`-rooted transformations here are the content and presentation facets of a
:class:`~guffin.model.render_bundle.RenderBundle`: :func:`transcribe` derives the
:class:`~guffin.model.vertex_tree.VertexTree` content, and :func:`build_view_map` derives the
:data:`~guffin.model.vertex_view.ViewMap` presentation overlay; :func:`to_render_bundle` bundles both.

Public symbols:

- :data:`SHOULD_NORMALIZE_HEADING_LEVELS` — whether heading levels should be
  normalized during transcription.
- :data:`SEMANTIC_BY_BULLET_TYPE` — member-keyed map from a Better Bullets kind to the
  :class:`~guffin.model.vertex_view.Semantic` it declares.
- :data:`SOURCE_CHANNEL_BY_PROVENANCE` — member-keyed map from a Better Bullets provenance to
  the :class:`~guffin.model.vertex_view.SourceChannel` it declares.
- :data:`TODO_STATE_BY_ROAM_STATE` — member-keyed map from a Roam TODO marker state to the
  :class:`~guffin.model.vertex.TodoState` it declares.
- :func:`vertex_type` — classify a :class:`~guffin.roam.node.RoamNode` into a
  :class:`~guffin.vertex.VertexType`.
- :func:`to_page_vertex` — build a :class:`~guffin.vertex.PageVertex` from a
  page node.
- :func:`to_image_vertex` — build an :class:`~guffin.vertex.ImageVertex` from a
  Firebase Storage image block node.
- :func:`to_pdf_vertex` — build a :class:`~guffin.vertex.PdfVertex` from a
  Firebase Storage PDF block node.
- :func:`to_asset_vertex` — build an :class:`~guffin.vertex.AssetVertex` from a
  bare Firebase Storage asset block node.
- :func:`to_heading_vertex` — build a :class:`~guffin.vertex.HeadingVertex` from
  a heading block node.
- :func:`to_text_vertex` — build a
  :class:`~guffin.vertex.TextVertex` from a plain text block node.
- :func:`to_todo_vertex` — build a :class:`~guffin.model.vertex.TodoVertex` from a
  TODO item block node.
- :func:`to_callout_vertex` — build a :class:`~guffin.vertex.CalloutVertex` from a
  callout block node.
- :func:`to_code_block_vertex` — build a :class:`~guffin.vertex.CodeBlockVertex` from a
  fenced code block node.
- :func:`to_quote_block_vertex` — build a :class:`~guffin.vertex.QuoteBlockVertex` from a
  block-quote node.
- :func:`to_block_embed_vertex` — build a :class:`~guffin.vertex.BlockEmbedVertex` from a
  block embed node.
- :func:`to_page_embed_vertex` — build a :class:`~guffin.vertex.PageEmbedVertex` from a
  page embed node.
- :func:`to_table_vertex` — build a :class:`~guffin.vertex.TableVertex` from a native table node
  (via :func:`~guffin.roam.node_tree.to_table` + Markdown normalization), returning it together
  with the IDs of all consumed descendant nodes.
- :func:`transcribe_standalone_node` — transcribe a :class:`~guffin.roam.node.RoamNode` into
  the appropriate :data:`~guffin.vertex.Vertex` subtype.
- :func:`transcribe` — transcribe all nodes in a :class:`~guffin.roam.node_tree.NodeTree`
  into a :class:`~guffin.vertex_tree.VertexTree`.
- :func:`build_view_map` — derive the presentation :data:`~guffin.model.vertex_view.ViewMap` for a
  :class:`~guffin.roam.node_tree.NodeTree`.
- :func:`to_render_bundle` — bundle :func:`transcribe` and :func:`build_view_map` into a
  :class:`~guffin.model.render_bundle.RenderBundle`.
"""

import logging
from collections.abc import Mapping
from itertools import chain
from typing import Final, assert_never

import regex
from pydantic import HttpUrl, TypeAdapter, validate_call

from guffin.common.filenames import url_file_name
from guffin.common.geometry import ImageSize
from guffin.common.markdown import FencedCodeBlock, HeadingLevel, parse_fenced_code_block
from guffin.common.media_type import MediaType
from guffin.common.programming_language import CodeLanguageId
from guffin.common.table import Table, TableStyle
from guffin.model.asset_storage import AssetStorage, StoreType
from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    AttributeInstance,
    AttributeValue,
    LiteralValue,
    ReferenceValue,
)
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.code_source import CodeSource
from guffin.model.publishing_semantics import code_language_of_vertex, code_source_of_vertex
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import (
    AssetVertex,
    BlockEmbedVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageEmbedVertex,
    PageVertex,
    PdfVertex,
    QuoteBlockVertex,
    QuoteType,
    TableVertex,
    TextVertex,
    TodoState,
    TodoVertex,
    Vertex,
    VertexChildren,
    VertexRefs,
    VertexType,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, Semantic, SourceChannel, VertexView, ViewMap
from guffin.roam.better_bullet import BetterBulletProvenance, BetterBulletType
from guffin.roam.blockquote import (
    RoamCallout,
    parse_callout,
    parse_pull_quote,
    strip_block_quote_marker,
)
from guffin.roam.code_language import CodeLanguage, canonical_id_for
from guffin.roam.markdown import (
    ATTRIBUTE_ASSIGNMENT_RE,
    BLOCK_EMBED_RE,
    FIREBASE_STORAGE_URL_RE,
    PAGE_EMBED_RE,
    TAG_RE,
    image_link_alt_text,
    image_link_url,
    pdf_embed_url,
)
from guffin.roam.node import (
    NodeType,
    RoamNode,
    better_bullet_provenance,
    better_bullet_type,
    effective_heading_level,
    image_size,
    node_type,
)
from guffin.roam.node_network import min_effective_heading_level
from guffin.roam.node_tree import NodeTree, to_table
from guffin.roam.primitives import Id, Uid, parse_daily_note_uid
from guffin.roam.todo import RoamTodo, parse_todo
from guffin.roam.todo import TodoState as RoamTodoState
from guffin.transcribe.roam_md_to_pandoc_md import to_pandoc_md

logger = logging.getLogger(__name__)

SHOULD_NORMALIZE_HEADING_LEVELS: Final[bool] = True
"""Whether heading levels should be normalized during transcription."""

_url_adapter: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating and coercing URL strings to :class:`~pydantic.HttpUrl`."""

_META_BLOCK_RE: Final[regex.Pattern[str]] = regex.compile(r"^(?P<domain>[^\s:]+)-meta::")
"""Matches a Guffin ``<domain>-meta::`` container block.

The block's children are folded onto the parent vertex's ``attribute_assignments`` (with
``domain=<domain>``); the right-hand side after ``::`` (typically the ``#.rm-g`` styling hook) is
ignored.  Anchored at the start so ``domain`` captures the prefix before ``-meta::``.
"""


def _resolve_children(node: RoamNode, id_map: dict[Id, RoamNode]) -> VertexChildren | None:
    """Return an ordered list of child UIDs for *node*, or ``None`` if childless.

    Children are sorted by :attr:`~guffin.roam.node.RoamNode.order`.  Stubs
    whose id is absent from *id_map* are silently dropped.  Attribute-block children and
    ``<domain>-meta::`` container children (:func:`_is_meta_block`) are excluded — they are folded
    into the parent vertex's :attr:`~guffin.model.vertex._BaseVertex.attribute_assignments` (see
    :func:`_resolve_attribute_assignments`) rather than transcribed as separate vertices.

    Args:
        node: The node whose children are to be resolved.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam.node.RoamNode`.

    Returns:
        Sorted list of child UIDs, or ``None`` when *node* has no (non-attribute) children or
        all child stubs are unresolvable.
    """
    if not node.children:
        return None
    resolved: Final[list[RoamNode]] = sorted(
        [
            id_map[c.id]
            for c in node.children
            if c.id in id_map
            and node_type(id_map[c.id]) is not NodeType.ATTRIBUTE_BLOCK
            and not _is_meta_block(id_map[c.id])
        ],
        key=lambda n: n.order if n.order is not None else 0,
    )
    uids: Final[VertexChildren] = [n.uid for n in resolved]
    return uids if uids else None


def _parse_attribute_assignment(node: RoamNode, tree: NodeTree) -> AttributeAssignment | None:
    """Parse an attribute-block *node*'s string into an :class:`~guffin.model.attribute_assignment.AttributeAssignment`.

    The attribute name and every tag-valued element are resolved to
    :class:`~guffin.model.vertex_link.VertexLink` references via the tree's
    :attr:`~guffin.roam.node_tree.NodeTree.page_name_map`; non-tag values become literals.

    Args:
        node: An attribute-block node whose ``string`` is wholly ``<attribute>:: <value>, …``.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` used to resolve referenced page titles.

    Returns:
        The parsed :class:`~guffin.model.attribute_assignment.AttributeAssignment`, or ``None`` when
        the attribute's own name resolves to a page beyond the fetch horizon (absent from *tree*) —
        the assignment is skipped rather than raising, so a boundary ref vertex carrying such an
        assignment is still transcribed instead of being dropped.

    Raises:
        ValueError: If ``node.string`` is ``None`` or is not wholly an attribute assignment.
    """
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    match: Final[regex.Match[str] | None] = ATTRIBUTE_ASSIGNMENT_RE.fullmatch(node.string.strip())
    if match is None:
        raise ValueError(f"RoamNode uid={node.uid!r} string is not an attribute assignment: {node.string!r}")
    attribute_name: Final[str] = match.group("attribute")
    link: Final[VertexLink | None] = _page_reference_link(attribute_name, tree)
    if link is None:
        logger.debug("attribute %r on uid=%r references a page absent from tree; skipping", attribute_name, node.uid)
        return None
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name=attribute_name), link=link),
        values=tuple(_to_attribute_value(raw, tree) for raw in match.captures("value")),
    )


def _is_meta_block(node: RoamNode) -> bool:
    """Return whether *node* is a Guffin ``<domain>-meta::`` container block (see :data:`_META_BLOCK_RE`)."""
    return node.string is not None and _META_BLOCK_RE.match(node.string.strip()) is not None


def _meta_domain(node: RoamNode) -> AttributeDomain:
    """Return the :class:`AttributeDomain` captured from a ``<domain>-meta::`` block.

    The caller ensures *node* is a meta block (:func:`_is_meta_block`).

    Raises:
        ValueError: If the captured ``<domain>`` prefix is not a recognised :class:`AttributeDomain`.
    """
    assert node.string is not None
    match: Final[regex.Match[str] | None] = _META_BLOCK_RE.match(node.string.strip())
    assert match is not None
    return AttributeDomain(match.group("domain"))


def _strip_surrounding_quotes(token: str) -> str:
    """Strip one pair of matching surrounding single or double quotes from *token*, if present."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    return token


def _parse_meta_child(node: RoamNode, domain: AttributeDomain, tree: NodeTree) -> AttributeAssignment | None:
    """Parse a ``<domain>-meta`` child *node* into an :class:`~guffin.model.attribute_assignment.AttributeAssignment`.

    This is the Guffin-specific (non-Roam-standard) attribute form: the child's string is
    ``<name>:: <value>, …`` whose values need not satisfy Roam's strict attribute syntax.  The name
    (text before ``::``) is resolved to its page :class:`~guffin.model.vertex_link.VertexLink` and the
    attribute is tagged with *domain*.  The right-hand side is split on commas; each token is trimmed,
    its surrounding quotes stripped, and rendered as a :class:`~guffin.model.attribute.ReferenceValue`
    when it is a tag (per :data:`~guffin.roam.markdown.TAG_RE`) or a
    :class:`~guffin.model.attribute.LiteralValue` otherwise.  An empty right-hand side yields no values.

    Args:
        node: A ``<domain>-meta`` child node whose ``string`` is ``<name>:: <value>, …``.
        domain: The domain captured from the enclosing ``<domain>-meta::`` block.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` used to resolve the attribute name's page.

    Returns:
        The parsed :class:`~guffin.model.attribute_assignment.AttributeAssignment` with
        ``attribute.domain`` set, or ``None`` when the attribute's own name resolves to a page beyond
        the fetch horizon (absent from *tree*) — the assignment is skipped rather than raising, so a
        boundary ref vertex carrying such an assignment is still transcribed instead of being dropped.

    Raises:
        ValueError: If ``node.string`` is ``None`` or lacks a ``::`` separator.
    """
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    name_part, separator, value_part = node.string.strip().partition("::")
    if not separator:
        raise ValueError(f"RoamNode uid={node.uid!r} meta child is not an attribute assignment: {node.string!r}")
    name: Final[str] = name_part.strip()
    link: Final[VertexLink | None] = _page_reference_link(name, tree)
    if link is None:
        logger.debug("meta attribute %r on uid=%r references a page absent from tree; skipping", name, node.uid)
        return None
    values: Final[tuple[AttributeValue, ...]] = tuple(
        _to_attribute_value(_strip_surrounding_quotes(token.strip()), tree)
        for token in value_part.split(",")
        if token.strip()
    )
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name=name, domain=domain), link=link),
        values=values,
    )


def _meta_child_assignments(meta_block: RoamNode, tree: NodeTree) -> list[AttributeAssignment]:
    """Return the attribute assignments folded from a ``<domain>-meta::`` *meta_block*'s children.

    Every child of *meta_block* (sorted by :attr:`~guffin.roam.node.RoamNode.order`) is parsed via
    :func:`_parse_meta_child` with the block's captured domain.  A child whose attribute name resolves
    to a page beyond the fetch horizon is skipped (see :func:`_parse_meta_child`).

    Args:
        meta_block: A node for which :func:`_is_meta_block` is ``True``.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the block belongs to.

    Returns:
        The assignments parsed from the meta block's children, in source order.
    """
    domain: Final[AttributeDomain] = _meta_domain(meta_block)
    meta_children: Final[list[RoamNode]] = sorted(
        [tree.id_map[gc.id] for gc in (meta_block.children or []) if gc.id in tree.id_map],
        key=lambda n: n.order if n.order is not None else 0,
    )
    parsed: Final[list[AttributeAssignment | None]] = [
        _parse_meta_child(child, domain, tree) for child in meta_children
    ]
    return [assignment for assignment in parsed if assignment is not None]


def _resolve_attribute_assignments(node: RoamNode, tree: NodeTree) -> list[AttributeAssignment] | None:
    """Return the attribute assignments folded onto *node*'s vertex, or ``None`` if there are none.

    Two child forms are folded, in *node*'s child order:

    - **Roam-standard** :attr:`~guffin.roam.node.NodeType.ATTRIBUTE_BLOCK` children, each parsed via
      :func:`_parse_attribute_assignment` (default domain).
    - **Guffin** ``<domain>-meta::`` container children (see :func:`_is_meta_block`), whose own
      children are each parsed via :func:`_parse_meta_child` with the captured domain
      (:func:`_meta_child_assignments`).

    Args:
        node: The node whose attribute-block and ``<domain>-meta`` children are to be folded in.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to.

    Returns:
        The parsed assignments in source order, or ``None`` when *node* has none.
    """
    if not node.children:
        return None
    children: Final[list[RoamNode]] = sorted(
        [tree.id_map[c.id] for c in node.children if c.id in tree.id_map],
        key=lambda n: n.order if n.order is not None else 0,
    )
    assignments: Final[list[AttributeAssignment]] = []
    for child in children:
        if _is_meta_block(child):
            assignments.extend(_meta_child_assignments(child, tree))
        elif node_type(child) is NodeType.ATTRIBUTE_BLOCK:
            assignment: AttributeAssignment | None = _parse_attribute_assignment(child, tree)
            if assignment is not None:
                assignments.append(assignment)
    return assignments if assignments else None


def _resolve_refs(node: RoamNode, id_map: dict[Id, RoamNode]) -> VertexRefs | None:
    """Return a list of referenced UIDs for *node*, or ``None`` if there are no refs.

    Stubs whose id is absent from *id_map* are silently dropped.

    Args:
        node: The node whose refs are to be resolved.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam.node.RoamNode`.

    Returns:
        List of referenced UIDs, or ``None`` when *node* has no refs or all ref
        stubs are unresolvable.
    """
    if not node.refs:
        return None
    resolved: Final[VertexRefs] = [id_map[r.id].uid for r in node.refs if r.id in id_map]
    return resolved if resolved else None


@validate_call
def vertex_type(node: RoamNode) -> VertexType:
    """Classify *node* into a :class:`~guffin.vertex.VertexType`.

    Dispatches on :func:`~guffin.roam.node.node_type` for a direct
    :class:`~guffin.roam.node.NodeType` → :class:`~guffin.vertex.VertexType` mapping.

    Args:
        node: The raw Roam node to classify.

    Returns:
        The :class:`~guffin.vertex.VertexType` for *node*.

    Raises:
        ValidationError: If *node* is ``None`` or invalid.
    """
    logger.debug("node=%r", node)
    match node_type(node):
        case NodeType.PAGE:
            return VertexType.PAGE
        case NodeType.TEXT_BLOCK:
            return VertexType.TEXT
        case NodeType.TODO_BLOCK:
            return VertexType.TODO
        case NodeType.CODE_BLOCK:
            return VertexType.CODE_BLOCK
        case NodeType.HEADING_BLOCK:
            return VertexType.HEADING
        case NodeType.IMAGE_BLOCK:
            return VertexType.IMAGE
        case NodeType.PDF_BLOCK:
            return VertexType.PDF
        case NodeType.CALLOUT_BLOCK:
            return VertexType.CALLOUT
        case NodeType.QUOTE_BLOCK:
            return VertexType.QUOTE_BLOCK
        case NodeType.NATIVE_TABLE:
            return VertexType.TABLE
        case NodeType.EMBED_BLOCK:
            return VertexType.BLOCK_EMBED
        case NodeType.EMBED_PAGE:
            return VertexType.PAGE_EMBED
        case NodeType.ASSET_BLOCK:
            return VertexType.ASSET
        case NodeType.ATTRIBUTE_BLOCK:
            # Attribute blocks are not transcribed as standalone vertices; they are folded into
            # their parent vertex's attribute_assignments field (see _resolve_attribute_assignments).
            raise ValueError(f"RoamNode uid={node.uid!r} is an attribute block; it has no standalone VertexType")


@validate_call
def to_page_vertex(node: RoamNode, tree: NodeTree) -> PageVertex:
    """Build a :class:`~guffin.vertex.PageVertex` from *node*.

    Args:
        node: A page node with ``node.title`` set.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.PageVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.title`` is ``None``.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.title is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'title'")
    return PageVertex(
        uid=node.uid,
        title=to_pandoc_md(node.title, tree),
        daily_note_date=parse_daily_note_uid(node.uid),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


def _asset_storage(firebase_storage_url: str) -> AssetStorage:
    """Return the :class:`~guffin.model.asset_storage.AssetStorage` locating a hosted asset.

    Roam marks an encrypted graph's uploads with a trailing ``.enc`` on the stored
    filename; that suffix is read here into the storage's encryption state.

    Args:
        firebase_storage_url: The asset's Firebase Storage URL string.

    Returns:
        An :class:`~guffin.model.asset_storage.AssetStorage` for the hosted asset.
    """
    location: Final[HttpUrl] = _url_adapter.validate_python(firebase_storage_url)
    stored_name: Final[str | None] = url_file_name(location)
    return AssetStorage(
        location=location,
        store_type=StoreType.FIREBASE_STORAGE,
        is_encrypted=stored_name is not None and stored_name.endswith(".enc"),
    )


@validate_call
def to_image_vertex(node: RoamNode, tree: NodeTree) -> ImageVertex:
    """Build an :class:`~guffin.vertex.ImageVertex` from *node*.

    Args:
        node: A block node whose ``node.string`` embeds a Firebase Storage image URL.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        An :class:`~guffin.vertex.ImageVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or contains no Firebase Storage URL.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    firebase_storage_url: Final[str | None] = image_link_url(node.string)
    if firebase_storage_url is None:
        raise ValueError(f"RoamNode uid={node.uid!r} 'string' contains no Firebase Storage URL")
    storage: Final[AssetStorage] = _asset_storage(firebase_storage_url)
    stored_name: Final[str | None] = url_file_name(storage.location)
    if stored_name is None:
        raise ValueError(f"RoamNode uid={node.uid!r} filename cannot be extracted from URL {firebase_storage_url!r}")
    # Roam encrypts hosted images with a double .enc extension; strip it to resolve the base media type.
    base_name: Final[str] = stored_name.removesuffix(".enc")
    resolved_type: Final[MediaType | None] = MediaType.from_file_name(base_name)
    if resolved_type is None:
        raise ValueError(f"RoamNode uid={node.uid!r} media type cannot be determined from file_name={stored_name!r}")
    media_type: Final[MediaType] = resolved_type
    size: Final[ImageSize | None] = image_size(node)
    if size is None:
        raise ValueError(f"RoamNode uid={node.uid!r} image_size returned None for an image block")
    return ImageVertex(
        uid=node.uid,
        storage=storage,
        alt_text=image_link_alt_text(node.string),
        media_type=media_type,
        scaled_image_size=size,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_pdf_vertex(node: RoamNode, tree: NodeTree) -> PdfVertex:
    """Build a :class:`~guffin.vertex.PdfVertex` from *node*.

    Args:
        node: A block node whose ``node.string`` is wholly a Roam PDF component
            (``{{pdf: <url>}}`` / ``{{[[pdf]]: <url>}}``) with a Firebase Storage URL.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.PdfVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or contains no Firebase Storage PDF component.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    firebase_storage_url: Final[str | None] = pdf_embed_url(node.string)
    if firebase_storage_url is None:
        raise ValueError(f"RoamNode uid={node.uid!r} 'string' contains no Firebase Storage PDF component")
    return PdfVertex(
        uid=node.uid,
        storage=_asset_storage(firebase_storage_url),
        media_type=MediaType.PDF,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_asset_vertex(node: RoamNode, tree: NodeTree) -> AssetVertex:
    """Build an :class:`~guffin.vertex.AssetVertex` from *node*.

    The asset's media type is inferred from the stored filename's extension when it can
    be; an unrecognizable extension leaves it ``None``.  The vertex's ``file_name`` is
    left ``None`` — the stored name is derivable from the storage location, and the
    genuinely independent upload-time name arrives only through asset fetching.

    Args:
        node: A block node whose ``node.string``, with surrounding whitespace trimmed,
            is wholly a bare Firebase Storage URL.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        An :class:`~guffin.vertex.AssetVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or is not wholly a bare Firebase Storage URL.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    trimmed: Final[str] = node.string.strip()
    if not FIREBASE_STORAGE_URL_RE.fullmatch(trimmed):
        raise ValueError(f"RoamNode uid={node.uid!r} 'string' is not wholly a bare Firebase Storage URL")
    storage: Final[AssetStorage] = _asset_storage(trimmed)
    stored_name: Final[str | None] = url_file_name(storage.location)
    media_type: Final[MediaType | None] = (
        MediaType.from_file_name(stored_name.removesuffix(".enc")) if stored_name is not None else None
    )
    return AssetVertex(
        uid=node.uid,
        storage=storage,
        media_type=media_type,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_heading_vertex(node: RoamNode, tree: NodeTree, heading_offset: int = 0) -> HeadingVertex:
    """Build a :class:`~guffin.vertex.HeadingVertex` from *node*.

    Args:
        node: A block node with an effective heading level (native ``node.heading``
            or ``node.props['ah-level']``).
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.
        heading_offset: Integer offset added to the effective heading level before
            building the vertex.  Use ``1 − min_level`` to normalize the shallowest
            heading to level 1; defaults to ``0`` (no adjustment).

    Returns:
        A :class:`~guffin.vertex.HeadingVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or no effective heading level is found.
    """
    logger.debug("node=%r, id_map keys=%r, heading_offset=%d", node, list(tree.id_map.keys()), heading_offset)
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    heading: Final[HeadingLevel | None] = effective_heading_level(node)
    if heading is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no effective heading level")
    return HeadingVertex(
        uid=node.uid,
        text=to_pandoc_md(node.string, tree),
        heading_level=heading + heading_offset,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_text_vertex(node: RoamNode, tree: NodeTree) -> TextVertex:
    """Build a :class:`~guffin.vertex.TextVertex` from *node*.

    Args:
        node: A plain text block node with ``node.string`` set.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.TextVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None``.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    return TextVertex(
        uid=node.uid,
        text=to_pandoc_md(node.string, tree),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


TODO_STATE_BY_ROAM_STATE: Final[Mapping[RoamTodoState, TodoState]] = {
    RoamTodoState.TODO: TodoState.TODO,
    RoamTodoState.DONE: TodoState.DONE,
}
"""Member-keyed map from a Roam TODO marker state to the :class:`~guffin.model.vertex.TodoState` it declares.

Total over :class:`~guffin.roam.todo.TodoState` (enforced by test), so the source vocabulary
is translated once at the transcription boundary and never reaches a renderer.
"""


@validate_call
def to_todo_vertex(node: RoamNode, tree: NodeTree) -> TodoVertex:
    """Build a :class:`~guffin.model.vertex.TodoVertex` from a TODO item block *node*.

    Decomposes ``node.string`` via :func:`~guffin.roam.todo.parse_todo` — the checkbox marker's
    keyword becomes the vertex's :attr:`~guffin.model.vertex.TodoVertex.todo_state` (via
    :data:`TODO_STATE_BY_ROAM_STATE`), and the marker-free item text — normalized via
    :func:`~guffin.transcribe.roam_md_to_pandoc_md.to_pandoc_md` — becomes its
    :attr:`~guffin.model.vertex.TodoVertex.text`, so formatting markup that wrapped the marker
    still wraps the text.

    Args:
        node: A TODO item block node whose ``string``'s first content is a Roam TODO marker.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.model.vertex.TodoVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or opens with no TODO marker.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    parsed: Final[RoamTodo | None] = parse_todo(node.string)
    if parsed is None:
        raise ValueError(f"RoamNode uid={node.uid!r} string opens with no TODO marker: {node.string!r}")
    return TodoVertex(
        uid=node.uid,
        todo_state=TODO_STATE_BY_ROAM_STATE[parsed.state],
        text=to_pandoc_md(parsed.text.strip(), tree),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_callout_vertex(node: RoamNode, tree: NodeTree) -> CalloutVertex:
    """Build a :class:`~guffin.vertex.CalloutVertex` from a callout block *node*.

    Parses the ``[[>]] [[!<TYPE>]]`` marker from ``node.string`` to extract the
    :class:`~guffin.vertex.CalloutVertex.CalloutType` and title text.

    Args:
        node: A callout block node whose ``string`` starts with a valid callout marker.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.CalloutVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or does not match the callout marker.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    parsed: Final[RoamCallout | None] = parse_callout(node.string)
    if parsed is None:
        raise ValueError(f"RoamNode uid={node.uid!r} string does not match callout marker: {node.string!r}")
    callout_type: Final[CalloutVertex.CalloutType] = CalloutVertex.CalloutType(parsed.callout_type.lower())
    title: Final[str] = to_pandoc_md(parsed.title.strip(), tree)
    body: Final[str] = to_pandoc_md(parsed.body.strip(), tree) if parsed.body else ""
    return CalloutVertex(
        uid=node.uid,
        callout_type=callout_type,
        title=title,
        body=body,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_code_block_vertex(node: RoamNode, tree: NodeTree) -> CodeBlockVertex:
    """Build a :class:`~guffin.vertex.CodeBlockVertex` from a fenced code block *node*.

    Splits ``node.string`` into its info string and code content via
    :func:`~guffin.common.markdown.parse_fenced_code_block`.  The block's language is the
    canonical language id (:data:`~guffin.common.programming_language.CodeLanguageId`) of
    its ``code-language::`` tag when one is present and legal (the tag exists because the
    Roam UI's fence-language dropdown is a closed set); otherwise the fence's own info
    string — a :class:`~guffin.roam.code_language.CodeLanguage` — mapped to its
    canonical id.  An illegal tag value is ignored with a warning (the vocabulary
    validator reports it separately).  A ``code-source::`` tag, when present and legal,
    populates the block's :class:`~guffin.model.code_source.CodeSource` provenance the
    same way (absent or illegal, the provenance stays ``None``).  The code content is
    preserved verbatim — Roam-to-Pandoc Markdown normalization is deliberately not
    applied, so the source is kept exactly as authored.

    Args:
        node: A code block node whose ``string`` is a fenced code block.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.CodeBlockVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None``, is not a fenced code block, or
            carries an info string that is not a recognised
            :class:`~guffin.roam.code_language.CodeLanguage`.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    parsed: Final[FencedCodeBlock] = parse_fenced_code_block(node.string.strip())
    vertex: Final[CodeBlockVertex] = CodeBlockVertex(
        uid=node.uid,
        code=parsed.code,
        language=canonical_id_for(CodeLanguage(parsed.info)),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )
    overrides: Final[dict[str, CodeLanguageId | CodeSource]] = {}
    language_override: Final[CodeLanguageId | None] = code_language_of_vertex(vertex)
    if language_override is not None:
        overrides["language"] = language_override
    source: Final[CodeSource | None] = code_source_of_vertex(vertex)
    if source is not None:
        overrides["code_source"] = source
    return vertex.model_copy(update=overrides) if overrides else vertex


@validate_call
def to_quote_block_vertex(node: RoamNode, tree: NodeTree) -> QuoteBlockVertex:
    """Build a :class:`~guffin.vertex.QuoteBlockVertex` from a quote-block *node*.

    Maps the Roam source form to the source-agnostic :class:`~guffin.vertex.QuoteType` at this
    boundary:

    - a Roam pull quote (``[[>]] [[!QUOTE]]``, per :func:`~guffin.roam.blockquote.parse_pull_quote`)
      becomes :attr:`~guffin.vertex.QuoteType.PULL`, its first line the ``quote`` and any following
      lines the ``attribution`` (the decorated pull-quote treatment);
    - a standard ``>`` or Roam-native ``[[>]]`` block quote becomes
      :attr:`~guffin.vertex.QuoteType.BLOCK`, the marker-stripped content the ``quote`` and
      ``attribution`` ``None`` (a plain block quote).

    Each text part is normalized to Pandoc Markdown via :func:`~guffin.transcribe.roam_md_to_pandoc_md.to_pandoc_md`.

    Args:
        node: A quote-block node whose ``string`` starts with a recognised quote marker
            (``>``, ``[[>]]``, or ``[[>]] [[!QUOTE]]``).
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.QuoteBlockVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or is not a recognised quote block.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    pull: Final[tuple[str, str | None] | None] = parse_pull_quote(node.string)
    if pull is not None:
        quote_type: QuoteType = QuoteType.PULL
        quote_raw, attribution_raw = pull
    else:
        quote_type = QuoteType.BLOCK
        quote_raw, attribution_raw = strip_block_quote_marker(node.string), None
    return QuoteBlockVertex(
        uid=node.uid,
        quote_type=quote_type,
        quote=to_pandoc_md(quote_raw, tree),
        attribution=to_pandoc_md(attribution_raw, tree) if attribution_raw is not None else None,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


@validate_call
def to_block_embed_vertex(node: RoamNode, tree: NodeTree) -> BlockEmbedVertex:
    """Build a :class:`~guffin.vertex.BlockEmbedVertex` from a block embed *node*.

    Extracts the embedded block's UID from ``node.string`` — a Roam block embed
    ``{{embed: ((<uid>))}}`` as matched by :data:`~guffin.roam.markdown.BLOCK_EMBED_RE` —
    and records it as an :attr:`~guffin.model.vertex_link.VertexLinkKind.EMBED`-kind
    :class:`~guffin.model.vertex_link.VertexLink` to the transcluded vertex.

    Args:
        node: A block embed node whose ``string`` is wholly ``{{embed: ((<uid>))}}``.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.BlockEmbedVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or is not wholly a block embed.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    embed_match: Final[regex.Match[str] | None] = BLOCK_EMBED_RE.fullmatch(node.string.strip())
    if embed_match is None:
        raise ValueError(f"RoamNode uid={node.uid!r} string is not a block embed: {node.string!r}")
    return BlockEmbedVertex(
        uid=node.uid,
        vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid=embed_match.group("uid")),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


def to_page_embed_vertex(node: RoamNode, tree: NodeTree) -> PageEmbedVertex:
    """Build a :class:`~guffin.vertex.PageEmbedVertex` from a page embed *node*.

    The page-reference sibling of :func:`to_block_embed_vertex`: extracts the embedded page's title
    from ``node.string`` — a Roam page embed ``{{embed: [[<page_name>]]}}`` as matched by
    :data:`~guffin.roam.markdown.PAGE_EMBED_RE` — resolves it to the page's UID via
    :meth:`~guffin.roam.node_tree.NodeTree.page_uid`, and records it as an
    :attr:`~guffin.model.vertex_link.VertexLinkKind.EMBED`-kind
    :class:`~guffin.model.vertex_link.VertexLink` to the transcluded page.

    Args:
        node: A page embed node whose ``string`` is wholly ``{{embed: [[<page_name>]]}}``.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to; its
            :meth:`~guffin.roam.node_tree.NodeTree.page_uid` resolves the page title to its UID
            and its :attr:`~guffin.roam.node_tree.NodeTree.id_map` resolves child and ref stubs.

    Returns:
        A :class:`~guffin.vertex.PageEmbedVertex` whose embed link targets the referenced page.

    Raises:
        ValueError: If ``node.string`` is ``None``, is not wholly a page embed, or names a page not
            present in the tree (e.g. the referenced page was not fetched).
    """
    logger.debug("node=%r", node)
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    embed_match: Final[regex.Match[str] | None] = PAGE_EMBED_RE.fullmatch(node.string.strip())
    if embed_match is None:
        raise ValueError(f"RoamNode uid={node.uid!r} string is not a page embed: {node.string!r}")
    return PageEmbedVertex(
        uid=node.uid,
        vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid=tree.page_uid(embed_match.group("page_name"))),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
        attribute_assignments=_resolve_attribute_assignments(node, tree),
    )


def _page_reference_link(page_name: str, tree: NodeTree) -> VertexLink | None:
    """Return a reference :class:`~guffin.model.vertex_link.VertexLink` to the page titled *page_name*.

    Args:
        page_name: The exact title of the referenced Roam page.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` used to resolve the title (via
            :meth:`~guffin.roam.node_tree.NodeTree.page_uid_or_none`).

    Returns:
        A :attr:`~guffin.model.vertex_link.VertexLinkKind.REFERENCE`-kind link to the page's UID, or
        ``None`` when no page titled *page_name* is present in *tree* — e.g. a reference to a page
        beyond the fetch horizon.  Callers degrade such a dangling reference (a value becomes a
        literal; an attribute whose own name is dangling is skipped) rather than dropping the whole
        host vertex.
    """
    page_uid: Final[Uid | None] = tree.page_uid_or_none(page_name)
    if page_uid is None:
        return None
    return VertexLink(kind=VertexLinkKind.REFERENCE, uid=page_uid)


def _to_attribute_value(raw_value: str, tree: NodeTree) -> AttributeValue:
    """Convert one raw attribute-value token into an :data:`~guffin.model.attribute.AttributeValue`.

    A token that is wholly a Roam tag (per :data:`~guffin.roam.markdown.TAG_RE`) becomes a
    :class:`~guffin.model.attribute.ReferenceValue` linking to the referenced page; any other token
    becomes a :class:`~guffin.model.attribute.LiteralValue`.

    Args:
        raw_value: A single value token captured from the attribute assignment (e.g. ``5`` or
            ``#[[callouts demo]]``).
        tree: The :class:`~guffin.roam.node_tree.NodeTree` used to resolve a referenced page.

    A tag whose referenced page lies beyond the fetch horizon (absent from *tree*) degrades to a
    :class:`~guffin.model.attribute.LiteralValue` carrying the raw token, rather than raising — so a
    boundary ref vertex whose ``tags::`` value points at an unfetched page is still transcribed
    instead of being dropped.

    Returns:
        A :class:`~guffin.model.attribute.LiteralValue` or :class:`~guffin.model.attribute.ReferenceValue`.
    """
    tag_match: Final[regex.Match[str] | None] = TAG_RE.fullmatch(raw_value)
    if tag_match is None:
        return LiteralValue(value=raw_value)
    page_name: Final[str | None] = tag_match.group("page_name") or tag_match.group("bare_page_name")
    assert page_name is not None  # exactly one of the tag's name groups matches
    link: Final[VertexLink | None] = _page_reference_link(page_name, tree)
    if link is None:
        logger.debug("attribute value references page %r absent from tree; keeping as literal", page_name)
        return LiteralValue(value=raw_value)
    return ReferenceValue(name=page_name, link=link)


@validate_call
def to_table_vertex(node: RoamNode, tree: NodeTree) -> tuple[TableVertex, frozenset[Id]]:
    """Build a :class:`~guffin.vertex.TableVertex` from a native table *node*.

    Delegates raw-grid reconstruction to :func:`~guffin.roam.node_tree.to_table`, then normalizes
    each cell string with :func:`~guffin.transcribe.roam_md_to_pandoc_md.to_pandoc_md`.
    All descendant nodes (rows and cells) are consumed into the returned
    :class:`~guffin.vertex.TableVertex`; consequently
    :attr:`~guffin.vertex.TableVertex.children` is always ``None`` — the descendants
    do not appear as separate vertices in the :class:`~guffin.vertex_tree.VertexTree`.
    The returned :class:`~python:frozenset` carries the :attr:`~guffin.roam.node.RoamNode.id`
    of every consumed descendant so that callers can skip them during traversal.

    Args:
        node: A native-table node whose :attr:`~guffin.roam.node.RoamNode.string`
            is one of :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKERS`.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve row and
            cell stubs to their full node records.

    Returns:
        A ``(TableVertex, frozenset[Id])`` pair: the built vertex with an all-default
        :class:`~guffin.common.table.TableStyle`, and the set of descendant node IDs
        consumed by this vertex (row and cell node IDs).

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If *node* has no children (empty table).
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if not node.children:
        raise ValueError(f"RoamNode uid={node.uid!r} has no children (empty table)")
    table_tree: Final[NodeTree] = NodeTree.build(node, list(tree.id_map.values()))
    consumed_ids: Final[frozenset[Id]] = frozenset(n.id for n in table_tree.tree_network)
    raw_table: Final[Table] = to_table(table_tree)
    # Normalize each raw Roam cell string to Pandoc Markdown (the roam-layer to_table leaves it raw).
    normalized: Final[Table] = raw_table.model_copy(
        update={"rows": tuple(tuple(to_pandoc_md(cell, table_tree) for cell in row) for row in raw_table.rows)}
    )
    return (
        TableVertex(
            uid=node.uid,
            children=None,
            refs=_resolve_refs(node, tree.id_map),
            attribute_assignments=_resolve_attribute_assignments(node, tree),
            table=normalized,
            table_style=TableStyle(),
        ),
        consumed_ids,
    )


@validate_call
def transcribe_standalone_node(node: RoamNode, tree: NodeTree, heading_offset: int = 0) -> Vertex:
    r"""Transcribe *node* into a normalized :class:`~guffin.vertex.Vertex`.

    Determines the :class:`~guffin.vertex.VertexType` via :func:`vertex_type`,
    resolves raw :class:`~guffin.roam.primitives.IdObject` stubs in children and refs to
    stable UIDs via :attr:`~guffin.roam.node_tree.NodeTree.id_map`, and handles both native Roam
    headings (levels 1–3 via ``node.heading``) and Augmented Headings extension levels
    (4–6 via ``node.props['ah-level']``).

    Args:
        node: The raw Roam node to transcribe.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to.
            :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve child and ref
            stubs to UIDs; stubs whose id is absent from the map are silently dropped.
        heading_offset: Integer offset forwarded to :func:`to_heading_vertex` when *node*
            is a heading block.  Defaults to ``0`` (no adjustment).

    Returns:
        A :class:`~guffin.vertex.Vertex` representing the normalized node.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If *node* has neither a ``title`` nor a ``string`` field set.
    """
    logger.debug("node=%r, tree root uid=%r, heading_offset=%d", node, tree.root_node.uid, heading_offset)
    match vertex_type(node):
        case VertexType.PAGE:
            return to_page_vertex(node, tree)
        case VertexType.IMAGE:
            return to_image_vertex(node, tree)
        case VertexType.PDF:
            return to_pdf_vertex(node, tree)
        case VertexType.HEADING:
            return to_heading_vertex(node, tree, heading_offset)
        case VertexType.TEXT:
            return to_text_vertex(node, tree)
        case VertexType.TODO:
            return to_todo_vertex(node, tree)
        case VertexType.CALLOUT:
            return to_callout_vertex(node, tree)
        case VertexType.CODE_BLOCK:
            return to_code_block_vertex(node, tree)
        case VertexType.QUOTE_BLOCK:
            return to_quote_block_vertex(node, tree)
        case VertexType.TABLE:
            raise NotImplementedError(f"RoamNode uid={node.uid!r}: TABLE is not a standalone NodeType")
        case VertexType.ASSET:
            return to_asset_vertex(node, tree)
        case VertexType.BLOCK_EMBED:
            return to_block_embed_vertex(node, tree)
        case VertexType.PAGE_EMBED:
            return to_page_embed_vertex(node, tree)
        case _ as unreachable:
            assert_never(unreachable)


def _subtree_ids(node: RoamNode, tree: NodeTree) -> frozenset[Id]:
    """Return the ids of *node* and every descendant (resolved via *tree*'s ``id_map``)."""
    ids: Final[set[Id]] = set()
    stack: Final[list[RoamNode]] = [node]
    while stack:
        current: RoamNode = stack.pop()
        ids.add(current.id)
        stack.extend(tree.id_map[c.id] for c in (current.children or []) if c.id in tree.id_map)
    return frozenset(ids)


@validate_call
def transcribe(node_tree: NodeTree) -> VertexTree:
    """Transcribe every node in *node_tree* into a :class:`~guffin.vertex_tree.VertexTree`.

    Traverses *node_tree* in pre-order DFS order.  Most nodes are transcribed
    one-to-one via :func:`transcribe_standalone_node`.  Exception: a
    :attr:`~guffin.roam.node.NodeType.NATIVE_TABLE` node and all of its
    descendants are consumed together into a single
    :class:`~guffin.vertex.TableVertex` via :func:`to_table_vertex`; those
    descendants are skipped when the DFS iterator later yields them.

    When :data:`SHOULD_NORMALIZE_HEADING_LEVELS` is ``True``, computes a
    *heading_offset* equal to ``1 − min effective heading level`` across all
    nodes in the tree, so that the shallowest heading maps to level 1; when no
    heading nodes are present, or when :data:`SHOULD_NORMALIZE_HEADING_LEVELS`
    is ``False``, *heading_offset* is 0.

    Args:
        node_tree: A validated tree of raw Roam nodes.

    Returns:
        A :class:`~guffin.vertex_tree.VertexTree` in document (DFS) order, with
        :attr:`~guffin.vertex_tree.VertexTree.ref_vertices` populated from
        :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id`.  A referenced node that is
        itself a member of the anchor tree yields no ref vertex — the tree pass already
        transcribes it (heading normalization applied), and each uid maps to exactly one
        vertex.  Referenced native-table
        nodes are consumed into a single :class:`~guffin.vertex.TableVertex` (with their
        row/cell descendants) just as in-tree tables are, so a cross-page table reference
        resolves to a complete table.

    Raises:
        ValueError: If any anchor node has neither a ``title`` nor a ``string`` field set.
    """
    min_level: Final[HeadingLevel | None] = (
        min_effective_heading_level(node_tree.tree_network) if SHOULD_NORMALIZE_HEADING_LEVELS else None
    )
    heading_offset: Final[int] = (1 - min_level) if min_level is not None else 0
    logger.debug("heading_offset=%d", heading_offset)
    consumed: Final[set[Id]] = set()
    vertices: Final[list[Vertex]] = []
    for node in node_tree.dfs():
        if node.id in consumed:
            continue
        # A <domain>-meta:: container and its whole subtree are folded onto the parent vertex's
        # attribute_assignments (see _resolve_attribute_assignments); consume them so they are not
        # transcribed as standalone vertices.  Checked before the attribute-block guard so a meta
        # block whose value happens to parse as an attribute is still consumed (not folded twice).
        if _is_meta_block(node):
            consumed.update(_subtree_ids(node, node_tree))
            continue
        # Attribute blocks are folded into their parent vertex's attribute_assignments field
        # (see _resolve_attribute_assignments), not transcribed as standalone vertices.
        if node_type(node) is NodeType.ATTRIBUTE_BLOCK:
            continue
        if node_type(node) == NodeType.NATIVE_TABLE:
            table_vertex, nodes_consumed = to_table_vertex(node, node_tree)
            consumed.update(nodes_consumed)
            vertices.append(table_vertex)
        else:
            vertices.append(transcribe_standalone_node(node, node_tree, heading_offset))
    ref_vertices: Final[list[Vertex]] = []
    ref_consumed: Final[set[Id]] = set()
    # A ref target can live inside the anchor tree itself (a block ref to an in-tree node).  Such a
    # node is already transcribed by the tree pass above — heading normalization applied — so the
    # ref passes skip it; transcribing it again would emit a duplicate, un-normalized vertex under
    # the same uid, and that duplicate would shadow the tree vertex in VertexTree.uid_map.
    tree_ids: Final[frozenset[Id]] = frozenset(tree_node.id for tree_node in node_tree.tree_network)
    # Native tables are multi-node constructs: consume each referenced table together with its
    # row/cell descendants first, so those descendants are not also transcribed as standalone
    # ref vertices.  refs_by_id is not in DFS order, so a single-pass consumed-set guard could
    # encounter a cell before its table; a dedicated table pass avoids that.
    for ref_node in node_tree.refs_by_id.values():
        if ref_node.id in tree_ids or node_type(ref_node) != NodeType.NATIVE_TABLE:
            continue
        try:
            ref_table_vertex, ref_nodes_consumed = to_table_vertex(ref_node, node_tree)
        except (NotImplementedError, ValueError) as exc:
            logger.debug("skipping ref table node uid=%r: %s", ref_node.uid, exc)
            continue
        ref_consumed.update(ref_nodes_consumed)
        ref_vertices.append(ref_table_vertex)
    for ref_node in node_tree.refs_by_id.values():
        # In-tree nodes are covered by the tree pass; native tables are consumed above; attribute
        # blocks and meta containers are not vertices.
        if (
            ref_node.id in tree_ids
            or ref_node.id in ref_consumed
            or node_type(ref_node) in (NodeType.NATIVE_TABLE, NodeType.ATTRIBUTE_BLOCK)
            or _is_meta_block(ref_node)
        ):
            continue
        try:
            ref_vertices.append(transcribe_standalone_node(ref_node, node_tree))
        except (NotImplementedError, ValueError) as exc:
            logger.debug("skipping ref node uid=%r: %s", ref_node.uid, exc)
    return VertexTree(tree_vertices=vertices, ref_vertices=ref_vertices)


SEMANTIC_BY_BULLET_TYPE: Final[Mapping[BetterBulletType, Semantic]] = {
    BetterBulletType.EQUAL: Semantic.DEFINITION,
    BetterBulletType.LEADS_TO: Semantic.LEADS_TO,
    BetterBulletType.RESULT: Semantic.RESULT,
    BetterBulletType.QUESTION: Semantic.QUESTION,
    BetterBulletType.IMPORTANT: Semantic.WARNING,
    BetterBulletType.IDEA: Semantic.IDEA,
    BetterBulletType.COROLLARY: Semantic.COROLLARY,
    BetterBulletType.CONTRAST: Semantic.CONTRAST,
    BetterBulletType.EVIDENCE: Semantic.EVIDENCE,
    BetterBulletType.CONCLUSION: Semantic.CONCLUSION,
    BetterBulletType.HYPOTHESIS: Semantic.HYPOTHESIS,
    BetterBulletType.DEPENDS_ON: Semantic.DEPENDS_ON,
    BetterBulletType.DECISION: Semantic.DECISION,
    BetterBulletType.REFERENCE: Semantic.REFERENCE,
    BetterBulletType.PROCESS: Semantic.PROCESS,
}
"""Member-keyed map from a Better Bullets kind to the :class:`~guffin.model.vertex_view.Semantic` it declares.

The bridge from the extension's persisted bullet vocabulary to the model's
markup-independent classification.  Total over
:class:`~guffin.roam.better_bullet.BetterBulletType` (enforced by test).
"""

SOURCE_CHANNEL_BY_PROVENANCE: Final[Mapping[BetterBulletProvenance, SourceChannel]] = {
    BetterBulletProvenance.CALENDAR_EVENT: SourceChannel.CALENDAR_EVENT,
    BetterBulletProvenance.EMAIL: SourceChannel.EMAIL,
    BetterBulletProvenance.PHONE_CALL: SourceChannel.VOICE_CALL,
    BetterBulletProvenance.CHAT_MESSAGE: SourceChannel.CHAT_MESSAGE,
    BetterBulletProvenance.SCANNED_POST: SourceChannel.POSTAL_MAIL,
    BetterBulletProvenance.SLACK: SourceChannel.SLACK,
}
"""Member-keyed map from a Better Bullets provenance to the :class:`~guffin.model.vertex_view.SourceChannel` it.

declares.

The bridge from the extension's persisted provenance vocabulary to the model's
markup-independent classification, spanning the label divergences (``phone`` →
``voice-call``, ``mail`` → ``postal-mail``).  Total over
:class:`~guffin.roam.better_bullet.BetterBulletProvenance` (enforced by test).
"""


@validate_call
def build_view_map(node_tree: NodeTree) -> ViewMap:
    """Derive the presentation :data:`~guffin.model.vertex_view.ViewMap` for *node_tree*.

    This is the presentation counterpart to :func:`transcribe` (which derives content), covering
    the same node population — the anchor subtree *and* the referenced nodes
    (:attr:`~guffin.roam.node_tree.NodeTree.refs_by_id`), so a transcluded page or block carries
    its authored presentation with it.  It records a
    :class:`~guffin.model.vertex_view.VertexView` keyed by uid for every node carrying at least
    one explicit declaration, each mapped to its model form:

    - an *explicit* children-view-type (:attr:`~guffin.roam.node.RoamNode.children_view_type`
      is not ``None``) maps straight to the matching
      :class:`~guffin.model.vertex_view.ChildrenLayout` — an explicit ``BULLET`` included, so it
      is recorded distinctly from an unset node rather than being conflated with the default;
    - a Better Bullets bullet kind (:func:`~guffin.roam.node.better_bullet_type`) maps to its
      :class:`~guffin.model.vertex_view.Semantic` via :data:`SEMANTIC_BY_BULLET_TYPE`;
    - a Better Bullets provenance badge (:func:`~guffin.roam.node.better_bullet_provenance`)
      maps to its :class:`~guffin.model.vertex_view.SourceChannel` via
      :data:`SOURCE_CHANNEL_BY_PROVENANCE`.

    The map is sparse, and each recorded view carries only the fields its node declares.  A
    node with no explicit children-view-type is absent (or its view's layout is unset) and at
    render time adopts its parent's effective layout (the tri-state effective-layout rules;
    see ``docs/render-pipeline.md``), falling back to
    :data:`~guffin.model.vertex_view.DEFAULT_CHILDREN_LAYOUT` only at a parentless root.

    Args:
        node_tree: A validated tree of raw Roam nodes.

    Returns:
        A :data:`~guffin.model.vertex_view.ViewMap` covering exactly the fetched nodes — anchor
        subtree and referenced nodes alike — that carry an explicit children-view-type, bullet
        kind, or provenance badge.
    """
    view_map: Final[ViewMap] = {}
    for node in chain(node_tree.dfs(), node_tree.refs_by_id.values()):
        layout: ChildrenLayout | None = (
            ChildrenLayout(node.children_view_type) if node.children_view_type is not None else None
        )
        bullet: BetterBulletType | None = better_bullet_type(node)
        provenance: BetterBulletProvenance | None = better_bullet_provenance(node)
        if layout is None and bullet is None and provenance is None:
            continue
        view_map[node.uid] = VertexView(
            children_layout=layout,
            semantic=SEMANTIC_BY_BULLET_TYPE[bullet] if bullet is not None else None,
            source_channel=SOURCE_CHANNEL_BY_PROVENANCE[provenance] if provenance is not None else None,
        )
    return view_map


@validate_call
def to_render_bundle(node_tree: NodeTree) -> RenderBundle:
    """Transcribe *node_tree* into a complete :class:`~guffin.model.render_bundle.RenderBundle`.

    Bundles the two :class:`~guffin.roam.node_tree.NodeTree`-rooted transformations: the
    :class:`~guffin.model.vertex_tree.VertexTree` content from :func:`transcribe` and the
    presentation :data:`~guffin.model.vertex_view.ViewMap` from :func:`build_view_map`.

    Args:
        node_tree: A validated tree of raw Roam nodes.

    Returns:
        A :class:`~guffin.model.render_bundle.RenderBundle` pairing the transcribed content with its
        presentation overlay.

    Raises:
        ValueError: If any anchor node has neither a ``title`` nor a ``string`` field set.
    """
    return RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))
