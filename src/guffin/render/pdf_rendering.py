"""Render a :class:`~guffin.vertex_tree.VertexTree` to a PDF via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.transcribe.roam_tree_to_guffin.transcribe` into a Panflute
:class:`~panflute.Doc` via :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc`,
then exports the document to PDF by serializing the Doc to Pandoc JSON and
invoking Pandoc via :mod:`pypandoc`.

Cloud Firestore image assets are fetched via
:func:`~guffin.render.image_fetch.fetch_and_enrich_images`, written to a temporary
directory, and embedded in the PDF as local-path
:class:`~panflute.Image` elements.  An optional *cache_dir* avoids
re-downloading unchanged assets across runs.

The Bergfink Pandoc/Typst template (bundled as package data under
``guffin/render/typst_resources/``, alongside the ``typst_*.lua`` Pandoc filters) is used by
default.  Pass *template_dir* to point at a
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

from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree, drop_attribute_assignments
from guffin.render.image_fetch import ImageRef, fetch_and_enrich_images
from guffin.render.pandoc_rendering import (
    InlineMap,
    make_resolver,
    pandoc_to_json,
    resolve_vertex_links,
    vertex_tree_to_pandoc,
)
from guffin.render.render_options import PdfRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


_TYPST_RESOURCES_PACKAGE: Final[str] = "guffin.render.typst_resources"
_CALLOUT_ICONS_PACKAGE: Final[str] = "guffin.render.callout_icons"
_TEMPLATE_ENTRY: Final[str] = "bergfink.typst"
_USER_CFG_FILENAME: Final[str] = "user_cfg.typ"
# Lua-filter filenames, resolved against the bundled typst_resources directory at render time.
_TYPST_CALLOUT_FILTER: Final[str] = "typst_callout.lua"
_TYPST_COLOR_SPAN_FILTER: Final[str] = "typst_color_span.lua"
_TYPST_LIST_PARA_FILTER: Final[str] = "typst_list_para.lua"


def _typst_resources_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/render/typst_resources/`` directory."""
    pkg_files = importlib.resources.files(_TYPST_RESOURCES_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as resources_path:
        return resources_path


def _callout_icons_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/render/callout_icons/`` directory."""
    pkg_files = importlib.resources.files(_CALLOUT_ICONS_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as resources_path:
        return resources_path


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
        extra_args=[
            f"--lua-filter={bundled_dir / _TYPST_CALLOUT_FILTER}",
            f"--lua-filter={bundled_dir / _TYPST_COLOR_SPAN_FILTER}",
            f"--lua-filter={bundled_dir / _TYPST_LIST_PARA_FILTER}",
        ],
    )
    typst_body_path: Final[Path] = output_dir / f"{stem}.body.typ"
    typst_body_path.write_text(typst_body, encoding="utf-8")
    logger.info("Wrote Typst body to %s", typst_body_path)
    typst_full_extra: list[str] = [
        f"--template={template_path}",
        f"--resource-path={bundled_dir}",
        f"--lua-filter={bundled_dir / _TYPST_CALLOUT_FILTER}",
        f"--lua-filter={bundled_dir / _TYPST_COLOR_SPAN_FILTER}",
        f"--lua-filter={bundled_dir / _TYPST_LIST_PARA_FILTER}",
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
    render_bundle: RenderBundle,
    filename_stem: str,
    api_endpoint: ApiEndpoint,
    options: PdfRenderOptions,
) -> None:
    """Render *render_bundle* to a PDF file inside ``options.output_dir``.

    Writes ``<output_dir>/<filename_stem>.pdf``.  Fetches all Cloud
    Firestore image assets into a temporary directory and enriches the vertex
    tree with each image's native pixel size via
    :func:`~guffin.render.image_fetch.fetch_and_enrich_images`, builds a Panflute
    :class:`~panflute.Doc` via
    :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc`, serializes it
    to Pandoc JSON, and invokes Pandoc (with the Typst PDF engine and the
    bundled Bergfink template) via :mod:`pypandoc` to produce the PDF.  The
    temporary image directory is removed after Pandoc completes.

    Pandoc and Typst must be installed and on ``PATH``.

    Args:
        render_bundle: The content tree (with its presentation view map) to render.
        filename_stem: Output filename stem, used verbatim to derive the output
            path; the caller is responsible for POSIX-safety.
        api_endpoint: Roam Local API endpoint used to fetch image assets.
        options: The PDF rendering options.  Reads ``output_dir`` (where the ``.pdf``
            is written; created if absent), ``cache_dir`` (optional cross-run asset
            cache keyed by a SHA-256 hash of the Cloud Firestore URL), ``template_dir``
            (optional directory with a ``user_cfg.typ`` override for the bundled
            Bergfink styling — passed to Pandoc as ``-V user-config=...`` so Bergfink
            loads it in place of the bundled default; all other template files always
            come from the bundled package data), and ``dump_pandoc_ast`` (write the
            serialized Panflute Doc to ``<output_dir>/<filename_stem>.pandoc.json``
            before invoking Pandoc).

    Raises:
        RuntimeError: If Pandoc or Typst is not found, or if the Pandoc
            conversion fails.
        FileNotFoundError: If ``options.template_dir`` is supplied but does not
            contain ``user_cfg.typ``.
    """
    output_dir: Final[Path] = options.output_dir
    cache_dir: Final[Path | None] = options.cache_dir
    template_dir: Final[Path | None] = options.template_dir
    dump_pandoc_ast: Final[bool] = options.dump_pandoc_ast
    # Attribute-assignment subtrees are pruned before the Panflute Doc build when suppressed.
    content: Final[VertexTree] = (
        drop_attribute_assignments(render_bundle.content) if options.suppress_attributes else render_bundle.content
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path: Final[Path] = output_dir / f"{filename_stem}.pdf"

    bundled_dir: Final[Path] = _typst_resources_dir()
    template_path: Final[Path] = bundled_dir / _TEMPLATE_ENTRY

    # typst_callout.lua reads this to inline the shared callout icons into gentle-clues.
    os.environ["GUFFIN_CALLOUT_ICONS_DIR"] = str(_callout_icons_dir())

    extra_args: list[str] = [
        "--pdf-engine=typst",
        f"--template={template_path}",
        f"--resource-path={bundled_dir}",
        f"--lua-filter={bundled_dir / _TYPST_CALLOUT_FILTER}",
        f"--lua-filter={bundled_dir / _TYPST_COLOR_SPAN_FILTER}",
        f"--lua-filter={bundled_dir / _TYPST_LIST_PARA_FILTER}",
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

        _dump_typst_sources(json_str, output_dir, filename_stem, template_path, bundled_dir, template_dir)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, "pdf", format="json", outputfile=str(output_path), extra_args=extra_args
        )

    logger.info("Wrote PDF to %s", output_path)
