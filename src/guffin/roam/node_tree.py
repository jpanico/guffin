"""Roam Research node-tree wrappers and traversal.

Public symbols:

- :class:`NodeTree` — a Pydantic-typed wrapper holding a :data:`~guffin.roam.node_network.NodeNetwork`;
  validates all tree invariants at construction time via :func:`is_tree`; must be created via
  :meth:`NodeTree.build`.
- :meth:`NodeTree.dfs` — return a :class:`NodeTreeDFSIterator` for pre-order depth-first traversal.
- :meth:`NodeTree.node_ids` — return the set of all :attr:`~guffin.roam.node.RoamNode.id` values in this tree.
- :meth:`NodeTree.node_refs_ids` — return the set of all :attr:`~guffin.roam.node.RoamNode.refs` ids across
  this tree.
- :meth:`NodeTree.external_refs_ids` — return the subset of :meth:`NodeTree.node_refs_ids` ids that fall outside
  :meth:`NodeTree.node_ids`.
- :class:`NodeTreeDFSIterator` — pre-order depth-first iterator over a :class:`NodeTree`.
- :func:`is_tree` — validate all tree invariants for a :class:`~guffin.roam.node.RoamNode` root
  and its :data:`~guffin.roam.node_network.NodeNetwork`; returns a
  :class:`~guffin.common.validation.ValidationResult`.
- :func:`to_table` — reconstruct a :class:`~guffin.common.table.Table` (raw cell strings) from a
  :class:`NodeTree` rooted at a Roam native-table node.
"""

import logging
from collections.abc import Iterator
from typing import Annotated, ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, model_validator, validate_call

from guffin.common.table import Table
from guffin.common.validation import ValidationError, ValidationResult, validate_all
from guffin.roam.node import NodeType, RoamNode, node_type
from guffin.roam.node_network import (
    NodeNetwork,
    all_children_present,
    all_descendants,
    all_parents_present,
    has_unique_ids,
    is_acyclic,
    refs_ids,
)
from guffin.roam.primitives import Id, Uid

logger = logging.getLogger(__name__)


class NodeTree(BaseModel):
    """A Pydantic-typed wrapper holding a :data:`~guffin.roam.node_network.NodeNetwork`.

    All tree invariants are validated at construction time via :func:`is_tree`; a
    :exc:`pydantic.ValidationError` is raised if *network* does not satisfy them.

    Instances must be created via :meth:`build` — direct construction raises
    :exc:`ValueError`.

    Attributes:
        root_node: The single root node of this tree.
        tree_network: All constituent nodes of this tree, including *root_node*.
        refs_by_id: Map of id → :class:`~guffin.roam.node.RoamNode` for every node in
            the source *super_network* that is either directly referenced via ``:block/refs``
            by a member of :attr:`tree_network`, or is a transitive descendant of such a
            node available in *super_network*; may be empty.
        id_map: Map of :attr:`~guffin.roam.node.RoamNode.id` → :class:`~guffin.roam.node.RoamNode`
            for every node in :attr:`tree_network` or :attr:`refs_by_id`; excluded from
            serialization.
        uid_map: Map of :attr:`~guffin.roam.node.RoamNode.uid` → :class:`~guffin.roam.node.RoamNode`
            for every node in :attr:`tree_network` or :attr:`refs_by_id`; excluded from
            serialization.
        page_name_map: Map of :attr:`~guffin.roam.node.RoamNode.title` →
            :class:`~guffin.roam.node.RoamNode` for every :attr:`~guffin.roam.node.NodeType.PAGE`
            node in :attr:`tree_network` or :attr:`refs_by_id`; excluded from serialization.

    Methods:
        build: Factory method — the only supported way to create a :class:`NodeTree`.
        dfs: Return a :class:`NodeTreeDFSIterator` for pre-order depth-first traversal.
        node_ids: Return the set of all :attr:`~guffin.roam.node.RoamNode.id` values in
            :attr:`tree_network`.
        node_refs_ids: Return the set of all :attr:`~guffin.roam.node.RoamNode.refs` ids
            across :attr:`tree_network`.
        external_refs_ids: Return the subset of :meth:`node_refs_ids` ids that are not members
            of :meth:`node_ids` — i.e. refs that resolve to nodes outside this tree.
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    _creating: ClassVar[bool] = False

    # Every field below holds already-validated, frozen RoamNodes assembled by build() from a
    # super_network that was validated on fetch.  SkipValidation stops the Pydantic constructor from
    # re-validating each node (and it appears in several maps, so it would be re-validated several
    # times over) on every NodeTree construction; the structural _validate_is_tree check still runs.
    root_node: Annotated[RoamNode, SkipValidation] = Field(..., description="The single root node of this tree.")
    tree_network: Annotated[NodeNetwork, SkipValidation] = Field(
        ..., description="All constituent nodes of this tree, including root_node."
    )
    refs_by_id: Annotated[dict[Id, RoamNode], SkipValidation] = Field(
        ...,
        description=(
            "Map of id → RoamNode for every node in super_network that is either directly referenced via "
            ":block/refs by a member of tree_network, or is a transitive descendant of such a node "
            "available in super_network; may be empty."
        ),
    )
    id_map: Annotated[dict[Id, RoamNode], SkipValidation] = Field(
        ...,
        exclude=True,
        description="Map of id → RoamNode for every node in tree_network or refs_by_id.",
    )
    uid_map: Annotated[dict[Uid, RoamNode], SkipValidation] = Field(
        ...,
        exclude=True,
        description="Map of uid → RoamNode for every node in tree_network or refs_by_id.",
    )
    page_name_map: Annotated[dict[str, RoamNode], SkipValidation] = Field(
        ...,
        exclude=True,
        description="Map of title → RoamNode for every PAGE node in tree_network or refs_by_id.",
    )

    @classmethod
    def build(cls, root_node: RoamNode, super_network: NodeNetwork) -> NodeTree:
        """Create a validated :class:`NodeTree` — the only supported construction path.

        Uses :func:`~guffin.roam.node_network.all_descendants` to extract the subtree rooted
        at *root_node* from *super_network*, builds :attr:`refs_by_id` from the direct ref
        targets of :attr:`tree_network` plus all their transitive descendants and the second-hop
        ref targets of those (bare nodes) available in *super_network*, derives :attr:`id_map`,
        :attr:`uid_map`, and :attr:`page_name_map`
        from the combined node pool, then delegates to the Pydantic constructor (which runs
        all validators including :meth:`_validate_is_tree`).

        Args:
            root_node: The single root node of the tree.
            super_network: Source node pool from which the tree's constituent nodes are
                drawn.  The :class:`~guffin.roam.node.RoamNode` instances in
                *super_network* are a superset of the nodes that will form
                :attr:`tree_network`.  Nodes outside :attr:`tree_network` are also
                searched for :attr:`refs_by_id` — both direct ref targets and their
                transitive descendants.  Child ids of ref nodes absent from
                *super_network* are skipped silently: the fetch query intentionally omits
                the subtrees of non-embed refs.

        Returns:
            A fully validated :class:`NodeTree`.

        Raises:
            ValueError: If *root_node* is not present in *super_network*, if any child
                id encountered during tree extraction cannot be resolved within
                *super_network*, or if any direct refs id from :attr:`tree_network` cannot
                be resolved within *super_network*.
            pydantic.ValidationError: If the extracted :attr:`tree_network` violates any
                tree invariant.
        """
        tree_ids: Final[set[Id]] = {root_node.id} | {n.id for n in all_descendants(root_node, super_network)}
        tree_network: Final[NodeNetwork] = [n for n in super_network if n.id in tree_ids]
        refs_by_id: Final[dict[Id, RoamNode]] = cls._build_refs_by_id(tree_network, super_network)
        id_map: Final[dict[Id, RoamNode]] = {n.id: n for n in tree_network} | refs_by_id
        uid_map: Final[dict[Uid, RoamNode]] = {n.uid: n for n in id_map.values()}
        page_name_map: Final[dict[str, RoamNode]] = {
            n.title: n for n in id_map.values() if node_type(n) == NodeType.PAGE and n.title is not None
        }
        cls._creating = True
        try:
            return cls(
                root_node=root_node,
                tree_network=tree_network,
                refs_by_id=refs_by_id,
                id_map=id_map,
                uid_map=uid_map,
                page_name_map=page_name_map,
            )
        finally:
            cls._creating = False

    @classmethod
    def _build_refs_by_id(cls, tree_network: NodeNetwork, super_network: NodeNetwork) -> dict[Id, RoamNode]:
        """Build the ``refs_by_id`` map from *tree_network*'s refs, their descendants, and second-hop refs.

        Collects all direct ``:block/refs`` targets of *tree_network* nodes, validates that each
        resolves within *super_network*, then expands with all transitive descendants of those ref
        nodes available in *super_network*.  Finally adds the second-hop ref targets — the
        ``:block/refs`` of the gathered (first-hop) ref nodes and their descendants — as bare nodes,
        so a referenced node's own attributes (e.g. a ``tags::`` attribute on a referenced page) can
        resolve their page references.  Matches the two-hop reach of the with-refs fetch query.
        Missing child ids are skipped silently — the fetch query intentionally omits subtrees of
        non-embed refs (and of second-hop refs).

        Args:
            tree_network: The constituent nodes of the tree.
            super_network: Source node pool; searched for direct ref targets and their transitive
                descendants.

        Returns:
            A ``dict[Id, RoamNode]`` mapping every resolved ref node and its available transitive
            descendants.  Ref ids that cannot be resolved in *super_network* are silently skipped
            (e.g. when the fetch was run with ``include_refs=False``).
        """
        super_by_id: Final[dict[Id, RoamNode]] = {n.id: n for n in super_network}
        tree_refs_ids: Final[set[Id]] = refs_ids(tree_network)
        direct_refs: Final[dict[Id, RoamNode]] = {n.id: n for n in super_network if n.id in tree_refs_ids}
        unresolvable_refs: Final[set[Id]] = tree_refs_ids - direct_refs.keys()
        if unresolvable_refs:
            logger.debug(
                "refs id(s) %r referenced in tree_network not present in super_network; skipping"
                " (fetch was likely run with include_refs=False)",
                sorted(unresolvable_refs),
            )
        refs_by_id: Final[dict[Id, RoamNode]] = dict(direct_refs)
        stack: Final[list[RoamNode]] = list(direct_refs.values())
        while stack:
            ref_node: RoamNode = stack.pop()
            if not ref_node.children:
                continue
            for child_ref in ref_node.children:
                if child_ref.id in refs_by_id:
                    continue
                child: RoamNode | None = super_by_id.get(child_ref.id)
                if child is None:
                    continue
                refs_by_id[child_ref.id] = child
                stack.append(child)
        # Second ref hop: include the ref targets of everything gathered so far (the first-hop ref
        # targets and their descendants) as bare nodes, matching the two-hop fetch query, so a
        # referenced node's own attributes (e.g. a `tags::` attribute on a referenced page) can
        # resolve their page references.  Their subtrees are intentionally not expanded — child stubs
        # absent from super_network are skipped, bounding the pool to two ref hops.
        second_hop_ids: Final[set[Id]] = refs_ids(list(refs_by_id.values())) - refs_by_id.keys()
        for second_hop_id in second_hop_ids:
            second_hop_node: RoamNode | None = super_by_id.get(second_hop_id)
            if second_hop_node is not None:
                refs_by_id[second_hop_id] = second_hop_node
        return refs_by_id

    @model_validator(mode="before")
    @classmethod
    def _require_build(cls, data: object) -> object:
        """Reject direct construction and require use of :meth:`build`.

        Raises:
            ValueError: Always, unless called from within :meth:`build`.
        """
        if not cls._creating:
            raise ValueError("NodeTree must be created via NodeTree.build(); direct construction is not supported.")
        return data

    @model_validator(mode="after")
    def _validate_is_tree(self) -> NodeTree:
        """Validate all tree invariants on *network* at construction time.

        Raises:
            ValueError: If *network* violates any tree invariant; the message lists every
                :class:`~guffin.common.validation.ValidationError` found.
        """
        result: Final[ValidationResult] = is_tree(self.root_node, self.tree_network)
        if not result.is_valid:
            raise ValueError("NodeTree network validation failed: " + "; ".join(str(e) for e in result.errors))
        return self

    def dfs(self) -> NodeTreeDFSIterator:
        """Return a pre-order depth-first iterator over this tree.

        Returns:
            A :class:`NodeTreeDFSIterator` seeded at the root of this tree.
        """
        return NodeTreeDFSIterator(self)

    def node_ids(self) -> set[Id]:
        """Return the set of all :attr:`~guffin.roam.node.RoamNode.id` values in this tree's network.

        Returns:
            A ``set[Id]`` containing the :attr:`~guffin.roam.node.RoamNode.id` of every node
            in :attr:`tree_network`.
        """
        return {n.id for n in self.tree_network}

    def node_refs_ids(self) -> set[Id]:
        """Return the set of all :attr:`~guffin.roam.node.RoamNode.refs` ids across this tree's network.

        Delegates to :func:`~guffin.roam.node_network.refs_ids` over :attr:`tree_network`.

        Returns:
            A ``set[Id]`` containing every id found in any node's ``refs`` list; empty if no node
            in :attr:`tree_network` has any ``refs``.
        """
        return refs_ids(self.tree_network)

    def external_refs_ids(self) -> set[Id]:
        """Return the subset of :meth:`node_refs_ids` ids that are not members of :meth:`node_ids`.

        These are ids referenced via ``:block/refs`` by nodes in this tree but resolved to nodes
        that live outside the tree — i.e. pages or blocks not included in :attr:`tree_network`.

        Returns:
            A ``set[Id]`` equal to ``node_refs_ids() - node_ids()``; empty when every ref id
            resolves to a node already in :attr:`network`.
        """
        return self.node_refs_ids() - self.node_ids()


class NodeTreeDFSIterator(Iterator[RoamNode]):
    """Pre-order depth-first iterator over a :class:`NodeTree`.

    Yields nodes starting from the single root, then recursively yields each
    child subtree in ascending :attr:`~guffin.roam.node.RoamNode.order` order.  The traversal
    is non-recursive internally (stack-based), so deep trees do not risk
    hitting Python's recursion limit.

    Usage::

        for node in NodeTreeDFSIterator(tree):
            ...

    Attributes:
        _id_map: Mapping from :attr:`~guffin.roam.node.RoamNode.id` to :class:`~guffin.roam.node.RoamNode`,
            built once at construction time.
        _stack: LIFO stack of nodes yet to be visited; initialized with the
            root node.
    """

    def __init__(self, tree: NodeTree) -> None:
        """Initialize the iterator from *tree*.

        Stores a reference to *tree*'s pre-built :attr:`~NodeTree.id_map` and
        seeds the stack with the single root node.

        Args:
            tree: The :class:`NodeTree` to traverse.
        """
        self._id_map: dict[Id, RoamNode] = tree.id_map
        self._stack: list[RoamNode] = [tree.root_node]

    def __iter__(self) -> Iterator[RoamNode]:
        """Return *self* (this object is its own iterator)."""
        return self

    def __next__(self) -> RoamNode:
        """Return the next node in pre-order depth-first traversal.

        Raises:
            StopIteration: When all nodes have been yielded.
        """
        if not self._stack:
            raise StopIteration
        node: RoamNode = self._stack.pop()
        if node.children:
            children: list[RoamNode] = sorted(
                [self._id_map[c.id] for c in node.children if c.id in self._id_map],
                key=lambda n: n.order if n.order is not None else 0,
            )
            self._stack.extend(reversed(children))
        return node


@validate_call
def is_tree(root_node: RoamNode, network: NodeNetwork) -> ValidationResult:
    """Return a :class:`~guffin.common.validation.ValidationResult` for all tree invariants on *network*.

    Runs every tree-invariant validator — :func:`~guffin.roam.node_network.has_unique_ids`,
    :func:`~guffin.roam.node_network.all_children_present`,
    :func:`~guffin.roam.node_network.all_parents_present`, and
    :func:`~guffin.roam.node_network.is_acyclic` — via
    :func:`~guffin.common.validation.validate_all`.  All validators run regardless of prior failures;
    the result accumulates every error found.

    Args:
        root_node: The single root node of *network*.
        network: The collection of nodes to validate.

    Returns:
        A :class:`~guffin.common.validation.ValidationResult` that is valid when *network* satisfies
        every tree invariant, or contains one :class:`~guffin.common.validation.ValidationError` per
        failed validator otherwise.
    """
    logger.debug("root_node=%r, network=%r", root_node, network)

    def _check_parents(network: NodeNetwork) -> ValidationError | None:
        return all_parents_present(network, root_node)

    return validate_all(
        network,
        [
            has_unique_ids,
            all_children_present,
            _check_parents,
            is_acyclic,
        ],
    )


@validate_call
def to_table(table_tree: NodeTree) -> Table:
    """Reconstruct a :class:`~guffin.common.table.Table` from a Roam native-table :class:`NodeTree`.

    Rebuilds the 2-D cell grid from the Roam native table's chain structure.  The root's direct
    children are the first-column cells, sorted by :attr:`~guffin.roam.node.RoamNode.order` to
    establish row sequence.  For each first-column cell, the algorithm follows the single-child
    chain — each cell's sole child is the next-column cell in the same row — collecting cell
    strings until the chain ends.

    Cell strings are stored verbatim (the raw Roam :attr:`~guffin.roam.node.RoamNode.string`); any
    Markdown normalization is the caller's concern.

    Args:
        table_tree: A :class:`NodeTree` whose root is a
            :attr:`~guffin.roam.node.NodeType.NATIVE_TABLE` node.

    Returns:
        A :class:`~guffin.common.table.Table` of raw cell strings, with a row header.

    Raises:
        ValidationError: If *table_tree* is ``None`` or invalid.
        ValueError: If the root node is not a :attr:`~guffin.roam.node.NodeType.NATIVE_TABLE` node,
            or if it has no children (empty table).
    """
    logger.debug("table_tree root uid=%r", table_tree.root_node.uid)
    root: Final[RoamNode] = table_tree.root_node
    if node_type(root) is not NodeType.NATIVE_TABLE:
        raise ValueError(f"RoamNode uid={root.uid!r} is not a native table (node_type={node_type(root)})")
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
            row.append(cell.string if cell.string is not None else "")
            next_cells: list[RoamNode] = sorted(
                [table_tree.id_map[c.id] for c in (cell.children or []) if c.id in table_tree.id_map],
                key=lambda n: n.order if n.order is not None else 0,
            )
            cell = next_cells[0] if next_cells else None
        rows.append(tuple(row))
    return Table(rows=tuple(rows), has_row_header=True)
