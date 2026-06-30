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

from guffin.common.provenance import Provenance
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
from guffin.render.project import ProjectProfile, TopLevelDivision
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


def _typst_template_args(
    bundled_dir: Path,
    template_path: Path,
    template_dir: Path | None,
    number_sections: bool,
    top_level_division: TopLevelDivision,
    emit_title_page: bool,
    provenance: Provenance | None,
) -> list[str]:
    """Build the Pandoc args that apply the Bergfink Typst template.

    Shared by the PDF conversion and the ``GUFFIN_DUMP_TYPST`` full-Typst dump, so the dumped
    ``<stem>.full.typ`` always reflects the same template, filters, and variables as the produced
    PDF.  Excludes the PDF-engine-only flags (``--pdf-engine``, ``--pdf-engine-opt``).

    Args:
        bundled_dir: Bundled templates directory, used as Pandoc's resource path.
        template_path: Path to the Bergfink Typst template entry point.
        template_dir: Optional user template directory; when set, its ``user_cfg.typ`` is passed as
            the Bergfink ``user-config`` override.
        number_sections: When ``True``, enables the Bergfink ``number-sections`` variable.
        top_level_division: When not :attr:`TopLevelDivision.SECTION`, enables the template's book
            mode (chapters open a new page, numbered hierarchically from level 1) by passing the
            ``top-level-division`` variable; ``SECTION`` passes nothing, leaving the default layout.
        emit_title_page: When ``True``, enables the Bergfink ``titlepage`` variable so the template
            renders a title page from the document metadata; ``False`` passes nothing (no title page).
        provenance: When set, passes its :meth:`~guffin.common.provenance.Provenance.summary` as the
            Bergfink ``footer-provenance`` variable so the template renders it on a line below the
            page footer; ``None`` passes nothing (no provenance in the footer).

    Returns:
        The Pandoc ``extra_args`` that apply the template (filters, resource path, and variables).
    """
    args: Final[list[str]] = [
        f"--template={template_path}",
        f"--resource-path={bundled_dir}",
        f"--lua-filter={bundled_dir / _TYPST_CALLOUT_FILTER}",
        f"--lua-filter={bundled_dir / _TYPST_COLOR_SPAN_FILTER}",
        f"--lua-filter={bundled_dir / _TYPST_LIST_PARA_FILTER}",
        "-V",
        "listings=true",
    ]
    # Bergfink reads section numbering from its own `number-sections` variable; Pandoc's
    # `--number-sections` flag does not set it, so pass it explicitly via -V.
    if number_sections:
        args.extend(["-V", "number-sections=true"])
    # Book mode is gated on this variable; SECTION passes nothing so the default layout is unchanged.
    if top_level_division is not TopLevelDivision.SECTION:
        args.extend(["-V", f"top-level-division={top_level_division.value}"])
    # Bergfink renders a title page only when the `titlepage` variable is set; pass nothing otherwise.
    if emit_title_page:
        args.extend(["-V", "titlepage=true"])
    # In PDF the provenance rides the page footer (a line below it) rather than an end-of-body block.
    if provenance is not None:
        args.extend(["-V", f"footer-provenance={provenance.summary()}"])
    if template_dir is not None:
        args.extend(["-V", f"user-config={template_dir / _USER_CFG_FILENAME}"])
    return args


def _dump_typst_sources(
    json_str: str,
    output_dir: Path,
    stem: str,
    bundled_dir: Path,
    template_args: list[str],
) -> None:
    """Dump intermediate Typst sources for debugging when ``GUFFIN_DUMP_TYPST`` is set.

    A no-op unless the ``GUFFIN_DUMP_TYPST`` environment variable is non-empty.  When
    enabled, converts the Pandoc JSON to Typst twice and writes both files to
    *output_dir*: ``<stem>.body.typ`` (the bare body) and ``<stem>.full.typ`` (with the
    template applied, using *template_args*).  Purely a debugging aid for inspecting the Typst the
    PDF is built from; it has no effect on the produced PDF.

    Args:
        json_str: The Pandoc JSON (serialized Panflute Doc) to convert to Typst.
        output_dir: Directory the ``.typ`` files are written into.
        stem: Output filename stem, shared with the ``.pdf``.
        bundled_dir: Bundled templates directory, used as Pandoc's resource path for the bare body.
        template_args: The same template-applying Pandoc args used by the PDF conversion (from
            :func:`_typst_template_args`), so the full dump matches the produced PDF.
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
    typst_full: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
        json_str, "typst", format="json", extra_args=template_args
    )
    typst_full_path: Final[Path] = output_dir / f"{stem}.full.typ"
    typst_full_path.write_text(typst_full, encoding="utf-8")
    logger.info("Wrote full Typst (with template) to %s", typst_full_path)


@validate_call
def render(
    render_bundle: RenderBundle,
    profile: ProjectProfile,
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

    When ``profile``'s structural policy sets ``number_sections``, headings are numbered (the
    Bergfink template's ``number-sections`` variable).  When its ``top_level_division`` is not
    ``SECTION`` (i.e. a book), the template's book mode is enabled: level-1 headings (chapters) open
    on a new page and, with numbering on, are numbered hierarchically from level 1 — mirroring the
    EPUB book output.  When its ``emit_title_page`` is set, the Bergfink ``titlepage`` partial renders
    a title page from the document metadata.

    When ``options.provenance`` is set, its summary is rendered on a line below the page footer (via
    the Bergfink ``footer-provenance`` variable) — unlike Markdown/EPUB, which carry it as an
    end-of-document block.

    Pandoc and Typst must be installed and on ``PATH``.

    Args:
        render_bundle: The content tree (with its presentation view map) to render.
        profile: The project profile (project type and bibliographic metadata) describing the kind
            of work being rendered.
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
    logger.debug("rendering PDF; structural_policy=%s", profile.structural_policy)
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

    # Validate the optional user-config override up front (the -V arg itself is added by
    # _typst_template_args).
    if template_dir is not None:
        user_cfg_path: Final[Path] = template_dir / _USER_CFG_FILENAME
        if not user_cfg_path.is_file():
            raise FileNotFoundError(f"template_dir={template_dir!r} does not contain {_USER_CFG_FILENAME!r}")
        logger.debug("using user_cfg override: %s", user_cfg_path)

    template_args: Final[list[str]] = _typst_template_args(
        bundled_dir,
        template_path,
        template_dir,
        profile.structural_policy.number_sections,
        profile.structural_policy.top_level_division,
        profile.structural_policy.emit_title_page,
        options.provenance,
    )
    extra_args: list[str] = ["--pdf-engine=typst", *template_args]

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
        # The PDF provenance rides the page footer (see _typst_template_args), not an end-of-body
        # colophon, so it is deliberately not passed to vertex_tree_to_pandoc here.
        pandoc_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            enriched_tree, image_files, render_bundle.view
        )
        doc: Final[pf.Doc] = pandoc_result[0]
        inline_map: Final[InlineMap] = pandoc_result[1]
        resolve_vertex_links(doc, enriched_tree, make_resolver(inline_map))
        json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, filename_stem)
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        _dump_typst_sources(json_str, output_dir, filename_stem, bundled_dir, template_args)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, "pdf", format="json", outputfile=str(output_path), extra_args=extra_args
        )

    logger.info("Wrote PDF to %s", output_path)
