"""VertexTree — normalized (transcribed) form of a NodeTree; traversal and filter helpers.

Public symbols:

- :class:`VertexTree` — normalized (transcribed) form of a
  :class:`~guffin.roam.node_tree.NodeTree`; a portable tree of :data:`~guffin.model.vertex.Vertex` instances.
- :meth:`VertexTree.dfs` — return a :class:`VertexTreeDFSIterator` for pre-order
  depth-first traversal.
- :class:`VertexTreeDFSIterator` — pre-order depth-first iterator over a
  :class:`VertexTree`.
- :func:`page_vertices` — return all :class:`~guffin.model.vertex.PageVertex` instances in a :class:`VertexTree`.
- :func:`heading_vertices` — return all :class:`~guffin.model.vertex.HeadingVertex` instances in a :class:`VertexTree`.
- :func:`text_vertices` — return all :class:`~guffin.model.vertex.TextVertex` instances in a
  :class:`VertexTree`.
- :func:`image_vertices` — return all :class:`~guffin.model.vertex.ImageVertex` instances in a :class:`VertexTree`.
- :func:`image_urls` — return all Cloud Firestore image URLs from a :class:`VertexTree`.
- :func:`root_vertex` — return the single root :data:`~guffin.model.vertex.Vertex` of a :class:`VertexTree`.
- :func:`map_vertices` — return a new :class:`VertexTree` with a mapping function applied to every vertex in both
  :attr:`VertexTree.tree_vertices` and :attr:`VertexTree.ref_vertices`.
- :func:`drop_attribute_assignments` — return a new :class:`VertexTree` with every
  :class:`~guffin.model.vertex.AttributeAssignmentVertex` (and its descendants) removed.
- :func:`enrich_image_original_sizes` — return a new :class:`VertexTree` with
  :attr:`~guffin.model.vertex.ImageVertex.original_image_size` populated from a UID→ImageSize map.
"""

import logging
from collections.abc import Callable, Iterator
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator, validate_call

from guffin.common.geometry import ImageSize

logger = logging.getLogger(__name__)
from guffin.model.primitives import Uid
from guffin.model.vertex import (
    AttributeAssignmentVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextVertex,
    Vertex,
)


def _default_ref_vertices() -> list[Annotated[Vertex, Field(discriminator="vertex_type")]]:
    return []


class VertexTree(BaseModel):
    """Normalized (transcribed) form of a :class:`~guffin.roam.node_tree.NodeTree`.

    Produced by :func:`~guffin.transcribe.roam_tree_to_guffin.transcribe`, which applies
    :func:`~guffin.transcribe.roam_tree_to_guffin.transcribe_standalone_node` to every node in the source
    :class:`~guffin.roam.node_tree.NodeTree` and collects the results here in the
    same insertion order.  The resulting collection is guaranteed to have exactly
    one :data:`~guffin.model.vertex.Vertex` per source :class:`~guffin.roam.node.RoamNode` and
    inherits the acyclic-tree structure of its origin.

    Attributes:
        tree_vertices: Transcribed vertices, one per source
            :class:`~guffin.roam.node.RoamNode`, in insertion order.
        ref_vertices: Stub vertices transcribed from
            :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` — nodes referenced
            from the anchor tree but not part of it.  Used only for UID lookup
            (e.g. by :func:`~guffin.render.pandoc_rendering.resolve_vertex_links`);
            not traversed by :class:`VertexTreeDFSIterator` or the filter helpers.
        uid_map: Map of :attr:`~guffin.model.vertex._BaseVertex.uid` →
            :data:`~guffin.model.vertex.Vertex` for every vertex in :attr:`tree_vertices` and
            :attr:`ref_vertices`; excluded from serialization.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    tree_vertices: list[Annotated[Vertex, Field(discriminator="vertex_type")]] = Field(
        ..., description="Transcribed vertices, one per source RoamNode."
    )
    ref_vertices: list[Annotated[Vertex, Field(discriminator="vertex_type")]] = Field(
        default_factory=_default_ref_vertices,
        description="Stub vertices for referenced nodes not in the anchor tree; for UID lookup only.",
    )
    uid_map: dict[Uid, Vertex] = Field(
        default_factory=dict,
        exclude=True,
        description="uid → Vertex map covering tree_vertices and ref_vertices; excluded from serialization.",
    )

    @model_validator(mode="after")
    def _build_uid_map(self) -> VertexTree:
        combined: dict[Uid, Vertex] = {v.uid: v for v in self.tree_vertices}
        combined.update({v.uid: v for v in self.ref_vertices})
        object.__setattr__(self, "uid_map", combined)
        return self

    def dfs(self) -> VertexTreeDFSIterator:
        """Return a pre-order depth-first iterator over this tree.

        Returns:
            A :class:`VertexTreeDFSIterator` seeded at the root of this tree.
        """
        return VertexTreeDFSIterator(self)


class VertexTreeDFSIterator(Iterator[Vertex]):
    """Pre-order depth-first iterator over a :class:`VertexTree`.

    Yields vertices starting from the single root, then recursively yields each
    child subtree in the order recorded in each vertex's
    :attr:`~guffin.model.vertex._BaseVertex.children` list (which preserves the original
    :attr:`~guffin.roam.node.RoamNode.order` sort applied during transcription).
    The traversal is non-recursive internally (stack-based), so deep trees do not
    risk hitting Python's recursion limit.

    Usage::

        for vertex in VertexTreeDFSIterator(tree):
            ...

    Attributes:
        _uid_map: Mapping from :attr:`~guffin.model.vertex._BaseVertex.uid` to
            :data:`~guffin.model.vertex.Vertex`; references the pre-built
            :attr:`~VertexTree.uid_map` from the source tree.
        _stack: LIFO stack of vertices yet to be visited; initialized with the
            root vertex.
    """

    def __init__(self, tree: VertexTree) -> None:
        """Initialize the iterator from *tree*.

        Stores a reference to *tree*'s pre-built :attr:`~VertexTree.uid_map`
        and seeds the stack with the single root vertex — the one whose uid
        does not appear in any other vertex's
        :attr:`~guffin.model.vertex._BaseVertex.children` list.

        Args:
            tree: The :class:`VertexTree` to traverse.
        """
        self._uid_map: dict[Uid, Vertex] = tree.uid_map
        self._stack: list[Vertex] = [root_vertex(tree)]

    def __iter__(self) -> Iterator[Vertex]:
        """Return *self* (this object is its own iterator)."""
        return self

    def __next__(self) -> Vertex:
        """Return the next vertex in pre-order depth-first traversal.

        Raises:
            StopIteration: When all vertices have been yielded.
        """
        if not self._stack:
            raise StopIteration
        vertex: Vertex = self._stack.pop()
        if vertex.children:
            children: list[Vertex] = [self._uid_map[uid] for uid in vertex.children if uid in self._uid_map]
            self._stack.extend(reversed(children))
        return vertex


@validate_call
def page_vertices(tree: VertexTree) -> list[PageVertex]:
    """Return all :class:`~guffin.model.vertex.PageVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.tree_vertices if isinstance(v, PageVertex)]


@validate_call
def heading_vertices(tree: VertexTree) -> list[HeadingVertex]:
    """Return all :class:`~guffin.model.vertex.HeadingVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.tree_vertices if isinstance(v, HeadingVertex)]


@validate_call
def text_vertices(tree: VertexTree) -> list[TextVertex]:
    """Return all :class:`~guffin.model.vertex.TextVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.tree_vertices if isinstance(v, TextVertex)]


@validate_call
def image_vertices(tree: VertexTree) -> list[ImageVertex]:
    """Return all :class:`~guffin.model.vertex.ImageVertex` instances in *tree*, in insertion order."""
    return [v for v in tree.tree_vertices if isinstance(v, ImageVertex)]


@validate_call
def image_urls(tree: VertexTree) -> list[HttpUrl]:
    """Return the Cloud Firestore URL of every :class:`~guffin.model.vertex.ImageVertex` in *tree*, in insertion.

    order.
    """
    return [v.source for v in image_vertices(tree)]


@validate_call
def root_vertex(tree: VertexTree) -> Vertex:
    """Return the single root :data:`~guffin.model.vertex.Vertex` of *tree*.

    The root is the unique vertex whose :attr:`~guffin.model.vertex._BaseVertex.uid` does not
    appear in any other vertex's :attr:`~guffin.model.vertex._BaseVertex.children` list.

    Args:
        tree: The :class:`VertexTree` to inspect.

    Returns:
        The root :data:`~guffin.model.vertex.Vertex`.
    """
    child_uids: Final[set[Uid]] = {uid for v in tree.tree_vertices if v.children for uid in v.children}
    return next(v for v in tree.tree_vertices if v.uid not in child_uids)


@validate_call
def map_vertices(tree: VertexTree, func: Callable[[Vertex], Vertex]) -> VertexTree:
    """Return a new :class:`VertexTree` with *func* applied to every vertex.

    The original *tree* is not modified; immutability is preserved via
    :meth:`~pydantic.BaseModel.model_copy`.

    Args:
        tree: The source :class:`VertexTree`.
        func: A callable that maps each :data:`~guffin.model.vertex.Vertex` to a
            (possibly new) :data:`~guffin.model.vertex.Vertex`.

    Returns:
        A new :class:`VertexTree` whose :attr:`~VertexTree.tree_vertices` are
        ``[func(v) for v in tree.tree_vertices]`` and whose
        :attr:`~VertexTree.ref_vertices` are ``[func(v) for v in tree.ref_vertices]``.
    """
    return VertexTree(
        tree_vertices=[func(vtx) for vtx in tree.tree_vertices],
        ref_vertices=[func(vtx) for vtx in tree.ref_vertices],
    )


@validate_call
def drop_attribute_assignments(tree: VertexTree) -> VertexTree:
    """Return a new :class:`VertexTree` with every attribute-assignment subtree removed.

    Every :class:`~guffin.model.vertex.AttributeAssignmentVertex` — and every vertex reachable
    through its :attr:`~guffin.model.vertex._BaseVertex.children` — is dropped from both
    :attr:`~VertexTree.tree_vertices` and :attr:`~VertexTree.ref_vertices`.  Each surviving
    vertex that listed a dropped vertex among its children has that child reference removed, so the
    result remains a well-formed tree.  The original *tree* is not modified.

    Args:
        tree: The source :class:`VertexTree`.

    Returns:
        A new :class:`VertexTree` with no :class:`~guffin.model.vertex.AttributeAssignmentVertex`
        (nor any descendant of one).
    """
    dropped: Final[set[Uid]] = set()
    stack: Final[list[Uid]] = [
        vtx.uid for vtx in (*tree.tree_vertices, *tree.ref_vertices) if isinstance(vtx, AttributeAssignmentVertex)
    ]
    while stack:
        uid: Uid = stack.pop()
        if uid in dropped:
            continue
        dropped.add(uid)
        vtx: Vertex | None = tree.uid_map.get(uid)
        if vtx is not None and vtx.children:
            stack.extend(vtx.children)

    def _prune(vertices: list[Vertex]) -> list[Vertex]:
        kept: list[Vertex] = []
        for vtx in vertices:
            if vtx.uid in dropped:
                continue
            if vtx.children and any(child in dropped for child in vtx.children):
                vtx = vtx.model_copy(update={"children": [child for child in vtx.children if child not in dropped]})
            kept.append(vtx)
        return kept

    return VertexTree(tree_vertices=_prune(tree.tree_vertices), ref_vertices=_prune(tree.ref_vertices))


@validate_call
def enrich_image_original_sizes(tree: VertexTree, sizes: dict[Uid, ImageSize]) -> VertexTree:
    """Return a new :class:`VertexTree` with :attr:`~guffin.model.vertex.ImageVertex.original_image_size` populated.

    Each :class:`~guffin.model.vertex.ImageVertex` whose UID appears in *sizes* receives a
    copy with :attr:`~guffin.model.vertex.ImageVertex.original_image_size` set to the
    corresponding :class:`~guffin.common.geometry.ImageSize`.  All other vertices pass
    through unchanged.

    Args:
        tree: The source :class:`VertexTree`.
        sizes: Mapping from :class:`~guffin.model.vertex.ImageVertex` UID to its native pixel dimensions.

    Returns:
        A new :class:`VertexTree` with :attr:`~guffin.model.vertex.ImageVertex.original_image_size`
        populated for all UIDs present in *sizes*.
    """

    def _enrich(vtx: Vertex) -> Vertex:
        if isinstance(vtx, ImageVertex):
            if vtx.uid in sizes:
                return vtx.model_copy(update={"original_image_size": sizes[vtx.uid]})
            logger.warning("ImageVertex uid=%r absent from sizes map; original_image_size left unset", vtx.uid)
        return vtx

    return map_vertices(tree, _enrich)
