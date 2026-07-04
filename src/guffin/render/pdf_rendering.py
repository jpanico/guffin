"""Render a :class:`~guffin.vertex_tree.VertexTree` to a PDF via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.transcribe.roam_tree_to_guffin.transcribe` into a Panflute
:class:`~panflute.Doc` via :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc`,
then exports the document to PDF by serializing the Doc to Pandoc JSON and
invoking Pandoc via :mod:`pypandoc`.

Cloud Firestore image assets are fetched via
:func:`~guffin.render.asset_fetch.fetch_and_enrich_assets`, written to a temporary
directory, and embedded in the PDF as local-path
:class:`~panflute.Image` elements.  Cloud Firestore PDF assets are fetched the same
way and attached to the output via Typst ``pdf.attach`` under their originally uploaded
filename; an embed tagged ``pdf-render:: inline`` additionally renders every page of
the asset in the document flow (one full-width Typst ``image`` per page), while the
untagged default keeps a hyperlink to the asset's source.  An optional *cache_dir*
avoids re-downloading unchanged assets across runs.

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
from typing import Final, NamedTuple

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
from pydantic import validate_call
from pypdf import PdfReader

from guffin.common.filenames import shell_safe_filename
from guffin.common.provenance import Provenance
from guffin.model.publishing_semantics import DEFAULT_PDF_RENDER, PdfRender, pdf_render_of_vertex
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import ImageVertex, PdfVertex
from guffin.model.vertex_tree import VertexTree, drop_attribute_assignments, drop_root_preamble
from guffin.render.asset_fetch import AssetRef, fetch_and_enrich_assets
from guffin.render.pandoc_ast import InlineMap, pandoc_to_json
from guffin.render.pandoc_rendering import (
    make_resolver,
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
        provenance: When set, passes its :meth:`~guffin.common.provenance.Provenance.summary` to the
            template — as the Bergfink ``titlepage-provenance`` variable (rendered at the foot of the
            title page) when *emit_title_page* is set, otherwise as ``footer-provenance`` (a line
            below the running page footer); ``None`` passes nothing.

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
    # In PDF the provenance rides the title page when one is emitted (at its foot), otherwise the
    # running page footer (a line below it) — never an end-of-body block.
    if provenance is not None:
        provenance_var: Final[str] = "titlepage-provenance" if emit_title_page else "footer-provenance"
        args.extend(["-V", f"{provenance_var}={provenance.summary()}"])
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


class _PdfEmbedSpec(NamedTuple):
    """Everything the Typst emission needs for one embedded PDF asset.

    Attributes:
        source_path: Local path of the fetched PDF file.
        attachment_name: Display-worthy filename the attachment carries in the produced PDF.
        pages: Number of pages in the PDF.
        render: The embed's :class:`~guffin.model.publishing_semantics.PdfRender` placement.
    """

    source_path: Path
    attachment_name: str
    pages: int
    render: PdfRender


def _typst_str(text: str) -> str:
    """Return *text* as a quoted Typst string literal (backslashes and quotes escaped)."""
    escaped: Final[str] = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _typst_raw_block(text: str) -> pf.RawBlock:
    """Return a Pandoc raw block of Typst markup.

    Panflute's ``RawBlock`` constructor validates its format against a fixed set that predates
    Pandoc's Typst support, so the format is assigned after construction (a plain attribute,
    validated only in the constructor).  Pandoc itself accepts ``typst`` raw blocks and its
    Typst writer passes them through verbatim.
    """
    raw: Final[pf.RawBlock] = pf.RawBlock(text, format="html")
    raw.format = "typst"
    return raw


def _prepare_pdf_embeds(tree: VertexTree, asset_refs: dict[Uid, AssetRef]) -> dict[str, _PdfEmbedSpec]:
    """Prepare an embed spec for every fetched PDF asset in *tree*.

    Each spec carries the fetched file's path, its page count, its
    :class:`~guffin.model.publishing_semantics.PdfRender` placement (the vertex's ``pdf-render``
    tag, defaulting per :data:`~guffin.model.publishing_semantics.DEFAULT_PDF_RENDER`), and a
    display-worthy attachment name — the originally uploaded filename when known (sanitized),
    else the deterministic storage name.  Colliding attachment names are disambiguated with the
    vertex UID; sanitized names that do not end in ``.pdf`` fall back to the storage name.

    The returned specs are keyed by the vertex's source URL — the URL its rendered link carries —
    so the Pandoc document can be matched against them.  When several PDF vertices share one
    source URL, the first (in :attr:`~guffin.model.vertex_tree.VertexTree.uid_map` order) wins.

    Args:
        tree: The vertex tree whose PDF assets to prepare.
        asset_refs: The fetched assets, as returned by
            :func:`~guffin.render.asset_fetch.fetch_assets`; PDF vertices absent from it
            (failed fetches) are skipped.

    Returns:
        A mapping from source URL to the :class:`_PdfEmbedSpec` for that PDF.
    """
    specs: Final[dict[str, _PdfEmbedSpec]] = {}
    used_names: Final[set[str]] = set()
    for vertex in tree.uid_map.values():
        if not isinstance(vertex, PdfVertex) or str(vertex.source) in specs:
            continue
        ref: AssetRef | None = asset_refs.get(vertex.uid)
        if ref is None:
            continue
        attachment_name: str = shell_safe_filename(vertex.original_file_name or "")
        if not attachment_name.lower().endswith(".pdf"):
            attachment_name = ref.path.name
        if attachment_name in used_names:
            attachment_name = f"{vertex.uid}-{attachment_name}"
        used_names.add(attachment_name)
        page_count: int = len(PdfReader(str(ref.path)).pages)
        specs[str(vertex.source)] = _PdfEmbedSpec(
            source_path=ref.path,
            attachment_name=attachment_name,
            pages=page_count,
            render=pdf_render_of_vertex(vertex) or DEFAULT_PDF_RENDER,
        )
        logger.info(
            "prepared PDF embed uid=%r -> %s (%d page(s), %s)",
            vertex.uid,
            attachment_name,
            page_count,
            specs[str(vertex.source)].render.value,
        )
    return specs


def _apply_pdf_embeds(doc: pf.Doc, specs: dict[str, _PdfEmbedSpec]) -> None:
    """Rewrite *doc*'s PDF-embed link paragraphs into their Typst form, in place.

    A PDF embed reaches the document as a paragraph containing a single link whose URL is the
    asset's source URL (see the :class:`~guffin.model.vertex.PdfVertex` rendering rules).  For
    each such paragraph with a spec in *specs*:

    - the original PDF is attached to the output once per asset via Typst ``pdf.attach``, under
      the spec's attachment name (a raw block emitted at the asset's first occurrence), and
    - a :attr:`~guffin.model.publishing_semantics.PdfRender.INLINE` embed replaces the paragraph
      with one full-width Typst ``image`` per page, while a
      :attr:`~guffin.model.publishing_semantics.PdfRender.LINK` embed keeps its link paragraph.

    Inline mentions of a PDF (a link inside surrounding prose) are left untouched.

    Args:
        doc: The Panflute document to rewrite.
        specs: Mapping from source URL to :class:`_PdfEmbedSpec`, as built by
            :func:`_prepare_pdf_embeds`.
    """
    attached: Final[set[str]] = set()

    def _action(elem: pf.Element, doc: pf.Doc) -> list[pf.Block] | None:
        if not isinstance(elem, pf.Para) or len(list(elem.content)) != 1:
            return None
        inline = list(elem.content)[0]
        if not isinstance(inline, pf.Link):
            return None
        spec: Final[_PdfEmbedSpec | None] = specs.get(inline.url)
        if spec is None:
            return None
        blocks: Final[list[pf.Block]] = []
        if inline.url not in attached:
            attached.add(inline.url)
            # Typst resolves the name as a root-relative path, so anchoring it at the root ("/")
            # makes the attachment display as the bare filename; the bytes come from read().
            blocks.append(
                _typst_raw_block(
                    f"#pdf.attach({_typst_str('/' + spec.attachment_name)}, "
                    f"read({_typst_str(str(spec.source_path))}, encoding: none))"
                )
            )
        if spec.render is PdfRender.INLINE:
            pages_markup: Final[str] = "\n".join(
                f"#image({_typst_str(str(spec.source_path))}, page: {page}, width: 100%)"
                for page in range(1, spec.pages + 1)
            )
            blocks.append(_typst_raw_block(pages_markup))
        else:
            blocks.append(elem)
        return blocks

    doc.walk(_action)


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
    :func:`~guffin.render.asset_fetch.fetch_and_enrich_assets`, builds a Panflute
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

    When ``options.provenance`` is set, its summary is rendered at the foot of the title page when one
    is emitted (``emit_title_page``), otherwise on a line below the running page footer — unlike
    Markdown/EPUB, which carry it as an end-of-document block.

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
            come from the bundled package data), ``dump_pandoc_ast`` (write the
            serialized Panflute Doc to ``<output_dir>/<filename_stem>.pandoc.json``
            before invoking Pandoc), ``include_preamble`` (keep or drop the root
            page's loose preamble; ``None`` defers to the profile policy's
            ``drop_preamble``), and ``number_sections`` (turn heading numbering on
            or off; ``None`` defers to the profile policy's ``number_sections``).

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
    # An explicit include_preamble option overrides the profile's drop_preamble directive.
    drop_preamble: Final[bool] = (
        profile.structural_policy.drop_preamble if options.include_preamble is None else not options.include_preamble
    )
    # Attribute-assignment subtrees are pruned before the Panflute Doc build when suppressed.
    stripped: Final[VertexTree] = (
        drop_attribute_assignments(render_bundle.content) if options.suppress_attributes else render_bundle.content
    )
    # Loose preamble (root-page children ahead of the first heading) is pruned so it cannot
    # strand on its own page ahead of the book's first division.
    content: Final[VertexTree] = drop_root_preamble(stripped) if drop_preamble else stripped
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

    # An explicit number_sections option overrides the profile's directive.
    number_sections: Final[bool] = (
        profile.structural_policy.number_sections if options.number_sections is None else options.number_sections
    )
    template_args: Final[list[str]] = _typst_template_args(
        bundled_dir,
        template_path,
        template_dir,
        number_sections,
        profile.structural_policy.top_level_division,
        profile.structural_policy.emit_title_page,
        render_bundle.provenance if options.emit_colophon else None,
    )
    # Typst confines file access to its project root, which Pandoc leaves at its own working
    # directory; the raw PDF-embed blocks (see _apply_pdf_embeds) read assets by absolute path
    # from a temporary directory, so the root is widened to the filesystem root.
    extra_args: list[str] = ["--pdf-engine=typst", "--pdf-engine-opt=--root=/", *template_args]

    # Reproducible builds: when GUFFIN_PDF_CREATION_TIMESTAMP is set, pin Typst's PDF creation
    # date (a UNIX timestamp) so the output is byte-identical across runs.  Used by fixture tests.
    creation_timestamp: Final[str | None] = os.environ.get("GUFFIN_PDF_CREATION_TIMESTAMP")
    if creation_timestamp:
        extra_args.append(f"--pdf-engine-opt=--creation-timestamp={creation_timestamp}")
        logger.debug("pinning Typst creation timestamp to %s", creation_timestamp)

    with tempfile.TemporaryDirectory() as tmp:
        fetched: Final[tuple[VertexTree, dict[Uid, AssetRef]]] = fetch_and_enrich_assets(
            content, api_endpoint, Path(tmp), cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        asset_refs: Final[dict[Uid, AssetRef]] = fetched[1]
        # Only image assets feed the document build: PDF vertices render as links to their
        # remote source, and _apply_pdf_embeds rewrites those into the Typst embedding below.
        asset_files: Final[dict[Uid, Path]] = {
            uid: ref.path for uid, ref in asset_refs.items() if isinstance(enriched_tree.uid_map[uid], ImageVertex)
        }
        pdf_specs: Final[dict[str, _PdfEmbedSpec]] = _prepare_pdf_embeds(enriched_tree, asset_refs)
        # The PDF provenance rides the page footer (see _typst_template_args), not an end-of-body
        # colophon, so it is deliberately not passed to vertex_tree_to_pandoc here.
        pandoc_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            enriched_tree, asset_files, render_bundle.view
        )
        doc: Final[pf.Doc] = pandoc_result[0]
        inline_map: Final[InlineMap] = pandoc_result[1]
        resolve_vertex_links(doc, enriched_tree, make_resolver(inline_map))
        _apply_pdf_embeds(doc, pdf_specs)
        json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, filename_stem)
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        _dump_typst_sources(json_str, output_dir, filename_stem, bundled_dir, template_args)

        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, "pdf", format="json", outputfile=str(output_path), extra_args=extra_args
        )

    logger.info("Wrote PDF to %s", output_path)
