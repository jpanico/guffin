"""Tests for the guffin.model.vertex_tree helpers: transcluded_vertices, assignments_for, root_vertex."""

from conftest import article1_vertex_tree

from guffin.model.attribute import Attribute, AttributeAssignment, AttributeInstance
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import BlockEmbedVertex, PageVertex, TextVertex
from guffin.model.vertex_tree import VertexTree, assignments_for, root_vertex, transcluded_vertices

_REF_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1")


def _page(uid: str = "pageuid01") -> PageVertex:
    return PageVertex(uid=uid, title="Page")


def _text(uid: str = "textuid01") -> TextVertex:
    return TextVertex(uid=uid, text="hello")


def _embed(uid: str, target_uid: str) -> BlockEmbedVertex:
    return BlockEmbedVertex(uid=uid, vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid=target_uid))


def _assignment_of(name: str) -> AttributeAssignment:
    return AttributeAssignment(attribute=AttributeInstance(definition=Attribute(name=name), link=_REF_LINK), values=())


# ---------------------------------------------------------------------------
# TestTranscludedVertices
# ---------------------------------------------------------------------------


class TestTranscludedVertices:
    """Tests for transcluded_vertices()."""

    def test_tree_without_embeds_returns_tree_vertices(self) -> None:
        """With no embeds, the result is exactly the tree vertices in insertion order."""
        page = PageVertex(uid="pageuid01", title="Page", children=["textuid01"])
        text = _text("textuid01")
        tree = VertexTree(tree_vertices=[page, text])
        assert transcluded_vertices(tree) == [page, text]

    def test_mentioned_ref_vertex_is_not_included(self) -> None:
        """A referenced vertex that is not embedded renders inline as text and is excluded."""
        page = PageVertex(uid="pageuid01", title="Page", refs=["refuid001"])
        tree = VertexTree(tree_vertices=[page], ref_vertices=[_text("refuid001")])
        assert transcluded_vertices(tree) == [page]

    def test_embed_target_and_subtree_included(self) -> None:
        """An embed pulls in its ref-vertex target together with the target's descendants."""
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        embed = _embed("embeduid1", "refuid001")
        target = TextVertex(uid="refuid001", text="embedded", children=["refuid002"])
        target_child = _text("refuid002")
        tree = VertexTree(tree_vertices=[page, embed], ref_vertices=[target, target_child])
        result = transcluded_vertices(tree)
        assert [v.uid for v in result] == ["pageuid01", "embeduid1", "refuid001", "refuid002"]

    def test_nested_embeds_followed(self) -> None:
        """An embed inside transcluded content is itself followed."""
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        outer = _embed("embeduid1", "refuid001")
        inner = _embed("refuid001", "refuid002")
        innermost = _text("refuid002")
        tree = VertexTree(tree_vertices=[page, outer], ref_vertices=[inner, innermost])
        result = transcluded_vertices(tree)
        assert [v.uid for v in result] == ["pageuid01", "embeduid1", "refuid001", "refuid002"]

    def test_embed_of_in_tree_vertex_is_not_duplicated(self) -> None:
        """An embed whose target already lives in the tree adds nothing (deduplicated by uid)."""
        page = PageVertex(uid="pageuid01", title="Page", children=["textuid01", "embeduid1"])
        text = _text("textuid01")
        embed = _embed("embeduid1", "textuid01")
        tree = VertexTree(tree_vertices=[page, text, embed])
        assert [v.uid for v in transcluded_vertices(tree)] == ["pageuid01", "textuid01", "embeduid1"]

    def test_missing_embed_target_skipped(self) -> None:
        """An embed whose target was not fetched contributes nothing."""
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        embed = _embed("embeduid1", "absentuid")
        tree = VertexTree(tree_vertices=[page, embed])
        assert [v.uid for v in transcluded_vertices(tree)] == ["pageuid01", "embeduid1"]

    def test_embed_cycle_terminates(self) -> None:
        """Mutually embedding blocks terminate, each vertex appearing once."""
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        embed_a = _embed("embeduid1", "refembed1")
        embed_b = _embed("refembed1", "embeduid1")
        tree = VertexTree(tree_vertices=[page, embed_a], ref_vertices=[embed_b])
        assert [v.uid for v in transcluded_vertices(tree)] == ["pageuid01", "embeduid1", "refembed1"]

    def test_article_fixture_has_no_transcluded_content(self) -> None:
        """Test Article 1 has no embeds, so the render-visible set equals its tree vertices."""
        tree = article1_vertex_tree()
        assert transcluded_vertices(tree) == list(tree.tree_vertices)


# ---------------------------------------------------------------------------
# TestAssignmentsFor
# ---------------------------------------------------------------------------


class TestAssignmentsFor:
    """Tests for assignments_for()."""

    def test_pairs_each_matching_assignment_with_its_vertex(self) -> None:
        """Matching assignments across several vertices come back paired with their hosts."""
        page = PageVertex(uid="pageuid01", title="Page", attribute_assignments=[_assignment_of("a")])
        text = TextVertex(uid="textuid01", text="hello", attribute_assignments=[_assignment_of("a")])
        tree = VertexTree(tree_vertices=[page, text])
        result = list(assignments_for(tree, Attribute(name="a")))
        assert [(vertex.uid, assignment.attribute.definition.name) for vertex, assignment in result] == [
            ("pageuid01", "a"),
            ("textuid01", "a"),
        ]

    def test_non_matching_assignments_excluded(self) -> None:
        """Assignments of other attributes do not appear."""
        page = PageVertex(uid="pageuid01", title="Page", attribute_assignments=[_assignment_of("b")])
        tree = VertexTree(tree_vertices=[page])
        assert list(assignments_for(tree, Attribute(name="a"))) == []

    def test_ref_vertices_are_walked(self) -> None:
        """An assignment on a referenced-vertex stub is included."""
        page = PageVertex(uid="pageuid01", title="Page")
        ref = TextVertex(uid="refuid001", text="stub", attribute_assignments=[_assignment_of("a")])
        tree = VertexTree(tree_vertices=[page], ref_vertices=[ref])
        result = list(assignments_for(tree, Attribute(name="a")))
        assert [vertex.uid for vertex, _assignment in result] == ["refuid001"]

    def test_empty_tree_yields_nothing(self) -> None:
        """A tree with no assignments yields an empty iterator."""
        tree = VertexTree(tree_vertices=[_page()])
        assert list(assignments_for(tree, Attribute(name="a"))) == []


# ---------------------------------------------------------------------------
# TestRootVertex
# ---------------------------------------------------------------------------


class TestRootVertex:
    """Tests for root_vertex()."""

    def test_single_vertex_is_root(self) -> None:
        """A tree with one vertex returns that vertex as root."""
        page = _page()
        tree = VertexTree(tree_vertices=[page])
        assert root_vertex(tree) == page

    def test_returns_vertex_with_no_parent(self) -> None:
        """Root is the vertex whose uid does not appear in any children list."""
        child = _text(uid="textuid01")
        tree = VertexTree(tree_vertices=[PageVertex(uid="pageuid01", title="Page", children=["textuid01"]), child])
        assert root_vertex(tree).uid == "pageuid01"

    def test_non_root_is_not_returned(self) -> None:
        """A child vertex is never returned as root."""
        page = PageVertex(uid="pageuid01", title="Page", children=["textuid01"])
        child = _text(uid="textuid01")
        tree = VertexTree(tree_vertices=[page, child])
        assert root_vertex(tree).uid != "textuid01"

    def test_article_fixture_root_is_page_vertex(self) -> None:
        """Test Article 1 fixture root is a PageVertex."""
        assert isinstance(root_vertex(article1_vertex_tree()), PageVertex)
