"""Tests for guffin.model.vertex_tree.VertexTreeDFSIterator."""

import pytest
from conftest import article1_vertex_tree

from guffin.model.vertex import (
    HeadingVertex,
    PageVertex,
    TextVertex,
    Vertex,
)
from guffin.model.vertex_tree import VertexTree, VertexTreeDFSIterator
from guffin.roam.primitives import Uid


class TestVertexTreeDFSIterator:
    """Tests for VertexTreeDFSIterator — pre-order depth-first traversal of a VertexTree."""

    # ------------------------------------------------------------------
    # single-vertex tree
    # ------------------------------------------------------------------

    def test_single_vertex_tree_yields_root(self) -> None:
        """Test that a one-vertex tree yields only the root vertex."""
        root = PageVertex(uid="root00001", title="My Page")
        tree = VertexTree(tree_vertices=[root])
        assert [v.uid for v in VertexTreeDFSIterator(tree)] == ["root00001"]

    # ------------------------------------------------------------------
    # two-vertex tree
    # ------------------------------------------------------------------

    def test_two_vertex_tree_yields_root_then_child(self) -> None:
        """Test that a root→child tree yields root first, then child."""
        root = PageVertex(uid="root00001", title="My Page", children=["chld00001"])
        child = TextVertex(uid="chld00001", text="Hello")
        tree = VertexTree(tree_vertices=[root, child])
        assert [v.uid for v in VertexTreeDFSIterator(tree)] == ["root00001", "chld00001"]

    # ------------------------------------------------------------------
    # child ordering
    # ------------------------------------------------------------------

    def test_children_yielded_in_children_list_order(self) -> None:
        """Test that children are visited in the order they appear in the children list.

        The first uid in children is visited before the second, regardless of
        the order the vertices appear in VertexTree.tree_vertices.
        """
        root = PageVertex(uid="root00001", title="Root", children=["chld00002", "chld00001"])
        child_first = TextVertex(uid="chld00002", text="first")
        child_second = TextVertex(uid="chld00001", text="second")
        tree = VertexTree(tree_vertices=[root, child_first, child_second])
        assert [v.uid for v in VertexTreeDFSIterator(tree)] == ["root00001", "chld00002", "chld00001"]

    # ------------------------------------------------------------------
    # pre-order semantics
    # ------------------------------------------------------------------

    def test_preorder_visits_subtree_before_sibling(self) -> None:
        """Test that a child's full subtree is visited before the next sibling (pre-order)."""
        root = PageVertex(uid="root00001", title="Root", children=["nodeA0001", "nodeB0001"])
        node_a = HeadingVertex(uid="nodeA0001", text="A", heading_level=2, children=["nodeA1001"])
        node_a1 = TextVertex(uid="nodeA1001", text="A1")
        node_b = TextVertex(uid="nodeB0001", text="B")
        tree = VertexTree(tree_vertices=[root, node_a, node_a1, node_b])
        assert [v.uid for v in VertexTreeDFSIterator(tree)] == [
            "root00001",
            "nodeA0001",
            "nodeA1001",
            "nodeB0001",
        ]

    # ------------------------------------------------------------------
    # coverage and exhaustion
    # ------------------------------------------------------------------

    def test_all_vertices_yielded_exactly_once(self) -> None:
        """Test that every vertex in the tree is yielded exactly once with no duplicates."""
        root = PageVertex(uid="root00001", title="Root", children=["chld00001", "chld00002"])
        child_a = TextVertex(uid="chld00001", text="a")
        child_b = TextVertex(uid="chld00002", text="b")
        tree = VertexTree(tree_vertices=[root, child_a, child_b])
        yielded: list[Vertex] = list(VertexTreeDFSIterator(tree))
        assert len(yielded) == 3
        assert len({v.uid for v in yielded}) == 3

    def test_iterator_exhausted_raises_stop_iteration(self) -> None:
        """Test that __next__ raises StopIteration once all vertices have been yielded."""
        root = PageVertex(uid="root00001", title="Root")
        tree = VertexTree(tree_vertices=[root])
        it: VertexTreeDFSIterator = VertexTreeDFSIterator(tree)
        assert next(it).uid == "root00001"
        with pytest.raises(StopIteration):
            next(it)

    def test_dfs_method_returns_iterator(self) -> None:
        """Test that VertexTree.dfs() returns a VertexTreeDFSIterator seeded at the root."""
        root = PageVertex(uid="root00001", title="Root")
        tree = VertexTree(tree_vertices=[root])
        it = tree.dfs()
        assert isinstance(it, VertexTreeDFSIterator)
        assert next(it).uid == "root00001"

    # ------------------------------------------------------------------
    # article fixture — structural invariants
    # ------------------------------------------------------------------

    def test_article_fixture_root_is_first(self) -> None:
        """Test that the root vertex (not a child of anything) is yielded first."""
        tree = article1_vertex_tree()
        first: Vertex = next(iter(VertexTreeDFSIterator(tree)))
        child_uids: set[Uid] = {uid for v in tree.tree_vertices if v.children for uid in v.children}
        assert first.uid not in child_uids

    def test_article_fixture_yields_all_vertices(self) -> None:
        """Test that the iterator yields every vertex in the article fixture exactly once."""
        tree = article1_vertex_tree()
        yielded: list[Vertex] = list(VertexTreeDFSIterator(tree))
        assert len(yielded) == len(tree.tree_vertices)
        assert {v.uid for v in yielded} == {v.uid for v in tree.tree_vertices}

    def test_article_fixture_parent_always_precedes_children(self) -> None:
        """Test that every parent vertex appears before all of its children in the traversal."""
        tree = article1_vertex_tree()
        yielded: list[Vertex] = list(VertexTreeDFSIterator(tree))
        position: dict[Uid, int] = {v.uid: i for i, v in enumerate(yielded)}
        for vertex in tree.tree_vertices:
            if vertex.children:
                for child_uid in vertex.children:
                    assert position[vertex.uid] < position[child_uid]

    # ------------------------------------------------------------------
    # article fixture — exact traversal order
    # ------------------------------------------------------------------

    def test_article_fixture_dfs_uid_order(self) -> None:
        """Test the exact pre-order DFS uid sequence for the test_article fixture.

        Expected traversal (by uid):
          6olpFWiw1  — root page "[[Test Article]] 1"
          cNW8lmXIM  — callout block        (children[0] of root)
          0EgPyHSZi  — Section 1            (children[1] of root)
          3BX-iWc-p  — Section 1.1          (children[0] of Section 1)
          TaN67WqnA  — illustration 1.1     (children[0] of Section 1.1)
          4_GrZ9su6  — text block           (children[0] of illustration 1.1)
          pfkKREU_Y  — image block          (children[0] of 4_GrZ9su6)
          uj8YolCoE  — image block          (children[1] of illustration 1.1)
          Ma5KGUH9O  — AI assistant         (children[1] of Section 1)
          wdMgyBiP9  — Section 2            (children[2] of root)
          drtANJYTg  — Section 2.1          (children[0] of Section 2)
          OaTXPl93p  — illustration 2.1     (children[0] of Section 2.1)
          tWkumkdUE  — text block           (children[0] of illustration 2.1)
          zZG-BfWvs  — image block          (children[1] of illustration 2.1)
          yFUau9Cpg  — Section 2.1.1        (children[1] of Section 2.1)
          bxkcECGwN  — Section 2.1.1.1      (children[0] of Section 2.1.1)
          5f1ahOFdp  — Section 2.2          (children[1] of Section 2)
          40bvW14UU  — Section 3            (children[3] of root)
          JW5PswS6v  — Section 3.1          (children[0] of Section 3)
        """
        tree = article1_vertex_tree()
        expected_uids: list[Uid] = [
            "6olpFWiw1",
            "cNW8lmXIM",
            "0EgPyHSZi",
            "3BX-iWc-p",
            "TaN67WqnA",
            "4_GrZ9su6",
            "pfkKREU_Y",
            "uj8YolCoE",
            "Ma5KGUH9O",
            "wdMgyBiP9",
            "drtANJYTg",
            "OaTXPl93p",
            "tWkumkdUE",
            "zZG-BfWvs",
            "yFUau9Cpg",
            "bxkcECGwN",
            "5f1ahOFdp",
            "40bvW14UU",
            "JW5PswS6v",
        ]
        assert [v.uid for v in VertexTreeDFSIterator(tree)] == expected_uids
