"""Roam Research node-fetch result types.

Public symbols:

- :class:`QueryAnchorKind` — enum discriminating a page-title anchor from a node-UID anchor.
- :class:`NodeFetchAnchor` — immutable model pairing a raw anchor string with its detected kind.
- :class:`NodeFetchSpec` — immutable model pairing a :class:`NodeFetchAnchor` with fetch options.
- :class:`NodeFetchResult` — immutable model bundling the fetch specification, its resolved node tree,
  a :data:`~guffin.roam.node.NodesByUid` index of all fetched nodes, and the raw
  Datalog query result before :class:`~guffin.roam.node.RoamNode` parsing.
- :func:`anchor_node` — return the :class:`~guffin.roam.node.RoamNode` in a
  :data:`~guffin.roam.node_network.NodeNetwork` that matches a :class:`NodeFetchAnchor`.
- :func:`anchor_tree` — return the subtree of a :data:`~guffin.roam.node_network.NodeNetwork`
  rooted at the node that matches a :class:`NodeFetchAnchor`.
"""

import enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator, validate_call

from guffin.roam.node import NodesByUid, RoamNode
from guffin.roam.node_network import NodeNetwork
from guffin.roam.node_tree import NodeTree
from guffin.roam.primitives import ANCHORED_UID_RE


@enum.unique
class QueryAnchorKind(enum.Enum):
    """Discriminates the kind of anchor passed to :class:`~guffin.roam.node_fetch.FetchRoamNodes` fetch methods.

    Attributes:
        PAGE_TITLE: The anchor is a Roam page title string.
        NODE_UID: The anchor is a ``:block/uid`` string (synthetic or daily-note).
    """

    PAGE_TITLE = enum.auto()
    NODE_UID = enum.auto()

    @staticmethod
    def of(target: str) -> QueryAnchorKind:
        """Return the :class:`QueryAnchorKind` for *target*.

        Args:
            target: A Roam page title, node UID, or Roam block-reference
                syntax ``((uid))``.

        Returns:
            :attr:`NODE_UID` when the trimmed *target* is wrapped in ``(( … ))`` (Roam
            block-reference syntax) or matches :data:`~guffin.roam.primitives.ANCHORED_UID_RE`
            directly; :attr:`PAGE_TITLE` otherwise.
        """
        trimmed: Final[str] = target.strip()
        if (trimmed.startswith("((") and trimmed.endswith("))")) or ANCHORED_UID_RE.match(trimmed):
            return QueryAnchorKind.NODE_UID
        return QueryAnchorKind.PAGE_TITLE


class NodeFetchAnchor(BaseModel):
    """Immutable model pairing a raw anchor string with its derived :class:`QueryAnchorKind`.

    Attributes:
        qualifier: The raw anchor string — a Roam page title (optionally wrapped in ``[[ ]]``),
            a node UID, or a Roam block-reference (``(( uid ))``).
        kind: Derived from *qualifier* via :meth:`QueryAnchorKind.of`.
        node_identifier: Normalized identifier extracted from :attr:`qualifier` — the bare page
            title (``[[ ]]`` stripped if present) for :attr:`~QueryAnchorKind.PAGE_TITLE` anchors,
            or the bare UID (``(( ))`` stripped if present) for
            :attr:`~QueryAnchorKind.NODE_UID` anchors.
    """

    model_config = ConfigDict(frozen=True)

    qualifier: str = Field(
        description=(
            "A Roam page title (optionally wrapped in [[ ]]), a node UID, "
            "or a Roam block-reference wrapped in (( ))."
        )
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kind(self) -> QueryAnchorKind:
        """Derive the :class:`QueryAnchorKind` from :attr:`qualifier`."""
        return QueryAnchorKind.of(self.qualifier)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def node_identifier(self) -> str:
        """Derive the normalized identifier from :attr:`qualifier`.

        Strips ``[[ ]]`` wrappers for :attr:`~QueryAnchorKind.PAGE_TITLE` anchors and
        ``(( ))`` wrappers for :attr:`~QueryAnchorKind.NODE_UID` anchors, then returns
        the bare page title or UID.
        """
        trimmed: Final[str] = self.qualifier.strip()
        if self.kind is QueryAnchorKind.PAGE_TITLE:
            if trimmed.startswith("[[") and trimmed.endswith("]]"):
                return trimmed[2:-2]
            return trimmed
        if trimmed.startswith("((") and trimmed.endswith("))"):
            return trimmed[2:-2]
        return trimmed

    def __str__(self) -> str:
        """Return the raw :attr:`qualifier` string."""
        return self.qualifier

    def __repr__(self) -> str:
        """Return a concise representation showing the raw :attr:`qualifier`."""
        return f"NodeFetchAnchor({self.qualifier!r})"


class NodeFetchSpec(BaseModel):
    """Immutable model pairing a fetch anchor with its fetch options.

    Attributes:
        anchor: The fetch anchor identifying the root node by page title or node UID.
        include_refs: When ``True``, the fetch includes every node referenced via
            ``:block/refs`` from the anchor node or any of its descendants.
            When ``False``, only the anchor node and its descendant blocks are fetched.
        include_node_tree: When ``True``, parse fetched pull-blocks into a
            :class:`~guffin.roam.node.RoamNode` model tree and populate
            :attr:`~NodeFetchResult.anchor_tree` and :attr:`~NodeFetchResult.nodes_by_uid`.
            When ``False``, skip parsing and return only the raw Datalog result;
            :attr:`~NodeFetchResult.anchor_tree` and :attr:`~NodeFetchResult.nodes_by_uid`
            will be ``None`` in the returned :class:`NodeFetchResult`.
    """

    model_config = ConfigDict(frozen=True)

    anchor: NodeFetchAnchor = Field(description="The fetch anchor identifying the root node.")
    include_refs: bool = Field(description="Whether to include :block/refs targets in the fetch.")
    include_node_tree: bool = Field(
        default=True,
        description=(
            "When True, parse pull-blocks into RoamNode models and populate anchor_tree and nodes_by_uid.  "
            "When False, skip parsing and return only the raw Datalog result; "
            "anchor_tree and nodes_by_uid will be None in the returned NodeFetchResult."
        ),
    )


class NodeFetchResult(BaseModel):
    """Immutable model bundling a fetch specification with its resolved node tree and UID index.

    This class cannot be instantiated directly; use the :meth:`from_network` class method,
    which is the sole public constructor.

    Attributes:
        fetch_spec: The fetch specification used to perform the fetch.
        anchor_tree: The :class:`~guffin.roam.node_tree.NodeTree` rooted at the fetch anchor.
            ``None`` when :attr:`~NodeFetchSpec.include_node_tree` is ``False``.
        nodes_by_uid: Index mapping each fetched node's UID to its
            :class:`~guffin.roam.node.RoamNode`.
            ``None`` when :attr:`~NodeFetchSpec.include_node_tree` is ``False``.
        raw_result: The raw Datalog query result from the Local API before
            :class:`~guffin.roam.node.RoamNode` parsing.  Each outer list element is a
            single-element row (Datalog ``[:find (pull ...)]`` always wraps each tuple in a
            list); the inner dict is the raw pull-block attribute map as returned by Roam.
        network: All :class:`~guffin.roam.node.RoamNode` instances fetched by this result,
            as a flat :data:`~guffin.roam.node_network.NodeNetwork` list.  Empty when
            :attr:`~NodeFetchSpec.include_node_tree` is ``False``.
    """

    model_config = ConfigDict(frozen=True)

    fetch_spec: NodeFetchSpec = Field(description="The fetch specification used to perform the fetch.")
    anchor_tree: NodeTree | None = Field(
        default=None,
        description=("The node tree rooted at the fetch anchor.  None when NodeFetchSpec.include_node_tree is False."),
    )
    nodes_by_uid: NodesByUid | None = Field(
        default=None,
        description=(
            "Index mapping each fetched node UID to its RoamNode.  None when NodeFetchSpec.include_node_tree is False."
        ),
    )
    raw_result: list[list[dict[str, object]]] = Field(
        description=(
            "Raw Datalog query result before RoamNode parsing.  Each outer element is a single-element row "
            "(Datalog :find wraps each tuple in a list); the inner dict is the raw pull-block attribute map."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _guard_direct_construction(cls, data: object) -> object:
        """Block direct instantiation of :class:`NodeFetchResult`.

        Raises:
            TypeError: Always — only :meth:`from_network` may construct instances,
                via :meth:`~pydantic.BaseModel.model_construct` which bypasses this guard.
        """
        raise TypeError(f"'{cls.__name__}' cannot be constructed directly; use '{cls.__name__}.from_network()' instead")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def network(self) -> NodeNetwork:
        """Return all fetched nodes as a flat :data:`~guffin.roam.node_network.NodeNetwork` list.

        Returns every node in :attr:`nodes_by_uid`, which includes both the structural nodes
        of :attr:`anchor_tree` and any additional nodes fetched via ``:block/refs`` when
        :attr:`~NodeFetchSpec.include_refs` was ``True``.  Returns an empty list when
        :attr:`~NodeFetchSpec.include_node_tree` is ``False`` (i.e. :attr:`nodes_by_uid`
        is ``None``).

        Returns:
            A :data:`~guffin.roam.node_network.NodeNetwork` containing every
            :class:`~guffin.roam.node.RoamNode` in :attr:`nodes_by_uid`, or ``[]``
            when :attr:`nodes_by_uid` is ``None``.
        """
        return list(self.nodes_by_uid.values()) if self.nodes_by_uid is not None else []

    @classmethod
    def from_raw_result(
        cls,
        fetch_spec: NodeFetchSpec,
        raw_result: list[list[dict[str, object]]],
    ) -> NodeFetchResult:
        """Construct a raw-only :class:`NodeFetchResult` when node parsing is skipped.

        Use this factory when :attr:`~NodeFetchSpec.include_node_tree` is ``False``.
        :attr:`anchor_tree` and :attr:`nodes_by_uid` are ``None``; only :attr:`raw_result`
        carries meaningful data.

        Uses :meth:`~pydantic.BaseModel.model_construct` to bypass the
        :meth:`_guard_direct_construction` validator, which blocks all other construction paths.

        Args:
            fetch_spec: The fetch specification used to perform the fetch.
            raw_result: The raw Datalog query result before :class:`~guffin.roam.node.RoamNode`
                parsing.  Stored verbatim in :attr:`~NodeFetchResult.raw_result`.

        Returns:
            A :class:`NodeFetchResult` with :attr:`anchor_tree` and :attr:`nodes_by_uid`
            set to ``None`` and :attr:`raw_result` set to *raw_result*.
        """
        return cls.model_construct(fetch_spec=fetch_spec, anchor_tree=None, nodes_by_uid=None, raw_result=raw_result)

    @classmethod
    def from_network(
        cls,
        network: NodeNetwork,
        fetch_spec: NodeFetchSpec,
        raw_result: list[list[dict[str, object]]],
    ) -> NodeFetchResult:
        """Construct a :class:`NodeFetchResult` from a raw *network* and *fetch_spec*.

        This is the sole public constructor for :class:`NodeFetchResult`.  It locates the
        anchor node within *network* via :func:`anchor_node`, wraps the full network in a
        :class:`~guffin.roam.node_tree.NodeTree` rooted there, and builds a
        :data:`~guffin.roam.node.NodesByUid` index over all nodes in *network*.

        Uses :meth:`~pydantic.BaseModel.model_construct` to bypass the
        :meth:`_guard_direct_construction` validator, which blocks all other construction paths.

        Args:
            network: The flat node network returned by the fetch.
            fetch_spec: The fetch specification whose :attr:`~NodeFetchSpec.anchor` identifies
                the root node of *network*.
            raw_result: The raw Datalog query result before :class:`~guffin.roam.node.RoamNode`
                parsing.  Stored verbatim in :attr:`~NodeFetchResult.raw_result`.

        Returns:
            A :class:`NodeFetchResult` whose :attr:`anchor_tree` is rooted at the node
            in *network* that matches :attr:`fetch_spec.anchor <NodeFetchSpec.anchor>`,
            whose :attr:`nodes_by_uid` indexes every node in *network* by
            :attr:`~guffin.roam.node.RoamNode.uid`, and whose :attr:`raw_result` is
            *raw_result*.

        Raises:
            ValueError: If no node in *network* matches :attr:`fetch_spec.anchor
                <NodeFetchSpec.anchor>`, or if *network* fails any
                :class:`~guffin.roam.node_tree.NodeTree` invariant.
        """
        root: Final[RoamNode] = anchor_node(network, fetch_spec.anchor)
        anchor_tree: Final[NodeTree] = NodeTree.build(super_network=network, root_node=root)
        by_uid: Final[NodesByUid] = {n.uid: n for n in network}
        return cls.model_construct(
            fetch_spec=fetch_spec, anchor_tree=anchor_tree, nodes_by_uid=by_uid, raw_result=raw_result
        )


@validate_call
def anchor_node(network: NodeNetwork, anchor: NodeFetchAnchor) -> RoamNode:
    """Return the node in *network* that matches *anchor*.

    Args:
        network: The node network to search.
        anchor: The fetch anchor whose :attr:`~NodeFetchAnchor.node_identifier` string identifies
            the anchor node — matched against :attr:`~guffin.roam.node.RoamNode.uid`
            for :attr:`~QueryAnchorKind.NODE_UID` anchors, or against
            :attr:`~guffin.roam.node.RoamNode.title` for :attr:`~QueryAnchorKind.PAGE_TITLE`
            anchors.

    Returns:
        The matching :class:`~guffin.roam.node.RoamNode`.

    Raises:
        ValueError: If no node in *network* matches *anchor*.
    """
    if anchor.kind is QueryAnchorKind.NODE_UID:
        found: RoamNode | None = next((n for n in network if n.uid == anchor.node_identifier), None)
    else:
        found = next((n for n in network if n.title == anchor.node_identifier), None)
    if found is None:
        raise ValueError(f"no node found in network matching anchor {anchor!r} (kind={anchor.kind!r})")
    return found


def _resolved_children(node: RoamNode, id_to_node: dict[int, RoamNode]) -> list[RoamNode]:
    """Resolve *node*'s child references to their full node records via *id_to_node*.

    Args:
        node: The node whose ``:block/children`` references to resolve.
        id_to_node: Mapping from ``:db/id`` to its :class:`~guffin.roam.node.RoamNode`.

    Returns:
        The child nodes in source order; empty when *node* has no children.

    Raises:
        ValueError: If any child reference resolves to an ``:db/id`` absent from *id_to_node*.
    """
    missing: Final[list[int]] = [ref.id for ref in node.children or () if ref.id not in id_to_node]
    if missing:
        raise ValueError(f"child ids {missing!r} not found in network (parent uid={node.uid!r})")
    return [id_to_node[ref.id] for ref in node.children or ()]


@validate_call
def anchor_tree(network: NodeNetwork, anchor: NodeFetchAnchor) -> NodeNetwork:
    """Return all nodes in *network* reachable from the anchor node via.

    :attr:`~guffin.roam.node.RoamNode.children`.

    Performs a depth-first traversal starting at the node identified by *anchor*,
    following ``:block/children`` references at every level.  The anchor node itself
    is always included in the result.

    Args:
        network: The node network to search.
        anchor: The fetch anchor identifying the root of the subtree.

    Returns:
        A :data:`~guffin.roam.node_network.NodeNetwork` containing the anchor node and
        every node transitively reachable through ``:block/children``, in DFS pre-order.

    Raises:
        ValueError: If no node in *network* matches *anchor*, or if a
            ``:block/children`` reference resolves to an ``:db/id`` that is not
            present in *network*.
    """
    id_to_node: Final[dict[int, RoamNode]] = {n.id: n for n in network}
    root: Final[RoamNode] = anchor_node(network, anchor)

    result: Final[list[RoamNode]] = []
    stack: Final[list[RoamNode]] = [root]
    visited: Final[set[int]] = set()

    while stack:
        node: RoamNode = stack.pop()
        if node.id in visited:
            continue
        visited.add(node.id)
        result.append(node)
        stack.extend(_resolved_children(node, id_to_node))

    return result
