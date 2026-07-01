"""EPUB post-processing: restore CMOS ``<body>`` divisions on the packaged e-book.

Pandoc assigns each content document's ``<body epub:type>`` division from its own hardcoded
classification of the section's ``epub:type`` term, which diverges from the conventional (CMOS)
placement for several terms (see :mod:`guffin.render.epub_semantics`).  During rendering each
matter-tagged heading is stamped with its CMOS division in the
:data:`~guffin.render.epub_semantics.MATTER_DATA_ATTRIBUTE` section attribute; this pass rewrites the
finished ``.epub`` so every content document's ``<body epub:type>`` reflects that stamped division,
then removes the attribute so it never reaches the reader.

Public symbols:

- **Functions**: :func:`restore_matter_divisions` — rewrite an ``.epub`` in place so each content
  document's ``<body>`` division matches its stamped CMOS matter.
"""

import logging
import zipfile
from pathlib import Path
from typing import Final

import regex
from pydantic import validate_call

from guffin.render.epub_semantics import MATTER_DATA_ATTRIBUTE

logger = logging.getLogger(__name__)

_FIRST_SECTION_RE: Final[regex.Pattern[str]] = regex.compile(r"<section\b[^>]*>")
_MATTER_ATTRIBUTE_RE: Final[regex.Pattern[str]] = regex.compile(rf'\s*{regex.escape(MATTER_DATA_ATTRIBUTE)}="([^"]*)"')
_BODY_DIVISION_RE: Final[regex.Pattern[str]] = regex.compile(r'(<body\b[^>]*\bepub:type=")[^"]*(")')


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
    with zipfile.ZipFile(epub_path) as source:
        infos: Final[list[zipfile.ZipInfo]] = source.infolist()
        payloads: Final[dict[str, bytes]] = {info.filename: source.read(info.filename) for info in infos}

    for info in infos:
        if info.filename.endswith(".xhtml"):
            payloads[info.filename] = _rewrite_document(payloads[info.filename].decode("utf-8")).encode("utf-8")

    temp_path: Final[Path] = epub_path.with_name(f"{epub_path.name}.tmp")
    with zipfile.ZipFile(temp_path, "w") as target:
        for info in infos:
            target.writestr(info, payloads[info.filename])
    temp_path.replace(epub_path)
    logger.info("Restored CMOS <body> divisions in %s", epub_path)
