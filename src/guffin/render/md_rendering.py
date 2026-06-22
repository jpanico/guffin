"""Render a :class:`~guffin.vertex_tree.VertexTree` to GFM and write Markdown exports to disk.

Converts the normalized vertex tree produced by
:func:`~guffin.roam_tree_to_vertex_tree.transcribe` to a GFM document via the
Pandoc object model (see :mod:`~guffin.pandoc_rendering`), and writes the
result to disk as either a plain ``.md`` file or a self-contained
``.mdbundle`` directory that embeds downloaded Cloud Firestore images.

Public symbols:

- :func:`render` — end-to-end: render a :class:`~guffin.vertex_tree.VertexTree` to
  a ``.mdbundle`` directory or plain ``.md`` file (parallel entry point to
  :func:`~guffin.render.pdf_rendering.render`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

import logging
from pathlib import Path
from typing import Final

_RENDER_DIR: Final[Path] = Path(__file__).parent
_GFM_CALLOUT_FILTER: Final[Path] = _RENDER_DIR / "gfm_callout.lua"
_GFM_COLOR_SPAN_FILTER: Final[Path] = _RENDER_DIR / "gfm_color_span.lua"
_GFM_IMAGE_FILTER: Final[Path] = _RENDER_DIR / "gfm_image.lua"
_GFM_MARK_FILTER: Final[Path] = _RENDER_DIR / "gfm_mark.lua"

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
from pydantic import validate_call

from guffin.common.filenames import shell_safe_filename
from guffin.model.link import VertexLink
from guffin.model.vertex import Vertex
from guffin.model.vertex_tree import VertexTree
from guffin.render.image_fetch import ImageRef, fetch_and_enrich_images
from guffin.render.pandoc_rendering import pandoc_to_json, resolve_vertex_links, vertex_tree_to_pandoc
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


def _resolve_vertex_link(vertex_link: VertexLink, vertex: Vertex, display: list[pf.Inline]) -> list[pf.Inline]:
    return display


@validate_call
def render(
    vertex_tree: VertexTree,
    filename_stem: str,
    output_dir: Path,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
    bundle: bool = True,
    dump_pandoc_ast: bool = False,
) -> None:
    """Render *vertex_tree* to a Markdown file or bundle inside *output_dir*.

    Converts *vertex_tree* to a Panflute :class:`~panflute.Doc` via
    :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc` (with the page
    title rendered as an H1 header), then invokes Pandoc to produce
    GFM output.  Writes the result in one of two modes controlled by
    *bundle*:

    - ``bundle=True`` (default) — fetches Cloud Firestore image assets and
      enriches the vertex tree with each image's native pixel size via
      :func:`~guffin.render.image_fetch.fetch_and_enrich_images`, places the images
      in the bundle directory, and writes a self-contained
      ``<normalized_filename_stem>.mdbundle/`` directory containing the
      Markdown file and all images.  Image links in the Markdown reference
      the local filenames.
    - ``bundle=False`` — writes the GFM text directly to
      ``<output_dir>/<normalized_filename_stem>.md`` without fetching
      images.  :class:`~guffin.vertex.ImageVertex` nodes fall back to
      hyperlinks pointing at the original Cloud Firestore URLs.

    Pandoc must be installed and on ``PATH``.

    Args:
        vertex_tree: The normalized vertex tree to render.
        filename_stem: String used to derive the output filename (e.g. a Roam
            page title or node UID); POSIX-normalized before use.
        output_dir: Directory in which the output file or bundle is written;
            created if it does not already exist.
        api_endpoint: Roam Local API endpoint used to fetch image assets
            (bundle mode only; not called when *bundle* is ``False``).
        cache_dir: Optional directory for caching downloaded image assets
            across runs.  Ignored when *bundle* is ``False``.
        bundle: When ``True`` (default), writes a ``.mdbundle`` directory with
            embedded images.  When ``False``, writes a plain ``.md`` file.
        dump_pandoc_ast: When ``True``, writes the Pandoc JSON AST (the
            serialized Panflute Doc) to
            ``<output_dir>/<normalized_filename_stem>.pandoc.json`` before
            invoking Pandoc.  Useful for debugging the intermediate
            representation.
    """
    stem: Final[str] = shell_safe_filename(filename_stem)

    if bundle:
        bundle_dir: Final[Path] = output_dir / f"{stem}.mdbundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created bundle directory: %s", bundle_dir)

        # the Paths in the returned ImageRefs are absolute
        fetched: Final[tuple[VertexTree, dict[Uid, ImageRef]]] = fetch_and_enrich_images(
            vertex_tree, api_endpoint, bundle_dir, cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        image_refs: Final[dict[Uid, ImageRef]] = fetched[1]
        # Strip to filename-only so Pandoc writes relative image references in the Markdown output.
        image_files: Final[dict[Uid, Path]] = {uid: Path(ref.path.name) for uid, ref in image_refs.items()}

        doc: Final[pf.Doc] = vertex_tree_to_pandoc(enriched_tree, image_files, title_in_header=True)
        resolve_vertex_links(doc, enriched_tree, _resolve_vertex_link)
        bundle_json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, stem)
        md_text: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            bundle_json_str,
            "gfm",
            format="json",
            extra_args=[
                "--wrap=none",
                f"--lua-filter={_GFM_CALLOUT_FILTER}",
                f"--lua-filter={_GFM_COLOR_SPAN_FILTER}",
                f"--lua-filter={_GFM_IMAGE_FILTER}",
                f"--lua-filter={_GFM_MARK_FILTER}",
            ],
        )
        output_file: Final[Path] = bundle_dir / f"{stem}.md"
        output_file.write_text(md_text, encoding="utf-8")
        logger.info("Wrote Markdown to: %s", output_file)

    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        no_bundle_doc: Final[pf.Doc] = vertex_tree_to_pandoc(vertex_tree, {}, title_in_header=True)
        resolve_vertex_links(no_bundle_doc, vertex_tree, _resolve_vertex_link)
        json_str: Final[str] = pandoc_to_json(no_bundle_doc, dump_pandoc_ast, output_dir, stem)
        no_bundle_md: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str,
            "gfm",
            format="json",
            extra_args=[
                "--wrap=none",
                f"--lua-filter={_GFM_CALLOUT_FILTER}",
                f"--lua-filter={_GFM_COLOR_SPAN_FILTER}",
                f"--lua-filter={_GFM_MARK_FILTER}",
            ],
        )
        output_path: Final[Path] = output_dir / f"{stem}.md"
        output_path.write_text(no_bundle_md, encoding="utf-8")
        logger.info("Wrote Markdown to %s", output_path)
