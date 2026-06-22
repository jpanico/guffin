"""Tests for graph module utility functions."""

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.vertex import ImageVertex, PageVertex, TextVertex
from guffin.model.vertex_tree import VertexTree, image_urls, image_vertices, root_vertex

from conftest import article1_vertex_tree

_URL_A = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/imgs%2Fa.jpeg?alt=media&token=aaa"
_URL_B = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/imgs%2Fb.jpeg?alt=media&token=bbb"

_ARTICLE_IMAGE_URL_0 = (
    "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com"
    "/o/imgs%2Fapp%2FSCFH%2F_otAwc2B9g.jpeg.enc?alt=media&token=25c3ac2a-f62e-462e-99b4-99b337a476c0"
)
_ARTICLE_IMAGE_URL_1 = (
    "https://firebasestorage.googleapis.com/v0/b/firescript-577a2.appspot.com"
    "/o/imgs%2Fapp%2FSCFH%2FaOC1FnrcwK.jpeg.enc?alt=media&token=c6e7a3c2-c682-4ae9-a3ee-8e6c388cd05a"
)


def _page(uid: str = "pageuid01") -> PageVertex:
    return PageVertex(uid=uid, title="Page")


def _image(uid: str = "imguid001", url: str = _URL_A) -> ImageVertex:
    return ImageVertex(uid=uid, source=url, media_type=MediaType.JPEG, scaled_image_size=ImageSize())  # type: ignore[arg-type]


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

    def test_article_fixture_has_one_image_vertex(self) -> None:
        """Test Article 1 fixture contains exactly two image vertices."""
        result = image_vertices(article1_vertex_tree())
        assert len(result) == 2
        assert all(isinstance(v, ImageVertex) for v in result)


# ---------------------------------------------------------------------------
# TestImageUrls
# ---------------------------------------------------------------------------


class TestImageUrls:
    """Tests for image_urls()."""

    def test_returns_source_urls(self) -> None:
        """Returns the source URL of each image vertex."""
        tree = VertexTree(tree_vertices=[_page(), _image("imguid001", _URL_A), _image("imguid002", _URL_B)])
        result = image_urls(tree)
        assert [str(u) for u in result] == [_URL_A, _URL_B]

    def test_returns_empty_list_when_no_images(self) -> None:
        """Tree with no images returns an empty list."""
        tree = VertexTree(tree_vertices=[_page()])
        assert image_urls(tree) == []

    def test_article_fixture_image_url(self) -> None:
        """Test Article 1 fixture image URLs match the known fixture values."""
        urls = image_urls(article1_vertex_tree())
        assert len(urls) == 2
        assert str(urls[0]) == _ARTICLE_IMAGE_URL_0
        assert str(urls[1]) == _ARTICLE_IMAGE_URL_1


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
