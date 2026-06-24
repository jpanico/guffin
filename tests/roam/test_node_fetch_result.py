"""Tests for the roam_node_fetch_result module."""

from typing import Final

import pytest
from pydantic import ValidationError

from guffin.roam.node_network import NodeNetwork
from guffin.roam.node import RoamNode
from guffin.roam.node_fetch_result import (
    NodeFetchAnchor,
    NodeFetchResult,
    NodeFetchSpec,
    QueryAnchorKind,
    anchor_node,
    anchor_tree,
)
from guffin.roam.primitives import IdObject

# ---------------------------------------------------------------------------
# Minimal test-node helpers
# ---------------------------------------------------------------------------

_PAGE_UID: Final[str] = "pageuid01"
_BLOCK_UID: Final[str] = "blckuid01"
_PAGE_TITLE: Final[str] = "My Test Page"
_VALID_UID: Final[str] = "wdMgyBiP9"


def _page_node(uid: str = _PAGE_UID, title: str = _PAGE_TITLE) -> RoamNode:
    """Return a minimal Page :class:`~guffin.roam.node.RoamNode` for use in tests."""
    return RoamNode(uid=uid, id=1, title=title, children=[])


# ---------------------------------------------------------------------------
# QueryAnchorKind
# ---------------------------------------------------------------------------


class TestQueryAnchorKind:
    """Tests for :class:`~guffin.roam.node_fetch_result.QueryAnchorKind`."""

    def test_of_returns_node_uid_for_valid_uid(self) -> None:
        """Test that a nine-character UID string resolves to NODE_UID."""
        assert QueryAnchorKind.of(_VALID_UID) is QueryAnchorKind.NODE_UID

    def test_of_returns_page_title_for_plain_string(self) -> None:
        """Test that a plain page-title string resolves to PAGE_TITLE."""
        assert QueryAnchorKind.of("My Page Title") is QueryAnchorKind.PAGE_TITLE

    def test_of_returns_page_title_for_short_string(self) -> None:
        """Test that a string shorter than nine characters resolves to PAGE_TITLE."""
        assert QueryAnchorKind.of("short") is QueryAnchorKind.PAGE_TITLE

    def test_of_returns_page_title_for_long_string(self) -> None:
        """Test that a string longer than nine characters resolves to PAGE_TITLE."""
        assert QueryAnchorKind.of("a" * 10) is QueryAnchorKind.PAGE_TITLE

    def test_of_returns_node_uid_for_block_reference_syntax(self) -> None:
        """Test that a UID wrapped in (( )) resolves to NODE_UID."""
        assert QueryAnchorKind.of(f"(({_VALID_UID}))") is QueryAnchorKind.NODE_UID

    def test_of_trims_whitespace_before_classifying_bare_uid(self) -> None:
        """Test that leading/trailing whitespace is stripped before matching a bare UID."""
        assert QueryAnchorKind.of(f"  {_VALID_UID}  ") is QueryAnchorKind.NODE_UID

    def test_of_trims_whitespace_before_classifying_block_reference(self) -> None:
        """Test that leading/trailing whitespace is stripped before matching a (( )) block reference."""
        assert QueryAnchorKind.of(f"  (({_VALID_UID}))  ") is QueryAnchorKind.NODE_UID

    def test_of_returns_page_title_for_unclosed_block_reference(self) -> None:
        """Test that a string starting with (( but not ending with )) resolves to PAGE_TITLE."""
        assert QueryAnchorKind.of(f"(({_VALID_UID}") is QueryAnchorKind.PAGE_TITLE

    def test_of_returns_page_title_for_unopened_block_reference(self) -> None:
        """Test that a string ending with )) but not starting with (( resolves to PAGE_TITLE."""
        assert QueryAnchorKind.of(f"{_VALID_UID}))") is QueryAnchorKind.PAGE_TITLE

    def test_of_returns_page_title_for_wiki_link_syntax(self) -> None:
        """Test that a [[ ]] wiki-link string resolves to PAGE_TITLE, not NODE_UID."""
        assert QueryAnchorKind.of("[[My Page]]") is QueryAnchorKind.PAGE_TITLE


# ---------------------------------------------------------------------------
# NodeFetchAnchor
# ---------------------------------------------------------------------------


class TestNodeFetchAnchor:
    """Tests for :class:`~guffin.roam.node_fetch_result.NodeFetchAnchor`."""

    def test_kind_is_node_uid_for_uid_target(self) -> None:
        """Test that a UID target produces kind=NODE_UID."""
        anchor: Final[NodeFetchAnchor] = NodeFetchAnchor(qualifier=_VALID_UID)
        assert anchor.kind is QueryAnchorKind.NODE_UID

    def test_kind_is_page_title_for_title_target(self) -> None:
        """Test that a page-title target produces kind=PAGE_TITLE."""
        anchor: Final[NodeFetchAnchor] = NodeFetchAnchor(qualifier="My Page")
        assert anchor.kind is QueryAnchorKind.PAGE_TITLE

    def test_target_is_preserved(self) -> None:
        """Test that the raw target string is stored as-is."""
        anchor: Final[NodeFetchAnchor] = NodeFetchAnchor(qualifier=_PAGE_TITLE)
        assert anchor.qualifier == _PAGE_TITLE

    def test_null_target_raises_validation_error(self) -> None:
        """Test that a None target raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeFetchAnchor(qualifier=None)  # type: ignore[arg-type]

    def test_missing_target_raises_validation_error(self) -> None:
        """Test that omitting target raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeFetchAnchor()  # type: ignore[call-arg]

    def test_immutability(self) -> None:
        """Test that NodeFetchAnchor instances are immutable (frozen)."""
        anchor: Final[NodeFetchAnchor] = NodeFetchAnchor(qualifier="My Page")
        with pytest.raises(Exception):
            anchor.qualifier = "Other Page"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NodeFetchSpec
# ---------------------------------------------------------------------------


class TestNodeFetchSpec:
    """Tests for :class:`~guffin.roam.node_fetch_result.NodeFetchSpec`."""

    def test_anchor_and_include_refs_false_stored(self) -> None:
        """Test that anchor and include_refs=False are stored correctly."""
        anchor: Final[NodeFetchAnchor] = NodeFetchAnchor(qualifier=_PAGE_TITLE)
        spec: Final[NodeFetchSpec] = NodeFetchSpec(anchor=anchor, include_refs=False)
        assert spec.anchor == anchor
        assert spec.include_refs is False

    def test_include_refs_true_stored(self) -> None:
        """Test that include_refs=True is stored correctly."""
        spec: Final[NodeFetchSpec] = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=_PAGE_TITLE), include_refs=True)
        assert spec.include_refs is True

    def test_immutability(self) -> None:
        """Test that NodeFetchSpec instances are immutable (frozen)."""
        spec: Final[NodeFetchSpec] = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=_PAGE_TITLE), include_refs=False)
        with pytest.raises(Exception):
            spec.include_refs = True  # type: ignore[misc]

    def test_missing_anchor_raises_validation_error(self) -> None:
        """Test that omitting anchor raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeFetchSpec(include_refs=False)  # type: ignore[call-arg]

    def test_missing_include_refs_raises_validation_error(self) -> None:
        """Test that omitting include_refs raises ValidationError."""
        with pytest.raises(ValidationError):
            NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=_PAGE_TITLE))  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# NodeFetchResult
# ---------------------------------------------------------------------------


class TestNodeFetchResult:
    """Tests for :class:`~guffin.roam.node_fetch_result.NodeFetchResult`."""

    def _make_result(self) -> NodeFetchResult:
        """Return a minimal valid :class:`~guffin.roam.node_fetch_result.NodeFetchResult`."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier=_PAGE_TITLE), include_refs=False
        )
        return NodeFetchResult.from_network([_page_node()], fetch_spec, raw_result=[[{}]])

    def test_valid_construction(self) -> None:
        """Test that a NodeFetchResult can be constructed with all required fields."""
        result: Final[NodeFetchResult] = self._make_result()
        assert result.fetch_spec.anchor.qualifier == _PAGE_TITLE
        assert result.anchor_tree is not None
        assert len(result.anchor_tree.tree_network) == 1
        assert result.nodes_by_uid is not None
        assert result.nodes_by_uid[_PAGE_UID].title == _PAGE_TITLE

    def test_immutability(self) -> None:
        """Test that NodeFetchResult instances are immutable (frozen)."""
        result: Final[NodeFetchResult] = self._make_result()
        with pytest.raises(Exception):
            result.fetch_spec = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="Other"), include_refs=False)  # type: ignore[misc]

    def test_network_contains_all_fetched_nodes(self) -> None:
        """Test that network returns every node in nodes_by_uid as a flat list."""
        result: Final[NodeFetchResult] = self._make_result()
        assert result.nodes_by_uid is not None
        assert {n.uid for n in result.network} == set(result.nodes_by_uid.keys())

    def test_direct_construction_raises_type_error(self) -> None:
        """Test that NodeFetchResult cannot be instantiated directly."""
        with pytest.raises(TypeError):
            NodeFetchResult.model_validate({})


# ---------------------------------------------------------------------------
# anchor_node
# ---------------------------------------------------------------------------


class TestAnchorNode:
    """Tests for :func:`~guffin.roam.node_fetch_result.anchor_node`."""

    def test_finds_node_by_uid(self) -> None:
        """Test that a NODE_UID anchor returns the node with the matching uid."""
        page: Final[RoamNode] = _page_node(uid=_VALID_UID)
        network: Final[NodeNetwork] = [page]
        result: Final[RoamNode] = anchor_node(network, NodeFetchAnchor(qualifier=_VALID_UID))
        assert result.uid == _VALID_UID

    def test_finds_node_by_title(self) -> None:
        """Test that a PAGE_TITLE anchor returns the node with the matching title."""
        page: Final[RoamNode] = _page_node(title=_PAGE_TITLE)
        network: Final[NodeNetwork] = [page]
        result: Final[RoamNode] = anchor_node(network, NodeFetchAnchor(qualifier=_PAGE_TITLE))
        assert result.title == _PAGE_TITLE

    def test_returns_correct_node_from_multi_node_network(self) -> None:
        """Test that the correct node is returned when the network contains multiple nodes."""
        page1: Final[RoamNode] = _page_node(uid="pgeuid001", title="Page One")
        page2: Final[RoamNode] = _page_node(uid="pgeuid002", title="Page Two")
        network: Final[NodeNetwork] = [page1, page2]
        result: Final[RoamNode] = anchor_node(network, NodeFetchAnchor(qualifier="Page Two"))
        assert result.uid == "pgeuid002"

    def test_raises_value_error_when_uid_not_found(self) -> None:
        """Test that a ValueError is raised when no node matches a NODE_UID anchor."""
        network: Final[NodeNetwork] = [_page_node()]
        with pytest.raises(ValueError, match=_VALID_UID):
            anchor_node(network, NodeFetchAnchor(qualifier=_VALID_UID))

    def test_raises_value_error_when_title_not_found(self) -> None:
        """Test that a ValueError is raised when no node matches a PAGE_TITLE anchor."""
        network: Final[NodeNetwork] = [_page_node()]
        with pytest.raises(ValueError, match="Nonexistent"):
            anchor_node(network, NodeFetchAnchor(qualifier="Nonexistent Page"))

    def test_raises_value_error_on_empty_network(self) -> None:
        """Test that a ValueError is raised when the network is empty."""
        with pytest.raises(ValueError):
            anchor_node([], NodeFetchAnchor(qualifier=_PAGE_TITLE))


# ---------------------------------------------------------------------------
# anchor_tree
# ---------------------------------------------------------------------------


def _page(uid: str, id_: int, title: str, child_ids: list[int]) -> RoamNode:
    """Return a Page :class:`~guffin.roam.node.RoamNode` with explicit id and child refs."""
    return RoamNode(
        uid=uid,
        id=id_,
        title=title,
        children=[IdObject(id=cid) for cid in child_ids],
    )


def _block(uid: str, id_: int, page_id: int, child_ids: list[int] | None = None) -> RoamNode:
    """Return a Block :class:`~guffin.roam.node.RoamNode` with explicit id and optional child refs."""
    return RoamNode(
        uid=uid,
        id=id_,
        string=uid,
        order=0,
        page=IdObject(id=page_id),
        parents=[IdObject(id=page_id)],
        children=[IdObject(id=cid) for cid in child_ids] if child_ids is not None else None,
    )


class TestAnchorTree:
    """Tests for :func:`~guffin.roam.node_fetch_result.anchor_tree`."""

    def test_returns_single_node_when_no_children(self) -> None:
        """Test that a page with no children returns only the anchor node."""
        page: Final[RoamNode] = _page(uid=_PAGE_UID, id_=1, title=_PAGE_TITLE, child_ids=[])
        network: Final[NodeNetwork] = [page]
        result: Final[NodeNetwork] = anchor_tree(network, NodeFetchAnchor(qualifier=_PAGE_TITLE))
        assert result == [page]

    def test_result_always_includes_anchor_node(self) -> None:
        """Test that the anchor node itself is always present in the result."""
        page: Final[RoamNode] = _page(uid=_PAGE_UID, id_=1, title=_PAGE_TITLE, child_ids=[])
        result: Final[NodeNetwork] = anchor_tree([page], NodeFetchAnchor(qualifier=_PAGE_TITLE))
        assert page in result

    def test_includes_direct_children(self) -> None:
        """Test that direct block children of the anchor are included in the result."""
        page: Final[RoamNode] = _page(uid="pageuid01", id_=1, title=_PAGE_TITLE, child_ids=[2, 3])
        block_a: Final[RoamNode] = _block(uid="blckuid01", id_=2, page_id=1)
        block_b: Final[RoamNode] = _block(uid="blckuid02", id_=3, page_id=1)
        network: Final[NodeNetwork] = [page, block_a, block_b]
        result: Final[NodeNetwork] = anchor_tree(network, NodeFetchAnchor(qualifier=_PAGE_TITLE))
        assert {n.uid for n in result} == {"pageuid01", "blckuid01", "blckuid02"}

    def test_includes_all_descendants_recursively(self) -> None:
        """Test that descendants at all depths are included in the result."""
        page: Final[RoamNode] = _page(uid="pageuid01", id_=1, title=_PAGE_TITLE, child_ids=[2])
        block_a: Final[RoamNode] = _block(uid="blckuid01", id_=2, page_id=1, child_ids=[3])
        block_a1: Final[RoamNode] = _block(uid="blckuid02", id_=3, page_id=1)
        network: Final[NodeNetwork] = [page, block_a, block_a1]
        result: Final[NodeNetwork] = anchor_tree(network, NodeFetchAnchor(qualifier=_PAGE_TITLE))
        assert {n.uid for n in result} == {"pageuid01", "blckuid01", "blckuid02"}

    def test_excludes_nodes_outside_subtree(self) -> None:
        """Test that nodes not reachable from the anchor are excluded."""
        page1: Final[RoamNode] = _page(uid=_VALID_UID, id_=1, title="Page One", child_ids=[])
        page2: Final[RoamNode] = _page(uid="pgeuid002", id_=2, title="Page Two", child_ids=[3])
        block_of_page2: Final[RoamNode] = _block(uid="blckuid01", id_=3, page_id=2)
        network: Final[NodeNetwork] = [page1, page2, block_of_page2]
        result: Final[NodeNetwork] = anchor_tree(network, NodeFetchAnchor(qualifier=_VALID_UID))
        assert {n.uid for n in result} == {_VALID_UID}

    def test_works_with_node_uid_anchor(self) -> None:
        """Test that anchor_tree works when anchor kind is NODE_UID."""
        block_root: Final[RoamNode] = _block(uid=_VALID_UID, id_=1, page_id=99, child_ids=[2])
        block_child: Final[RoamNode] = _block(uid="blckuid01", id_=2, page_id=99)
        network: Final[NodeNetwork] = [block_root, block_child]
        result: Final[NodeNetwork] = anchor_tree(network, NodeFetchAnchor(qualifier=_VALID_UID))
        assert {n.uid for n in result} == {_VALID_UID, "blckuid01"}

    def test_raises_value_error_when_anchor_not_in_network(self) -> None:
        """Test that ValueError is raised when the anchor matches no node."""
        page: Final[RoamNode] = _page_node()
        with pytest.raises(ValueError):
            anchor_tree([page], NodeFetchAnchor(qualifier="Nonexistent Page"))

    def test_raises_value_error_when_child_id_missing_from_network(self) -> None:
        """Test that ValueError is raised when a child id is absent from the network."""
        page: Final[RoamNode] = _page(uid=_PAGE_UID, id_=1, title=_PAGE_TITLE, child_ids=[99])
        with pytest.raises(ValueError, match="99"):
            anchor_tree([page], NodeFetchAnchor(qualifier=_PAGE_TITLE))
