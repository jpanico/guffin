"""Tests for the roam_tree module."""

import pytest

from guffin.roam.network import (
    all_children_present,
    all_parents_present,
    has_unique_ids,
    is_acyclic,
)
from guffin.roam.node import NodeType, RoamNode, node_type
from guffin.roam.primitives import Id, IdObject
from guffin.roam.tree import NodeTree, NodeTreeDFSIterator, is_tree
from guffin.common.validation import ValidationError

from conftest import STUB_TIME, STUB_USER, article1_node_tree


class TestIsTree:
    """Tests for is_tree."""

    # ------------------------------------------------------------------
    # valid trees → ValidationResult with no errors
    # ------------------------------------------------------------------

    def test_empty_network_returns_valid(self) -> None:
        """Test that an empty network satisfies all remaining tree invariants."""
        stub_root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        result = is_tree(stub_root, [])
        assert result.is_valid is True

    def test_single_root_node_is_valid(self) -> None:
        """Test that a single parentless node satisfies all tree invariants."""
        node = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        result = is_tree(node, [node])
        assert result.is_valid is True

    def test_two_node_tree_is_valid(self) -> None:
        """Test that a proper root→child pair satisfies all tree invariants."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        result = is_tree(root, [root, child])
        assert result.is_valid is True

    def test_three_node_chain_is_valid(self) -> None:
        """Test that a three-node linear chain satisfies all tree invariants."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        mid = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=20)],
        )
        leaf = RoamNode(
            uid="block0002",
            id=20,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        result = is_tree(root, [root, mid, leaf])
        assert result.is_valid is True

    # ------------------------------------------------------------------
    # invalid trees → ValidationResult with errors
    # ------------------------------------------------------------------

    def test_self_loop_returns_invalid(self) -> None:
        """Test that a self-loop violates is_acyclic and returns an invalid result."""
        node = RoamNode(uid="cycleA001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=1)])
        result = is_tree(node, [node])
        assert result.is_valid is False
        assert result.errors == (
            ValidationError(
                message="child-edge graph contains a directed cycle involving node 'cycleA001'",
                validator=is_acyclic,
            ),
        )

    def test_missing_child_returns_invalid(self) -> None:
        """Test that an absent child reference violates all_children_present and returns an invalid result."""
        parent = RoamNode(
            uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=99)]
        )
        result = is_tree(parent, [parent])
        assert result.is_valid is False
        assert result.errors == (
            ValidationError(
                message="child ids absent from network: [99]; referenced by nodes: [1]",
                validator=all_children_present,
            ),
        )

    def test_absent_non_root_parent_returns_invalid(self) -> None:
        """Test that an absent parent on a non-root node violates all_parents_present and returns an invalid result."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=1), IdObject(id=99)],
            page=IdObject(id=1),
        )
        result = is_tree(root, [root, child])
        assert result.is_valid is False
        assert result.errors == (
            ValidationError(
                message="parent ids absent from network: [99]; referenced by nodes: [10]",
                validator=all_parents_present,
            ),
        )

    def test_two_roots_returns_valid(self) -> None:
        """Test that two parentless nodes satisfy all tree invariants."""
        node1 = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        node2 = RoamNode(uid="page00002", id=2, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        result = is_tree(node1, [node1, node2])
        assert result.is_valid is True

    def test_multiple_failures_accumulate_all_errors(self) -> None:
        """Test that all validators run even after prior failures, accumulating every error."""
        # duplicate id=1 → has_unique_ids fails
        # node1 references absent child id=99 → all_children_present fails
        # node2 references absent parent id=88 → all_parents_present fails
        node1 = RoamNode(
            uid="page00001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            title="stub",
            children=[IdObject(id=99)],
        )
        node2 = RoamNode(
            uid="page00002",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            string="stub",
            parents=[IdObject(id=1), IdObject(id=88)],
            page=IdObject(id=1),
        )
        result = is_tree(node1, [node1, node2])
        assert result.is_valid is False
        assert result.errors == (
            ValidationError(message="expected unique node ids; found duplicates: [1]", validator=has_unique_ids),
            ValidationError(
                message="child ids absent from network: [99]; referenced by nodes: [1]",
                validator=all_children_present,
            ),
            ValidationError(
                message="parent ids absent from network: [88]; referenced by nodes: [1]",
                validator=all_parents_present,
            ),
        )

    def test_not_rooted_subtree_is_valid(self) -> None:
        """Test that a node-UID subtree with an external root parent is valid."""
        # root's parent (id=99) is outside the network — all_parents_present always exempts the root node's parents
        root = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="root",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        child = RoamNode(
            uid="block0002",
            id=20,
            time=STUB_TIME,
            user=STUB_USER,
            string="child",
            parents=[IdObject(id=10)],
            page=IdObject(id=99),
            children=[],
        )
        result = is_tree(root, [root, child])
        assert result.is_valid is True

    def test_subtree_root_external_parent_is_always_exempt(self) -> None:
        """Test that a subtree root's external parent is always exempt — no flag required."""
        root = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="root",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        result = is_tree(root, [root])
        assert result.is_valid is True


class TestNodeTree:
    """Tests for NodeTree."""

    def test_article_fixture_is_valid_tree(self) -> None:
        """Test that test_article_1_nodes.yaml constructs a valid NodeTree without raising."""
        node_tree = article1_node_tree()
        assert node_tree.tree_network

    def test_direct_construction_raises(self) -> None:
        """Test that constructing NodeTree directly (bypassing build) raises ValueError."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        with pytest.raises(Exception, match="NodeTree.build"):
            NodeTree(tree_network=[root], root_node=root)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# TestNodeTreeNodeIds
# ---------------------------------------------------------------------------


class TestNodeTreeNodeIds:
    """Tests for NodeTree.node_ids — the set of all RoamNode.id values in the tree."""

    def test_single_root_returns_singleton(self) -> None:
        """Test that a tree with only a root node returns a set containing just root.id."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert tree.node_ids() == {1}

    def test_article_fixture_node_ids_matches_network(self) -> None:
        """Test that node_ids() equals {n.id for n in tree.tree_network} for the article fixture."""
        tree = article1_node_tree()
        assert tree.node_ids() == {n.id for n in tree.tree_network}


# ---------------------------------------------------------------------------
# TestNodeTreeNodeRefsIds
# ---------------------------------------------------------------------------


class TestNodeTreeNodeRefsIds:
    """Tests for NodeTree.node_refs_ids — the set of all RoamNode.refs ids across the tree."""

    def test_no_refs_returns_empty_set(self) -> None:
        """Test that a tree whose nodes have no refs returns an empty set."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert tree.node_refs_ids() == set()

    def test_block_with_ref_returns_ref_id(self) -> None:
        """Test that a block node with a ref contributes its ref id to the result."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[some page]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=99)],
        )
        ext = RoamNode(uid="extpage01", id=99, time=STUB_TIME, user=STUB_USER, title="some page", children=[])
        tree = NodeTree.build(super_network=[root, block, ext], root_node=root)
        assert tree.node_refs_ids() == {99}


# ---------------------------------------------------------------------------
# TestNodeTreeExternalRefsIds
# ---------------------------------------------------------------------------


class TestNodeTreeExternalRefsIds:
    """Tests for NodeTree.external_refs_ids — ids in node_refs_ids but not in node_ids."""

    # ------------------------------------------------------------------
    # no refs → empty set
    # ------------------------------------------------------------------

    def test_no_refs_returns_empty_set(self) -> None:
        """Test that a tree with no refs at all returns an empty set."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert tree.external_refs_ids() == set()

    def test_no_refs_on_block_nodes_returns_empty_set(self) -> None:
        """Test that a tree whose block nodes have no refs returns an empty set."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="plain text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, block], root_node=root)
        assert tree.external_refs_ids() == set()

    # ------------------------------------------------------------------
    # all refs internal → empty set
    # ------------------------------------------------------------------

    def test_all_refs_internal_returns_empty_set(self) -> None:
        """Test that a tree whose every ref id resolves to a member node returns an empty set."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[stub]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=1)],  # refs back to the root page — internal
        )
        tree = NodeTree.build(super_network=[root, block], root_node=root)
        assert tree.external_refs_ids() == set()

    # ------------------------------------------------------------------
    # all refs external → full refs set returned
    # ------------------------------------------------------------------

    def test_all_refs_external_returns_full_refs_set(self) -> None:
        """Test that a tree whose every ref id is absent from node_ids returns the full refs set."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[External]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=99)],  # id=99 not in tree_network
        )
        ext = RoamNode(uid="extpage01", id=99, time=STUB_TIME, user=STUB_USER, title="External", children=[])
        tree = NodeTree.build(super_network=[root, block, ext], root_node=root)
        assert tree.external_refs_ids() == {99}

    # ------------------------------------------------------------------
    # mixed internal and external refs → only external ids returned
    # ------------------------------------------------------------------

    def test_mixed_refs_returns_only_external_ids(self) -> None:
        """Test that only ref ids absent from node_ids are returned when refs are mixed."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[stub]] [[External]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=1), IdObject(id=99)],  # id=1 internal, id=99 external
        )
        ext = RoamNode(uid="extpage01", id=99, time=STUB_TIME, user=STUB_USER, title="External", children=[])
        tree = NodeTree.build(super_network=[root, block, ext], root_node=root)
        assert tree.external_refs_ids() == {99}

    def test_multiple_external_refs_across_nodes(self) -> None:
        """Test that external refs from multiple nodes are all returned."""
        root = RoamNode(
            uid="page00001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        block_a = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[ExtA]]",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50)],
        )
        block_b = RoamNode(
            uid="block0002",
            id=20,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[stub]] [[ExtB]]",
            order=1,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=1), IdObject(id=60)],  # id=1 internal, id=60 external
        )
        ext_a = RoamNode(uid="extpage01", id=50, time=STUB_TIME, user=STUB_USER, title="ExtA", children=[])
        ext_b = RoamNode(uid="extpage02", id=60, time=STUB_TIME, user=STUB_USER, title="ExtB", children=[])
        tree = NodeTree.build(super_network=[root, block_a, block_b, ext_a, ext_b], root_node=root)
        assert tree.external_refs_ids() == {50, 60}

    # ------------------------------------------------------------------
    # article fixture — semantic identity check
    # ------------------------------------------------------------------

    def test_article_fixture_external_refs_are_subset_of_refs_ids(self) -> None:
        """Test that external_refs_ids is always a subset of node_refs_ids for the article fixture."""
        tree = article1_node_tree()
        assert tree.external_refs_ids() <= tree.node_refs_ids()

    def test_article_fixture_external_refs_disjoint_from_node_ids(self) -> None:
        """Test that external_refs_ids has no overlap with node_ids for the article fixture."""
        tree = article1_node_tree()
        assert tree.external_refs_ids().isdisjoint(tree.node_ids())

    def test_article_fixture_external_refs_equals_set_difference(self) -> None:
        """Test that external_refs_ids equals node_refs_ids minus node_ids for the article fixture."""
        tree = article1_node_tree()
        assert tree.external_refs_ids() == tree.node_refs_ids() - tree.node_ids()


# ---------------------------------------------------------------------------
# TestNodeTreeIdMap
# ---------------------------------------------------------------------------


class TestNodeTreeIdMap:
    """Tests for NodeTree.id_map — merged id → RoamNode index over tree_network and refs_by_id."""

    def test_single_root_maps_root_by_id(self) -> None:
        """Test that a one-node tree produces id_map = {root.id: root}."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert tree.id_map == {1: root}

    def test_covers_all_tree_network_nodes(self) -> None:
        """Test that every node in tree_network appears in id_map."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="text",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, block], root_node=root)
        assert all(n.id in tree.id_map for n in tree.tree_network)

    def test_covers_all_refs_by_id_nodes(self) -> None:
        """Test that every node in refs_by_id appears in id_map."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[Ref]]",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=99)],
        )
        ref_page = RoamNode(uid="refpage01", id=99, time=STUB_TIME, user=STUB_USER, title="Ref", children=[])
        tree = NodeTree.build(super_network=[root, block, ref_page], root_node=root)
        assert 99 in tree.id_map
        assert tree.id_map[99] is ref_page

    def test_keys_equal_union_of_tree_and_refs_ids(self) -> None:
        """Test that id_map.keys() equals the union of tree_network ids and refs_by_id ids."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[Ref]]",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=99)],
        )
        ref_page = RoamNode(uid="refpage01", id=99, time=STUB_TIME, user=STUB_USER, title="Ref", children=[])
        tree = NodeTree.build(super_network=[root, block, ref_page], root_node=root)
        expected: set[Id] = {n.id for n in tree.tree_network} | set(tree.refs_by_id.keys())
        assert set(tree.id_map.keys()) == expected

    def test_article_fixture_id_map_covers_tree_and_refs(self) -> None:
        """Test that the article fixture's id_map keys equal tree_network ids ∪ refs_by_id keys."""
        tree = article1_node_tree()
        expected: set[Id] = {n.id for n in tree.tree_network} | set(tree.refs_by_id.keys())
        assert set(tree.id_map.keys()) == expected

    def test_excluded_from_model_dump(self) -> None:
        """Test that id_map does not appear in model_dump() output."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert "id_map" not in tree.model_dump()


# ---------------------------------------------------------------------------
# TestNodeTreePageNameMap
# ---------------------------------------------------------------------------


class TestNodeTreePageNameMap:
    """Tests for NodeTree.page_name_map — title → RoamNode index for all ROAM_PAGE nodes."""

    def test_single_root_page_maps_by_title(self) -> None:
        """Test that a one-node tree produces page_name_map = {root.title: root}."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="My Page", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert tree.page_name_map == {"My Page": root}

    def test_excludes_block_nodes(self) -> None:
        """Test that block (non-ROAM_PAGE) nodes are absent from page_name_map."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="plain text",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, block], root_node=root)
        assert all(node_type(n) == NodeType.ROAM_PAGE for n in tree.page_name_map.values())

    def test_includes_ref_page_nodes(self) -> None:
        """Test that ROAM_PAGE nodes from refs_by_id appear in page_name_map."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[Ref Page]]",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=99)],
        )
        ref_page = RoamNode(uid="refpage01", id=99, time=STUB_TIME, user=STUB_USER, title="Ref Page", children=[])
        tree = NodeTree.build(super_network=[root, block, ref_page], root_node=root)
        assert "Ref Page" in tree.page_name_map
        assert tree.page_name_map["Ref Page"] is ref_page

    def test_maps_by_title(self) -> None:
        """Test that page_name_map[n.title] == n for every ROAM_PAGE node in id_map."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        block = RoamNode(
            uid="block0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="[[Other]]",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=99)],
        )
        ref_page = RoamNode(uid="refpage01", id=99, time=STUB_TIME, user=STUB_USER, title="Other", children=[])
        tree = NodeTree.build(super_network=[root, block, ref_page], root_node=root)
        for title, node in tree.page_name_map.items():
            assert node.title == title

    def test_article_fixture_contains_root_page(self) -> None:
        """Test that the article fixture's root page is in page_name_map."""
        tree = article1_node_tree()
        assert tree.root_node.title is not None
        assert tree.root_node.title in tree.page_name_map

    def test_article_fixture_all_values_are_pages(self) -> None:
        """Test that every value in the article fixture's page_name_map is a ROAM_PAGE node."""
        tree = article1_node_tree()
        assert all(node_type(n) == NodeType.ROAM_PAGE for n in tree.page_name_map.values())

    def test_excluded_from_model_dump(self) -> None:
        """Test that page_name_map does not appear in model_dump() output."""
        root = RoamNode(uid="page00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert "page_name_map" not in tree.model_dump()


# ---------------------------------------------------------------------------
# TestNodeTreeDFSIterator
# ---------------------------------------------------------------------------


class TestNodeTreeDFSIterator:
    """Tests for NodeTreeDFSIterator — pre-order depth-first traversal of a NodeTree."""

    def test_single_node_tree_yields_root(self) -> None:
        """Test that a one-node tree yields only the root node."""
        root = RoamNode(uid="root00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        assert [n.uid for n in NodeTreeDFSIterator(tree)] == ["root00001"]

    def test_two_node_tree_yields_root_then_child(self) -> None:
        """Test that a root→child tree yields root first, then child."""
        root = RoamNode(uid="root00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="chld00001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="c",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, child], root_node=root)
        assert [n.uid for n in NodeTreeDFSIterator(tree)] == ["root00001", "chld00001"]

    def test_children_yielded_in_ascending_order_field(self) -> None:
        """Test that children are visited in ascending order-field order, not id order."""
        root = RoamNode(
            uid="root00001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        # id=20 has order=0 so it should come first despite having the larger id
        child_first = RoamNode(
            uid="chld00002",
            id=20,
            time=STUB_TIME,
            user=STUB_USER,
            string="first",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        child_second = RoamNode(
            uid="chld00001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="second",
            order=1,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, child_first, child_second], root_node=root)
        assert [n.uid for n in NodeTreeDFSIterator(tree)] == ["root00001", "chld00002", "chld00001"]

    def test_preorder_visits_subtree_before_sibling(self) -> None:
        """Test that a child's full subtree is visited before the next sibling (pre-order)."""
        root = RoamNode(
            uid="root00001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        node_a = RoamNode(
            uid="nodeA0001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="A",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=11)],
        )
        node_a1 = RoamNode(
            uid="nodeA1001",
            id=11,
            time=STUB_TIME,
            user=STUB_USER,
            string="A1",
            order=0,
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        node_b = RoamNode(
            uid="nodeB0001",
            id=20,
            time=STUB_TIME,
            user=STUB_USER,
            string="B",
            order=1,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, node_a, node_a1, node_b], root_node=root)
        assert [n.uid for n in NodeTreeDFSIterator(tree)] == ["root00001", "nodeA0001", "nodeA1001", "nodeB0001"]

    def test_all_nodes_yielded_exactly_once(self) -> None:
        """Test that every node in the tree is yielded exactly once with no duplicates."""
        root = RoamNode(
            uid="root00001",
            id=1,
            time=STUB_TIME,
            user=STUB_USER,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        child_a = RoamNode(
            uid="chld00001",
            id=10,
            time=STUB_TIME,
            user=STUB_USER,
            string="a",
            order=0,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        child_b = RoamNode(
            uid="chld00002",
            id=20,
            time=STUB_TIME,
            user=STUB_USER,
            string="b",
            order=1,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = NodeTree.build(super_network=[root, child_a, child_b], root_node=root)
        yielded: list[RoamNode] = list(NodeTreeDFSIterator(tree))
        assert len(yielded) == 3
        assert len({n.uid for n in yielded}) == 3

    def test_iterator_exhausted_raises_stop_iteration(self) -> None:
        """Test that __next__ raises StopIteration once all nodes have been yielded."""
        root = RoamNode(uid="root00001", id=1, time=STUB_TIME, user=STUB_USER, title="stub", children=[])
        tree = NodeTree.build(super_network=[root], root_node=root)
        it: NodeTreeDFSIterator = NodeTreeDFSIterator(tree)
        assert next(it).uid == "root00001"
        with pytest.raises(StopIteration):
            next(it)

    def test_article_fixture_yields_all_nodes(self) -> None:
        """Test that the iterator yields every node in the article fixture exactly once."""
        tree = article1_node_tree()
        yielded: list[RoamNode] = list(NodeTreeDFSIterator(tree))
        assert len(yielded) == len(tree.tree_network)
        assert {n.uid for n in yielded} == {n.uid for n in tree.tree_network}

    def test_article_fixture_parent_always_precedes_children(self) -> None:
        """Test that every parent node appears before all of its children in the traversal."""
        tree = article1_node_tree()
        yielded: list[RoamNode] = list(NodeTreeDFSIterator(tree))
        position: dict[str, int] = {n.uid: i for i, n in enumerate(yielded)}
        for node in tree.tree_network:
            if node.children:
                for child_stub in node.children:
                    child: RoamNode = tree.id_map[child_stub.id]
                    assert position[node.uid] < position[child.uid]

    def test_article_fixture_dfs_id_order(self) -> None:
        """Test the exact pre-order DFS id sequence for the test_article fixture.

        Expected traversal (by Datomic entity id):
          3327  — root page "[[Test Article]] 1"
          11113 — callout block        (order=0, child of root)
          3328  — Section 1            (order=1, child of root)
          3331  — Section 1.1          (order=0, child of 3328)
          3334  — illustration 1.1     (order=0, child of 3331)
          11165 — text block           (order=0, child of 3334)
          11124 — image block          (order=1, child of 3334)
          4758  — AI assistant text    (order=1, child of 3328)
          3329  — Section 2            (order=2, child of root)
          3332  — Section 2.1          (order=0, child of 3329)
          11163 — illustration 2.1     (order=0, child of 3332)
          11167 — text block           (order=0, child of 11163)
          11164 — image block          (order=1, child of 11163)
          4025  — Section 2.1.1        (order=1, child of 3332)
          4028  — Section 2.1.1.1      (order=0, child of 4025)
          4026  — Section 2.2          (order=1, child of 3329)
          3330  — Section 3            (order=3, child of root)
          3333  — Section 3.1          (order=0, child of 3330)
        """
        tree = article1_node_tree()
        expected_ids: list[Id] = [
            3327,
            11113,
            3328,
            3331,
            3334,
            11165,
            11124,
            4758,
            3329,
            3332,
            11163,
            11167,
            11164,
            4025,
            4028,
            4026,
            3330,
            3333,
        ]
        assert [n.id for n in NodeTreeDFSIterator(tree)] == expected_ids
