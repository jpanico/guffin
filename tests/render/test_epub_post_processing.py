"""Tests for guffin.render.epub_post_processing."""

import zipfile
from pathlib import Path
from typing import Final

from guffin.render.epub_post_processing import restore_matter_divisions, stamp_titlepage_revision

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


def _title_page_doc(subtitle: bool = False) -> str:
    """A minimal Pandoc-shaped title-page document, optionally carrying a subtitle paragraph."""
    subtitle_para: Final[str] = '\n  <p class="subtitle">A Subtitle</p>' if subtitle else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns:epub="http://www.idpf.org/2007/ops">\n'
        '<body epub:type="frontmatter">\n'
        '<section epub:type="titlepage" class="titlepage">\n'
        f'  <h1 class="title">Dorian Gray</h1>{subtitle_para}\n'
        '  <p class="author">Oscar Wilde</p>\n'
        "</section>\n</body>\n</html>\n"
    )


class TestStampTitlepageRevision:
    """stamp_titlepage_revision injects the authored revision name directly below the title block."""

    def test_revision_follows_the_title(self, tmp_path: Path) -> None:
        """The revision paragraph lands directly after the title heading, before the author."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/title_page.xhtml": _title_page_doc()})
        stamp_titlepage_revision(epub, "draft-3")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/title_page.xhtml").decode("utf-8")
        title_end: Final[int] = xhtml.index("</h1>")
        revision_at: Final[int] = xhtml.index('<p class="revision">revision: draft-3</p>')
        author_at: Final[int] = xhtml.index('<p class="author">')
        assert title_end < revision_at < author_at

    def test_revision_follows_the_subtitle_when_present(self, tmp_path: Path) -> None:
        """With a subtitle, the revision paragraph lands after it, keeping the title unit intact."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/title_page.xhtml": _title_page_doc(subtitle=True)})
        stamp_titlepage_revision(epub, "draft-3")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/title_page.xhtml").decode("utf-8")
        subtitle_at: Final[int] = xhtml.index('<p class="subtitle">')
        revision_at: Final[int] = xhtml.index('<p class="revision">')
        assert subtitle_at < revision_at

    def test_revision_name_is_xml_escaped(self, tmp_path: Path) -> None:
        """Markup-significant characters in the name are escaped."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/title_page.xhtml": _title_page_doc()})
        stamp_titlepage_revision(epub, "draft <3>")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/title_page.xhtml").decode("utf-8")
        assert "revision: draft &lt;3&gt;" in xhtml

    def test_non_title_page_documents_are_untouched(self, tmp_path: Path) -> None:
        """Content documents other than the title page are never stamped."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _PLAIN_DOC})
        stamp_titlepage_revision(epub, "draft-3")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/ch001.xhtml").decode("utf-8")
        assert "revision" not in xhtml

    def test_mimetype_stays_first_and_stored(self, tmp_path: Path) -> None:
        """Repackaging preserves the EPUB's mimetype-first, uncompressed requirement."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/title_page.xhtml": _title_page_doc()})
        stamp_titlepage_revision(epub, "draft-3")
        with zipfile.ZipFile(epub) as archive:
            infos: Final[list[zipfile.ZipInfo]] = archive.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
