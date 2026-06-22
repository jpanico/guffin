"""Shared tree-loading pipeline for Roam Research CLI commands.

Public symbols:

- :func:`fetch_roam_trees` — fetch nodes for a :class:`~guffin.roam.node_fetch_result.NodeFetchSpec`
  and return a :class:`~guffin.roam.node_fetch_result.NodeFetchResult` paired with an optional
  :class:`~guffin.vertex_tree.VertexTree`, ready for rendering or further processing.
"""

import logging
from typing import Final

from pydantic import validate_call

from guffin.model.vertex_tree import VertexTree
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import FetchRoamNodes
from guffin.roam.node_fetch_result import NodeFetchResult, NodeFetchSpec
from guffin.roam.node_tree import NodeTree
from guffin.pipeline.roam_tree_to_vertex_tree import transcribe

logger = logging.getLogger(__name__)


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
