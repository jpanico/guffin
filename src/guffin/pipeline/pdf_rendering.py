"""Render a :class:`~guffin.vertex_tree.VertexTree` to a PDF via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.pipeline.roam_tree_to_vertex_tree.transcribe` into a Panflute
:class:`~panflute.Doc` via :func:`~guffin.pipeline.pandoc_rendering.vertex_tree_to_pandoc`,
then exports the document to PDF by serializing the Doc to Pandoc JSON and
invoking Pandoc via :mod:`pypandoc`.

Cloud Firestore image assets are fetched via
:func:`~guffin.pipeline.image_fetch.fetch_and_enrich_images`, written to a temporary
directory, and embedded in the PDF as local-path
:class:`~panflute.Image` elements.  An optional *cache_dir* avoids
re-downloading unchanged assets across runs.

The Bergfink Pandoc/Typst template (bundled as package data under
``guffin/templates/``) is used by default.  Pass *template_dir* to point at a
directory containing a ``user_cfg.typ`` override; Bergfink's ``$if(user-config)$``
mechanism will load it in place of the bundled default.

Public symbols:

- :func:`render` — fetch image assets, build the Pandoc object model,
  and write a PDF file.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

import importlib.resources
import logging
import os
import tempfile
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
from pydantic import validate_call

from guffin.common.filenames import shell_safe_filename
from guffin.model.link import VertexLink
from guffin.model.vertex import Vertex
from guffin.model.vertex_tree import VertexTree
from guffin.pipeline.image_fetch import ImageRef, fetch_and_enrich_images
from guffin.pipeline.pandoc_rendering import pandoc_to_json, resolve_vertex_links, vertex_tree_to_pandoc
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


def _resolve_vertex_link(vertex_link: VertexLink, vertex: Vertex, display: list[pf.Inline]) -> list[pf.Inline]:
    return display


_TEMPLATE_PACKAGE: Final[str] = "guffin.templates"
_TEMPLATE_ENTRY: Final[str] = "bergfink.typst"
_USER_CFG_FILENAME: Final[str] = "user_cfg.typ"
_TYPST_CALLOUT_FILTER: Final[Path] = Path(__file__).parent / "typst_callout.lua"
_TYPST_COLOR_SPAN_FILTER: Final[Path] = Path(__file__).parent / "typst_color_span.lua"


def _bundled_templates_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/templates/`` directory."""
    pkg_files = importlib.resources.files(_TEMPLATE_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as templates_path:
        return templates_path


def _dump_typst_sources(
    json_str: str,
    output_dir: Path,
    stem: str,
    template_path: Path,
    bundled_dir: Path,
    template_dir: Path | None,
) -> None:
    """Dump intermediate Typst sources for debugging when ``GUFFIN_DUMP_TYPST`` is set.

    A no-op unless the ``GUFFIN_DUMP_TYPST`` environment variable is non-empty.  When
    enabled, converts the Pandoc JSON to Typst twice and writes both files to
    *output_dir*: ``<stem>.body.typ`` (the bare body) and ``<stem>.full.typ`` (with the
    template applied).  Purely a debugging aid for inspecting the Typst the PDF is built
    from; it has no effect on the produced PDF.

    Args:
        json_str: The Pandoc JSON (serialized Panflute Doc) to convert to Typst.
        output_dir: Directory the ``.typ`` files are written into.
        stem: Output filename stem, shared with the ``.pdf``.
        template_path: Path to the Bergfink Typst template entry point.
        bundled_dir: Bundled templates directory, used as Pandoc's resource path.
        template_dir: Optional user template directory; when set, a ``user-config``
            override is applied to the full-Typst conversion.
    """
    if not os.environ.get("GUFFIN_DUMP_TYPST"):
        return
    typst_body: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
        json_str,
        "typst",
        format="json",
        extra_args=[f"--lua-filter={_TYPST_CALLOUT_FILTER}", f"--lua-filter={_TYPST_COLOR_SPAN_FILTER}"],
    )
    typst_body_path: Final[Path] = output_dir / f"{stem}.body.typ"
    typst_body_path.write_text(typst_body, encoding="utf-8")
    logger.info("Wrote Typst body to %s", typst_body_path)
    typst_full_extra: list[str] = [
        f"--template={template_path}",
        f"--resource-path={bundled_dir}",
        f"--lua-filter={_TYPST_CALLOUT_FILTER}",
        f"--lua-filter={_TYPST_COLOR_SPAN_FILTER}",
        "-V",
        "listings=true",
    ]
    if template_dir is not None:
        typst_full_extra.extend(["-V", f"user-config={template_dir / _USER_CFG_FILENAME}"])
    typst_full: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
        json_str, "typst", format="json", extra_args=typst_full_extra
    )
    typst_full_path: Final[Path] = output_dir / f"{stem}.full.typ"
    typst_full_path.write_text(typst_full, encoding="utf-8")
    logger.info("Wrote full Typst (with template) to %s", typst_full_path)


@validate_call
def render(
    vertex_tree: VertexTree,
    filename_stem: str,
    output_dir: Path,
    api_endpoint: ApiEndpoint,
    cache_dir: Path | None = None,
    template_dir: Path | None = None,
    dump_pandoc_ast: bool = False,
) -> None:
    """Render *vertex_tree* to a PDF file inside *output_dir*.

    Derives the output filename from *filename_stem* via
    :func:`~guffin.common.filenames.shell_safe_filename`, creating
    ``<output_dir>/<normalized_filename_stem>.pdf``.  Fetches all Cloud
    Firestore image assets into a temporary directory and enriches the vertex
    tree with each image's native pixel size via
    :func:`~guffin.pipeline.image_fetch.fetch_and_enrich_images`, builds a Panflute
    :class:`~panflute.Doc` via
    :func:`~guffin.pipeline.pandoc_rendering.vertex_tree_to_pandoc`, serializes it
    to Pandoc JSON, and invokes Pandoc (with the Typst PDF engine and the
    bundled Bergfink template) via :mod:`pypandoc` to produce the PDF.  The
    temporary image directory is removed after Pandoc completes.

    Pandoc and Typst must be installed and on ``PATH``.

    Args:
        vertex_tree: The normalized vertex tree to render.
        filename_stem: String used to derive the output filename (e.g. a Roam
            page title or node UID); POSIX-normalized before use.
        output_dir: Directory in which the ``.pdf`` file is written; created
            if it does not already exist.
        api_endpoint: Roam Local API endpoint used to fetch image assets.
        cache_dir: Optional directory for caching downloaded image assets
            across runs.  Uses a SHA-256 hash of the Cloud Firestore URL as
            the cache key.
        template_dir: Optional directory containing a ``user_cfg.typ`` file
            that overrides the bundled Bergfink default styling.  When
            supplied, Pandoc receives ``-V user-config=<template_dir>/user_cfg.typ``
            so Bergfink loads the user-supplied config in place of the
            bundled one.  All other template files are always sourced from
            the bundled package data.
        dump_pandoc_ast: When ``True``, writes the Pandoc JSON AST (the
            serialized Panflute Doc) to
            ``<output_dir>/<normalized_filename_stem>.pandoc.json`` before
            invoking Pandoc.  Useful for debugging the intermediate
            representation.

    Raises:
        RuntimeError: If Pandoc or Typst is not found, or if the Pandoc
            conversion fails.
        FileNotFoundError: If *template_dir* is supplied but does not contain
            ``user_cfg.typ``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stem: Final[str] = shell_safe_filename(filename_stem)
    output_path: Final[Path] = output_dir / f"{stem}.pdf"

    bundled_dir: Final[Path] = _bundled_templates_dir()
    template_path: Final[Path] = bundled_dir / _TEMPLATE_ENTRY

    extra_args: list[str] = [
        "--pdf-engine=typst",
        f"--template={template_path}",
        f"--resource-path={bundled_dir}",
        f"--lua-filter={_TYPST_CALLOUT_FILTER}",
        f"--lua-filter={_TYPST_COLOR_SPAN_FILTER}",
        "-V",
        "listings=true",
    ]

    if template_dir is not None:
        user_cfg_path: Final[Path] = template_dir / _USER_CFG_FILENAME
        if not user_cfg_path.is_file():
            raise FileNotFoundError(f"template_dir={template_dir!r} does not contain {_USER_CFG_FILENAME!r}")
        extra_args.extend(["-V", f"user-config={user_cfg_path}"])
        logger.debug("using user_cfg override: %s", user_cfg_path)

    # Reproducible builds: when GUFFIN_PDF_CREATION_TIMESTAMP is set, pin Typst's PDF creation
    # date (a UNIX timestamp) so the output is byte-identical across runs.  Used by fixture tests.
    creation_timestamp: Final[str | None] = os.environ.get("GUFFIN_PDF_CREATION_TIMESTAMP")
    if creation_timestamp:
        extra_args.append(f"--pdf-engine-opt=--creation-timestamp={creation_timestamp}")
        logger.debug("pinning Typst creation timestamp to %s", creation_timestamp)

    with tempfile.TemporaryDirectory() as tmp:
        fetched: Final[tuple[VertexTree, dict[Uid, ImageRef]]] = fetch_and_enrich_images(
            vertex_tree, api_endpoint, Path(tmp), cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        image_refs: Final[dict[Uid, ImageRef]] = fetched[1]
        image_files: Final[dict[Uid, Path]] = {uid: ref.path for uid, ref in image_refs.items()}
        doc: Final[pf.Doc] = vertex_tree_to_pandoc(enriched_tree, image_files)
        resolve_vertex_links(doc, enriched_tree, _resolve_vertex_link)
        json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, stem)
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        _dump_typst_sources(json_str, output_dir, stem, template_path, bundled_dir, template_dir)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, "pdf", format="json", outputfile=str(output_path), extra_args=extra_args
        )

    logger.info("Wrote PDF to %s", output_path)
