"""Render a :class:`~guffin.vertex_tree.VertexTree` to GFM and write Markdown exports to disk.

Converts the normalized vertex tree produced by
:func:`~guffin.transcribe.roam_tree_to_guffin.transcribe` to a GFM document via the
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

import importlib.resources
import logging
from pathlib import Path
from typing import Final

_GFM_RESOURCES_PACKAGE: Final[str] = "guffin.render.gfm_resources"
# Lua-filter filenames, resolved against the bundled gfm_resources directory at render time.
_GFM_BRACKET_FILTER: Final[str] = "gfm_bracket.lua"
_GFM_CALLOUT_FILTER: Final[str] = "gfm_callout.lua"
_GFM_CODE_SOURCE_FILTER: Final[str] = "gfm_code_source.lua"
_GFM_COLOR_SPAN_FILTER: Final[str] = "gfm_color_span.lua"
_GFM_IMAGE_FILTER: Final[str] = "gfm_image.lua"
_GFM_MARK_FILTER: Final[str] = "gfm_mark.lua"
_GFM_QUOTE_FILTER: Final[str] = "gfm_quote.lua"

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
from pydantic import validate_call

from guffin.common.revision import Revision
from guffin.model.publishing_semantics import (
    drop_page_breaks,
    drop_unpublished,
    promote_non_body_sections,
    strip_element_numbers,
)
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree, drop_attribute_assignments, drop_code_sources
from guffin.render.asset_fetch import AssetRef, fetch_and_enrich_assets
from guffin.render.md_post_processing import strip_list_separator_comments
from guffin.render.pandoc_ast import InlineMap, pandoc_to_json
from guffin.render.pandoc_rendering import (
    make_resolver,
    resolve_vertex_links,
    revision_line,
    strip_pdf_placement,
    vertex_tree_to_pandoc,
)
from guffin.render.project import ProjectProfile, TopLevelDivision
from guffin.render.render_options import MarkdownRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


def _stamp_revision_metadata(doc: pf.Doc, revision: Revision | None) -> None:
    """Stamp *revision*'s one-line summary into *doc*'s ``revision`` metadata entry, in place.

    The entry carries the entire :meth:`~guffin.common.revision.Revision.summary` line —
    authored name, snapshot hash, and timestamps — so a document whose metadata is serialized
    (e.g. as YAML front matter) records exactly which content snapshot produced it.  A ``None``
    *revision* leaves *doc* untouched.

    Mutates *doc* in place; does not return a value.

    Args:
        doc: The document to rewrite.
        revision: The content revision to stamp, or ``None`` to stamp nothing.
    """
    if revision is None:
        return
    doc.metadata["revision"] = pf.MetaString(revision.summary())


def _insert_revision_line(doc: pf.Doc, revision_name: str | None) -> None:
    """Insert *revision_name* directly below *doc*'s leading title header, in place.

    The line renders as an emphasized ``revision: <name>`` paragraph — the document's
    author-declared revision name, presented where a reader looks for edition facts: right under
    the title.  A ``None`` *revision_name*, or a *doc* that does not open with a title header,
    leaves *doc* untouched.

    Mutates *doc* in place; does not return a value.

    Args:
        doc: The document to rewrite.
        revision_name: The author-declared revision name, or ``None`` to insert nothing.
    """
    if revision_name is None:
        return
    blocks: Final[list[pf.Block]] = list(doc.content)
    if not blocks or not isinstance(blocks[0], pf.Header):
        return
    doc.content.insert(1, revision_line(revision_name))


def _gfm_resources_dir() -> Path:
    """Return the absolute path to the bundled ``guffin/render/gfm_resources/`` directory."""
    pkg_files = importlib.resources.files(_GFM_RESOURCES_PACKAGE)
    # ``as_file`` gives a real filesystem path even for zipped wheels.
    with importlib.resources.as_file(pkg_files) as resources_path:
        return resources_path


@validate_call
def render(
    render_bundle: RenderBundle,
    profile: ProjectProfile,
    filename_stem: str,
    api_endpoint: ApiEndpoint,
    options: MarkdownRenderOptions,
) -> None:
    """Render *render_bundle* to a Markdown file or bundle inside ``options.output_dir``.

    Converts *render_bundle*'s content tree to a Panflute :class:`~panflute.Doc` via
    :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc` (with the page
    title rendered as an H1 header), then invokes Pandoc to produce
    GFM output.  When the profile's structural policy sets ``emit_title_page``, the GFM
    conversion runs standalone, so the document metadata (title, authors, publisher, …) is
    serialized as a YAML front-matter block ahead of the body — the format's expression of
    the directive, since an unpaginated document has no title *page*; the title renders both
    there and as the leading H1.  Whenever a title H1 is emitted, the content headings are
    demoted one level (clamped at H6) so the title contains them rather than sitting beside
    them (the ``title_in_header`` contract of ``vertex_tree_to_pandoc``).  The bundle's content revision follows the
    same split: a front-matter-emitting profile records the entire revision summary as a
    ``revision`` metadata entry in the YAML block (see :func:`_stamp_revision_metadata`),
    while a profile without front matter renders just the author-declared revision name as an
    emphasized line directly below the title H1 (see :func:`_insert_revision_line`).  Writes
    the result in one of two modes
    controlled by ``options.should_bundle``:

    - ``should_bundle=True`` (default) — fetches Cloud Firestore image and PDF assets
      via :func:`~guffin.render.asset_fetch.fetch_and_enrich_assets` (which also
      enriches the vertex tree with each image's native pixel size), places the
      assets in the bundle directory, and writes a self-contained
      ``<filename_stem>.mdbundle/`` directory containing the
      Markdown file and all assets.  Image and PDF links in the Markdown
      reference the local filenames.
    - ``should_bundle=False`` — writes the GFM text directly to
      ``<output_dir>/<filename_stem>.md`` without fetching
      assets.  :class:`~guffin.vertex.ImageVertex` and
      :class:`~guffin.vertex.PdfVertex` nodes fall back to
      hyperlinks pointing at the original Cloud Firestore URLs.

    Pandoc must be installed and on ``PATH``.

    Args:
        render_bundle: The content tree (with its presentation view map) to render.
        profile: The project profile (project type and bibliographic metadata) describing the kind
            of work being rendered.
        filename_stem: Output filename stem, used verbatim to derive the output
            path; the caller is responsible for POSIX-safety.
        api_endpoint: Roam Local API endpoint used to fetch image assets
            (bundle mode only; not called when ``options.should_bundle`` is ``False``).
        options: The Markdown rendering options.  Reads ``output_dir`` (where the
            output file or bundle is written; created if absent), ``should_bundle``
            (``.mdbundle`` directory with embedded images vs. a plain ``.md`` file),
            ``cache_dir`` (optional cross-run asset cache, ignored when ``should_bundle`` is
            ``False``), and ``dump_pandoc_ast`` (write the serialized Panflute Doc to
            ``<output_dir>/<filename_stem>.pandoc.json`` before invoking Pandoc).
    """
    logger.debug("rendering Markdown; structural_policy=%s", profile.structural_policy)
    output_dir: Final[Path] = options.output_dir
    cache_dir: Final[Path | None] = options.cache_dir
    should_bundle: Final[bool] = options.should_bundle
    dump_pandoc_ast: Final[bool] = options.dump_pandoc_ast
    # GFM's expression of the emit_title_page directive: no page model means no title page, but
    # --standalone engages Pandoc's GFM template, which serializes the document metadata (title,
    # authors, publisher, ...) as a YAML front-matter block — the format's bibliographic record.
    standalone_args: Final[list[str]] = ["--standalone"] if profile.structural_policy.emit_title_page else []
    # The authored revision name (the root's revision:: value) is bibliographic content, not
    # origin bookkeeping (that's the colophon's job): when the profile emits no front-matter
    # record to carry it (emit_title_page unset — the default profile), it renders as an
    # emphasized line directly below the title H1 instead.
    revision_name: Final[str | None] = (
        render_bundle.revision.revision
        if render_bundle.revision is not None and not profile.structural_policy.emit_title_page
        else None
    )
    # A front-matter-emitting profile records the content revision there instead: the whole
    # summary line (name + snapshot + timestamps) joins the bibliographic metadata the
    # standalone conversion serializes.
    title_page_revision: Final[Revision | None] = (
        render_bundle.revision if profile.structural_policy.emit_title_page else None
    )
    # Unpublished subtrees (publish:: false) are pruned first, so they feed neither the asset
    # fetch nor the rendered output.
    published: Final[VertexTree] = drop_unpublished(render_bundle.content)
    # Attribute-assignment subtrees are pruned before the Panflute Doc build when suppressed.
    attributed: Final[VertexTree] = drop_attribute_assignments(published) if options.suppress_attributes else published
    # Internal element numbers are authoring bookkeeping; they render only on explicit request.
    numbered: Final[VertexTree] = attributed if options.emit_element_numbers else strip_element_numbers(attributed)
    # Code-source attributions likewise render only on explicit request.
    sourced: Final[VertexTree] = numbered if options.emit_code_sources else drop_code_sources(numbered)
    # Authored page-break directives are honored only when the profile's policy says so; a
    # policy that fixes its own pagination has the tags dropped (each drop logged).  GFM output
    # expresses no page break either way — the gate is kept for policy uniformity across formats.
    paginated: Final[VertexTree] = sourced if profile.structural_policy.honor_page_breaks else drop_page_breaks(sourced)
    # In a parts book, explicit front-/back-matter sections at the root stand outside the parts:
    # promoted to part level so a ToC built from heading levels cannot nest them under the
    # preceding part.
    parts_book: Final[bool] = profile.structural_policy.top_level_division is TopLevelDivision.PART
    content: Final[VertexTree] = promote_non_body_sections(paginated) if parts_book else paginated
    gfm_dir: Final[Path] = _gfm_resources_dir()
    if should_bundle:
        bundle_dir: Final[Path] = output_dir / f"{filename_stem}.mdbundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created bundle directory: %s", bundle_dir)

        # the Paths in the returned AssetRefs are absolute
        fetched: Final[tuple[VertexTree, dict[Uid, AssetRef]]] = fetch_and_enrich_assets(
            content, api_endpoint, bundle_dir, cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        asset_refs: Final[dict[Uid, AssetRef]] = fetched[1]
        # Strip to filename-only so Pandoc writes relative asset references in the Markdown output.
        asset_files: Final[dict[Uid, Path]] = {uid: Path(ref.path.name) for uid, ref in asset_refs.items()}

        pandoc_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            enriched_tree,
            asset_files,
            render_bundle.view,
            title_in_header=True,
            provenance=render_bundle.provenance if options.emit_colophon else None,
            revision=render_bundle.revision if options.emit_colophon else None,
        )
        doc: Final[pf.Doc] = pandoc_result[0]
        inline_map: Final[InlineMap] = pandoc_result[1]
        resolve_vertex_links(doc, enriched_tree, make_resolver(inline_map, options.daily_note_format))
        # This conversion places no PDF pages, so the placement scaffold must not reach the GFM
        # writer (an attributed link falls back to a raw HTML anchor).
        strip_pdf_placement(doc)
        _insert_revision_line(doc, revision_name)
        _stamp_revision_metadata(doc, title_page_revision)
        bundle_json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, filename_stem)
        md_text: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            bundle_json_str,
            "gfm",
            format="json",
            extra_args=[
                "--wrap=none",
                *standalone_args,
                f"--lua-filter={gfm_dir / _GFM_CALLOUT_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_QUOTE_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_CODE_SOURCE_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_COLOR_SPAN_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_IMAGE_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_MARK_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_BRACKET_FILTER}",
            ],
        )
        output_file: Final[Path] = bundle_dir / f"{filename_stem}.md"
        output_file.write_text(strip_list_separator_comments(md_text), encoding="utf-8")
        logger.info("Wrote Markdown to: %s", output_file)

    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        no_bundle_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            content,
            {},
            render_bundle.view,
            title_in_header=True,
            provenance=render_bundle.provenance if options.emit_colophon else None,
            revision=render_bundle.revision if options.emit_colophon else None,
        )
        no_bundle_doc: Final[pf.Doc] = no_bundle_result[0]
        no_bundle_inline_map: Final[InlineMap] = no_bundle_result[1]
        resolve_vertex_links(no_bundle_doc, content, make_resolver(no_bundle_inline_map, options.daily_note_format))
        # This conversion places no PDF pages, so the placement scaffold must not reach the GFM
        # writer (an attributed link falls back to a raw HTML anchor).
        strip_pdf_placement(no_bundle_doc)
        _insert_revision_line(no_bundle_doc, revision_name)
        _stamp_revision_metadata(no_bundle_doc, title_page_revision)
        json_str: Final[str] = pandoc_to_json(no_bundle_doc, dump_pandoc_ast, output_dir, filename_stem)
        no_bundle_md: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str,
            "gfm",
            format="json",
            extra_args=[
                "--wrap=none",
                *standalone_args,
                f"--lua-filter={gfm_dir / _GFM_CALLOUT_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_QUOTE_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_CODE_SOURCE_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_COLOR_SPAN_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_MARK_FILTER}",
                f"--lua-filter={gfm_dir / _GFM_BRACKET_FILTER}",
            ],
        )
        output_path: Final[Path] = output_dir / f"{filename_stem}.md"
        output_path.write_text(strip_list_separator_comments(no_bundle_md), encoding="utf-8")
        logger.info("Wrote Markdown to %s", output_path)
