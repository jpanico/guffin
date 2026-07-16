"""Tests for the guffin.model.vertex_tree helpers.

Covers transcluded_vertices, assignments_for, standalone_link_target_of_text,
standalone_link_target, visible_asset_vertices, and root_vertex.
"""

from conftest import article1_vertex_tree
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.model.attribute import Attribute, AttributeInstance
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.vertex import (
    BlockEmbedVertex,
    HeadingVertex,
    ImageVertex,
    PageEmbedVertex,
    PageVertex,
    TableVertex,
    TextVertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import (
    VertexTree,
    assignments_for,
    root_vertex,
    standalone_link_target,
    standalone_link_target_of_text,
    transcluded_vertices,
    visible_asset_vertices,
)

_REF_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1")


def _page(uid: str = "pageuid01") -> PageVertex:
    return PageVertex(uid=uid, title="Page")


def _text(uid: str = "textuid01") -> TextVertex:
    return TextVertex(uid=uid, text="hello")


def _embed(uid: str, target_uid: str) -> BlockEmbedVertex:
    return BlockEmbedVertex(uid=uid, vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid=target_uid))


def _page_embed(uid: str, target_uid: str) -> PageEmbedVertex:
    return PageEmbedVertex(uid=uid, vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid=target_uid))


def _assignment_of(name: str) -> AttributeAssignment:
    return AttributeAssignment(attribute=AttributeInstance(definition=Attribute(name=name), link=_REF_LINK), values=())


def _image(uid: str = "imguid001") -> ImageVertex:
    return ImageVertex(
        uid=uid,
        source=HttpUrl("https://example.com/imgs/photo.jpeg"),
        media_type=MediaType.JPEG,
        scaled_image_size=ImageSize(),
    )


def _standalone_ref(target_uid: str) -> str:
    """A text that is a standalone reference-form vertex link to *target_uid*."""
    return f"[display]({vertex_link_url(target_uid, VertexLinkKind.REFERENCE)})"


def _sole_ref_text(uid: str, target_uid: str) -> TextVertex:
    """A text vertex whose entire content is one reference-form vertex link to *target_uid*."""
    return TextVertex(uid=uid, text=_standalone_ref(target_uid))


def _table(uid: str, cells: list[list[str]]) -> TableVertex:
    """A table vertex over the given cell-text grid, all-default style."""
    return TableVertex(uid=uid, table=Table(rows=cells), table_style=TableStyle())


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

    def test_page_embed_target_and_subtree_included(self) -> None:
        """A page embed pulls in its target page together with the page's descendants."""
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        embed = _page_embed("embeduid1", "refpage01")
        target = PageVertex(uid="refpage01", title="Embedded Page", children=["refuid002"])
        target_child = _text("refuid002")
        tree = VertexTree(tree_vertices=[page, embed], ref_vertices=[target, target_child])
        result = transcluded_vertices(tree)
        assert [v.uid for v in result] == ["pageuid01", "embeduid1", "refpage01", "refuid002"]

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

    def test_mention_only_ref_vertices_are_excluded(self) -> None:
        """An assignment on a merely-mentioned ref vertex (not transcluded) is excluded."""
        page = PageVertex(uid="pageuid01", title="Page", refs=["refuid001"])
        ref = TextVertex(uid="refuid001", text="stub", attribute_assignments=[_assignment_of("a")])
        tree = VertexTree(tree_vertices=[page], ref_vertices=[ref])
        assert list(assignments_for(tree, Attribute(name="a"))) == []

    def test_embed_transcluded_ref_vertices_are_walked(self) -> None:
        """An assignment on a ref vertex reached through an embed (part of the document) is included."""
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        embed = _embed("embeduid1", "refuid001")
        target = TextVertex(uid="refuid001", text="embedded", attribute_assignments=[_assignment_of("a")])
        tree = VertexTree(tree_vertices=[page, embed], ref_vertices=[target])
        result = list(assignments_for(tree, Attribute(name="a")))
        assert [vertex.uid for vertex, _assignment in result] == ["refuid001"]

    def test_empty_tree_yields_nothing(self) -> None:
        """A tree with no assignments yields an empty iterator."""
        tree = VertexTree(tree_vertices=[_page()])
        assert list(assignments_for(tree, Attribute(name="a"))) == []


# ---------------------------------------------------------------------------
# TestStandaloneLinkTarget
# ---------------------------------------------------------------------------


class TestStandaloneLinkTarget:
    """Tests for standalone_link_target()."""

    def test_sole_reference_resolves_to_target(self) -> None:
        """A text vertex whose whole content is one reference link resolves to the destination."""
        target = _image("imguid001")
        referrer = _sole_ref_text("textuid01", "imguid001")
        tree = VertexTree(tree_vertices=[referrer], ref_vertices=[target])
        assert standalone_link_target(referrer, tree) == target

    def test_heading_sole_reference_resolves_to_target(self) -> None:
        """A heading vertex whose whole text is one reference link resolves to the destination."""
        target = _text("textuid02")
        heading = HeadingVertex(
            uid="headuid01",
            text=f"[display]({vertex_link_url('textuid02', VertexLinkKind.REFERENCE)})",
            heading_level=1,
        )
        tree = VertexTree(tree_vertices=[heading], ref_vertices=[target])
        assert standalone_link_target(heading, tree) == target

    def test_link_amid_text_is_none(self) -> None:
        """A reference mixed with surrounding text is not standalone."""
        referrer = TextVertex(
            uid="textuid01", text=f"see [display]({vertex_link_url('imguid001', VertexLinkKind.REFERENCE)})"
        )
        tree = VertexTree(tree_vertices=[referrer], ref_vertices=[_image("imguid001")])
        assert standalone_link_target(referrer, tree) is None

    def test_non_text_bearing_vertex_is_none(self) -> None:
        """A vertex without a text field (e.g. an image) has no standalone link."""
        image = _image("imguid001")
        tree = VertexTree(tree_vertices=[image])
        assert standalone_link_target(image, tree) is None

    def test_missing_destination_is_none(self) -> None:
        """A standalone link to a UID absent from the tree resolves to None."""
        referrer = _sole_ref_text("textuid01", "absentuid")
        tree = VertexTree(tree_vertices=[referrer])
        assert standalone_link_target(referrer, tree) is None


# ---------------------------------------------------------------------------
# TestStandaloneLinkTargetOfText
# ---------------------------------------------------------------------------


class TestStandaloneLinkTargetOfText:
    """Tests for standalone_link_target_of_text()."""

    def test_standalone_reference_resolves_to_target(self) -> None:
        """A text that is one reference link resolves to the destination."""
        target = _image("imguid001")
        tree = VertexTree(tree_vertices=[_page()], ref_vertices=[target])
        assert standalone_link_target_of_text(_standalone_ref("imguid001"), tree) == target

    def test_standalone_embed_resolves_to_target(self) -> None:
        """A text that is one embed link resolves to the destination (kind-agnostic)."""
        target = _image("imguid001")
        tree = VertexTree(tree_vertices=[_page()], ref_vertices=[target])
        text = f"[display]({vertex_link_url('imguid001', VertexLinkKind.EMBED)})"
        assert standalone_link_target_of_text(text, tree) == target

    def test_link_amid_text_is_none(self) -> None:
        """A reference mixed with surrounding text is not standalone."""
        tree = VertexTree(tree_vertices=[_page()], ref_vertices=[_image("imguid001")])
        assert standalone_link_target_of_text(f"see {_standalone_ref('imguid001')}", tree) is None

    def test_plain_text_is_none(self) -> None:
        """A text with no vertex link resolves to None."""
        tree = VertexTree(tree_vertices=[_page()])
        assert standalone_link_target_of_text("just some text", tree) is None

    def test_missing_destination_is_none(self) -> None:
        """A standalone link to a UID absent from the tree resolves to None."""
        tree = VertexTree(tree_vertices=[_page()])
        assert standalone_link_target_of_text(_standalone_ref("absentuid"), tree) is None


# ---------------------------------------------------------------------------
# TestVisibleAssetVertices
# ---------------------------------------------------------------------------


class TestVisibleAssetVertices:
    """Tests for visible_asset_vertices()."""

    def test_in_tree_asset_included(self) -> None:
        """An asset vertex in the tree is displayed."""
        image = _image("imguid001")
        page = PageVertex(uid="pageuid01", title="Page", children=["imguid001"])
        tree = VertexTree(tree_vertices=[page, image])
        assert visible_asset_vertices(tree) == [image]

    def test_mentioned_ref_asset_excluded(self) -> None:
        """A ref-side asset merely linked inline amid text renders as a link and is not displayed."""
        referrer = TextVertex(
            uid="textuid01", text=f"see [photo]({vertex_link_url('imguid001', VertexLinkKind.REFERENCE)}) here"
        )
        page = PageVertex(uid="pageuid01", title="Page", children=["textuid01"])
        tree = VertexTree(tree_vertices=[page, referrer], ref_vertices=[_image("imguid001")])
        assert visible_asset_vertices(tree) == []

    def test_unreferenced_ref_asset_excluded(self) -> None:
        """A ref-side asset nothing visible points at (e.g. deep in a mentioned page) is not displayed."""
        page = PageVertex(uid="pageuid01", title="Page", refs=["imguid001"])
        tree = VertexTree(tree_vertices=[page], ref_vertices=[_image("imguid001")])
        assert visible_asset_vertices(tree) == []

    def test_sole_ref_target_asset_included(self) -> None:
        """A ref-side asset targeted by a vertex that is a standalone reference to it is displayed."""
        image = _image("imguid001")
        referrer = _sole_ref_text("textuid01", "imguid001")
        page = PageVertex(uid="pageuid01", title="Page", children=["textuid01"])
        tree = VertexTree(tree_vertices=[page, referrer], ref_vertices=[image])
        assert visible_asset_vertices(tree) == [image]

    def test_standalone_cell_ref_target_asset_included(self) -> None:
        """A ref-side asset targeted by a table cell that is a standalone reference to it is displayed."""
        image = _image("imguid001")
        table = _table("tableuid1", [[_standalone_ref("imguid001"), "plain cell"]])
        page = PageVertex(uid="pageuid01", title="Page", children=["tableuid1"])
        tree = VertexTree(tree_vertices=[page, table], ref_vertices=[image])
        assert visible_asset_vertices(tree) == [image]

    def test_mentioned_cell_asset_excluded(self) -> None:
        """An asset linked amid other text inside a cell is a mention, not a display."""
        table = _table("tableuid1", [[f"see {_standalone_ref('imguid001')}"]])
        page = PageVertex(uid="pageuid01", title="Page", children=["tableuid1"])
        tree = VertexTree(tree_vertices=[page, table], ref_vertices=[_image("imguid001")])
        assert visible_asset_vertices(tree) == []

    def test_cell_asset_deduplicated_with_block_display(self) -> None:
        """An asset displayed both as a block and from a cell appears once."""
        image = _image("imguid001")
        table = _table("tableuid1", [[_standalone_ref("imguid001")]])
        page = PageVertex(uid="pageuid01", title="Page", children=["imguid001", "tableuid1"])
        tree = VertexTree(tree_vertices=[page, image, table])
        assert visible_asset_vertices(tree) == [image]

    def test_embed_transcluded_asset_included(self) -> None:
        """A ref-side asset inside an embed-transcluded subtree is displayed."""
        image = _image("imguid001")
        embed = _embed("embeduid1", "refuid001")
        target = TextVertex(uid="refuid001", text="host", children=["imguid001"])
        page = PageVertex(uid="pageuid01", title="Page", children=["embeduid1"])
        tree = VertexTree(tree_vertices=[page, embed], ref_vertices=[target, image])
        assert visible_asset_vertices(tree) == [image]

    def test_asset_referenced_twice_deduplicated(self) -> None:
        """An asset both in the tree and sole-referenced appears once."""
        image = _image("imguid001")
        referrer = _sole_ref_text("textuid01", "imguid001")
        page = PageVertex(uid="pageuid01", title="Page", children=["imguid001", "textuid01"])
        tree = VertexTree(tree_vertices=[page, image, referrer])
        assert visible_asset_vertices(tree) == [image]

    def test_no_assets_yields_empty(self) -> None:
        """A tree without asset vertices yields an empty list."""
        tree = VertexTree(tree_vertices=[_page()])
        assert visible_asset_vertices(tree) == []


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
