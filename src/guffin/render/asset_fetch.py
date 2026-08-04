"""Image and PDF asset fetching for the rendering pipeline — Pandoc-free.

Walks a :class:`~guffin.vertex_tree.VertexTree`, fetches every *displayed*
asset-bearing vertex's (:data:`~guffin.model.vertex.AssetBearingVertex`, scoped per
:func:`~guffin.model.vertex_tree.visible_asset_vertices` plus the root's cover image)
Firebase Storage asset to a local directory via
:func:`~guffin.roam.asset_fetch.fetch_and_cache_asset`, and returns a
``{uid: AssetRef}`` mapping bundling each asset's on-disk location.

This module deliberately has no Pandoc/Panflute dependency so it can be shared
by rendering back-ends that must remain Pandoc-free.

Public symbols:

- :class:`AssetRef` — association of an asset vertex's UID, on-disk path, (for
  images) native pixel size, and (when known) original upload filename.
- :func:`fetch_asset` — fetch a single asset-bearing vertex's file to a local
  directory; return its :class:`AssetRef`.
- :func:`fetch_assets` — fetch every displayed asset-bearing vertex's file from a
  :class:`~guffin.vertex_tree.VertexTree` to a local directory; return a
  ``{uid: AssetRef}`` mapping.
- :func:`fetch_and_enrich_assets` — :func:`fetch_assets` plus tree enrichment; returns the
  tree with ``original_image_size`` (images) and ``original_file_name`` (PDFs) populated,
  together with the ``{uid: AssetRef}`` mapping.
- :func:`pdf_asset_paths` — map each fetched PDF asset's source URL to its local path.
- :func:`cover_image_path` — pure lookup: the fetched local path of the cover image a
  tree's root vertex references, resolved against a :func:`fetch_assets` result; ``None``
  when no cover is declared.
"""

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import validate_call

from guffin.common.filenames import shell_safe_filename
from guffin.common.geometry import ImageSize
from guffin.model.publishing_semantics import cover_image_vertex
from guffin.model.vertex import AssetBearingVertex, ImageVertex, PdfVertex
from guffin.model.vertex_tree import (
    VertexTree,
    enrich_image_original_sizes,
    enrich_pdf_original_file_names,
    visible_asset_vertices,
)
from guffin.roam.asset import RoamAsset, RoamImageAsset
from guffin.roam.asset_fetch import fetch_and_cache_asset
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


class AssetRef(NamedTuple):
    """An asset-bearing vertex's fetched asset: its UID, on-disk path, pixel size, and original name.

    The association produced by :func:`fetch_assets` for every asset
    successfully fetched from Firebase Storage.

    Attributes:
        uid: The source :data:`~guffin.model.vertex.AssetBearingVertex` UID.
        path: Local filesystem path of the written asset file.
        size: Native pixel dimensions of an image asset — an empty
            :class:`~guffin.common.geometry.ImageSize` when they could not be
            determined — or ``None`` for a non-image asset (a PDF has no
            pixel size).
        original_file_name: The filename the asset was originally uploaded
            under, or ``None`` when unknown.
    """

    uid: Uid
    path: Path
    size: ImageSize | None
    original_file_name: str | None = None


def _preferred_file_name(asset: RoamAsset) -> str:
    """The filename an asset should be written under, before collision handling.

    Prefers the asset's original upload filename, normalized by
    :func:`~guffin.common.filenames.shell_safe_filename`.  Falls back to the
    deterministic ``<sha256>.<ext>`` cache filename when the original is
    unknown, or when normalization leaves no usable stem (an empty string or
    a bare-extension dotfile).

    Args:
        asset: The fetched asset to name.

    Returns:
        The preferred filename for the asset.
    """
    if asset.original_file_name is None:
        return asset.file_name
    safe_name: Final[str] = shell_safe_filename(asset.original_file_name)
    if not safe_name or safe_name.startswith("."):
        return asset.file_name
    return safe_name


def _resolved_file_name(asset: RoamAsset, source_url: str, claimed_names: Mapping[str, str]) -> str:
    """The distinct on-disk filename for *asset*, given the names already claimed.

    Starts from :func:`_preferred_file_name` and, while that name is claimed
    by an asset from a *different* source, appends an increasing numeric
    suffix to the stem (``paper.pdf`` → ``paper-1.pdf`` → ``paper-2.pdf`` …)
    until a free name is found.  An asset whose *source_url* already holds a
    claim resolves to its claimed name again.

    Args:
        asset: The fetched asset to name.
        source_url: The source URL identifying the asset.
        claimed_names: Read-only mapping of already-claimed filename to the
            source URL of the asset holding the claim.

    Returns:
        The resolved filename for the asset.
    """
    # locals() is exactly the parameters when read as the first statement.
    logger.debug("args: %r", locals())
    preferred: Final[str] = _preferred_file_name(asset)
    stem: Final[str] = Path(preferred).stem
    suffix: Final[str] = Path(preferred).suffix
    candidate = preferred
    counter = 1
    while candidate in claimed_names and claimed_names[candidate] != source_url:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


@validate_call
def fetch_asset(
    vertex: AssetBearingVertex,
    api_endpoint: ApiEndpoint,
    asset_dir: Path,
    cache_dir: Path | None = None,
    claimed_names: Mapping[str, str] | None = None,
) -> AssetRef:
    """Fetch *vertex*'s Firebase Storage asset to *asset_dir*.

    Delegates fetching and caching to
    :func:`~guffin.roam.asset_fetch.fetch_and_cache_asset`, writes the asset
    into *asset_dir* under its original upload filename (normalized to a
    POSIX-safe form, falling back to the deterministic ``<sha256>.<ext>``
    cache filename when the original is unknown or normalizes to nothing
    usable), and returns the resulting association.

    Args:
        vertex: The asset-bearing vertex whose asset to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        asset_dir: Directory where the fetched asset file is written.
        cache_dir: Optional directory for caching downloaded assets across
            runs.
        claimed_names: Read-only mapping of filenames already in use in
            *asset_dir* to the source URL of the asset holding each name.
            The written filename is disambiguated with a numeric suffix
            rather than colliding with a name held by a different source;
            a source that already holds a claim reuses its name.  ``None``
            (the default) means no names are claimed.  Never modified.

    Returns:
        An :class:`AssetRef` bundling the written file's path, the native
        pixel size for an image asset (``None`` for a non-image asset), and
        the original upload filename when known.
    """
    # locals() is exactly the parameters when read as the first statement.
    logger.debug("args: %r", locals())
    names: Final[Mapping[str, str]] = claimed_names if claimed_names is not None else {}
    asset: Final[RoamAsset] = fetch_and_cache_asset(vertex.source, api_endpoint, cache_dir)
    file_name: Final[str] = _resolved_file_name(asset, str(vertex.source), names)
    asset_path: Final[Path] = asset_dir / file_name
    asset_path.write_bytes(asset.contents)
    size: Final[ImageSize | None] = asset.image_size if isinstance(asset, RoamImageAsset) else None
    return AssetRef(uid=vertex.uid, path=asset_path, size=size, original_file_name=asset.original_file_name)


@validate_call
def fetch_assets(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    asset_dir: Path,
    cache_dir: Path | None = None,
) -> dict[Uid, AssetRef]:
    """Fetch every displayed asset-bearing vertex's file to *asset_dir*.

    Fetches each asset via :func:`fetch_asset`, coordinating the filename
    claims across the whole fetch, so two distinct assets sharing an upload
    name land under distinct (numeric-suffixed) filenames.  Vertices that
    fail to fetch are skipped with a warning and will fall back to a
    hyperlink in the rendered output.

    The fetch is scoped to the assets the rendered document actually places from
    local files: the *displayed* assets (per
    :func:`~guffin.model.vertex_tree.visible_asset_vertices` — render-visible asset
    vertices, plus assets a render-visible vertex references standalone, which covers an
    asset referenced from another page whose reference is the block's whole content),
    together with the root's ``cover-image`` (per
    :func:`~guffin.model.publishing_semantics.cover_image_vertex`), whose vertex is
    typically reachable only through
    :attr:`~guffin.model.vertex_tree.VertexTree.ref_vertices`.  An asset merely
    *mentioned* inline amid surrounding text renders as a remote hyperlink and is not
    fetched.

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
    # locals() is exactly the parameters when read as the first statement.
    logger.debug("args: %r", locals())
    displayed: Final[list[AssetBearingVertex]] = visible_asset_vertices(vertex_tree)
    cover: Final[ImageVertex | None] = cover_image_vertex(vertex_tree)
    fetchable: Final[list[AssetBearingVertex]] = (
        [*displayed, cover] if cover is not None and all(cover.uid != vertex.uid for vertex in displayed) else displayed
    )
    asset_refs: Final[dict[Uid, AssetRef]] = {}
    claimed_names: Final[dict[str, str]] = {}
    for vertex in fetchable:
        try:
            ref: AssetRef = fetch_asset(vertex, api_endpoint, asset_dir, cache_dir, claimed_names=claimed_names)
        except Exception as e:
            logger.warning("Failed to fetch asset uid=%r source=%s: %s", vertex.uid, vertex.source, e)
            continue
        claimed_names[ref.path.name] = str(vertex.source)
        asset_refs[vertex.uid] = ref
        logger.info("Fetched asset uid=%r -> %s", vertex.uid, ref.path.name)
    return asset_refs


@validate_call
def fetch_and_enrich_assets(
    vertex_tree: VertexTree,
    api_endpoint: ApiEndpoint,
    asset_dir: Path,
    cache_dir: Path | None = None,
) -> tuple[VertexTree, dict[Uid, AssetRef]]:
    """Fetch every displayed asset and return the tree enriched with what fetching alone can know.

    Convenience wrapper over :func:`fetch_assets`: after fetching, populates
    :attr:`~guffin.vertex.ImageVertex.original_image_size` on each image vertex
    (via :func:`~guffin.vertex_tree.enrich_image_original_sizes`) and
    :attr:`~guffin.vertex.PdfVertex.original_file_name` on each PDF vertex
    (via :func:`~guffin.vertex_tree.enrich_pdf_original_file_names`) from the
    corresponding :class:`AssetRef`.

    Args:
        vertex_tree: The vertex tree whose assets to fetch.
        api_endpoint: Roam Local API endpoint (URL + bearer token).
        asset_dir: Directory where fetched asset files are written.
        cache_dir: Optional directory for caching downloaded assets across runs.

    Returns:
        A ``(enriched_tree, asset_refs)`` pair: *enriched_tree* is the enriched copy of
        *vertex_tree*; *asset_refs* is the ``{uid: AssetRef}`` mapping as returned by
        :func:`fetch_assets`.
    """
    # locals() is exactly the parameters when read as the first statement.
    logger.debug("args: %r", locals())
    asset_refs: Final[dict[Uid, AssetRef]] = fetch_assets(vertex_tree, api_endpoint, asset_dir, cache_dir)
    original_sizes: Final[dict[Uid, ImageSize]] = {
        uid: ref.size for uid, ref in asset_refs.items() if ref.size is not None
    }
    original_names: Final[dict[Uid, str]] = {
        uid: ref.original_file_name for uid, ref in asset_refs.items() if ref.original_file_name is not None
    }
    sized_tree: Final[VertexTree] = enrich_image_original_sizes(vertex_tree, original_sizes)
    enriched_tree: Final[VertexTree] = enrich_pdf_original_file_names(sized_tree, original_names)
    return enriched_tree, asset_refs


@validate_call
def cover_image_path(vertex_tree: VertexTree, asset_refs: Mapping[Uid, AssetRef]) -> Path | None:
    """Return the fetched local path of the cover image *vertex_tree*'s root references, or ``None``.

    A pure lookup over already-fetched assets: resolves the root vertex's ``cover-image`` block
    reference to the :class:`~guffin.model.vertex.ImageVertex` it names
    (:func:`~guffin.model.publishing_semantics.cover_image_vertex`) and returns that vertex's
    fetched location from *asset_refs* — the mapping produced by :func:`fetch_assets`, whose
    scope explicitly includes the root's cover image, so the cover is fetched exactly once,
    under the fetch-wide filename-claim coordination.

    Args:
        vertex_tree: The vertex tree whose root may reference a cover image block.
        asset_refs: The ``{uid: AssetRef}`` mapping of the tree's fetched assets.

    Returns:
        The cover file's local path; ``None`` when the root references no (resolvable) cover,
        or — with a warning — when the cover's asset is absent from *asset_refs* (its fetch
        failed and was already warned about by :func:`fetch_assets`).
    """
    # locals() is exactly the parameters when read as the first statement.
    logger.debug("args: %r", locals())
    cover_vertex: Final[ImageVertex | None] = cover_image_vertex(vertex_tree)
    if cover_vertex is None:
        return None
    cover_ref: Final[AssetRef | None] = asset_refs.get(cover_vertex.uid)
    if cover_ref is None:
        logger.warning("cover image uid=%r was not fetched; rendering without a cover", cover_vertex.uid)
        return None
    return cover_ref.path


@validate_call
def pdf_asset_paths(tree: VertexTree, asset_refs: dict[Uid, AssetRef]) -> dict[str, Path]:
    """Map each fetched PDF asset's source URL to its local file path.

    The keys are the PDF vertices' source URLs — the URL a rendered embed link carries — so a
    Pandoc document's PDF-embed paragraphs can be matched against the mapping.  When several PDF
    vertices share one source URL, the first (in
    :attr:`~guffin.model.vertex_tree.VertexTree.uid_map` order) wins.  PDF vertices absent from
    *asset_refs* (failed fetches) contribute no entry.

    Args:
        tree: The vertex tree whose PDF assets to map.
        asset_refs: The fetched assets, as returned by
            :func:`fetch_assets`.

    Returns:
        A mapping from source URL to the fetched PDF's local path.
    """
    paths: Final[dict[str, Path]] = {}
    for vertex in tree.uid_map.values():
        if not isinstance(vertex, PdfVertex) or str(vertex.source) in paths:
            continue
        ref: AssetRef | None = asset_refs.get(vertex.uid)
        if ref is None:
            continue
        paths[str(vertex.source)] = ref.path
    return paths
