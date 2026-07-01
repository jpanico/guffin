"""Tests for guffin.render.epub_post_processing."""

import zipfile
from pathlib import Path
from typing import Final

from guffin.render.epub_post_processing import restore_matter_divisions

_MIMETYPE: Final[str] = "application/epub+zip"

_STAMPED_DOC: Final[str] = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<html xmlns:epub="http://www.idpf.org/2007/ops">\n'
    '<body epub:type="bodymatter">\n'
    '<section id="intro" class="level1 unnumbered" epub:type="introduction" data-guffin-matter="frontmatter">\n'
    "<h1>Intro</h1>\n</section>\n</body>\n</html>\n"
)

_PLAIN_DOC: Final[str] = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<html xmlns:epub="http://www.idpf.org/2007/ops">\n'
    '<body epub:type="bodymatter">\n'
    '<section id="ch1" class="level1"><h1>Chapter</h1></section>\n</body>\n</html>\n'
)


def _write_epub(path: Path, documents: dict[str, str]) -> None:
    """Write a minimal EPUB at *path*: ``mimetype`` first (stored), then each named XHTML document."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), _MIMETYPE, compress_type=zipfile.ZIP_STORED)
        for name, xhtml in documents.items():
            archive.writestr(name, xhtml)


class TestRestoreMatterDivisions:
    """restore_matter_divisions promotes the stamped CMOS matter to <body> and strips the scaffold."""

    def test_stamped_document_body_is_rewritten(self, tmp_path: Path) -> None:
        """A document whose section carries data-guffin-matter gets that <body> division."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _STAMPED_DOC})
        restore_matter_divisions(epub)
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/ch001.xhtml").decode("utf-8")
        assert '<body epub:type="frontmatter">' in xhtml
        assert "bodymatter" not in xhtml
        assert "data-guffin-matter" not in xhtml
        # the section's own epub:type term is left intact
        assert 'epub:type="introduction"' in xhtml

    def test_unstamped_document_is_untouched(self, tmp_path: Path) -> None:
        """A document with no data-guffin-matter keeps Pandoc's original <body> division."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _PLAIN_DOC})
        restore_matter_divisions(epub)
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/ch001.xhtml").decode("utf-8")
        assert '<body epub:type="bodymatter">' in xhtml

    def test_mimetype_stays_first_and_stored(self, tmp_path: Path) -> None:
        """Repackaging preserves the EPUB's mimetype-first, uncompressed requirement."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _STAMPED_DOC})
        restore_matter_divisions(epub)
        with zipfile.ZipFile(epub) as archive:
            infos: Final[list[zipfile.ZipInfo]] = archive.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
