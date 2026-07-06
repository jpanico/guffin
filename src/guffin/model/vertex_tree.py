"""VertexTree — normalized (transcribed) form of a NodeTree; traversal and transform helpers.

Public symbols:

- :class:`VertexTree` — normalized (transcribed) form of a
  :class:`~guffin.roam.node_tree.NodeTree`; a portable tree of :data:`~guffin.model.vertex.Vertex` instances.
- :meth:`VertexTree.dfs` — return a :class:`VertexTreeDFSIterator` for pre-order
  depth-first traversal.
- :class:`VertexTreeDFSIterator` — pre-order depth-first iterator over a
  :class:`VertexTree`.
- :func:`transcluded_vertices` — return every render-visible vertex in a :class:`VertexTree`: the
  tree vertices plus all content transcluded through block embeds.
- :func:`assignments_for` — return every ``(vertex, assignment)`` pair in a :class:`VertexTree`
  whose assignment is for a given :class:`~guffin.model.attribute.Attribute`.
- :func:`root_vertex` — return the single root :data:`~guffin.model.vertex.Vertex` of a :class:`VertexTree`.
- :func:`map_vertices` — return a new :class:`VertexTree` with a mapping function applied to every vertex in both
  :attr:`VertexTree.tree_vertices` and :attr:`VertexTree.ref_vertices`.
- :func:`drop_attribute_assignments` — return a new :class:`VertexTree` with every vertex's
  :attr:`~guffin.model.vertex._BaseVertex.attribute_assignments` cleared.
- :func:`drop_root_preamble` — return a new :class:`VertexTree` with the root vertex's loose
  preamble (children preceding its first heading child) pruned.
- :func:`enrich_image_original_sizes` — return a new :class:`VertexTree` with
  :attr:`~guffin.model.vertex.ImageVertex.original_image_size` populated from a UID→ImageSize map.
- :func:`enrich_pdf_original_file_names` — return a new :class:`VertexTree` with
  :attr:`~guffin.model.vertex.PdfVertex.original_file_name` populated from a UID→filename map.
"""

import logging
from collections import deque
from collections.abc import Callable, Iterator
from itertools import chain
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, model_validator, validate_call

from guffin.common.geometry import ImageSize

logger = logging.getLogger(__name__)
from guffin.model.attribute import Attribute
from guffin.model.attribute_assignment import AttributeAssignment, is_assignment_for
from guffin.model.primitives import Uid
from guffin.model.vertex import (
    BlockEmbedVertex,
    HeadingVertex,
    ImageVertex,
    PdfVertex,
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
            not traversed by :class:`VertexTreeDFSIterator` (though
            :func:`transcluded_vertices` reaches those transcluded via block embeds).
        uid_map: Map of :attr:`~guffin.model.vertex._BaseVertex.uid` →
            :data:`~guffin.model.vertex.Vertex` for every vertex in :attr:`tree_vertices` and
            :attr:`ref_vertices`; excluded from serialization.
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

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
def transcluded_vertices(tree: VertexTree) -> list[Vertex]:
    """Return every render-visible vertex in *tree*: the tree vertices plus all transcluded content.

    A :class:`~guffin.model.vertex.BlockEmbedVertex` transcludes its target — the target vertex and
    its whole subtree are reproduced at the embed site — so a vertex reachable only through
    :attr:`VertexTree.ref_vertices` may still contribute content to a rendered document.  This
    helper returns :attr:`VertexTree.tree_vertices` followed by every additional vertex reachable
    through a block embed's target subtree, with embeds inside transcluded content followed
    recursively (cycles terminate).  A referenced vertex that is merely *mentioned* (a page or
    block reference, which renders inline as text) is not transcluded and is not included.  Embed
    targets absent from :attr:`VertexTree.uid_map` are skipped.

    Args:
        tree: The :class:`VertexTree` to walk.

    Returns:
        The render-visible vertices, each appearing once (deduplicated by UID): the tree vertices
        first, in insertion order, then the transcluded vertices in first-reached order.
    """
    visible: Final[list[Vertex]] = []
    seen: Final[set[Uid]] = set()
    queue: Final[deque[Vertex]] = deque(tree.tree_vertices)
    while queue:
        vertex: Vertex = queue.popleft()
        if vertex.uid in seen:
            continue
        seen.add(vertex.uid)
        visible.append(vertex)
        # Children may live outside tree_vertices when *vertex* was reached through an embed.
        queue.extend(tree.uid_map[uid] for uid in vertex.children or () if uid in tree.uid_map)
        if isinstance(vertex, BlockEmbedVertex) and vertex.vertex_link.uid in tree.uid_map:
            queue.append(tree.uid_map[vertex.vertex_link.uid])
    return visible


@validate_call
def assignments_for(tree: VertexTree, attribute: Attribute) -> Iterator[tuple[Vertex, AttributeAssignment]]:
    """Return every ``(vertex, assignment)`` pair in *tree* whose assignment is for *attribute*.

    An assignment matches per :func:`~guffin.model.attribute_assignment.is_assignment_for` (identity:
    name + domain).  Both the tree vertices and the referenced-vertex stubs
    (:attr:`VertexTree.ref_vertices`) are walked.

    Args:
        tree: The :class:`VertexTree` to walk.
        attribute: The attribute whose assignments to return.

    Returns:
        A lazy iterator of each matching assignment, paired with the vertex it is declared on.
    """
    return (
        (vertex, assignment)
        for vertex in chain(tree.tree_vertices, tree.ref_vertices)
        for assignment in vertex.attribute_assignments or ()
        if is_assignment_for(assignment, attribute)
    )


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
    """Return a new :class:`VertexTree` with every vertex's attribute assignments cleared.

    Each vertex's :attr:`~guffin.model.vertex._BaseVertex.attribute_assignments` is set to ``None``,
    so the rendered output omits the Roam attribute pills.  All other fields are preserved and the
    original *tree* is not modified.

    Args:
        tree: The source :class:`VertexTree`.

    Returns:
        A new :class:`VertexTree` whose vertices all have ``attribute_assignments=None``.
    """

    def _clear(vtx: Vertex) -> Vertex:
        return vtx.model_copy(update={"attribute_assignments": None}) if vtx.attribute_assignments else vtx

    return map_vertices(tree, _clear)


@validate_call
def drop_root_preamble(tree: VertexTree) -> VertexTree:
    """Return a new :class:`VertexTree` with the root vertex's loose preamble pruned.

    The *loose preamble* is the run of the root vertex's children that precede its first
    :class:`~guffin.model.vertex.HeadingVertex` child — content that belongs
    to no titled division.  Those children (and their entire subtrees) are removed from
    :attr:`~VertexTree.tree_vertices` and from the root's
    :attr:`~guffin.model.vertex._BaseVertex.children` list.  The rule is root-type-independent:
    whether the tree roots at a page or at a subtree export's heading or block, the root is the
    document's container and its children are the document's top-level run.  The original *tree*
    is not modified.

    The tree passes through unchanged when there is nothing to prune or nothing to anchor the
    prune to:

    - the root has no children;
    - the root's first child is already a heading (no preamble);
    - the root has no heading children at all (every child would be preamble; the content is
      retained and a warning is logged instead).

    Args:
        tree: The source :class:`VertexTree`.

    Returns:
        A new :class:`VertexTree` without the preamble vertices, or *tree* itself when no prune
        applies.
    """
    root: Final[Vertex] = root_vertex(tree)
    if not root.children:
        return tree
    child_vertices: Final[list[Vertex]] = [tree.uid_map[uid] for uid in root.children]
    heading_index: Final[int | None] = next(
        (idx for idx, vtx in enumerate(child_vertices) if isinstance(vtx, HeadingVertex)), None
    )
    if heading_index is None:
        logger.warning("root vertex uid=%r has no heading children; loose preamble retained", root.uid)
        return tree
    if heading_index == 0:
        return tree

    # Collect the preamble children and every descendant beneath them.
    preamble_uids: Final[set[Uid]] = set()
    pending: Final[list[Uid]] = list(root.children[:heading_index])
    while pending:
        uid = pending.pop()
        preamble_uids.add(uid)
        vertex = tree.uid_map.get(uid)
        if vertex is not None and vertex.children:
            pending.extend(vertex.children)
    logger.info(
        "dropping %d loose preamble vertices ahead of the first heading child of root vertex uid=%r",
        len(preamble_uids),
        root.uid,
    )

    pruned_root: Final[Vertex] = root.model_copy(update={"children": list(root.children[heading_index:])})
    return VertexTree(
        tree_vertices=[
            pruned_root if vtx.uid == root.uid else vtx for vtx in tree.tree_vertices if vtx.uid not in preamble_uids
        ],
        ref_vertices=tree.ref_vertices,
    )


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


@validate_call
def enrich_pdf_original_file_names(tree: VertexTree, names: dict[Uid, str]) -> VertexTree:
    """Return a new :class:`VertexTree` with :attr:`~guffin.model.vertex.PdfVertex.original_file_name` populated.

    Each :class:`~guffin.model.vertex.PdfVertex` whose UID appears in *names* receives a copy with
    :attr:`~guffin.model.vertex.PdfVertex.original_file_name` set to the corresponding name.  All
    other vertices — including PDF vertices absent from *names*, whose original filename is simply
    unknown — pass through unchanged.

    Args:
        tree: The source :class:`VertexTree`.
        names: Mapping from :class:`~guffin.model.vertex.PdfVertex` UID to the filename the PDF
            was originally uploaded under.

    Returns:
        A new :class:`VertexTree` with
        :attr:`~guffin.model.vertex.PdfVertex.original_file_name` populated for all UIDs present
        in *names*.
    """

    def _enrich(vtx: Vertex) -> Vertex:
        if isinstance(vtx, PdfVertex) and vtx.uid in names:
            return vtx.model_copy(update={"original_file_name": names[vtx.uid]})
        return vtx

    return map_vertices(tree, _enrich)
