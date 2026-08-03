"""Render a :class:`~guffin.vertex_tree.VertexTree` to an EPUB 3 file via the Pandoc object model.

Converts the normalized vertex tree produced by
:func:`~guffin.transcribe.roam_tree_to_guffin.transcribe` into a Panflute
:class:`~panflute.Doc` via :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc`,
then exports the document to EPUB by serializing the Doc to Pandoc JSON and invoking Pandoc
(its ``epub3`` writer) via :mod:`pypandoc`.

The root :class:`~guffin.vertex.PageVertex` title is stored as the Pandoc document metadata
``title``, which Pandoc maps to the EPUB ``dc:title`` (and generates a title page from); the
remaining EPUB-required metadata (a ``urn:uuid`` identifier, the date, and a language fallback)
is filled in automatically by Pandoc.  Top-level headings become the e-book's chapters via
Pandoc's default EPUB split level.

Cloud Firestore image assets are fetched via
:func:`~guffin.render.asset_fetch.fetch_and_enrich_assets`, written to a temporary directory,
and embedded in the EPUB by Pandoc's writer as local-path :class:`~panflute.Image` elements.  An
optional *cache_dir* avoids re-downloading unchanged assets across runs.

Roam color/highlight/pill styling is preserved by the bundled ``epub_*.lua`` Pandoc filters (under
``guffin/render/epub_resources/``), which emit inline-styled XHTML; ``epub_callout.lua`` also
prepends a shared SVG icon from ``guffin/render/callout_icons/`` into each callout's title header
(icon + title, mirroring the gentle-clues PDF callout).  The bundled ``epub.css`` stylesheet (same
directory) is applied via Pandoc ``--css`` and sets the e-book's font family and callout styling.

Public symbols:

- :func:`render` — fetch image assets, build the Pandoc object model, and write an EPUB file.
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
from guffin.common.revision import Revision
from guffin.model.publishing_semantics import (
    PdfRenderPlacement,
    drop_page_breaks,
    drop_unpublished,
    illustrators_of_vertex,
    promote_non_body_sections,
    strip_element_numbers,
)
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import ImageVertex
from guffin.model.vertex_tree import (
    VertexTree,
    drop_attribute_assignments,
    drop_code_sources,
    drop_root_preamble,
    root_vertex,
)
from guffin.render.asset_fetch import AssetRef, cover_image_path, fetch_and_enrich_assets, pdf_asset_paths
from guffin.render.callout_theme import callout_accent, callout_title_tint
from guffin.render.epub_post_processing import (
    bake_code_line_numbers,
    restore_matter_divisions,
    stamp_titlepage_illustrators,
    stamp_titlepage_provenance,
    stamp_titlepage_revision,
)
from guffin.render.pandoc_ast import InlineMap, pandoc_to_json
from guffin.render.pandoc_rendering import (
    PDF_PLACEMENT_ATTRIBUTE,
    colophon_summary,
    make_resolver,
    resolve_vertex_links,
    revision_line,
    vertex_tree_to_pandoc,
)
from guffin.render.pdf_appendix import (
    AppendixEntries,
    appendix_anchor,
    appendix_section,
    entry_identifier,
)
from guffin.render.pdf_placement import (
    honoured_pdf_render,
    prune_emptied_list_containers,
    requested_pdf_render,
    warn_unresolvable_external_link,
)
from guffin.render.pdf_raster import rasterize_pages
from guffin.render.project import ProjectProfile, ProjectType, TopLevelDivision
from guffin.render.render_options import EpubRenderOptions, OutputFormat
from guffin.roam.blockquote import CalloutType
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


_EPUB_RESOURCES_PACKAGE: Final[str] = "guffin.render.epub_resources"
_CALLOUT_ICONS_PACKAGE: Final[str] = "guffin.render.callout_icons"
# Lua-filter filenames, resolved against the bundled epub_resources directory at render time.
_EPUB_BULLET_FILTER: Final[str] = "epub_bullet.lua"
_EPUB_COLOR_SPAN_FILTER: Final[str] = "epub_color_span.lua"
_EPUB_MARK_FILTER: Final[str] = "epub_mark.lua"
_EPUB_CALLOUT_FILTER: Final[str] = "epub_callout.lua"
_EPUB_NUMBER_LINES_FILTER: Final[str] = "epub_number_lines.lua"
_EPUB_TODO_FILTER: Final[str] = "epub_todo.lua"
# Bundled default stylesheet (the customization point for the e-book's font family).
_EPUB_STYLESHEET: Final[str] = "epub.css"
# Pandoc EPUB writer name (EPUB 3).
_EPUB_WRITER: Final[str] = "epub3"


def _epub_resources_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/render/epub_resources/`` directory."""
    pkg_files = importlib.resources.files(_EPUB_RESOURCES_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as resources_path:
        return resources_path


def _callout_icons_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/render/callout_icons/`` directory."""
    pkg_files = importlib.resources.files(_CALLOUT_ICONS_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as resources_path:
        return resources_path


def _callout_colors_css() -> str:
    """Return the per-type callout colour CSS, generated from the canonical palette.

    One left-accent-bar rule and one title-band tint rule per
    :class:`~guffin.roam.blockquote.CalloutType`, derived from the single-source palette
    (:func:`~guffin.render.callout_theme.callout_accent` /
    :func:`~guffin.render.callout_theme.callout_title_tint`).  Loaded after ``epub.css`` so these
    per-type colours win over its structural defaults; this is why ``epub.css`` no longer hardcodes
    them.
    """
    rules: Final[list[str]] = []
    for callout_type in CalloutType:
        suffix: str = callout_type.value.lower()
        rules.append(f"div.callout-{suffix} {{ border-left-color: {callout_accent(callout_type)}; }}")
        rules.append(
            f"div.callout-{suffix} > div.callout-title {{ background-color: {callout_title_tint(callout_type)}; }}"
        )
    return "\n".join(rules) + "\n"


def _split_level_for(division: TopLevelDivision) -> int:
    """Return the Pandoc EPUB ``--split-level`` for a top-level *division*.

    Pandoc splits an EPUB into separate content files at headings of this level (valid range 1-6).
    The split should fall on the heading level where a standalone "chapter" unit begins: a book
    with parts puts chapters at level 2 (parts occupy level 1), so it splits at 2; every other
    division keeps the top-level unit at level 1 and splits there.

    Args:
        division: The top-level structural division the highest headings represent.

    Returns:
        The ``--split-level`` value: ``2`` for :attr:`TopLevelDivision.PART`, otherwise ``1``.
    """
    return 2 if division is TopLevelDivision.PART else 1


PDF_PAGE_CLASS: Final[str] = "pdf-page"
"""Class on a rasterised appendix page image, so ``epub.css`` can bound its height.

A page image is about 1.4 times as tall as the column is wide, so at full width it cannot fit
under its own heading and a reading system pushes it to the next screen — stranding the heading.
The stylesheet caps it, and asks the reader to keep each entry's heading
(:data:`~guffin.render.pdf_appendix.APPENDIX_ENTRY_CLASS`) with what follows.
"""


def _page_images(source: Path, image_dir: Path) -> list[pf.Block]:
    """Reproduce every page of the PDF at *source* as a rasterised image block."""
    return [
        pf.Para(pf.Image(pf.Str(f"page {number}"), url=str(image), title=f"page {number}", classes=[PDF_PAGE_CLASS]))
        for number, image in enumerate(rasterize_pages(source, image_dir), start=1)
    ]


def _apply_pdf_appendix(
    doc: pf.Doc,
    asset_paths: dict[str, Path],
    project_type: ProjectType,
    image_dir: Path,
    default_override: PdfRenderPlacement | None = None,
) -> None:
    """Resolve every PDF embed for EPUB output, reproducing appendix-placed PDFs as page images.

    EPUB cannot display a PDF, so an
    :attr:`~guffin.model.publishing_semantics.PdfRenderPlacement.APPENDIX_IMAGE` occurrence has its pages
    rasterised into *image_dir* and reproduced in a generated back-matter appendix, with an
    intra-publication link left where the PDF was embedded.  Every other placement is a reference
    — a link to the hosted original, or the bare filename — except a
    :attr:`~guffin.model.publishing_semantics.PdfRenderPlacement.STRIP` occurrence, which is
    removed outright, as though the embed were absent.

    Args:
        doc: The Panflute document to rewrite.
        asset_paths: Mapping from source URL to the fetched PDF's local path.
        project_type: The kind of work being produced, which selects the default placement.
        image_dir: Directory the rasterised page images are written into; Pandoc embeds them into
            the package from there.
        default_override: The placement an untagged occurrence resolves to instead of the
            built-in default matrix; an authored stamp always outranks it.
    """
    appendix: Final[AppendixEntries] = {}
    stripped: Final[list[bool]] = []

    def _action(elem: pf.Element, doc: pf.Doc) -> list[pf.Block] | None:
        if not isinstance(elem, pf.Para) or len(list(elem.content)) != 1:
            return None
        link = list(elem.content)[0]
        if not isinstance(link, pf.Link) or PDF_PLACEMENT_ATTRIBUTE not in link.attributes:
            return None
        requested: Final[PdfRenderPlacement] = requested_pdf_render(
            link, OutputFormat.EPUB, project_type, default_override=default_override
        )
        if requested is PdfRenderPlacement.STRIP:
            # A stripped occurrence vanishes regardless of fetch state — no pages, link, or name.
            stripped.append(True)
            return []
        path: Final[Path | None] = asset_paths.get(link.url)
        if path is None:
            # A failed fetch: the link to the remote source stays, minus the scaffold attribute.
            link.attributes.pop(PDF_PLACEMENT_ATTRIBUTE, None)
            return None
        placement: Final[PdfRenderPlacement] = honoured_pdf_render(requested, OutputFormat.EPUB, uid=path.name)
        del link.attributes[PDF_PLACEMENT_ATTRIBUTE]
        if placement is PdfRenderPlacement.APPENDIX_IMAGE:
            label: Final[list[pf.Inline]] = list(link.content)
            return [appendix_anchor(label, entry_identifier(appendix, path, label))]
        if placement is PdfRenderPlacement.NAME_ONLY:
            return [pf.Para(*list(link.content))]
        if placement is PdfRenderPlacement.EXTERNAL_LINK:
            warn_unresolvable_external_link(link.title, str(link.url))
        return None

    doc.walk(_action)
    if stripped:
        prune_emptied_list_containers(doc)
    if appendix:
        doc.content.extend(appendix_section(appendix, lambda path: _page_images(path, image_dir)))


@validate_call
def render(
    render_bundle: RenderBundle,
    profile: ProjectProfile,
    filename_stem: str,
    api_endpoint: ApiEndpoint,
    options: EpubRenderOptions,
) -> None:
    """Render *render_bundle* to an EPUB file inside ``options.output_dir``.

    Writes ``<output_dir>/<filename_stem>.epub``.  Fetches all Cloud Firestore image assets into
    a temporary directory and enriches the vertex tree with each image's native pixel size via
    :func:`~guffin.render.asset_fetch.fetch_and_enrich_assets`, builds a Panflute
    :class:`~panflute.Doc` via :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc`
    (storing the page title as document metadata so it becomes the EPUB ``dc:title`` and title
    page), serializes it to Pandoc JSON, and invokes Pandoc's ``epub3`` writer via :mod:`pypandoc`
    to produce the EPUB.  The temporary image directory is removed after Pandoc completes.

    The EPUB is split into separate content files at the heading level given by ``--split-level``,
    derived from ``profile``'s structural policy: a book with parts (chapters at heading level 2)
    splits at level 2, every other project type splits at level 1 so each top-level heading begins
    a new file.  When the policy's ``number_sections`` is set (subject to the option override
    below), headings are numbered via Pandoc's ``--number-sections``.  The policy's
    ``emit_title_page`` drives Pandoc's ``--epub-title-page``, which includes (or omits) a title
    page generated from the document metadata.

    When ``options.emit_colophon`` is set and the bundle carries provenance, its summary rides the
    foot of the generated title page when one is emitted (stamped after packaging via
    :func:`~guffin.render.epub_post_processing.stamp_titlepage_provenance`), otherwise it is
    appended as an end-of-document colophon block — mirroring the PDF placement rules.  When the
    bundle's revision carries an author-declared revision name, it renders independent of the
    colophon: stamped directly below the title on the generated title page when one is emitted
    (via :func:`~guffin.render.epub_post_processing.stamp_titlepage_revision`, mirroring the PDF
    title page), otherwise inserted as the emphasized first block of the reading flow — the
    first thing a reader sees on opening the book, since the body carries no title of its own.
    When the root declares ``illustrators`` and a title page is emitted, an illustration credit
    line is stamped directly below the authors (via
    :func:`~guffin.render.epub_post_processing.stamp_titlepage_illustrators`), since Pandoc's
    generated title page renders creators but not contributors.

    Code listings are rewritten after packaging so their line numbers are literal text rather
    than skylighting's CSS-counter gutter (via
    :func:`~guffin.render.epub_post_processing.bake_code_line_numbers`), which reading systems
    without CSS-counter/positioning support (notably the Kindle app) cannot render.

    Pandoc must be installed and on ``PATH``.

    Args:
        render_bundle: The content tree (with its presentation view map) to render.
        profile: The project profile (project type and bibliographic metadata) describing the kind
            of work being rendered.  Its structural policy's ``top_level_division`` selects the
            EPUB ``--split-level``.
        filename_stem: Output filename stem, used verbatim to derive the output path; the caller
            is responsible for POSIX-safety.
        api_endpoint: Roam Local API endpoint used to fetch image assets.
        options: The EPUB rendering options.  Reads ``output_dir`` (where the ``.epub`` is written;
            created if absent), ``cache_dir`` (optional cross-run asset cache), ``suppress_attributes``
            (drop Roam attribute assignments before the build), ``dump_pandoc_ast`` (write the
            serialized Panflute Doc to ``<output_dir>/<filename_stem>.pandoc.json`` before invoking
            Pandoc), ``include_preamble`` (keep or drop the export root's loose preamble; ``None``
            defers to the profile policy's ``drop_preamble``), and ``number_sections`` (turn
            heading numbering on or off; ``None`` defers to the profile policy's
            ``number_sections``).

    Raises:
        RuntimeError: If Pandoc is not found, or if the Pandoc conversion fails.
    """
    logger.debug("rendering EPUB; structural_policy=%s", profile.structural_policy)
    split_level: Final[int] = _split_level_for(profile.structural_policy.top_level_division)
    # An explicit number_sections option overrides the profile's directive.
    number_sections: Final[bool] = (
        profile.structural_policy.number_sections if options.number_sections is None else options.number_sections
    )
    emit_title_page: Final[bool] = profile.structural_policy.emit_title_page
    # An explicit include_preamble option overrides the profile's drop_preamble directive.
    drop_preamble: Final[bool] = (
        profile.structural_policy.drop_preamble if options.include_preamble is None else not options.include_preamble
    )
    output_dir: Final[Path] = options.output_dir
    cache_dir: Final[Path | None] = options.cache_dir
    dump_pandoc_ast: Final[bool] = options.dump_pandoc_ast
    # Unpublished subtrees (publish:: false) are pruned first, so they feed neither the asset
    # fetch nor any later structural decision.
    published: Final[VertexTree] = drop_unpublished(render_bundle.content)
    # Attribute-assignment subtrees are pruned before the Panflute Doc build when suppressed.
    stripped: Final[VertexTree] = drop_attribute_assignments(published) if options.suppress_attributes else published
    # Internal element numbers are authoring bookkeeping; they render only on explicit request.
    numbered: Final[VertexTree] = stripped if options.emit_element_numbers else strip_element_numbers(stripped)
    # Code-source attributions likewise render only on explicit request.
    sourced: Final[VertexTree] = numbered if options.emit_code_sources else drop_code_sources(numbered)
    # Authored page-break directives are honored only when the profile's policy says so; a
    # policy that fixes its own pagination has the tags dropped (each drop logged).
    paginated: Final[VertexTree] = sourced if profile.structural_policy.honor_page_breaks else drop_page_breaks(sourced)
    # In a parts book, explicit front-/back-matter sections at the root stand outside the parts:
    # promoted to part level so the nav (nested by heading level) cannot adopt them into the
    # preceding part.
    parts_book: Final[bool] = profile.structural_policy.top_level_division is TopLevelDivision.PART
    promoted: Final[VertexTree] = promote_non_body_sections(paginated) if parts_book else paginated
    # Loose preamble (root children ahead of the first heading) is pruned so it cannot
    # surface as a spurious title-bearing chapter ahead of the book's first division.
    content: Final[VertexTree] = drop_root_preamble(promoted) if drop_preamble else promoted
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path: Final[Path] = output_dir / f"{filename_stem}.epub"

    epub_dir: Final[Path] = _epub_resources_dir()
    # epub_callout.lua reads this to inline the shared callout icons into the callout label.
    os.environ["GUFFIN_CALLOUT_ICONS_DIR"] = str(_callout_icons_dir())

    with tempfile.TemporaryDirectory() as tmp:
        fetched: Final[tuple[VertexTree, dict[Uid, AssetRef]]] = fetch_and_enrich_assets(
            content, api_endpoint, Path(tmp), cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        asset_refs: Final[dict[Uid, AssetRef]] = fetched[1]
        # Only image assets feed the document build: a PDF asset cannot be embedded in this
        # format yet, and a link to its temporary local path would be dead in the output, so
        # PdfVertex entries are withheld and render as links to their remote source.
        asset_files: Final[dict[Uid, Path]] = {
            uid: ref.path for uid, ref in asset_refs.items() if isinstance(enriched_tree.uid_map[uid], ImageVertex)
        }
        # A root-declared cover-image attribute supplies the package cover (content-driven,
        # whatever the profile): Pandoc generates the cover document and manifest entry from it.
        cover_path: Final[Path | None] = cover_image_path(content, asset_refs)
        # The colophon (software provenance + content revision) rides the title page when one is
        # emitted (stamped after packaging, below); otherwise it renders as an end-of-document
        # colophon block — mirroring the PDF placement.
        provenance: Final[Provenance | None] = render_bundle.provenance if options.emit_colophon else None
        revision: Final[Revision | None] = render_bundle.revision if options.emit_colophon else None
        pandoc_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            enriched_tree,
            asset_files,
            render_bundle.view,
            provenance=None if emit_title_page else provenance,
            revision=None if emit_title_page else revision,
        )
        doc: Final[pf.Doc] = pandoc_result[0]
        inline_map: Final[InlineMap] = pandoc_result[1]
        resolve_vertex_links(doc, enriched_tree, make_resolver(inline_map, options.daily_note_format))
        # Appendix-placed PDFs are rasterised into the asset directory and reproduced at the
        # back; every other placement is a reference.  Either way the scaffold must not reach the
        # XHTML output as a stray attribute.
        _apply_pdf_appendix(
            doc,
            pdf_asset_paths(enriched_tree, asset_refs),
            profile.project_type,
            Path(tmp),
            default_override=options.default_pdf_render,
        )
        # Without a title page to stamp, the authored revision name leads the reading flow
        # instead — the first block a reader sees on opening the book (the EPUB body carries no
        # title of its own; dc:title lives in the package metadata).
        if not emit_title_page and render_bundle.revision is not None and render_bundle.revision.revision is not None:
            doc.content.insert(0, revision_line(render_bundle.revision.revision))
        json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, filename_stem)
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        # The per-type callout colours are generated from the canonical palette into a second
        # stylesheet, loaded after epub.css so they win over its structural defaults.
        callout_colors_css: Final[Path] = Path(tmp) / "callout_colors.css"
        callout_colors_css.write_text(_callout_colors_css(), encoding="utf-8")

        extra_args: list[str] = [
            f"--lua-filter={epub_dir / _EPUB_BULLET_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_CALLOUT_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_COLOR_SPAN_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_MARK_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_TODO_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_NUMBER_LINES_FILTER}",
            f"--css={epub_dir / _EPUB_STYLESHEET}",
            f"--css={callout_colors_css}",
            f"--split-level={split_level}",
            # Pandoc generates an EPUB title page from the metadata by default; gate it on the policy.
            f"--epub-title-page={'true' if emit_title_page else 'false'}",
        ]
        if cover_path is not None:
            extra_args.append(f"--epub-cover-image={cover_path}")
        if number_sections:
            extra_args.append("--number-sections")
        # The emit_toc directive is deliberately unmapped in this format: Pandoc always generates
        # the EPUB 3 nav document, which reading systems surface as their own ToC affordance —
        # that alone expresses "the work presents a navigable ToC".  Passing --toc would place the
        # nav document in the spine as well, presenting a second, redundant ToC page.
        #
        # Deliberately NO --toc-depth cap either: Pandoc emits a spec-correct, full-depth nav.
        # Apple Books has a long-standing bug (reported since 2016, still unfixed) rendering
        # 3-level-deep nav ToCs — when the ToC returns one level from its deepest item (e.g. a
        # part > chapter > section run, then the next chapter), Apple Books floats that sibling to
        # the top level instead of one level back, so a chapter reads as a part.  This is Apple's
        # bug, not ours: the nav is correct EPUB 3, and Calibre and the Kindle app both render it
        # correctly.  We keep the correct nav rather than flatten the ToC to compensate.
        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, _EPUB_WRITER, format="json", outputfile=str(output_path), extra_args=extra_args
        )

    restore_matter_divisions(output_path)
    bake_code_line_numbers(output_path)
    if emit_title_page and (provenance is not None or revision is not None):
        stamp_titlepage_provenance(output_path, colophon_summary(provenance, revision))
    # The authored revision name rides the title page directly below the title — content, not
    # origin bookkeeping, so independent of the colophon above (mirroring the PDF title page).
    if emit_title_page and render_bundle.revision is not None and render_bundle.revision.revision is not None:
        stamp_titlepage_revision(output_path, render_bundle.revision.revision)
    # Pandoc's generated title page renders creators but not contributors, so the illustration
    # credit is stamped below the authors — mirroring the PDF title page.
    illustrator_names: Final[tuple[str, ...]] = illustrators_of_vertex(root_vertex(content))
    if emit_title_page and illustrator_names:
        stamp_titlepage_illustrators(output_path, f"Illustrations by {', '.join(illustrator_names)}")
    logger.info("Wrote EPUB to %s", output_path)
