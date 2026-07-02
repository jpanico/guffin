"""Unit tests for guffin.render.image_fetch."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Final

import pytest
from conftest import article1_vertex_tree
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.vertex import ImageVertex, PageVertex, TextVertex
from guffin.model.vertex_tree import VertexTree
from guffin.render.image_fetch import ImageRef, fetch_and_enrich_images, fetch_images
from guffin.roam.asset import RoamAsset, RoamImageAsset
from guffin.roam.local_api import ApiEndpoint, ApiEndpointURL
from guffin.roam.primitives import Uid

_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")
_ENDPOINT: Final[ApiEndpoint] = ApiEndpoint(
    url=ApiEndpointURL(local_api_port=3333, graph_name="test-graph"),
    bearer_token="test-token",
)
_LAST_MODIFIED: Final[datetime] = datetime(2024, 6, 1, 12, 0, 0)


def _image_vertex(uid: str) -> ImageVertex:
    """Build a minimal ImageVertex pointing at _IMAGE_URL."""
    return ImageVertex(
        uid=uid,
        source=_IMAGE_URL,
        media_type=MediaType.JPEG,
        scaled_image_size=ImageSize(),
    )


class TestFetchImages:
    """Tests for fetch_images() — fetch_and_cache_asset is mocked; only tmp_path writes touch disk."""

    def test_image_asset_yields_imageref_with_path_size_and_written_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A RoamImageAsset produces an ImageRef whose path holds the bytes and whose size is the asset's."""
        contents: Final[bytes] = b"\xff\xd8\xff\xe0jpegbody"
        asset: Final[RoamImageAsset] = RoamImageAsset(
            file_name="photo.jpg",
            last_modified=_LAST_MODIFIED,
            media_type=MediaType.JPEG,
            contents=contents,
            image_size=ImageSize(width=640, height=480),
        )

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return asset

        monkeypatch.setattr("guffin.render.image_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        result: Final[dict[Uid, ImageRef]] = fetch_images(tree, _ENDPOINT, tmp_path)

        assert list(result) == ["img00001a"]
        ref: Final[ImageRef] = result["img00001a"]
        assert ref.uid == "img00001a"
        assert ref.path == tmp_path / "photo.jpg"
        assert ref.path.read_bytes() == contents
        assert ref.size == ImageSize(width=640, height=480)

    def test_base_roamasset_yields_empty_size(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A base RoamAsset (not a RoamImageAsset) yields an empty ImageSize."""
        asset: Final[RoamAsset] = RoamAsset(
            file_name="photo.jpg",
            last_modified=_LAST_MODIFIED,
            media_type=MediaType.JPEG,
            contents=b"bytes",
        )

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return asset

        monkeypatch.setattr("guffin.render.image_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        result: Final[dict[Uid, ImageRef]] = fetch_images(tree, _ENDPOINT, tmp_path)

        assert result["img00001a"].size == ImageSize()

    def test_fetch_failure_skips_vertex_and_logs_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When fetch_and_cache_asset raises, the vertex is absent and a warning is logged."""

        def _raising(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            raise RuntimeError("network down")

        monkeypatch.setattr("guffin.render.image_fetch.fetch_and_cache_asset", _raising)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        with caplog.at_level(logging.WARNING, logger="guffin.render.image_fetch"):
            result: Final[dict[Uid, ImageRef]] = fetch_images(tree, _ENDPOINT, tmp_path)

        assert result == {}
        assert any("Failed to fetch image" in r.message for r in caplog.records)

    def test_non_image_vertices_are_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only ImageVertex entries are fetched; page and text vertices are ignored."""

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return RoamImageAsset(
                file_name="photo.jpg",
                last_modified=_LAST_MODIFIED,
                media_type=MediaType.JPEG,
                contents=b"body",
                image_size=ImageSize(width=1, height=1),
            )

        monkeypatch.setattr("guffin.render.image_fetch.fetch_and_cache_asset", _fake)

        page: Final[PageVertex] = PageVertex(uid="page00001", title="P", children=["img00001a"])
        text: Final[TextVertex] = TextVertex(uid="txt00001a", text="hello")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[page, text, _image_vertex("img00001a")])
        result: Final[dict[Uid, ImageRef]] = fetch_images(tree, _ENDPOINT, tmp_path)

        assert list(result) == ["img00001a"]


class TestFetchAndEnrichImages:
    """Tests for fetch_and_enrich_images() — fetch_images plus tree enrichment."""

    def test_returns_enriched_tree_and_refs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The returned tree carries original_image_size from the fetched ref, alongside the refs map."""
        asset: Final[RoamImageAsset] = RoamImageAsset(
            file_name="photo.jpg",
            last_modified=_LAST_MODIFIED,
            media_type=MediaType.JPEG,
            contents=b"\xff\xd8\xff\xe0body",
            image_size=ImageSize(width=800, height=600),
        )

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return asset

        monkeypatch.setattr("guffin.render.image_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        fetched: Final[tuple[VertexTree, dict[Uid, ImageRef]]] = fetch_and_enrich_images(tree, _ENDPOINT, tmp_path)
        enriched_tree: Final[VertexTree] = fetched[0]
        image_refs: Final[dict[Uid, ImageRef]] = fetched[1]

        assert list(image_refs) == ["img00001a"]
        assert image_refs["img00001a"].size == ImageSize(width=800, height=600)
        enriched_image: Final[ImageVertex] = next(v for v in enriched_tree.tree_vertices if isinstance(v, ImageVertex))
        assert enriched_image.original_image_size == ImageSize(width=800, height=600)

    def test_input_tree_left_unmodified(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Enrichment returns a copy; the input tree's ImageVertex is left unchanged."""

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return RoamImageAsset(
                file_name="photo.jpg",
                last_modified=_LAST_MODIFIED,
                media_type=MediaType.JPEG,
                contents=b"body",
                image_size=ImageSize(width=10, height=20),
            )

        monkeypatch.setattr("guffin.render.image_fetch.fetch_and_cache_asset", _fake)

        original_image: Final[ImageVertex] = _image_vertex("img00001a")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[original_image])
        fetch_and_enrich_images(tree, _ENDPOINT, tmp_path)

        assert original_image.original_image_size is None

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_enriches_test_article_1_images(
        self, live_api_endpoint: ApiEndpoint, live_cache_dir: Path, tmp_path: Path
    ) -> None:
        """Fetching the [[Test Article]] 1 images populates every ImageVertex's original_image_size (500x477)."""
        tree: Final[VertexTree] = article1_vertex_tree()
        fetched: Final[tuple[VertexTree, dict[Uid, ImageRef]]] = fetch_and_enrich_images(
            tree, live_api_endpoint, tmp_path, live_cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        images: Final[list[ImageVertex]] = [v for v in enriched_tree.tree_vertices if isinstance(v, ImageVertex)]
        assert images
        for image in images:
            assert image.original_image_size == ImageSize(width=500, height=477)
