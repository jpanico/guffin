"""Tests for guffin.vertex_tree — map_vertices and related helpers."""

import logging
from typing import Final

import pytest
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.vertex import ImageVertex, TextVertex, Vertex
from guffin.model.vertex_tree import VertexTree, enrich_image_original_sizes, map_vertices

logger = logging.getLogger(__name__)


def _make_text_tree(uid_text_pairs: list[tuple[str, str]]) -> VertexTree:
    return VertexTree(tree_vertices=[TextVertex(uid=uid, text=text) for uid, text in uid_text_pairs])


_IMAGE_SOURCE: Final[HttpUrl] = HttpUrl("https://example.com/img.jpg")


def _make_image_vertex(uid: str) -> ImageVertex:
    return ImageVertex(
        uid=uid,
        source=_IMAGE_SOURCE,
        media_type=MediaType.JPEG,
        scaled_image_size=ImageSize(width=100, height=100),
    )


class TestMapVertices:
    """Tests for map_vertices()."""

    def test_returns_new_tree_instance(self) -> None:
        """Identity fn produces a distinct VertexTree object, not the original."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello")])
        result: Final[VertexTree] = map_vertices(tree, lambda v: v)
        assert result is not tree

    def test_fn_applied_to_all_vertices(self) -> None:
        """Fn is invoked exactly once for every vertex in the tree."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])
        seen_uids: Final[list[str]] = []

        def _record(vtx: Vertex) -> Vertex:
            seen_uids.append(vtx.uid)
            return vtx

        map_vertices(tree, _record)
        assert sorted(seen_uids) == ["aaaaaaaaa", "bbbbbbbbb"]

    def test_fn_transforms_vertex_fields(self) -> None:
        """Fn's return values appear verbatim in the result tree."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])

        def _upcase(vtx: Vertex) -> Vertex:
            if isinstance(vtx, TextVertex):
                return vtx.model_copy(update={"text": vtx.text.upper()})
            return vtx

        result: Final[VertexTree] = map_vertices(tree, _upcase)
        texts: Final[list[str]] = [vtx.text for vtx in result.tree_vertices if isinstance(vtx, TextVertex)]
        assert texts == ["HELLO", "WORLD"]

    def test_unmatched_vertices_pass_through_unchanged(self) -> None:
        """Vertices not modified by fn are returned as-is."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello"), ("bbbbbbbbb", "world")])

        def _transform_first_only(vtx: Vertex) -> Vertex:
            if isinstance(vtx, TextVertex) and vtx.uid == "aaaaaaaaa":
                return vtx.model_copy(update={"text": "changed"})
            return vtx

        result: Final[VertexTree] = map_vertices(tree, _transform_first_only)
        texts: Final[list[str]] = [vtx.text for vtx in result.tree_vertices if isinstance(vtx, TextVertex)]
        assert texts == ["changed", "world"]


class TestEnrichImageOriginalSizes:
    """Tests for enrich_image_original_sizes()."""

    def test_matched_uid_sets_original_image_size(self) -> None:
        """ImageVertex whose UID is in sizes receives original_image_size."""
        vertex: Final[ImageVertex] = _make_image_vertex("img000001")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[vertex])
        size: Final[ImageSize] = ImageSize(width=320, height=240)
        result: Final[VertexTree] = enrich_image_original_sizes(tree, {"img000001": size})
        enriched: Final[ImageVertex] = next(v for v in result.tree_vertices if isinstance(v, ImageVertex))
        assert enriched.original_image_size == size

    def test_unmatched_image_vertex_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """ImageVertex absent from sizes map logs a WARNING and keeps original_image_size as None."""
        vertex: Final[ImageVertex] = _make_image_vertex("img000002")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[vertex])
        with caplog.at_level(logging.WARNING, logger="guffin.vertex_tree"):
            result: Final[VertexTree] = enrich_image_original_sizes(tree, {})
        unmatched: Final[ImageVertex] = next(v for v in result.tree_vertices if isinstance(v, ImageVertex))
        assert unmatched.original_image_size is None
        assert any("absent from sizes map" in r.message for r in caplog.records)

    def test_non_image_vertices_pass_through(self) -> None:
        """TextVertex is returned unchanged regardless of the sizes map."""
        tree: Final[VertexTree] = _make_text_tree([("aaaaaaaaa", "hello")])
        result: Final[VertexTree] = enrich_image_original_sizes(tree, {})
        texts: Final[list[str]] = [v.text for v in result.tree_vertices if isinstance(v, TextVertex)]
        assert texts == ["hello"]

    def test_mixed_tree_partial_match(self) -> None:
        """Matched image gets size; unmatched image stays None; text vertex passes through unchanged."""
        img_matched: Final[ImageVertex] = _make_image_vertex("img000003")
        img_unmatched: Final[ImageVertex] = _make_image_vertex("img000004")
        text: Final[TextVertex] = TextVertex(uid="aaaaaaaaa", text="hello")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[img_matched, img_unmatched, text])
        size: Final[ImageSize] = ImageSize(width=800, height=600)
        result: Final[VertexTree] = enrich_image_original_sizes(tree, {"img000003": size})
        result_by_uid: Final[dict[str, Vertex]] = {v.uid: v for v in result.tree_vertices}
        matched_result: Final[Vertex] = result_by_uid["img000003"]
        unmatched_result: Final[Vertex] = result_by_uid["img000004"]
        assert isinstance(matched_result, ImageVertex)
        assert isinstance(unmatched_result, ImageVertex)
        assert matched_result.original_image_size == size
        assert unmatched_result.original_image_size is None
        assert isinstance(result_by_uid["aaaaaaaaa"], TextVertex)
