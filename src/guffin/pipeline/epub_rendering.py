"""Render a :class:`~guffin.vertex_tree.VertexTree` to an EPUB 3 file via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.pipeline.roam_tree_to_guffin.transcribe` into a Panflute
:class:`~panflute.Doc` via :func:`~guffin.pipeline.pandoc_rendering.vertex_tree_to_pandoc`,
then exports the document to EPUB by serializing the Doc to Pandoc JSON and invoking Pandoc
(its ``epub3`` writer) via :mod:`pypandoc`.

The root :class:`~guffin.vertex.PageVertex` title is stored as the Pandoc document metadata
``title``, which Pandoc maps to the EPUB ``dc:title`` (and generates a title page from); the
remaining EPUB-required metadata (a ``urn:uuid`` identifier, the date, and a language fallback)
is filled in automatically by Pandoc.  Top-level headings become the e-book's chapters via
Pandoc's default EPUB split level.

Cloud Firestore image assets are fetched via
:func:`~guffin.pipeline.image_fetch.fetch_and_enrich_images`, written to a temporary directory,
and embedded in the EPUB by Pandoc's writer as local-path :class:`~panflute.Image` elements.  An
optional *cache_dir* avoids re-downloading unchanged assets across runs.

Roam color/highlight/pill styling is preserved by the bundled ``epub_*.lua`` Pandoc filters (under
``guffin/pipeline/epub_resources/``), which emit inline-styled XHTML.

Public symbols:

- :func:`render` — fetch image assets, build the Pandoc object model, and write an EPUB file.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

import importlib.resources
import logging
import tempfile
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
from pydantic import validate_call

from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree, drop_attribute_assignments
from guffin.pipeline.image_fetch import ImageRef, fetch_and_enrich_images
from guffin.pipeline.pandoc_rendering import (
    InlineMap,
    make_resolver,
    pandoc_to_json,
    resolve_vertex_links,
    vertex_tree_to_pandoc,
)
from guffin.pipeline.render_options import EpubRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


_EPUB_RESOURCES_PACKAGE: Final[str] = "guffin.pipeline.epub_resources"
# Lua-filter filenames, resolved against the bundled epub_resources directory at render time.
_EPUB_COLOR_SPAN_FILTER: Final[str] = "epub_color_span.lua"
_EPUB_MARK_FILTER: Final[str] = "epub_mark.lua"
# Pandoc EPUB writer name (EPUB 3).
_EPUB_WRITER: Final[str] = "epub3"


def _epub_resources_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/pipeline/epub_resources/`` directory."""
    pkg_files = importlib.resources.files(_EPUB_RESOURCES_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as resources_path:
        return resources_path


@validate_call
def render(
    render_bundle: RenderBundle,
    filename_stem: str,
    api_endpoint: ApiEndpoint,
    options: EpubRenderOptions,
) -> None:
    """Render *render_bundle* to an EPUB file inside ``options.output_dir``.

    Writes ``<output_dir>/<filename_stem>.epub``.  Fetches all Cloud Firestore image assets into
    a temporary directory and enriches the vertex tree with each image's native pixel size via
    :func:`~guffin.pipeline.image_fetch.fetch_and_enrich_images`, builds a Panflute
    :class:`~panflute.Doc` via :func:`~guffin.pipeline.pandoc_rendering.vertex_tree_to_pandoc`
    (storing the page title as document metadata so it becomes the EPUB ``dc:title`` and title
    page), serializes it to Pandoc JSON, and invokes Pandoc's ``epub3`` writer via :mod:`pypandoc`
    to produce the EPUB.  The temporary image directory is removed after Pandoc completes.

    Pandoc must be installed and on ``PATH``.

    Args:
        render_bundle: The content tree (with its presentation view map) to render.
        filename_stem: Output filename stem, used verbatim to derive the output path; the caller
            is responsible for POSIX-safety.
        api_endpoint: Roam Local API endpoint used to fetch image assets.
        options: The EPUB rendering options.  Reads ``output_dir`` (where the ``.epub`` is written;
            created if absent), ``cache_dir`` (optional cross-run asset cache), ``suppress_attributes``
            (drop Roam attribute assignments before the build), and ``dump_pandoc_ast`` (write the
            serialized Panflute Doc to ``<output_dir>/<filename_stem>.pandoc.json`` before invoking
            Pandoc).

    Raises:
        RuntimeError: If Pandoc is not found, or if the Pandoc conversion fails.
    """
    output_dir: Final[Path] = options.output_dir
    cache_dir: Final[Path | None] = options.cache_dir
    dump_pandoc_ast: Final[bool] = options.dump_pandoc_ast
    # Attribute-assignment subtrees are pruned before the Panflute Doc build when suppressed.
    content: Final[VertexTree] = (
        drop_attribute_assignments(render_bundle.content) if options.suppress_attributes else render_bundle.content
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path: Final[Path] = output_dir / f"{filename_stem}.epub"

    epub_dir: Final[Path] = _epub_resources_dir()

    with tempfile.TemporaryDirectory() as tmp:
        fetched: Final[tuple[VertexTree, dict[Uid, ImageRef]]] = fetch_and_enrich_images(
            content, api_endpoint, Path(tmp), cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        image_refs: Final[dict[Uid, ImageRef]] = fetched[1]
        image_files: Final[dict[Uid, Path]] = {uid: ref.path for uid, ref in image_refs.items()}
        pandoc_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            enriched_tree, image_files, render_bundle.view
        )
        doc: Final[pf.Doc] = pandoc_result[0]
        inline_map: Final[InlineMap] = pandoc_result[1]
        resolve_vertex_links(doc, enriched_tree, make_resolver(inline_map))
        json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, filename_stem)
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str,
            _EPUB_WRITER,
            format="json",
            outputfile=str(output_path),
            extra_args=[
                f"--lua-filter={epub_dir / _EPUB_COLOR_SPAN_FILTER}",
                f"--lua-filter={epub_dir / _EPUB_MARK_FILTER}",
            ],
        )

    logger.info("Wrote EPUB to %s", output_path)
