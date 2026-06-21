"""Image asset fetching for the rendering pipeline — Pandoc-free.

Walks a :class:`~guffin.vertex_tree.VertexTree`, fetches every
:class:`~guffin.vertex.ImageVertex`'s Cloud Firestore asset to a local
directory via :func:`~guffin.roam.asset_fetch.fetch_and_cache_asset`, and
returns a ``{uid: ImageRef}`` mapping bundling each image's on-disk path and
native pixel size.

This module deliberately has no Pandoc/Panflute dependency so it can be shared
by rendering back-ends that must remain Pandoc-free.

Public symbols:

- :class:`ImageRef` — 3-way association of an image vertex's UID, on-disk path, and pixel size.
- :func:`fetch_images` — fetch all :class:`~guffin.vertex.ImageVertex` assets from a
  :class:`~guffin.vertex_tree.VertexTree` to a local directory; return a ``{uid: ImageRef}`` mapping.
- :func:`fetch_and_enrich_images` — :func:`fetch_images` plus tree enrichment; returns the
  ``original_image_size``-populated tree together with the ``{uid: ImageRef}`` mapping.
"""

import logging
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import validate_call

from guffin.common.geometry import ImageSize
from guffin.vertex import ImageVertex
from guffin.vertex_tree import VertexTree, enrich_image_original_sizes
from guffin.roam.asset import RoamAsset, RoamImageAsset
from guffin.roam.asset_fetch import fetch_and_cache_asset
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


class ImageRef(NamedTuple):
    """An :class:`~guffin.vertex.ImageVertex`'s fetched asset: its UID, on-disk path, and pixel size.

    The 3-way association produced by :func:`fetch_images` for every image
    successfully fetched from Cloud Firestore.

    Attributes:
        uid: The source :class:`~guffin.vertex.ImageVertex` UID.
        path: Local filesystem path of the written image file.
        size: Native pixel dimensions of the image, or an empty
            :class:`~guffin.common.geometry.ImageSize` when they could not be determined.
    """

    uid: Uid
    path: Path
    size: ImageSize


@validate_call
def fetch_images(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    image_dir: Path,
    cache_dir: Path | None = None,
) -> dict[Uid, ImageRef]:
    """Fetch all :class:`~guffin.vertex.ImageVertex` assets to *image_dir*.

    Delegates fetching and caching to
    :func:`~guffin.roam.asset_fetch.fetch_and_cache_asset`.  Each fetched
    asset is written to *image_dir* under its deterministic
    ``<sha256>.<ext>`` filename.  Vertices that fail to fetch are skipped
    with a warning and will fall back to a hyperlink in the rendered output.

    Args:
        vertex_tree: The vertex tree whose image assets to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        image_dir: Directory where fetched image files are written.
        cache_dir: Optional directory for caching downloaded assets across
            runs.

    Returns:
        A mapping from :class:`~guffin.vertex.ImageVertex` UID to an
        :class:`ImageRef` bundling the local path and native pixel size of
        the fetched image.  Vertices that could not be fetched are absent
        from the mapping.
    """
    image_refs: dict[Uid, ImageRef] = {}
    for vertex in vertex_tree.tree_vertices:
        if not isinstance(vertex, ImageVertex):
            continue
        try:
            asset: RoamAsset = fetch_and_cache_asset(vertex.source, api_endpoint, cache_dir)
            img_path: Path = image_dir / asset.file_name
            img_path.write_bytes(asset.contents)
            size: ImageSize = asset.image_size if isinstance(asset, RoamImageAsset) else ImageSize()
            image_refs[vertex.uid] = ImageRef(uid=vertex.uid, path=img_path, size=size)
            logger.info("Fetched image uid=%r -> %s", vertex.uid, img_path.name)
        except Exception as e:
            logger.warning("Failed to fetch image uid=%r source=%s: %s", vertex.uid, vertex.source, e)
    return image_refs


@validate_call
def fetch_and_enrich_images(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    image_dir: Path,
    cache_dir: Path | None = None,
) -> tuple[VertexTree, dict[Uid, ImageRef]]:
    """Fetch every image asset and return the tree enriched with their native sizes.

    Convenience wrapper over :func:`fetch_images`: after fetching, populates
    :attr:`~guffin.vertex.ImageVertex.original_image_size` on each image vertex
    from the corresponding :class:`ImageRef` size via
    :func:`~guffin.vertex_tree.enrich_image_original_sizes`.

    Args:
        vertex_tree: The vertex tree whose image assets to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        image_dir: Directory where fetched image files are written.
        cache_dir: Optional directory for caching downloaded assets across runs.

    Returns:
        A ``(enriched_tree, image_refs)`` pair: *enriched_tree* is a copy of
        *vertex_tree* with every :class:`~guffin.vertex.ImageVertex`'s
        ``original_image_size`` populated from its fetched image; *image_refs*
        is the ``{uid: ImageRef}`` mapping as returned by :func:`fetch_images`.
    """
    image_refs: Final[dict[Uid, ImageRef]] = fetch_images(vertex_tree, api_endpoint, image_dir, cache_dir)
    original_sizes: Final[dict[Uid, ImageSize]] = {uid: ref.size for uid, ref in image_refs.items()}
    enriched_tree: Final[VertexTree] = enrich_image_original_sizes(vertex_tree, original_sizes)
    return enriched_tree, image_refs
