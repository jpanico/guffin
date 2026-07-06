"""Tests for the guffin.roam.node_network module."""

import pytest
from conftest import article1_node_tree

from guffin.common.validation import ValidationError
from guffin.roam.node import RoamNode
from guffin.roam.node_network import (
    all_children_present,
    all_descendants,
    all_parents_present,
    has_unique_ids,
    is_acyclic,
    min_effective_heading_level,
    refs_ids,
)
from guffin.roam.primitives import IdObject


class TestAllDescendants:
    """Tests for all_descendants."""

    # ------------------------------------------------------------------
    # ancestor is a leaf → empty result
    # ------------------------------------------------------------------

    def test_leaf_ancestor_returns_empty(self) -> None:
        """Test that an ancestor with no children returns an empty list."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[])
        assert all_descendants(ancestor, [ancestor]) == []

    def test_ancestor_with_none_children_returns_empty(self) -> None:
        """Test that an ancestor whose children field is None returns an empty list."""
        ancestor = RoamNode(
            uid="block0001",
            id=10,
            string="leaf",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_descendants(ancestor, [ancestor]) == []

    # ------------------------------------------------------------------
    # single-level descendants
    # ------------------------------------------------------------------

    def test_single_child_returned(self) -> None:
        """Test that an ancestor with one child returns a list containing just that child."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="child",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_descendants(ancestor, [ancestor, child]) == [child]

    def test_multiple_direct_children_all_returned(self) -> None:
        """Test that all direct children of an ancestor are returned."""
        ancestor = RoamNode(
            uid="page00001",
            id=1,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        child1 = RoamNode(
            uid="block0001",
            id=10,
            string="c1",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        child2 = RoamNode(
            uid="block0002",
            id=20,
            string="c2",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        result = all_descendants(ancestor, [ancestor, child1, child2])
        assert {n.id for n in result} == {10, 20}

    # ------------------------------------------------------------------
    # multi-level descendants
    # ------------------------------------------------------------------

    def test_deep_chain_returns_all_descendants(self) -> None:
        """Test that a linear chain ancestor→child→grandchild returns both descendants."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="child",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=20)],
        )
        grandchild = RoamNode(
            uid="block0002",
            id=20,
            string="grandchild",
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        result = all_descendants(ancestor, [ancestor, child, grandchild])
        assert {n.id for n in result} == {10, 20}

    def test_branching_tree_returns_all_descendants(self) -> None:
        """Test that a branching tree returns every node reachable from the ancestor."""
        ancestor = RoamNode(
            uid="page00001",
            id=1,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        child1 = RoamNode(
            uid="block0001",
            id=10,
            string="c1",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=30)],
        )
        child2 = RoamNode(
            uid="block0002",
            id=20,
            string="c2",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=40)],
        )
        grandchild1 = RoamNode(
            uid="block0003",
            id=30,
            string="gc1",
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        grandchild2 = RoamNode(
            uid="block0004",
            id=40,
            string="gc2",
            parents=[IdObject(id=20)],
            page=IdObject(id=1),
        )
        network = [ancestor, child1, child2, grandchild1, grandchild2]
        result = all_descendants(ancestor, network)
        assert {n.id for n in result} == {10, 20, 30, 40}

    # ------------------------------------------------------------------
    # ancestor excluded from result
    # ------------------------------------------------------------------

    def test_ancestor_not_included_in_result(self) -> None:
        """Test that the ancestor itself is never included in the returned NodeNetwork."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="child",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        result = all_descendants(ancestor, [ancestor, child])
        assert ancestor not in result

    # ------------------------------------------------------------------
    # unreachable nodes in network are excluded
    # ------------------------------------------------------------------

    def test_unreachable_nodes_excluded(self) -> None:
        """Test that nodes in the network that are not reachable from ancestor are excluded."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="child",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        unrelated = RoamNode(
            uid="block0099",
            id=99,
            string="unrelated",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        result = all_descendants(ancestor, [ancestor, child, unrelated])
        assert {n.id for n in result} == {10}

    # ------------------------------------------------------------------
    # error cases
    # ------------------------------------------------------------------

    def test_ancestor_not_in_network_raises(self) -> None:
        """Test that passing an ancestor not present in the network raises ValueError."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[])
        other = RoamNode(uid="page00002", id=2, title="other", children=[])
        with pytest.raises(ValueError, match="is not present in network"):
            all_descendants(ancestor, [other])

    def test_unresolvable_child_id_raises(self) -> None:
        """Test that a child id not present in the network raises ValueError."""
        ancestor = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=99)])
        with pytest.raises(ValueError, match="is not resolvable in network"):
            all_descendants(ancestor, [ancestor])


class TestAllChildrenPresent:
    """Tests for all_children_present."""

    # ------------------------------------------------------------------
    # trivially satisfied → None
    # ------------------------------------------------------------------

    def test_empty_network_returns_none(self) -> None:
        """Test that an empty network vacuously satisfies the condition and returns None."""
        assert all_children_present([]) is None

    def test_network_with_no_children_returns_none(self) -> None:
        """Test that a network of leaf nodes (all children=None) vacuously returns None."""
        node1 = RoamNode(uid="page00001", id=1, title="stub", children=[])
        node2 = RoamNode(
            uid="block0001",
            id=10,
            string="text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_children_present([node1, node2]) is None

    def test_node_with_empty_children_list_returns_none(self) -> None:
        """Test that a node with an empty children list vacuously returns None."""
        node = RoamNode(uid="page00001", id=1, title="stub", children=[])
        assert all_children_present([node]) is None

    # ------------------------------------------------------------------
    # all children present → None
    # ------------------------------------------------------------------

    def test_single_child_present_returns_none(self) -> None:
        """Test that a parent whose single child id is in the network returns None."""
        parent = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_children_present([parent, child]) is None

    def test_multiple_children_all_present_returns_none(self) -> None:
        """Test that a parent whose every child id is in the network returns None."""
        parent = RoamNode(
            uid="page00001",
            id=1,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        child1 = RoamNode(
            uid="block0001",
            id=10,
            string="c1",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        child2 = RoamNode(
            uid="block0002",
            id=20,
            string="c2",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_children_present([parent, child1, child2]) is None

    def test_multi_level_network_all_children_present_returns_none(self) -> None:
        """Test that a multi-level network with all children present at every level returns None."""
        root = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        mid = RoamNode(
            uid="block0001",
            id=10,
            string="mid",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=20)],
        )
        leaf = RoamNode(
            uid="block0002",
            id=20,
            string="leaf",
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        assert all_children_present([root, mid, leaf]) is None

    # ------------------------------------------------------------------
    # at least one child absent → ValidationError
    # ------------------------------------------------------------------

    def test_single_absent_child_returns_error(self) -> None:
        """Test that a node whose single child id is absent from the network returns a ValidationError."""
        parent = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=99)])
        assert all_children_present([parent]) == ValidationError(
            message="child ids absent from network: [99]; referenced by nodes: [1]",
            validator=all_children_present,
        )

    def test_one_absent_among_several_children_returns_error(self) -> None:
        """Test that a node with one absent child id among several returns a ValidationError."""
        parent = RoamNode(
            uid="page00001",
            id=1,
            title="stub",
            children=[IdObject(id=10), IdObject(id=99)],
        )
        child = RoamNode(
            uid="block0001",
            id=10,
            string="text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_children_present([parent, child]) == ValidationError(
            message="child ids absent from network: [99]; referenced by nodes: [1]",
            validator=all_children_present,
        )

    def test_absent_child_in_second_node_returns_error(self) -> None:
        """Test that a missing child in any node in the network returns a ValidationError."""
        root = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        mid = RoamNode(
            uid="block0001",
            id=10,
            string="mid",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=99)],
        )
        assert all_children_present([root, mid]) == ValidationError(
            message="child ids absent from network: [99]; referenced by nodes: [10]",
            validator=all_children_present,
        )


class TestAllParentsPresent:
    """Tests for all_parents_present."""

    # ------------------------------------------------------------------
    # trivially satisfied → None
    # ------------------------------------------------------------------

    def test_empty_network_returns_none(self) -> None:
        """Test that an empty network vacuously satisfies the condition and returns None."""
        stub = RoamNode(uid="page00001", id=1, title="stub", children=[])
        assert all_parents_present([], stub) is None

    def test_network_with_no_parents_returns_none(self) -> None:
        """Test that a network of root nodes (all parents=None) vacuously returns None."""
        node1 = RoamNode(uid="page00001", id=1, title="stub", children=[])
        node2 = RoamNode(uid="page00002", id=2, title="stub", children=[])
        assert all_parents_present([node1, node2], node1) is None

    def test_node_with_empty_parents_list_returns_none(self) -> None:
        """Test that a node with an empty parents list vacuously returns None."""
        node = RoamNode(uid="block0001", id=10, string="stub", parents=[], page=IdObject(id=99))
        assert all_parents_present([node], node) is None

    # ------------------------------------------------------------------
    # all parents present → None
    # ------------------------------------------------------------------

    def test_single_parent_present_returns_none(self) -> None:
        """Test that a child whose single parent id is in the network returns None."""
        parent = RoamNode(uid="page00001", id=1, title="stub", children=[])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert all_parents_present([parent, child], parent) is None

    def test_multi_level_network_all_parents_present_returns_none(self) -> None:
        """Test that a multi-level network with all parents present at every level returns None."""
        root = RoamNode(uid="page00001", id=1, title="stub", children=[])
        mid = RoamNode(
            uid="block0001",
            id=10,
            string="mid",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        leaf = RoamNode(
            uid="block0002",
            id=20,
            string="leaf",
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        assert all_parents_present([root, mid, leaf], root) is None

    # ------------------------------------------------------------------
    # at least one parent absent → ValidationError
    # ------------------------------------------------------------------

    def test_single_absent_parent_returns_error(self) -> None:
        """Test that a non-root node whose single parent id is absent from the network returns a ValidationError."""
        root = RoamNode(uid="page00001", id=1, title="stub", children=[])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert all_parents_present([root, child], root) == ValidationError(
            message="parent ids absent from network: [99]; referenced by nodes: [10]",
            validator=all_parents_present,
        )

    def test_one_absent_among_several_parents_returns_error(self) -> None:
        """Test that a node with one absent parent id among several returns a ValidationError."""
        parent = RoamNode(uid="page00001", id=1, title="stub", children=[])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=1), IdObject(id=99)],
            page=IdObject(id=1),
        )
        assert all_parents_present([parent, child], parent) == ValidationError(
            message="parent ids absent from network: [99]; referenced by nodes: [10]",
            validator=all_parents_present,
        )

    def test_absent_parent_in_second_node_returns_error(self) -> None:
        """Test that a missing parent in any node in the network returns a ValidationError."""
        root = RoamNode(uid="page00001", id=1, title="stub", children=[])
        mid = RoamNode(
            uid="block0001",
            id=10,
            string="mid",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        leaf = RoamNode(
            uid="block0002",
            id=20,
            string="leaf",
            parents=[IdObject(id=99)],
            page=IdObject(id=1),
        )
        assert all_parents_present([root, mid, leaf], root) == ValidationError(
            message="parent ids absent from network: [99]; referenced by nodes: [20]",
            validator=all_parents_present,
        )

    # ------------------------------------------------------------------
    # root's external parents exempt from parent-presence check
    # ------------------------------------------------------------------

    def test_root_with_absent_parent_returns_none(self) -> None:
        """Test that a root node's absent parent is exempt from the check."""
        root = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert all_parents_present([root], root) is None

    def test_external_ancestor_in_non_root_parents_returns_none(self) -> None:
        """Test that external ancestors propagate: a non-root node's parents list may include external ancestor ids.

        Because RoamNode.parents holds the complete ancestor path (not just the immediate parent),
        a non-root node in a sub-network will carry external ancestor ids in its parents list — the
        same ids that appear in the root's parents.  These must be exempt from the check.
        """
        root = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        child = RoamNode(
            uid="block0002",
            id=20,
            string="stub",
            parents=[IdObject(id=99), IdObject(id=10)],
            page=IdObject(id=99),
        )
        assert all_parents_present([root, child], root) is None

    def test_non_root_with_absent_parent_returns_error(self) -> None:
        """Test that only root's external parents are exempt — absent parents on non-root nodes are still caught."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=1), IdObject(id=99)],
            page=IdObject(id=1),
        )
        assert all_parents_present([page, child], page) == ValidationError(
            message="parent ids absent from network: [99]; referenced by nodes: [10]",
            validator=all_parents_present,
        )

    def test_subtree_with_external_root_parent_returns_none(self) -> None:
        """Test a subtree: root's external parent is exempt; child's present parent is valid."""
        root = RoamNode(
            uid="block0001",
            id=10,
            string="root",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        child = RoamNode(
            uid="block0002",
            id=20,
            string="child",
            parents=[IdObject(id=10)],
            page=IdObject(id=99),
        )
        assert all_parents_present([root, child], root) is None


class TestHasUniqueIds:
    """Tests for has_unique_ids."""

    # ------------------------------------------------------------------
    # trivially satisfied → None
    # ------------------------------------------------------------------

    def test_empty_network_returns_none(self) -> None:
        """Test that an empty network vacuously satisfies the condition and returns None."""
        assert has_unique_ids([]) is None

    def test_single_node_returns_none(self) -> None:
        """Test that a one-node network trivially has unique ids and returns None."""
        node = RoamNode(uid="page00001", id=1, title="stub", children=[])
        assert has_unique_ids([node]) is None

    # ------------------------------------------------------------------
    # all ids distinct → None
    # ------------------------------------------------------------------

    def test_two_nodes_with_distinct_ids_returns_none(self) -> None:
        """Test that a two-node network with distinct ids returns None."""
        node1 = RoamNode(uid="page00001", id=1, title="stub", children=[])
        node2 = RoamNode(uid="page00002", id=2, title="stub", children=[])
        assert has_unique_ids([node1, node2]) is None

    def test_three_nodes_with_distinct_ids_returns_none(self) -> None:
        """Test that a three-node network with all distinct ids returns None."""
        node1 = RoamNode(uid="page00001", id=1, title="stub", children=[])
        node2 = RoamNode(
            uid="block0001",
            id=10,
            string="text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        node3 = RoamNode(
            uid="block0002",
            id=20,
            string="text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert has_unique_ids([node1, node2, node3]) is None

    # ------------------------------------------------------------------
    # at least one duplicate id → ValidationError
    # ------------------------------------------------------------------

    def test_two_nodes_with_same_id_returns_error(self) -> None:
        """Test that a two-node network where both nodes share the same id returns a ValidationError."""
        node1 = RoamNode(uid="page00001", id=1, title="stub", children=[])
        node2 = RoamNode(uid="page00002", id=1, title="stub", children=[])
        assert has_unique_ids([node1, node2]) == ValidationError(
            message="expected unique node ids; found duplicates: [1]",
            validator=has_unique_ids,
        )

    def test_one_duplicate_among_several_nodes_returns_error(self) -> None:
        """Test that a single duplicate id among otherwise distinct ids returns a ValidationError."""
        node1 = RoamNode(uid="page00001", id=1, title="stub", children=[])
        node2 = RoamNode(
            uid="block0001",
            id=10,
            string="a",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        node3 = RoamNode(
            uid="block0002",
            id=10,
            string="b",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert has_unique_ids([node1, node2, node3]) == ValidationError(
            message="expected unique node ids; found duplicates: [10]",
            validator=has_unique_ids,
        )


class TestIsAcyclic:
    """Tests for is_acyclic."""

    # ------------------------------------------------------------------
    # trivially satisfied → None
    # ------------------------------------------------------------------

    def test_empty_network_returns_none(self) -> None:
        """Test that an empty network vacuously satisfies the condition and returns None."""
        assert is_acyclic([]) is None

    def test_single_node_no_children_returns_none(self) -> None:
        """Test that a single node with no children has no cycle and returns None."""
        node = RoamNode(uid="page00001", id=1, title="stub", children=[])
        assert is_acyclic([node]) is None

    def test_single_node_empty_children_returns_none(self) -> None:
        """Test that a single node with an empty children list has no cycle and returns None."""
        node = RoamNode(uid="page00001", id=1, title="stub", children=[])
        assert is_acyclic([node]) is None

    # ------------------------------------------------------------------
    # acyclic networks → None
    # ------------------------------------------------------------------

    def test_two_node_chain_returns_none(self) -> None:
        """Test that a two-node parent→child chain has no cycle and returns None."""
        parent = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        child = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert is_acyclic([parent, child]) is None

    def test_three_node_chain_returns_none(self) -> None:
        """Test that a three-node linear chain has no cycle and returns None."""
        root = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=10)])
        mid = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            children=[IdObject(id=20)],
        )
        leaf = RoamNode(
            uid="block0002",
            id=20,
            string="stub",
            parents=[IdObject(id=10)],
            page=IdObject(id=1),
        )
        assert is_acyclic([root, mid, leaf]) is None

    def test_branching_tree_returns_none(self) -> None:
        """Test that a root with two children (no cross-edges) has no cycle and returns None."""
        root = RoamNode(
            uid="page00001",
            id=1,
            title="stub",
            children=[IdObject(id=10), IdObject(id=20)],
        )
        child1 = RoamNode(
            uid="block0001",
            id=10,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        child2 = RoamNode(
            uid="block0002",
            id=20,
            string="stub",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert is_acyclic([root, child1, child2]) is None

    def test_child_outside_network_is_skipped_returns_none(self) -> None:
        """Test that a child reference outside the network is silently skipped and returns None."""
        node = RoamNode(uid="page00001", id=1, title="stub", children=[IdObject(id=99)])
        assert is_acyclic([node]) is None

    # ------------------------------------------------------------------
    # cyclic networks → ValidationError
    # ------------------------------------------------------------------

    def test_self_loop_returns_error(self) -> None:
        """Test that a node whose children list references itself returns a ValidationError."""
        node = RoamNode(uid="cycleA001", id=1, title="stub", children=[IdObject(id=1)])
        assert is_acyclic([node]) == ValidationError(
            message="child-edge graph contains a directed cycle involving node 'cycleA001'",
            validator=is_acyclic,
        )

    def test_two_node_mutual_cycle_returns_error(self) -> None:
        """Test that a two-node cycle (A→B→A via children) returns a ValidationError."""
        node_a = RoamNode(uid="cycleA001", id=1, title="stub", children=[IdObject(id=2)])
        node_b = RoamNode(uid="cycleB001", id=2, title="stub", children=[IdObject(id=1)])
        assert is_acyclic([node_a, node_b]) == ValidationError(
            message="child-edge graph contains a directed cycle involving node 'cycleA001'",
            validator=is_acyclic,
        )

    def test_three_node_cycle_returns_error(self) -> None:
        """Test that a three-node cycle (A→B→C→A via children) returns a ValidationError."""
        node_a = RoamNode(uid="cycleA001", id=1, title="stub", children=[IdObject(id=2)])
        node_b = RoamNode(uid="cycleB001", id=2, title="stub", children=[IdObject(id=3)])
        node_c = RoamNode(uid="cycleC001", id=3, title="stub", children=[IdObject(id=1)])
        assert is_acyclic([node_a, node_b, node_c]) == ValidationError(
            message="child-edge graph contains a directed cycle involving node 'cycleA001'",
            validator=is_acyclic,
        )


class TestRefsIds:
    """Tests for refs_ids."""

    # ------------------------------------------------------------------
    # empty / no refs → empty set
    # ------------------------------------------------------------------

    def test_empty_network_returns_empty_set(self) -> None:
        """Test that an empty network returns an empty set."""
        assert refs_ids([]) == set()

    def test_network_with_no_refs_returns_empty_set(self) -> None:
        """Test that a network where no node has a refs field returns an empty set."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        block = RoamNode(
            uid="block0001",
            id=10,
            string="no refs here",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert refs_ids([page, block]) == set()

    # ------------------------------------------------------------------
    # refs present → correct ids returned
    # ------------------------------------------------------------------

    def test_single_node_one_ref_returns_singleton(self) -> None:
        """Test that a single node with one ref returns a one-element set containing that ref id."""
        block = RoamNode(
            uid="block0001",
            id=10,
            string="[[Target]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50)],
        )
        assert refs_ids([block]) == {50}

    def test_single_node_multiple_refs_returns_all_ids(self) -> None:
        """Test that a single node with multiple refs returns all their ids."""
        block = RoamNode(
            uid="block0001",
            id=10,
            string="[[A]] [[B]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50), IdObject(id=60), IdObject(id=70)],
        )
        assert refs_ids([block]) == {50, 60, 70}

    def test_multiple_nodes_refs_are_unioned(self) -> None:
        """Test that refs from multiple nodes are unioned into a single set."""
        block_a = RoamNode(
            uid="block0001",
            id=10,
            string="[[A]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50)],
        )
        block_b = RoamNode(
            uid="block0002",
            id=20,
            string="[[B]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=60)],
        )
        assert refs_ids([block_a, block_b]) == {50, 60}

    def test_duplicate_ref_ids_are_deduplicated(self) -> None:
        """Test that the same ref id appearing in multiple nodes is included only once."""
        block_a = RoamNode(
            uid="block0001",
            id=10,
            string="[[Shared]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50)],
        )
        block_b = RoamNode(
            uid="block0002",
            id=20,
            string="[[Shared]] again",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50)],
        )
        assert refs_ids([block_a, block_b]) == {50}

    def test_mixed_nodes_with_and_without_refs_ids(self) -> None:
        """Test that only refs from nodes that have a non-None refs field are collected."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        block_no_refs = RoamNode(
            uid="block0001",
            id=10,
            string="plain text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        block_with_refs = RoamNode(
            uid="block0002",
            id=20,
            string="[[Target]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=50)],
        )
        assert refs_ids([page, block_no_refs, block_with_refs]) == {50}

    def test_node_with_empty_refs_list_returns_empty_set(self) -> None:
        """Test that a node whose refs field is an empty list contributes nothing."""
        block = RoamNode(
            uid="block0001",
            id=10,
            string="no links",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[],
        )
        assert refs_ids([block]) == set()

    def test_article_fixture_refs(self) -> None:
        """Test that the article fixture network has the expected :block/refs ids.

        The test_article_1 fixture contains:
        - The page title "[[Test Article]] 1", producing a ref to the "Test Article" page (id 4223).
        - A callout block with [[>]] and [[!INFO]] wikilinks, producing two more ref ids (5450, 5462).
        - A Section 3.2 PDF embed in the page-reference form ``{{[[pdf]]: <url>}}``, referencing
          the "pdf" page (246).
        - Its ``guffin-meta:: #.rm-g`` child block, referencing the "guffin-meta" (11839) and
          ".rm-g" (321) pages, with the nested ``pdf-render:: inline`` referencing the
          "pdf-render" page (11933).
        - The Section 3.2 text block, whose inline ``guffin-meta::`` mention made Roam create
          (and reference) a page literally titled "the following block embeds a PDF with
          guffin-meta" (11932).
        - Section 3.1_5's ``publish:: false`` meta child, referencing the "publish" page (11943).
        """
        assert refs_ids(article1_node_tree().tree_network) == {
            246,
            321,
            4223,
            5450,
            5462,
            11839,
            11932,
            11933,
            11943,
        }


class TestMinEffectiveHeadingLevel:
    """Tests for min_effective_heading_level."""

    def test_empty_network_returns_none(self) -> None:
        """Test that an empty network returns None."""
        assert min_effective_heading_level([]) is None

    def test_no_heading_nodes_returns_none(self) -> None:
        """Test that a network with no heading nodes returns None."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        block = RoamNode(
            uid="block0001",
            id=10,
            string="plain text",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert min_effective_heading_level([page, block]) is None

    def test_single_heading_returns_its_level(self) -> None:
        """Test that a network with one heading node returns that heading's level."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        heading = RoamNode(
            uid="block0001",
            id=10,
            string="Section",
            heading=2,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert min_effective_heading_level([page, heading]) == 2

    def test_multiple_headings_returns_minimum(self) -> None:
        """Test that the minimum level is returned when multiple heading nodes are present."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        h2 = RoamNode(
            uid="block0001",
            id=10,
            string="H2",
            heading=2,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        h3 = RoamNode(
            uid="block0002",
            id=20,
            string="H3",
            heading=3,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert min_effective_heading_level([page, h2, h3]) == 2

    def test_non_heading_nodes_do_not_affect_result(self) -> None:
        """Test that plain-text and page nodes are ignored when computing the minimum."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        plain = RoamNode(
            uid="block0001",
            id=10,
            string="plain",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        h3 = RoamNode(
            uid="block0002",
            id=20,
            string="H3",
            heading=3,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert min_effective_heading_level([page, plain, h3]) == 3

    def test_augmented_heading_is_included(self) -> None:
        """Test that an Augmented Headings ah-level property is treated as an effective heading."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        ah5 = RoamNode(
            uid="block0001",
            id=10,
            string="H5 via AH",
            props={"ah-level": "h5"},
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert min_effective_heading_level([page, ah5]) == 5

    def test_native_and_augmented_headings_minimum_returned(self) -> None:
        """Test that native and augmented heading levels are compared together."""
        page = RoamNode(uid="page00001", id=1, title="stub", children=[])
        h3 = RoamNode(
            uid="block0001",
            id=10,
            string="H3",
            heading=3,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        ah4 = RoamNode(
            uid="block0002",
            id=20,
            string="H4 via AH",
            props={"ah-level": "h4"},
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert min_effective_heading_level([page, h3, ah4]) == 3
