"""Image and PDF asset fetching for the rendering pipeline — Pandoc-free.

Walks a :class:`~guffin.vertex_tree.VertexTree`, fetches every asset-bearing
vertex's (:class:`~guffin.vertex.ImageVertex` or :class:`~guffin.vertex.PdfVertex`)
Cloud Firestore asset to a local directory via
:func:`~guffin.roam.asset_fetch.fetch_and_cache_asset`, and returns a
``{uid: AssetRef}`` mapping bundling each asset's on-disk location.

This module deliberately has no Pandoc/Panflute dependency so it can be shared
by rendering back-ends that must remain Pandoc-free.

Public symbols:

- :class:`AssetRef` — association of an asset vertex's UID, on-disk path, and (for
  images) native pixel size.
- :func:`fetch_assets` — fetch every asset-bearing vertex's file from a
  :class:`~guffin.vertex_tree.VertexTree` to a local directory; return a
  ``{uid: AssetRef}`` mapping.
- :func:`fetch_and_enrich_assets` — :func:`fetch_assets` plus tree enrichment; returns the
  ``original_image_size``-populated tree together with the ``{uid: AssetRef}`` mapping.
"""

import logging
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import validate_call

from guffin.common.geometry import ImageSize
from guffin.model.vertex import ImageVertex, PdfVertex
from guffin.model.vertex_tree import VertexTree, enrich_image_original_sizes
from guffin.roam.asset import RoamAsset, RoamImageAsset
from guffin.roam.asset_fetch import fetch_and_cache_asset
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


class AssetRef(NamedTuple):
    """An asset-bearing vertex's fetched asset: its UID, on-disk path, and pixel size.

    The association produced by :func:`fetch_assets` for every asset
    successfully fetched from Cloud Firestore.

    Attributes:
        uid: The source :class:`~guffin.vertex.ImageVertex` or
            :class:`~guffin.vertex.PdfVertex` UID.
        path: Local filesystem path of the written asset file.
        size: Native pixel dimensions of an image asset — an empty
            :class:`~guffin.common.geometry.ImageSize` when they could not be
            determined — or ``None`` for a non-image asset (a PDF has no
            pixel size).
    """

    uid: Uid
    path: Path
    size: ImageSize | None


@validate_call
def fetch_assets(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    asset_dir: Path,
    cache_dir: Path | None = None,
) -> dict[Uid, AssetRef]:
    """Fetch every asset-bearing vertex's file to *asset_dir*.

    Scans for :class:`~guffin.vertex.ImageVertex` and
    :class:`~guffin.vertex.PdfVertex` entries, delegating fetching and caching
    to :func:`~guffin.roam.asset_fetch.fetch_and_cache_asset`.  Each fetched
    asset is written to *asset_dir* under its deterministic
    ``<sha256>.<ext>`` filename.  Vertices that fail to fetch are skipped
    with a warning and will fall back to a hyperlink in the rendered output.

    Every vertex in :attr:`~guffin.model.vertex_tree.VertexTree.uid_map` is scanned
    (covering both :attr:`~guffin.model.vertex_tree.VertexTree.tree_vertices` and
    :attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`, deduplicated by UID),
    so an asset referenced from another page (a block reference whose destination is
    an asset vertex outside the anchor tree) is fetched like an in-tree asset,
    rather than left as a remote hyperlink.

    Args:
        vertex_tree: The vertex tree whose assets to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        asset_dir: Directory where fetched asset files are written.
        cache_dir: Optional directory for caching downloaded assets across
            runs.

    Returns:
        A mapping from asset vertex UID to an :class:`AssetRef` bundling the
        local path of the fetched file and, for images, its native pixel
        size.  Vertices that could not be fetched are absent from the
        mapping.
    """
    asset_refs: Final[dict[Uid, AssetRef]] = {}
    for vertex in vertex_tree.uid_map.values():
        if not isinstance(vertex, ImageVertex | PdfVertex):
            continue
        try:
            asset: RoamAsset = fetch_and_cache_asset(vertex.source, api_endpoint, cache_dir)
            asset_path: Path = asset_dir / asset.file_name
            asset_path.write_bytes(asset.contents)
            size: ImageSize | None = asset.image_size if isinstance(asset, RoamImageAsset) else None
            asset_refs[vertex.uid] = AssetRef(uid=vertex.uid, path=asset_path, size=size)
            logger.info("Fetched asset uid=%r -> %s", vertex.uid, asset_path.name)
        except Exception as e:
            logger.warning("Failed to fetch asset uid=%r source=%s: %s", vertex.uid, vertex.source, e)
    return asset_refs


@validate_call
def fetch_and_enrich_assets(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    asset_dir: Path,
    cache_dir: Path | None = None,
) -> tuple[VertexTree, dict[Uid, AssetRef]]:
    """Fetch every asset and return the tree enriched with the images' native sizes.

    Convenience wrapper over :func:`fetch_assets`: after fetching, populates
    :attr:`~guffin.vertex.ImageVertex.original_image_size` on each image vertex
    from the corresponding :class:`AssetRef` size via
    :func:`~guffin.vertex_tree.enrich_image_original_sizes`.  Non-image assets
    carry no pixel size and do not participate in the enrichment.

    Args:
        vertex_tree: The vertex tree whose assets to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        asset_dir: Directory where fetched asset files are written.
        cache_dir: Optional directory for caching downloaded assets across runs.

    Returns:
        A ``(enriched_tree, asset_refs)`` pair: *enriched_tree* is a copy of
        *vertex_tree* with every :class:`~guffin.vertex.ImageVertex`'s
        ``original_image_size`` populated from its fetched image; *asset_refs*
        is the ``{uid: AssetRef}`` mapping as returned by :func:`fetch_assets`.
    """
    asset_refs: Final[dict[Uid, AssetRef]] = fetch_assets(vertex_tree, api_endpoint, asset_dir, cache_dir)
    original_sizes: Final[dict[Uid, ImageSize]] = {
        uid: ref.size for uid, ref in asset_refs.items() if ref.size is not None
    }
    enriched_tree: Final[VertexTree] = enrich_image_original_sizes(vertex_tree, original_sizes)
    return enriched_tree, asset_refs
