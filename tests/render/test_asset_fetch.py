"""Unit tests for guffin.render.asset_fetch."""

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
from guffin.model.vertex import ImageVertex, PageVertex, PdfVertex, TextVertex
from guffin.model.vertex_tree import VertexTree
from guffin.render.asset_fetch import AssetRef, fetch_and_enrich_assets, fetch_assets
from guffin.roam.asset import RoamAsset, RoamImageAsset
from guffin.roam.local_api import ApiEndpoint, ApiEndpointURL
from guffin.roam.primitives import Uid

_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")
_PDF_URL: HttpUrl = HttpUrl("https://example.com/pdfs/paper.pdf")
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


def _image_asset(size: ImageSize = ImageSize(width=640, height=480), contents: bytes = b"body") -> RoamImageAsset:
    """Build a RoamImageAsset named photo.jpg with the given pixel size and contents."""
    return RoamImageAsset(
        file_name="photo.jpg",
        last_modified=_LAST_MODIFIED,
        media_type=MediaType.JPEG,
        contents=contents,
        image_size=size,
    )


def _pdf_asset(contents: bytes = b"%PDF-1.7 body") -> RoamAsset:
    """Build a base (non-image) RoamAsset named paper.pdf with the given contents."""
    return RoamAsset(
        file_name="paper.pdf",
        last_modified=_LAST_MODIFIED,
        media_type=MediaType.PDF,
        contents=contents,
    )


class TestFetchAssets:
    """Tests for fetch_assets() — fetch_and_cache_asset is mocked; only tmp_path writes touch disk."""

    def test_image_asset_yields_ref_with_path_size_and_written_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A RoamImageAsset produces an AssetRef whose path holds the bytes and whose size is the asset's."""
        contents: Final[bytes] = b"\xff\xd8\xff\xe0jpegbody"
        asset: Final[RoamImageAsset] = _image_asset(contents=contents)

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return asset

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        result: Final[dict[Uid, AssetRef]] = fetch_assets(tree, _ENDPOINT, tmp_path)

        assert list(result) == ["img00001a"]
        ref: Final[AssetRef] = result["img00001a"]
        assert ref.uid == "img00001a"
        assert ref.path == tmp_path / "photo.jpg"
        assert ref.path.read_bytes() == contents
        assert ref.size == ImageSize(width=640, height=480)

    def test_pdf_asset_yields_ref_with_written_bytes_and_no_size(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-image RoamAsset produces an AssetRef holding the bytes, with size None."""
        contents: Final[bytes] = b"%PDF-1.7 body"
        asset: Final[RoamAsset] = _pdf_asset(contents=contents)

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return asset

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[PdfVertex(uid="pdf00001a", source=_PDF_URL)])
        result: Final[dict[Uid, AssetRef]] = fetch_assets(tree, _ENDPOINT, tmp_path)

        assert list(result) == ["pdf00001a"]
        ref: Final[AssetRef] = result["pdf00001a"]
        assert ref.path == tmp_path / "paper.pdf"
        assert ref.path.read_bytes() == contents
        assert ref.size is None

    def test_image_and_pdf_vertices_fetched_together(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """One pass fetches both asset kinds, keyed by their vertex UIDs."""

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return _image_asset() if firebase_url == _IMAGE_URL else _pdf_asset()

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(
            tree_vertices=[_image_vertex("img00001a"), PdfVertex(uid="pdf00001a", source=_PDF_URL)]
        )
        result: Final[dict[Uid, AssetRef]] = fetch_assets(tree, _ENDPOINT, tmp_path)

        assert sorted(result) == ["img00001a", "pdf00001a"]
        assert result["img00001a"].size == ImageSize(width=640, height=480)
        assert result["pdf00001a"].size is None

    def test_fetch_failure_skips_vertex_and_logs_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When fetch_and_cache_asset raises, the vertex is absent and a warning is logged."""

        def _raising(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            raise RuntimeError("network down")

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _raising)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        with caplog.at_level(logging.WARNING, logger="guffin.render.asset_fetch"):
            result: Final[dict[Uid, AssetRef]] = fetch_assets(tree, _ENDPOINT, tmp_path)

        assert result == {}
        assert any("Failed to fetch asset" in r.message for r in caplog.records)

    def test_non_asset_vertices_are_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only ImageVertex and PdfVertex entries are fetched; page and text vertices are ignored."""

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return _image_asset(size=ImageSize(width=1, height=1))

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        page: Final[PageVertex] = PageVertex(uid="page00001", title="P", children=["img00001a"])
        text: Final[TextVertex] = TextVertex(uid="txt00001a", text="hello")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[page, text, _image_vertex("img00001a")])
        result: Final[dict[Uid, AssetRef]] = fetch_assets(tree, _ENDPOINT, tmp_path)

        assert list(result) == ["img00001a"]


class TestFetchAndEnrichAssets:
    """Tests for fetch_and_enrich_assets() — fetch_assets plus tree enrichment."""

    def test_returns_enriched_tree_and_refs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The returned tree carries original_image_size from the fetched ref, alongside the refs map."""
        asset: Final[RoamImageAsset] = _image_asset(size=ImageSize(width=800, height=600))

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return asset

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[_image_vertex("img00001a")])
        fetched: Final[tuple[VertexTree, dict[Uid, AssetRef]]] = fetch_and_enrich_assets(tree, _ENDPOINT, tmp_path)
        enriched_tree: Final[VertexTree] = fetched[0]
        asset_refs: Final[dict[Uid, AssetRef]] = fetched[1]

        assert list(asset_refs) == ["img00001a"]
        assert asset_refs["img00001a"].size == ImageSize(width=800, height=600)
        enriched_image: Final[ImageVertex] = next(v for v in enriched_tree.tree_vertices if isinstance(v, ImageVertex))
        assert enriched_image.original_image_size == ImageSize(width=800, height=600)

    def test_pdf_assets_do_not_participate_in_enrichment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A fetched PDF (size None) is returned in the refs map but contributes no image size."""

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return _pdf_asset()

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        tree: Final[VertexTree] = VertexTree(tree_vertices=[PdfVertex(uid="pdf00001a", source=_PDF_URL)])
        fetched: Final[tuple[VertexTree, dict[Uid, AssetRef]]] = fetch_and_enrich_assets(tree, _ENDPOINT, tmp_path)

        assert list(fetched[1]) == ["pdf00001a"]

    def test_input_tree_left_unmodified(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Enrichment returns a copy; the input tree's ImageVertex is left unchanged."""

        def _fake(firebase_url: HttpUrl, api_endpoint: ApiEndpoint, cache_dir: Path | None = None) -> RoamAsset:
            return _image_asset(size=ImageSize(width=10, height=20))

        monkeypatch.setattr("guffin.render.asset_fetch.fetch_and_cache_asset", _fake)

        original_image: Final[ImageVertex] = _image_vertex("img00001a")
        tree: Final[VertexTree] = VertexTree(tree_vertices=[original_image])
        fetch_and_enrich_assets(tree, _ENDPOINT, tmp_path)

        assert original_image.original_image_size is None

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_enriches_test_article_1_images(
        self, live_api_endpoint: ApiEndpoint, live_cache_dir: Path, tmp_path: Path
    ) -> None:
        """Fetching the [[Test Article]] 1 images populates every ImageVertex's original_image_size (500x477)."""
        tree: Final[VertexTree] = article1_vertex_tree()
        fetched: Final[tuple[VertexTree, dict[Uid, AssetRef]]] = fetch_and_enrich_assets(
            tree, live_api_endpoint, tmp_path, live_cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        images: Final[list[ImageVertex]] = [v for v in enriched_tree.tree_vertices if isinstance(v, ImageVertex)]
        assert images
        for image in images:
            assert image.original_image_size == ImageSize(width=500, height=477)
