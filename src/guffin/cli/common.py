"""Shared tree-loading pipeline for Roam Research CLI commands.

Public symbols:

- :func:`fetch_roam_trees` — fetch nodes for a :class:`~guffin.roam.node_fetch_result.NodeFetchSpec`
  and return a :class:`~guffin.roam.node_fetch_result.NodeFetchResult` paired with an optional
  :class:`~guffin.vertex_tree.VertexTree`, ready for rendering or further processing.
- :func:`deduce_out_file_stem` — derive a shell-safe output filename stem from a
  :class:`~guffin.model.vertex_tree.VertexTree`'s root vertex.
"""

import logging
import textwrap
from typing import Final

import regex
from pydantic import validate_call

from guffin.common.filenames import shell_safe_filename
from guffin.model.vertex import (
    BlockEmbedVertex,
    BlockQuoteVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
)
from guffin.model.vertex_tree import VertexTree, root_vertex
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import FetchRoamNodes
from guffin.roam.node_fetch_result import NodeFetchResult, NodeFetchSpec
from guffin.roam.node_tree import NodeTree
from guffin.pipeline.roam_tree_to_vertex_tree import transcribe

logger = logging.getLogger(__name__)

_MD_LINK_RE: Final[regex.Pattern[str]] = regex.compile(r"\[([^\]]*)\]\([^)]*\)")
"""Matches a Markdown inline link ``[text](url)``; group 1 is the link text.

Used to unwrap links to their text when deriving a filename stem, so a rendered page
reference like ``[Test Article](x-guffin:vertex/abc)`` contributes only ``Test Article``
rather than leaking the URL into the filename.
"""


@validate_call
def fetch_roam_trees(
    fetch_spec: NodeFetchSpec,
    include_vertex_tree: bool,
    api_endpoint: ApiEndpoint,
) -> tuple[NodeFetchResult, VertexTree | None]:
    """Fetch Roam nodes for *fetch_spec* and build a validated node tree and vertex tree.

    Fetches :class:`~guffin.roam.node.RoamNode` records for *fetch_spec* via
    *api_endpoint*, constructs a :class:`~guffin.roam.node_tree.NodeTree`, and optionally
    transcribes it to a :class:`~guffin.vertex_tree.VertexTree`.

    Propagates any exception raised during fetching or transcription; callers are
    responsible for exit behaviour.

    Args:
        fetch_spec: The fetch specification carrying the anchor, include_refs flag, and
            include_node_tree flag.
        include_vertex_tree: When ``True``, transcribes the node tree to a
            :class:`~guffin.vertex_tree.VertexTree` and returns it as the second element of
            the pair.  When ``False``, skips transcription and returns ``None`` instead.
        api_endpoint: Configured API endpoint used to fetch nodes.

    Returns:
        A ``(fetch_result, vertex_tree)`` pair ready for rendering or further processing.
        ``vertex_tree`` is ``None`` when *include_vertex_tree* is ``False``.
    """
    result: Final[NodeFetchResult] = FetchRoamNodes.fetch_roam_nodes(
        anchor=fetch_spec.anchor,
        api_endpoint=api_endpoint,
        include_refs=fetch_spec.include_refs,
        include_node_tree=fetch_spec.include_node_tree or include_vertex_tree,
    )

    if not include_vertex_tree:
        logger.debug("result=%r", result)
        return result, None

    assert (
        result.anchor_tree is not None
    ), "anchor_tree is None; fetch_spec has include_node_tree=False, which is unsupported here"
    anchor_tree: Final[NodeTree] = result.anchor_tree
    vertex_tree: Final[VertexTree] = transcribe(anchor_tree)
    logger.debug("node_tree=%r\n\nvertex_tree=%r", anchor_tree, vertex_tree)
    return result, vertex_tree


def _stem_basis(vertex: Vertex, vertex_tree: VertexTree) -> str:
    """Return the raw (un-clipped) filename-stem basis for *vertex*.

    For a :class:`~guffin.model.vertex.BlockEmbedVertex`, recurses into the embedded
    vertex resolved through *vertex_tree*'s ``uid_map``.
    """
    match vertex:
        case PageVertex():
            return vertex.title
        case HeadingVertex() | TextVertex() | BlockQuoteVertex():
            return vertex.text
        case ImageVertex():
            return vertex.alt_text or vertex.file_name or str(vertex.source)
        case CalloutVertex():
            return vertex.title or vertex.body
        case CodeBlockVertex():
            return vertex.code
        case TableVertex():
            return "_".join(vertex.table.rows[0])
        case BlockEmbedVertex():
            return _stem_basis(vertex_tree.uid_map[vertex.vertex_link.uid], vertex_tree)


@validate_call
def deduce_out_file_stem(vertex_tree: VertexTree) -> str:
    """Derive a filename stem for the export output from *vertex_tree*'s root vertex.

    The stem basis is taken from the root vertex according to its type — page title,
    block text, image alt-text/filename/source, callout title-or-body, code, the
    first table row's cells joined by ``_``, or (for a block embed) the embedded
    vertex's basis.  Markdown links in the basis are unwrapped to their text (so a
    rendered page reference contributes only its text, not the URL), then the basis is
    shortened to 40 characters and normalised to a POSIX-safe filename.

    Args:
        vertex_tree: The transcribed tree whose root supplies the stem basis.

    Returns:
        A shell-safe filename stem (no extension or directory component).
    """
    basis: Final[str] = _stem_basis(root_vertex(vertex_tree), vertex_tree)
    unwrapped_basis: Final[str] = _MD_LINK_RE.sub(r"\1", basis)
    clipped_basis: Final[str] = textwrap.shorten(unwrapped_basis, width=40, placeholder="..._")
    return shell_safe_filename(clipped_basis)
