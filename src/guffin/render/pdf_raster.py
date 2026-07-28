"""Rasterise a PDF's pages to images, for formats that cannot reproduce PDF pages natively.

The PDF output path places a source PDF's pages losslessly — Typst embeds each as a Form XObject,
so its text stays selectable — but no other output format can display a PDF at all.  Reproducing
those pages in an EPUB or a Markdown bundle means rendering them to images first.

Rendering is done by ``pypdfium2`` (PDFium, the renderer in Chrome), chosen over PyMuPDF because
its BSD-3-Clause/Apache-2.0 licensing suits an MIT project where PyMuPDF's AGPL would not.

Public symbols:

- :data:`PAGE_RASTER_DPI` — the resolution rasterised pages are rendered at.
- :func:`rasterize_pages` — render every page of a PDF to a PNG file.
"""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportArgumentType=false
# Rationale: pypdfium2 ships no type stubs, so its symbols are Unknown to pyright; the suppressed
# rules fire entirely on that propagation, as they do for panflute elsewhere in this package.
# reportArgumentType too: pypdfium2's inferred signature types `scale` as int, but it documents
# and accepts a float — an integer scale would restrict rendering to whole multiples of 72 dpi.

import logging
from pathlib import Path
from typing import Final

import pypdfium2
from pydantic import validate_call

logger = logging.getLogger(__name__)

PAGE_RASTER_DPI: Final[int] = 150
"""Resolution for a rasterised page, in dots per inch.

A compromise: 150 dpi keeps small print in a booking confirmation or an e-ticket legible on a
high-density screen, while an A4 page stays around 1240×1755 — a few hundred kilobytes per page,
where 300 dpi would roughly quadruple that for a book that may carry dozens of them.
"""

_PDF_POINTS_PER_INCH: Final[int] = 72
"""PDF user-space units per inch, the base ``pypdfium2`` scales its rendering from."""


@validate_call
def rasterize_pages(source: Path, output_dir: Path, dpi: int = PAGE_RASTER_DPI) -> list[Path]:
    """Render every page of the PDF at *source* to a PNG in *output_dir*.

    Files are named after the source's stem with a page suffix (``report-p1.png``), so a document
    reproducing several PDFs keeps their pages distinguishable, and re-rendering the same source
    overwrites rather than accumulating.

    Args:
        source: The PDF to rasterise.
        output_dir: The directory to write the page images into; must already exist.
        dpi: Rendering resolution.

    Returns:
        The written page images, in page order.
    """
    document: Final[pypdfium2.PdfDocument] = pypdfium2.PdfDocument(str(source))
    try:
        written: Final[list[Path]] = []
        for number, page in enumerate(document, start=1):
            image_path: Path = output_dir / f"{source.stem}-p{number}.png"
            page.render(scale=float(dpi) / _PDF_POINTS_PER_INCH).to_pil().save(image_path)
            written.append(image_path)
        logger.info("rasterised PDF %s (%d page(s) at %d dpi)", source.name, len(written), dpi)
        return written
    finally:
        document.close()
