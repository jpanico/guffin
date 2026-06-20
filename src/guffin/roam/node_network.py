"""Roam Research node-network type and validators.

Public symbols:

- :data:`NodeNetwork` — a collection of :class:`~guffin.roam.node.RoamNode` instances.
- :func:`all_children_present` — :data:`~guffin.common.validation.Validator` requiring all child ids in a
  :data:`NodeNetwork` to resolve to member nodes.
- :func:`all_descendants` — collect all nodes reachable from an ancestor via child edges.
- :func:`all_parents_present` — validator function requiring all non-root parent ids in a
  :data:`NodeNetwork` to resolve to member nodes; accepts a *root_node* argument whose own
  parent ids are exempt from the check.
- :func:`has_unique_ids` — :data:`~guffin.common.validation.Validator` requiring every
  :attr:`~guffin.roam.node.RoamNode.id` in a :data:`NodeNetwork` to be unique.
- :func:`is_acyclic` — :data:`~guffin.common.validation.Validator` requiring the child-edge graph of a
  :data:`NodeNetwork` to be cycle-free.
- :func:`refs_ids` — return the set of all :attr:`~guffin.roam.node.RoamNode.refs` ids across every
  node in a :data:`NodeNetwork`.
- :func:`direct_refs_nodes` — return the :data:`NodeNetwork` of nodes in a :data:`NodeNetwork` whose
  :attr:`~guffin.roam.node.RoamNode.id` is referenced by any node's
  :attr:`~guffin.roam.node.RoamNode.refs` list.
- :func:`refs_nodes` — return the :data:`NodeNetwork` of all direct-ref target nodes in a
  :data:`NodeNetwork` plus all of their transitive descendants available in that network.
- :func:`min_effective_heading_level` — return the minimum effective heading level across all
  nodes in a :data:`NodeNetwork`, or ``None`` if no node is a heading.
"""

from typing import Final

from pydantic import validate_call

from guffin.roam.node import RoamNode, effective_heading_level
from guffin.common.markdown import HeadingLevel
from guffin.roam.primitives import Id, Uid
from guffin.common.validation import ValidationError

type NodeNetwork = list[RoamNode]
"""A collection of :class:`~guffin.roam.node.RoamNode` instances.

Relationships between nodes are encoded via :attr:`~guffin.roam.node.RoamNode.children`,
:attr:`~guffin.roam.node.RoamNode.parents`, and :attr:`~guffin.roam.node.RoamNode.page` as
:class:`~guffin.roam.primitives.IdObject` stubs referencing :attr:`~guffin.roam.node.RoamNode.id`
values within the collection.
"""


@validate_call
def all_children_present(network: NodeNetwork) -> ValidationError | None:
    """Return ``None`` when every child id referenced in *network* resolves to a node in *network*.

    Iterates every node in *network* and checks that each :attr:`~guffin.roam.node.RoamNode.id`
    value found in a node's :attr:`~guffin.roam.node.RoamNode.children` list corresponds to the
    :attr:`~guffin.roam.node.RoamNode.id` of at least one node in *network*.

    A network with no children at all vacuously satisfies this condition and
    returns ``None``.

    Args:
        network: The collection of nodes to examine.

    Returns:
        ``None`` if every child id in *network* resolves to a node in *network*;
        a :class:`~guffin.common.validation.ValidationError` listing the sorted
        absent child ids and the sorted ids of the nodes that referenced them otherwise.
    """
    network_ids: Final[set[Id]] = {n.id for n in network}
    violations: Final[list[tuple[Id, Id]]] = [
        (n.id, child.id) for n in network if n.children for child in n.children if child.id not in network_ids
    ]
    if not violations:
        return None
    missing_ids: Final[list[Id]] = sorted({child_id for _, child_id in violations})
    node_ids: Final[list[Id]] = sorted({node_id for node_id, _ in violations})
    return ValidationError(
        message=f"child ids absent from network: {missing_ids}; referenced by nodes: {node_ids}",
        validator=all_children_present,
    )


@validate_call
def all_parents_present(network: NodeNetwork, root_node: RoamNode) -> ValidationError | None:
    """Return ``None`` when every parent id referenced in *network* resolves to a node in *network*.

    Iterates every node in *network* and checks that each :attr:`~guffin.roam.node.RoamNode.id`
    value found in a node's :attr:`~guffin.roam.node.RoamNode.parents` list corresponds to the
    :attr:`~guffin.roam.node.RoamNode.id` of at least one node in *network*.  Parent ids that
    appear in *root_node*'s :attr:`~guffin.roam.node.RoamNode.parents` list are exempt from this
    check — they are considered external ancestors that legitimately live outside *network*.

    A network with no parents at all vacuously satisfies this condition and returns ``None``.

    Args:
        network: The collection of nodes to examine.
        root_node: The root of *network*.  Its parent ids are treated as external ancestors and
            exempt from the presence check.

    Returns:
        ``None`` if every applicable parent id in *network* resolves to a node in
        *network*; a :class:`~guffin.common.validation.ValidationError` listing the sorted
        absent parent ids and the sorted ids of the nodes that referenced them otherwise.
    """
    network_ids: Final[set[Id]] = {n.id for n in network}
    external_ancestor_ids: Final[set[Id]] = {p.id for p in (root_node.parents or [])}
    violations: Final[list[tuple[Id, Id]]] = [
        (n.id, parent.id)
        for n in network
        if n.parents
        for parent in n.parents
        if parent.id not in network_ids and parent.id not in external_ancestor_ids
    ]
    if not violations:
        return None
    missing_ids: Final[list[Id]] = sorted({parent_id for _, parent_id in violations})
    node_ids: Final[list[Id]] = sorted({node_id for node_id, _ in violations})
    return ValidationError(
        message=f"parent ids absent from network: {missing_ids}; referenced by nodes: {node_ids}",
        validator=all_parents_present,
    )


@validate_call
def has_unique_ids(network: NodeNetwork) -> ValidationError | None:
    """Return ``None`` when every :attr:`~guffin.roam.node.RoamNode.id` in *network* is unique.

    Checks that no two nodes in *network* share the same :attr:`~guffin.roam.node.RoamNode.id`
    value.  An empty network vacuously satisfies this condition.

    Args:
        network: The collection of nodes to examine.

    Returns:
        ``None`` if all node ids in *network* are distinct; a
        :class:`~guffin.common.validation.ValidationError` listing the sorted
        duplicate ids otherwise.
    """
    ids: Final[list[Id]] = [n.id for n in network]
    if len(ids) == len(set(ids)):
        return None
    seen: Final[set[Id]] = set()
    duplicates: Final[set[Id]] = set()
    for id_ in ids:
        if id_ in seen:
            duplicates.add(id_)
        seen.add(id_)
    dup_ids: Final[list[Id]] = sorted(duplicates)
    return ValidationError(message=f"expected unique node ids; found duplicates: {dup_ids}", validator=has_unique_ids)


@validate_call
def is_acyclic(network: NodeNetwork) -> ValidationError | None:
    """Return ``None`` when the child-edge graph of *network* contains no directed cycles.

    Performs a depth-first search over the :attr:`~guffin.roam.node.RoamNode.children` edges of
    *network*, colouring each node white (unvisited), grey (on the current DFS
    path), or black (fully explored).  Encountering a grey node during
    traversal reveals a back-edge and therefore a cycle.

    Child references that point to nodes absent from *network* are silently
    skipped; use :func:`all_children_present` to validate referential
    integrity separately.

    An empty network vacuously satisfies this condition and returns ``None``.

    Args:
        network: The collection of nodes to examine.

    Returns:
        ``None`` if *network* contains no directed cycles; a
        :class:`~guffin.common.validation.ValidationError` naming the uid of the
        cycle-involved node otherwise.
    """
    id_to_node: Final[dict[Id, RoamNode]] = {n.id: n for n in network}
    _WHITE: Final[int] = 0
    _GREY: Final[int] = 1
    _BLACK: Final[int] = 2
    color: Final[dict[Id, int]] = {n.id: _WHITE for n in network}

    def _dfs(node_id: Id) -> Uid | None:
        """Return the uid of a cycle-involved node, or ``None`` if no cycle is found."""
        color[node_id] = _GREY
        node = id_to_node[node_id]
        if node.children:
            for child_stub in node.children:
                child_id = child_stub.id
                if child_id not in color:
                    continue  # child outside network — skip
                if color[child_id] == _GREY:
                    return id_to_node[child_id].uid  # back-edge → cycle detected
                if color[child_id] == _WHITE:
                    cycle_uid = _dfs(child_id)
                    if cycle_uid is not None:
                        return cycle_uid
        color[node_id] = _BLACK
        return None

    for n in network:
        if color[n.id] == _WHITE:
            cycle_uid = _dfs(n.id)
            if cycle_uid is not None:
                return ValidationError(
                    message=f"child-edge graph contains a directed cycle involving node '{cycle_uid}'",
                    validator=is_acyclic,
                )
    return None


@validate_call
def all_descendants(ancestor: RoamNode, network: NodeNetwork) -> NodeNetwork:
    """Collect all descendant nodes of *ancestor* reachable via child edges in *network*.

    Performs an iterative depth-first traversal starting from *ancestor*, following each
    node's :attr:`~guffin.roam.node.RoamNode.children` links.  The traversal is bounded
    to *network*; any child id that cannot be resolved to a node in *network* raises a
    :class:`ValueError`.

    Args:
        ancestor: The root node from which to start the traversal.  Must be a member of
            *network*.
        network: The collection of nodes to search.

    Returns:
        A :class:`NodeNetwork` containing every node reachable from *ancestor* via child
        edges, excluding *ancestor* itself.  Nodes appear in DFS discovery order.

    Raises:
        ValueError: If *ancestor* is not present in *network*, or if any child id
            encountered during traversal cannot be resolved to a node in *network*.
    """
    network_by_id: Final[dict[Id, RoamNode]] = {n.id: n for n in network}

    if ancestor.id not in network_by_id:
        raise ValueError(f"ancestor node (uid={ancestor.uid!r}, id={ancestor.id!r}) is not present in network")

    result: Final[list[RoamNode]] = []
    stack: Final[list[RoamNode]] = [ancestor]
    visited: Final[set[Id]] = {ancestor.id}

    while stack:
        node: RoamNode = stack.pop()
        if node.children:
            for child_stub in node.children:
                child_id: Id = child_stub.id
                if child_id not in network_by_id:
                    raise ValueError(
                        f"child id={child_id!r} referenced by node (uid={node.uid!r}, id={node.id!r}) "
                        f"is not resolvable in network"
                    )
                if child_id not in visited:
                    visited.add(child_id)
                    child_node: RoamNode = network_by_id[child_id]
                    result.append(child_node)
                    stack.append(child_node)

    return result


@validate_call
def refs_ids(network: NodeNetwork) -> set[Id]:
    """Return the set of all :attr:`~guffin.roam.node.RoamNode.refs` ids across every node in *network*.

    Collects every :attr:`~guffin.roam.primitives.IdObject.id` found in the
    :attr:`~guffin.roam.node.RoamNode.refs` field of every node in *network*.  Nodes whose
    ``refs`` field is ``None`` contribute nothing.  An empty *network* returns an empty set.

    Args:
        network: The collection of nodes to examine.

    Returns:
        A ``set[Id]`` containing every id found in any node's ``refs`` list; empty if no node
        in *network* has any ``refs``.
    """
    return {ref.id for n in network if n.refs for ref in n.refs}


@validate_call
def direct_refs_nodes(network: NodeNetwork) -> NodeNetwork:
    """Return the nodes in *network* that are referenced by any node's ``refs`` list.

    Finds all ids across *network* via :func:`refs_ids`, then returns the subset of nodes
    in *network* whose :attr:`~guffin.roam.node.RoamNode.id` appears in that set.  Ref
    targets that resolve to nodes outside *network* are not included; use
    :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` when the full ref-node pool may be
    broader than *network* itself.

    Args:
        network: The collection of nodes to examine.

    Returns:
        A :data:`NodeNetwork` containing every node in *network* whose id is referenced via
        ``:block/refs`` by at least one other node in *network*; empty if no such node exists.
        The order follows the original *network* order; duplicate ids cannot arise because
        :data:`NodeNetwork` members are deduplicated by id in well-formed networks.
    """
    target_ids: Final[set[Id]] = refs_ids(network)
    return [n for n in network if n.id in target_ids]


@validate_call
def refs_nodes(network: NodeNetwork) -> NodeNetwork:
    """Return all direct-ref target nodes from *network* plus all their transitive descendants.

    First identifies direct ref targets via :func:`direct_refs_nodes`, then performs an
    iterative DFS over each target's child edges, collecting every reachable descendant
    present in *network*.  Each node appears at most once in the result regardless of how
    many paths lead to it.

    Args:
        network: The collection of nodes to examine.

    Returns:
        A :data:`NodeNetwork` containing every direct-ref target node in *network* and every
        node transitively reachable from those targets via child edges within *network*;
        empty if *network* has no nodes whose ids are referenced via ``:block/refs``.

    Raises:
        ValueError: If any child id encountered during traversal cannot be resolved to a
            node in *network*.
    """
    visited: Final[set[Id]] = set()
    result: Final[list[RoamNode]] = []
    for ref_node in direct_refs_nodes(network):
        if ref_node.id in visited:
            continue
        visited.add(ref_node.id)
        result.append(ref_node)
        for desc in all_descendants(ref_node, network):
            if desc.id not in visited:
                visited.add(desc.id)
                result.append(desc)
    return result


@validate_call
def min_effective_heading_level(network: NodeNetwork) -> HeadingLevel | None:
    """Return the minimum effective heading level across all nodes in *network*.

    Applies :func:`~guffin.roam.node.effective_heading_level` to every node,
    collecting all non-``None`` results, and returns the smallest value.
    Returns ``None`` when *network* contains no heading nodes.

    Args:
        network: The collection of nodes to examine.

    Returns:
        The minimum :data:`~guffin.common.markdown.HeadingLevel` found across
        all nodes in *network*, or ``None`` if no node is a heading.
    """
    levels: Final[set[HeadingLevel]] = {lvl for node in network if (lvl := effective_heading_level(node)) is not None}
    return min(levels) if levels else None
