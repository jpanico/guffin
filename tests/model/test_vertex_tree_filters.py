"""Tests for the guffin.model.vertex_tree helpers: image_vertices, pdf_vertices, transcluded_vertices, root_vertex."""

from conftest import article1_vertex_tree

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import BlockEmbedVertex, ImageVertex, PageVertex, PdfVertex, TextVertex
from guffin.model.vertex_tree import VertexTree, image_vertices, pdf_vertices, root_vertex, transcluded_vertices

_URL_A = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/imgs%2Fa.jpeg?alt=media&token=aaa"
_URL_B = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/imgs%2Fb.jpeg?alt=media&token=bbb"
_PDF_URL_A = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fa.pdf?alt=media&token=aaa"
_PDF_URL_B = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fb.pdf?alt=media&token=bbb"


def _page(uid: str = "pageuid01") -> PageVertex:
    return PageVertex(uid=uid, title="Page")


def _image(uid: str = "imguid001", url: str = _URL_A) -> ImageVertex:
    return ImageVertex(uid=uid, source=url, media_type=MediaType.JPEG, scaled_image_size=ImageSize())  # type: ignore[arg-type]


def _pdf(uid: str = "pdfuid001", url: str = _PDF_URL_A) -> PdfVertex:
    return PdfVertex(uid=uid, source=url)  # type: ignore[arg-type]


def _text(uid: str = "textuid01") -> TextVertex:
    return TextVertex(uid=uid, text="hello")


def _embed(uid: str, target_uid: str) -> BlockEmbedVertex:
    return BlockEmbedVertex(uid=uid, vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid=target_uid))


# ---------------------------------------------------------------------------
# TestImageVertices
# ---------------------------------------------------------------------------


class TestImageVertices:
    """Tests for image_vertices()."""

    def test_returns_only_image_vertices(self) -> None:
        """Mixed tree — only the ImageVertex is returned."""
        tree = VertexTree(tree_vertices=[_page(), _image("imguid001")])
        result = image_vertices(tree)
        assert len(result) == 1
        assert result[0].uid == "imguid001"

    def test_returns_empty_list_when_no_images(self) -> None:
        """Tree with no images returns an empty list."""
        tree = VertexTree(tree_vertices=[_page()])
        assert image_vertices(tree) == []

    def test_preserves_insertion_order(self) -> None:
        """Multiple image vertices are returned in insertion order."""
        tree = VertexTree(tree_vertices=[_page(), _image("imguid001", _URL_A), _image("imguid002", _URL_B)])
        result = image_vertices(tree)
        assert [v.uid for v in result] == ["imguid001", "imguid002"]

    def test_article_fixture_image_vertex_count(self) -> None:
        """Test Article 1 fixture contains exactly three image vertices."""
        result = image_vertices(article1_vertex_tree())
        assert len(result) == 3
        assert all(isinstance(v, ImageVertex) for v in result)


# ---------------------------------------------------------------------------
# TestPdfVertices
# ---------------------------------------------------------------------------


class TestPdfVertices:
    """Tests for pdf_vertices()."""

    def test_returns_only_pdf_vertices(self) -> None:
        """Mixed tree — only the PdfVertex is returned."""
        tree = VertexTree(tree_vertices=[_page(), _image("imguid001"), _pdf("pdfuid001")])
        result = pdf_vertices(tree)
        assert len(result) == 1
        assert result[0].uid == "pdfuid001"

    def test_returns_empty_list_when_no_pdfs(self) -> None:
        """Tree with no PDFs returns an empty list."""
        tree = VertexTree(tree_vertices=[_page(), _image("imguid001")])
        assert pdf_vertices(tree) == []

    def test_preserves_insertion_order(self) -> None:
        """Multiple PDF vertices are returned in insertion order."""
        tree = VertexTree(tree_vertices=[_page(), _pdf("pdfuid001", _PDF_URL_A), _pdf("pdfuid002", _PDF_URL_B)])
        result = pdf_vertices(tree)
        assert [v.uid for v in result] == ["pdfuid001", "pdfuid002"]

    def test_article_fixture_pdf_vertex_count(self) -> None:
        """Test Article 1 fixture contains exactly one PDF vertex."""
        result = pdf_vertices(article1_vertex_tree())
        assert [v.uid for v in result] == ["pTvGGeTlB"]
        assert all(isinstance(v, PdfVertex) for v in result)


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
