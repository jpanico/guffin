"""Transcribe `RoamNode` to `Vertex`.

Public symbols:

- :data:`SHOULD_NORMALIZE_HEADING_LEVELS` — whether heading levels should be
  normalized during transcription.
- :func:`vertex_type` — classify a :class:`~guffin.roam.node.RoamNode` into a
  :class:`~guffin.vertex.VertexType`.
- :func:`to_page_vertex` — build a :class:`~guffin.vertex.PageVertex` from a
  page node.
- :func:`to_image_vertex` — build an :class:`~guffin.vertex.ImageVertex` from a
  Firestore image block node.
- :func:`to_heading_vertex` — build a :class:`~guffin.vertex.HeadingVertex` from
  a heading block node.
- :func:`to_text_vertex` — build a
  :class:`~guffin.vertex.TextVertex` from a plain text block node.
- :func:`to_callout_vertex` — build a :class:`~guffin.vertex.CalloutVertex` from a
  callout block node.
- :func:`to_code_block_vertex` — build a :class:`~guffin.vertex.CodeBlockVertex` from a
  fenced code block node.
- :func:`to_block_quote_vertex` — build a :class:`~guffin.vertex.BlockQuoteVertex` from a
  block-quote node.
- :func:`to_table` — build a :class:`~guffin.common.table.Table` from a
  :class:`~guffin.roam.node_tree.NodeTree` rooted at a native table node.
- :func:`to_table_vertex` — build a :class:`~guffin.vertex.TableVertex` from a native table node,
  returning it together with the IDs of all consumed descendant nodes.
- :func:`transcribe_standalone_node` — transcribe a :class:`~guffin.roam.node.RoamNode` into
  the appropriate :data:`~guffin.vertex.Vertex` subtype.
- :func:`transcribe` — transcribe all nodes in a :class:`~guffin.roam.node_tree.NodeTree`
  into a :class:`~guffin.vertex_tree.VertexTree`.
"""

import logging
from typing import Final, assert_never
from urllib.parse import unquote, urlparse

import regex
from pydantic import HttpUrl, TypeAdapter, validate_call

from guffin.model.vertex import (
    BlockQuoteVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
    VertexChildren,
    VertexRefs,
    VertexType,
)
from guffin.model.vertex_tree import VertexTree
from guffin.pipeline.roam_md_to_pandoc_md import to_pandoc_md
from guffin.roam.node_network import min_effective_heading_level
from guffin.roam.node import NodeType, RoamNode, effective_heading_level, image_size, node_type
from guffin.roam.node_tree import NodeTree
from guffin.common.code_language import CodeLanguage
from guffin.common.geometry import ImageSize
from guffin.common.markdown import FencedCodeBlock, parse_fenced_code_block
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.roam.markdown import IMAGE_LINK_RE, RoamCallout, parse_callout, strip_block_quote_marker
from guffin.common.markdown import HeadingLevel
from guffin.roam.primitives import Id

logger = logging.getLogger(__name__)

SHOULD_NORMALIZE_HEADING_LEVELS: Final[bool] = True
"""Whether heading levels should be normalized during transcription."""

_url_adapter: TypeAdapter[HttpUrl] = TypeAdapter(HttpUrl)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating and coercing URL strings to :class:`~pydantic.HttpUrl`."""


def _resolve_children(node: RoamNode, id_map: dict[Id, RoamNode]) -> VertexChildren | None:
    """Return an ordered list of child UIDs for *node*, or ``None`` if childless.

    Children are sorted by :attr:`~guffin.roam.node.RoamNode.order`.  Stubs
    whose id is absent from *id_map* are silently dropped.

    Args:
        node: The node whose children are to be resolved.
        id_map: Mapping from Datomic entity id to :class:`~guffin.roam.node.RoamNode`.

    Returns:
        Sorted list of child UIDs, or ``None`` when *node* has no children or
        all child stubs are unresolvable.
    """
    if not node.children:
        return None
    resolved: Final[list[RoamNode]] = sorted(
        [id_map[c.id] for c in node.children if c.id in id_map],
        key=lambda n: n.order if n.order is not None else 0,
    )
    uids: Final[VertexChildren] = [n.uid for n in resolved]
    return uids if uids else None


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


def _extract_firestore_url(string: str) -> str | None:
    """Return the Cloud Firestore storage URL embedded in *string*, or ``None`` if absent.

    Args:
        string: A raw block string that may contain a Roam markdown image link.

    Returns:
        The URL string captured from the first Firestore image link, or ``None``.
    """
    m: Final[regex.Match[str] | None] = IMAGE_LINK_RE.search(string)
    return m.group("url") if m else None


def _extract_alt_text(string: str) -> str | None:
    """Return the alt text from the first Firestore image link in *string*, or ``None``.

    The captured alt text is stripped of leading and trailing whitespace.  Returns
    ``None`` when no Firestore image link is found or the alt text is empty after
    stripping.

    Args:
        string: A raw block string that may contain a Roam markdown image link.

    Returns:
        The stripped alt text string, or ``None``.
    """
    m: Final[regex.Match[str] | None] = IMAGE_LINK_RE.search(string)
    if m is None:
        return None
    alt: Final[str] = m.group("alt").strip()
    return alt if alt else None


def _extract_file_name(firestore_url: str) -> str | None:
    """Return the original filename encoded in a Firestore URL, or ``None`` on failure.

    Firestore URLs encode the object path after ``/o/`` using percent-encoding.
    The filename is the last path segment after URL-decoding.

    Args:
        firestore_url: A ``https://firebasestorage.googleapis.com/...`` URL string.

    Returns:
        The decoded filename (e.g. ``"image.png"``), or ``None`` if extraction fails.
    """
    try:
        path = urlparse(firestore_url).path
        parts = path.split("/o/", maxsplit=1)
        if len(parts) == 2:
            return unquote(parts[1]).split("/")[-1]
    except Exception:
        pass
    return None


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
        case NodeType.ROAM_PAGE:
            return VertexType.GUFFIN_PAGE
        case NodeType.ROAM_PLAIN_BLOCK:
            return VertexType.GUFFIN_TEXT
        case NodeType.ROAM_CODE_BLOCK:
            return VertexType.GUFFIN_CODE_BLOCK
        case NodeType.ROAM_HEADING_BLOCK:
            return VertexType.GUFFIN_HEADING
        case NodeType.ROAM_IMAGE_BLOCK:
            return VertexType.GUFFIN_IMAGE
        case NodeType.ROAM_CALLOUT_BLOCK:
            return VertexType.GUFFIN_CALLOUT
        case NodeType.ROAM_BLOCK_QUOTE:
            return VertexType.GUFFIN_BLOCK_QUOTE
        case NodeType.ROAM_NATIVE_TABLE:
            return VertexType.GUFFIN_TABLE
        case NodeType.ROAM_EMBED_BLOCK:
            # Block embeds are not yet expanded; transcribe as text so the {{embed: ...}}
            # construct is preserved verbatim (same as a plain block).
            return VertexType.GUFFIN_TEXT


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
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
    )


@validate_call
def to_image_vertex(node: RoamNode, tree: NodeTree) -> ImageVertex:
    """Build an :class:`~guffin.vertex.ImageVertex` from *node*.

    Args:
        node: A block node whose ``node.string`` embeds a Firestore image URL.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        An :class:`~guffin.vertex.ImageVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or contains no Firestore URL.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    firestore_url: Final[str | None] = _extract_firestore_url(node.string)
    if firestore_url is None:
        raise ValueError(f"RoamNode uid={node.uid!r} 'string' contains no Firestore URL")
    file_name: Final[str | None] = _extract_file_name(firestore_url)
    if file_name is None:
        raise ValueError(f"RoamNode uid={node.uid!r} filename cannot be extracted from URL {firestore_url!r}")
    # Roam encrypts hosted images with a double .enc extension; strip it to resolve the base media type.
    base_name: Final[str] = file_name.removesuffix(".enc")
    resolved_type: Final[MediaType | None] = MediaType.from_file_name(base_name)
    if resolved_type is None:
        raise ValueError(f"RoamNode uid={node.uid!r} media type cannot be determined from file_name={file_name!r}")
    media_type: Final[MediaType] = resolved_type
    size: Final[ImageSize | None] = image_size(node)
    if size is None:
        raise ValueError(f"RoamNode uid={node.uid!r} image_size returned None for an image block")
    return ImageVertex(
        uid=node.uid,
        source=_url_adapter.validate_python(firestore_url),
        alt_text=_extract_alt_text(node.string),
        file_name=file_name,
        media_type=media_type,
        scaled_image_size=size,
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
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
    )


@validate_call
def to_code_block_vertex(node: RoamNode, tree: NodeTree) -> CodeBlockVertex:
    """Build a :class:`~guffin.vertex.CodeBlockVertex` from a fenced code block *node*.

    Splits ``node.string`` into its info string and code content via
    :func:`~guffin.common.markdown.parse_fenced_code_block`, mapping the info
    string to a :class:`~guffin.common.code_language.CodeLanguage`.  The code
    content is preserved verbatim — Roam-to-Pandoc Markdown normalization is
    deliberately not applied, so the source is kept exactly as authored.

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
            :class:`~guffin.common.code_language.CodeLanguage`.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    parsed: Final[FencedCodeBlock] = parse_fenced_code_block(node.string.strip())
    return CodeBlockVertex(
        uid=node.uid,
        code=parsed.code,
        language=CodeLanguage(parsed.info),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
    )


@validate_call
def to_block_quote_vertex(node: RoamNode, tree: NodeTree) -> BlockQuoteVertex:
    """Build a :class:`~guffin.vertex.BlockQuoteVertex` from a block-quote *node*.

    Strips the leading block-quote marker (``>`` or ``[[>]]``) from ``node.string``
    via :func:`~guffin.roam.primitives.strip_block_quote_marker` before storing the
    remaining content as :attr:`~guffin.vertex.BlockQuoteVertex.text`.

    Args:
        node: A block-quote node whose ``string`` starts with a recognised block-quote
            marker (standard Markdown ``>`` or Roam-specific ``[[>]]``).
        tree: The :class:`~guffin.roam.node_tree.NodeTree` the node belongs to;
            its :attr:`~guffin.roam.node_tree.NodeTree.id_map` is used to resolve
            child and ref stubs to UIDs.

    Returns:
        A :class:`~guffin.vertex.BlockQuoteVertex`.

    Raises:
        ValidationError: If *node* or *tree* is ``None`` or invalid.
        ValueError: If ``node.string`` is ``None`` or is not a recognised block quote.
    """
    logger.debug("node=%r, id_map keys=%r", node, list(tree.id_map.keys()))
    if node.string is None:
        raise ValueError(f"RoamNode uid={node.uid!r} has no 'string'")
    return BlockQuoteVertex(
        uid=node.uid,
        text=to_pandoc_md(strip_block_quote_marker(node.string), tree),
        children=_resolve_children(node, tree.id_map),
        refs=_resolve_refs(node, tree.id_map),
    )


@validate_call
def to_table(table_tree: NodeTree) -> Table:
    """Build a :class:`~guffin.common.table.Table` from a :class:`~guffin.roam.node_tree.NodeTree` rooted at a native.

    table.

    node.

    Reconstructs the 2-D cell grid from the Roam native table's chain structure.
    The root's direct children are the first-column cells, sorted by
    :attr:`~guffin.roam.node.RoamNode.order` to establish row sequence.  For each
    first-column cell, the algorithm follows the single-child chain — each cell's
    sole child is the next-column cell in the same row — collecting cell strings
    until the chain ends.  Each cell's :attr:`~guffin.roam.node.RoamNode.string`
    is passed through :func:`~guffin.pipeline.roam_md_to_pandoc_md.to_pandoc_md` before
    being stored.

    Args:
        table_tree: A :class:`~guffin.roam.node_tree.NodeTree` whose root is a
            :attr:`~guffin.roam.node.NodeType.ROAM_NATIVE_TABLE` node.

    Returns:
        A :class:`~guffin.common.table.Table` with default header flags.

    Raises:
        ValidationError: If *table_tree* is ``None`` or invalid.
        ValueError: If the root node has no children (empty table).
    """
    logger.debug("table_tree root uid=%r", table_tree.root_node.uid)
    root: Final[RoamNode] = table_tree.root_node
    if not root.children:
        raise ValueError(f"RoamNode uid={root.uid!r} has no children (empty table)")
    col1_cells: Final[list[RoamNode]] = sorted(
        [table_tree.id_map[c.id] for c in root.children if c.id in table_tree.id_map],
        key=lambda n: n.order if n.order is not None else 0,
    )
    rows: Final[list[tuple[str, ...]]] = []
    for col1_cell in col1_cells:
        row: list[str] = []
        cell: RoamNode | None = col1_cell
        while cell is not None:
            row.append(to_pandoc_md(cell.string, table_tree) if cell.string is not None else "")
            next_cells: list[RoamNode] = sorted(
                [table_tree.id_map[c.id] for c in (cell.children or []) if c.id in table_tree.id_map],
                key=lambda n: n.order if n.order is not None else 0,
            )
            cell = next_cells[0] if next_cells else None
        rows.append(tuple(row))
    return Table(rows=tuple(rows), has_row_header=True)


@validate_call
def to_table_vertex(node: RoamNode, tree: NodeTree) -> tuple[TableVertex, frozenset[Id]]:
    """Build a :class:`~guffin.vertex.TableVertex` from a native table *node*.

    Delegates :class:`~guffin.common.table.Table` construction to :func:`to_table`.
    All descendant nodes (rows and cells) are consumed into the returned
    :class:`~guffin.vertex.TableVertex`; consequently
    :attr:`~guffin.vertex.TableVertex.children` is always ``None`` — the descendants
    do not appear as separate vertices in the :class:`~guffin.vertex_tree.VertexTree`.
    The returned :class:`~python:frozenset` carries the :attr:`~guffin.roam.node.RoamNode.id`
    of every consumed descendant so that callers can skip them during traversal.

    Args:
        node: A native-table node whose :attr:`~guffin.roam.node.RoamNode.string`
            equals :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKER`.
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
    return (
        TableVertex(
            uid=node.uid,
            children=None,
            refs=_resolve_refs(node, tree.id_map),
            table=to_table(table_tree),
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
        case VertexType.GUFFIN_PAGE:
            return to_page_vertex(node, tree)
        case VertexType.GUFFIN_IMAGE:
            return to_image_vertex(node, tree)
        case VertexType.GUFFIN_HEADING:
            return to_heading_vertex(node, tree, heading_offset)
        case VertexType.GUFFIN_TEXT:
            return to_text_vertex(node, tree)
        case VertexType.GUFFIN_CALLOUT:
            return to_callout_vertex(node, tree)
        case VertexType.GUFFIN_CODE_BLOCK:
            return to_code_block_vertex(node, tree)
        case VertexType.GUFFIN_BLOCK_QUOTE:
            return to_block_quote_vertex(node, tree)
        case VertexType.GUFFIN_TABLE:
            raise NotImplementedError(f"RoamNode uid={node.uid!r}: GUFFIN_TABLE is not a standalone NodeType")
        case _ as unreachable:
            assert_never(unreachable)


@validate_call
def transcribe(node_tree: NodeTree) -> VertexTree:
    """Transcribe every node in *node_tree* into a :class:`~guffin.vertex_tree.VertexTree`.

    Traverses *node_tree* in pre-order DFS order.  Most nodes are transcribed
    one-to-one via :func:`transcribe_standalone_node`.  Exception: a
    :attr:`~guffin.roam.node.NodeType.ROAM_NATIVE_TABLE` node and all of its
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
        :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id`.  Referenced native-table
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
        if node_type(node) == NodeType.ROAM_NATIVE_TABLE:
            table_vertex, nodes_consumed = to_table_vertex(node, node_tree)
            consumed.update(nodes_consumed)
            vertices.append(table_vertex)
        else:
            vertices.append(transcribe_standalone_node(node, node_tree, heading_offset))
    ref_vertices: Final[list[Vertex]] = []
    ref_consumed: Final[set[Id]] = set()
    # Native tables are multi-node constructs: consume each referenced table together with its
    # row/cell descendants first, so those descendants are not also transcribed as standalone
    # ref vertices.  refs_by_id is not in DFS order, so a single-pass consumed-set guard could
    # encounter a cell before its table; a dedicated table pass avoids that.
    for ref_node in node_tree.refs_by_id.values():
        if node_type(ref_node) != NodeType.ROAM_NATIVE_TABLE:
            continue
        try:
            ref_table_vertex, ref_nodes_consumed = to_table_vertex(ref_node, node_tree)
        except (NotImplementedError, ValueError) as exc:
            logger.debug("skipping ref table node uid=%r: %s", ref_node.uid, exc)
            continue
        ref_consumed.update(ref_nodes_consumed)
        ref_vertices.append(ref_table_vertex)
    for ref_node in node_tree.refs_by_id.values():
        if ref_node.id in ref_consumed or node_type(ref_node) == NodeType.ROAM_NATIVE_TABLE:
            continue
        try:
            ref_vertices.append(transcribe_standalone_node(ref_node, node_tree))
        except (NotImplementedError, ValueError) as exc:
            logger.debug("skipping ref node uid=%r: %s", ref_node.uid, exc)
    return VertexTree(tree_vertices=vertices, ref_vertices=ref_vertices)
