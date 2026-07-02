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
:func:`~guffin.render.image_fetch.fetch_and_enrich_images`, written to a temporary directory,
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
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree, drop_attribute_assignments, drop_root_preamble
from guffin.render.epub_post_processing import restore_matter_divisions, stamp_titlepage_provenance
from guffin.render.image_fetch import ImageRef, fetch_and_enrich_images
from guffin.render.pandoc_ast import InlineMap, pandoc_to_json
from guffin.render.pandoc_rendering import (
    make_resolver,
    resolve_vertex_links,
    vertex_tree_to_pandoc,
)
from guffin.render.project import ProjectProfile, TopLevelDivision
from guffin.render.render_options import EpubRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


_EPUB_RESOURCES_PACKAGE: Final[str] = "guffin.render.epub_resources"
_CALLOUT_ICONS_PACKAGE: Final[str] = "guffin.render.callout_icons"
# Lua-filter filenames, resolved against the bundled epub_resources directory at render time.
_EPUB_COLOR_SPAN_FILTER: Final[str] = "epub_color_span.lua"
_EPUB_MARK_FILTER: Final[str] = "epub_mark.lua"
_EPUB_CALLOUT_FILTER: Final[str] = "epub_callout.lua"
_EPUB_NUMBER_LINES_FILTER: Final[str] = "epub_number_lines.lua"
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
    :func:`~guffin.render.image_fetch.fetch_and_enrich_images`, builds a Panflute
    :class:`~panflute.Doc` via :func:`~guffin.render.pandoc_rendering.vertex_tree_to_pandoc`
    (storing the page title as document metadata so it becomes the EPUB ``dc:title`` and title
    page), serializes it to Pandoc JSON, and invokes Pandoc's ``epub3`` writer via :mod:`pypandoc`
    to produce the EPUB.  The temporary image directory is removed after Pandoc completes.

    The EPUB is split into separate content files at the heading level given by ``--split-level``,
    derived from ``profile``'s structural policy: a book with parts (chapters at heading level 2)
    splits at level 2, every other project type splits at level 1 so each top-level heading begins
    a new file.  When the policy's ``number_sections`` is set, headings are numbered via Pandoc's
    ``--number-sections``.  The policy's ``emit_title_page`` drives Pandoc's ``--epub-title-page``,
    which includes (or omits) a title page generated from the document metadata.

    When ``options.emit_colophon`` is set and the bundle carries provenance, its summary rides the
    foot of the generated title page when one is emitted (stamped after packaging via
    :func:`~guffin.render.epub_post_processing.stamp_titlepage_provenance`), otherwise it is
    appended as an end-of-document colophon block — mirroring the PDF placement rules.

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
            Pandoc), and ``include_preamble`` (keep or drop the root page's loose preamble;
            ``None`` defers to the profile policy's ``drop_preamble``).

    Raises:
        RuntimeError: If Pandoc is not found, or if the Pandoc conversion fails.
    """
    logger.debug("rendering EPUB; structural_policy=%s", profile.structural_policy)
    split_level: Final[int] = _split_level_for(profile.structural_policy.top_level_division)
    number_sections: Final[bool] = profile.structural_policy.number_sections
    emit_title_page: Final[bool] = profile.structural_policy.emit_title_page
    # An explicit include_preamble option overrides the profile's drop_preamble directive.
    drop_preamble: Final[bool] = (
        profile.structural_policy.drop_preamble if options.include_preamble is None else not options.include_preamble
    )
    output_dir: Final[Path] = options.output_dir
    cache_dir: Final[Path | None] = options.cache_dir
    dump_pandoc_ast: Final[bool] = options.dump_pandoc_ast
    # Attribute-assignment subtrees are pruned before the Panflute Doc build when suppressed.
    stripped: Final[VertexTree] = (
        drop_attribute_assignments(render_bundle.content) if options.suppress_attributes else render_bundle.content
    )
    # Loose preamble (root-page children ahead of the first heading) is pruned so it cannot
    # surface as a spurious title-bearing chapter ahead of the book's first division.
    content: Final[VertexTree] = drop_root_preamble(stripped) if drop_preamble else stripped
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path: Final[Path] = output_dir / f"{filename_stem}.epub"

    epub_dir: Final[Path] = _epub_resources_dir()
    # epub_callout.lua reads this to inline the shared callout icons into the callout label.
    os.environ["GUFFIN_CALLOUT_ICONS_DIR"] = str(_callout_icons_dir())

    with tempfile.TemporaryDirectory() as tmp:
        fetched: Final[tuple[VertexTree, dict[Uid, ImageRef]]] = fetch_and_enrich_images(
            content, api_endpoint, Path(tmp), cache_dir
        )
        enriched_tree: Final[VertexTree] = fetched[0]
        image_refs: Final[dict[Uid, ImageRef]] = fetched[1]
        image_files: Final[dict[Uid, Path]] = {uid: ref.path for uid, ref in image_refs.items()}
        # The provenance rides the title page when one is emitted (stamped after packaging, below);
        # otherwise it renders as an end-of-document colophon block — mirroring the PDF placement.
        provenance: Final[Provenance | None] = render_bundle.provenance if options.emit_colophon else None
        pandoc_result: Final[tuple[pf.Doc, InlineMap]] = vertex_tree_to_pandoc(
            enriched_tree,
            image_files,
            render_bundle.view,
            provenance=None if emit_title_page else provenance,
        )
        doc: Final[pf.Doc] = pandoc_result[0]
        inline_map: Final[InlineMap] = pandoc_result[1]
        resolve_vertex_links(doc, enriched_tree, make_resolver(inline_map))
        json_str: Final[str] = pandoc_to_json(doc, dump_pandoc_ast, output_dir, filename_stem)
        logger.debug("pandoc JSON length=%d bytes, output_path=%s", len(json_str), output_path)

        extra_args: list[str] = [
            f"--lua-filter={epub_dir / _EPUB_CALLOUT_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_COLOR_SPAN_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_MARK_FILTER}",
            f"--lua-filter={epub_dir / _EPUB_NUMBER_LINES_FILTER}",
            f"--css={epub_dir / _EPUB_STYLESHEET}",
            f"--split-level={split_level}",
            # Pandoc generates an EPUB title page from the metadata by default; gate it on the policy.
            f"--epub-title-page={'true' if emit_title_page else 'false'}",
        ]
        if number_sections:
            extra_args.append("--number-sections")
        pypandoc.convert_text(  # type: ignore[no-untyped-call]
            json_str, _EPUB_WRITER, format="json", outputfile=str(output_path), extra_args=extra_args
        )

    restore_matter_divisions(output_path)
    if emit_title_page and provenance is not None:
        stamp_titlepage_provenance(output_path, provenance.summary())
    logger.info("Wrote EPUB to %s", output_path)
