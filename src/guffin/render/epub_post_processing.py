"""EPUB post-processing: content rewrites applied to the packaged e-book.

Two passes operate on the finished ``.epub`` (both preserve entry order, timestamps, and per-entry
compression, so the ``mimetype`` entry stays first and uncompressed):

- **CMOS division restoration.**  Pandoc assigns each content document's ``<body epub:type>``
  division from its own hardcoded classification of the section's ``epub:type`` term, which
  diverges from the conventional (CMOS) placement for several terms (see
  :mod:`guffin.render.epub_semantics`).  During rendering each matter-tagged heading is stamped
  with its CMOS division in the :data:`~guffin.render.epub_semantics.MATTER_DATA_ATTRIBUTE`
  section attribute; :func:`restore_matter_divisions` rewrites the packaged e-book so every
  content document's ``<body epub:type>`` reflects that stamped division, then removes the
  attribute so it never reaches the reader.

- **Title-page provenance.**  Pandoc's generated title page is built from the document metadata
  alone and cannot carry arbitrary extra content; :func:`stamp_titlepage_provenance` injects a
  provenance line at the foot of the generated title page after packaging.

Public symbols:

- **Functions**: :func:`restore_matter_divisions` — rewrite an ``.epub`` in place so each content
  document's ``<body>`` division matches its stamped CMOS matter;
  :func:`stamp_titlepage_provenance` — inject a provenance line at the foot of the generated
  title page.
"""

import logging
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Final
from xml.sax.saxutils import escape

import regex
from pydantic import validate_call

from guffin.render.epub_semantics import MATTER_DATA_ATTRIBUTE

logger = logging.getLogger(__name__)

_FIRST_SECTION_RE: Final[regex.Pattern[str]] = regex.compile(r"<section\b[^>]*>")
_MATTER_ATTRIBUTE_RE: Final[regex.Pattern[str]] = regex.compile(rf'\s*{regex.escape(MATTER_DATA_ATTRIBUTE)}="([^"]*)"')
_BODY_DIVISION_RE: Final[regex.Pattern[str]] = regex.compile(r'(<body\b[^>]*\bepub:type=")[^"]*(")')
_TITLE_PAGE_SUFFIX: Final[str] = "title_page.xhtml"
_SECTION_CLOSE: Final[str] = "</section>"


def _rewrite_xhtml_entries(epub_path: Path, transform: Callable[[str, str], str]) -> None:
    """Rewrite the EPUB at *epub_path* in place, applying *transform* to every XHTML entry.

    *transform* receives each entry's filename and XHTML source and returns the (possibly
    unchanged) replacement source.  Entry order, timestamps, and per-entry compression are
    preserved, so the ``mimetype`` entry stays first and uncompressed.

    Args:
        epub_path: Path to the ``.epub`` file to rewrite.
        transform: ``(filename, xhtml) -> xhtml`` mapping applied to each ``.xhtml`` entry.
    """
    with zipfile.ZipFile(epub_path) as source:
        infos: Final[list[zipfile.ZipInfo]] = source.infolist()
        payloads: Final[dict[str, bytes]] = {info.filename: source.read(info.filename) for info in infos}

    for info in infos:
        if info.filename.endswith(".xhtml"):
            payloads[info.filename] = transform(info.filename, payloads[info.filename].decode("utf-8")).encode("utf-8")

    temp_path: Final[Path] = epub_path.with_name(f"{epub_path.name}.tmp")
    with zipfile.ZipFile(temp_path, "w") as target:
        for info in infos:
            target.writestr(info, payloads[info.filename])
    temp_path.replace(epub_path)


def _rewrite_document(xhtml: str) -> str:
    """Return *xhtml* with its ``<body>`` division set from the outermost section's stamped matter.

    The outermost ``<section>`` is the one whose ``epub:type`` term Pandoc used to pick the ``<body>``
    division; if it carries :data:`~guffin.render.epub_semantics.MATTER_DATA_ATTRIBUTE`, that value
    replaces the ``<body epub:type>`` division.  The stamped attribute is then stripped from every
    section so it does not reach the reader.

    Args:
        xhtml: The content document's XHTML source.

    Returns:
        The rewritten XHTML.
    """
    result: str = xhtml
    first_section: Final[regex.Match[str] | None] = _FIRST_SECTION_RE.search(xhtml)
    if first_section is not None:
        stamped: Final[regex.Match[str] | None] = _MATTER_ATTRIBUTE_RE.search(first_section.group(0))
        if stamped is not None:
            division: Final[str] = stamped.group(1)
            result = _BODY_DIVISION_RE.sub(lambda match: f"{match.group(1)}{division}{match.group(2)}", result, count=1)
    return _MATTER_ATTRIBUTE_RE.sub("", result)


@validate_call
def restore_matter_divisions(epub_path: Path) -> None:
    """Rewrite the EPUB at *epub_path* in place so each ``<body>`` division reflects its CMOS matter.

    For every content document, promotes the CMOS division stamped on its outermost section (in
    :data:`~guffin.render.epub_semantics.MATTER_DATA_ATTRIBUTE`) to the document's ``<body
    epub:type>``, then removes the stamped attribute.  Documents without the attribute (e.g. the
    Pandoc-generated title page and navigation) are left untouched.  Entry order, timestamps, and
    per-entry compression are preserved, so the ``mimetype`` entry stays first and uncompressed.

    Args:
        epub_path: Path to the ``.epub`` file to rewrite.
    """
    _rewrite_xhtml_entries(epub_path, lambda _filename, xhtml: _rewrite_document(xhtml))
    logger.info("Restored CMOS <body> divisions in %s", epub_path)


@validate_call
def stamp_titlepage_provenance(epub_path: Path, summary: str) -> None:
    """Inject *summary* as a provenance line at the foot of the EPUB's generated title page.

    Rewrites the EPUB at *epub_path* in place: a ``<p class="provenance">`` paragraph holding the
    (XML-escaped) *summary* text is inserted at the end of the title-page document's ``titlepage``
    section, so the provenance rides the title page rather than floating at the end of the body
    content.  Entry order, timestamps, and per-entry compression are preserved, so the ``mimetype``
    entry stays first and uncompressed.

    When the package contains no generated title-page document (``title_page.xhtml``), a warning is
    logged and the EPUB is left unchanged.

    Args:
        epub_path: Path to the ``.epub`` file to rewrite.
        summary: The provenance summary line to inject (plain text; escaped for XML here).
    """
    provenance_para: Final[str] = f'  <p class="provenance">{escape(summary)}</p>\n'
    stamped_names: Final[list[str]] = []

    def _stamp(filename: str, xhtml: str) -> str:
        if not filename.endswith(_TITLE_PAGE_SUFFIX) or _SECTION_CLOSE not in xhtml:
            return xhtml
        stamped_names.append(filename)
        return xhtml.replace(_SECTION_CLOSE, f"{provenance_para}{_SECTION_CLOSE}", 1)

    _rewrite_xhtml_entries(epub_path, _stamp)
    if stamped_names:
        logger.info("Stamped title-page provenance in %s", epub_path)
    else:
        logger.warning("No title-page document found in %s; provenance not stamped", epub_path)
