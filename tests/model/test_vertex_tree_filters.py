"""Tests for guffin.model.vertex_tree filter helpers: image_vertices, pdf_vertices, root_vertex."""

from conftest import article1_vertex_tree

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.vertex import ImageVertex, PageVertex, PdfVertex, TextVertex
from guffin.model.vertex_tree import VertexTree, image_vertices, pdf_vertices, root_vertex

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
