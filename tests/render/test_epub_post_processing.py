"""Tests for guffin.render.epub_post_processing."""

import zipfile
from pathlib import Path
from typing import Final

from guffin.render.epub_post_processing import (
    bake_code_line_numbers,
    restore_matter_divisions,
    stamp_titlepage_illustrators,
    stamp_titlepage_revision,
)

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


class TestStampTitlepageIllustrators:
    """stamp_titlepage_illustrators injects the credit line directly below the author paragraphs."""

    def test_credit_follows_the_authors(self, tmp_path: Path) -> None:
        """The credit paragraph lands directly after the author run."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/title_page.xhtml": _title_page_doc()})
        stamp_titlepage_illustrators(epub, "Illustrations by Emi Panico")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/title_page.xhtml").decode("utf-8")
        author_at: Final[int] = xhtml.index('<p class="author">')
        credit_at: Final[int] = xhtml.index('<p class="illustrators">Illustrations by Emi Panico</p>')
        assert author_at < credit_at

    def test_without_authors_credit_follows_the_title_block(self, tmp_path: Path) -> None:
        """With no author paragraphs, the credit lands after the title block."""
        authorless: Final[str] = _title_page_doc().replace('  <p class="author">Oscar Wilde</p>\n', "")
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/title_page.xhtml": authorless})
        stamp_titlepage_illustrators(epub, "Illustrations by Emi Panico")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/title_page.xhtml").decode("utf-8")
        title_end: Final[int] = xhtml.index("</h1>")
        assert xhtml.index('<p class="illustrators">') > title_end

    def test_non_title_page_documents_are_untouched(self, tmp_path: Path) -> None:
        """Content documents other than the title page are never stamped."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _PLAIN_DOC})
        stamp_titlepage_illustrators(epub, "Illustrations by Emi Panico")
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/ch001.xhtml").decode("utf-8")
        assert "illustrators" not in xhtml


_NUMBERED_LISTING_DOC: Final[str] = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<html xmlns:epub="http://www.idpf.org/2007/ops">\n'
    '<body epub:type="bodymatter">\n'
    '<section id="ch1" class="level1"><h1>Chapter</h1>\n'
    '<div class="sourceCode" id="cb1">'
    '<pre class="sourceCode numberSource python numberLines"><code class="sourceCode python">'
    '<span id="cb1-1"><a href="#cb1-1" aria-hidden="true"></a><span class="kw">def</span> foo():</span>\n'
    '<span id="cb1-2"><a href="#cb1-2"></a></span>\n'
    '<span id="cb1-3"><a href="#cb1-3"></a>    <span class="cf">return</span> <span class="dv">1</span></span>\n'
    '<span id="cb1-4"><a href="#cb1-4"></a></span>\n'
    '<span id="cb1-5"><a href="#cb1-5"></a></span>\n'
    '<span id="cb1-6"><a href="#cb1-6"></a></span>\n'
    '<span id="cb1-7"><a href="#cb1-7"></a></span>\n'
    '<span id="cb1-8"><a href="#cb1-8"></a></span>\n'
    '<span id="cb1-9"><a href="#cb1-9"></a></span>\n'
    '<span id="cb1-10"><a href="#cb1-10"></a>foo()</span></code></pre></div>\n'
    "</section>\n</body>\n</html>\n"
)

_NBSP: Final[str] = "\u00a0"


class TestBakeCodeLineNumbers:
    """bake_code_line_numbers rewrites skylighting's CSS-counter gutter into literal-text numbers."""

    def _baked(self, tmp_path: Path) -> str:
        """Write the numbered-listing document into an EPUB, bake it, and return the result XHTML."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _NUMBERED_LISTING_DOC})
        bake_code_line_numbers(epub)
        with zipfile.ZipFile(epub) as archive:
            return archive.read("EPUB/text/ch001.xhtml").decode("utf-8")

    def test_line_numbers_become_literal_text(self, tmp_path: Path) -> None:
        """Each line leads with a span.line-number holding its number as literal text."""
        xhtml: Final[str] = self._baked(tmp_path)
        assert f'<span class="line-number">{_NBSP}1{_NBSP}</span><span class="kw">def</span> foo():' in xhtml
        assert f'<span class="line-number">10{_NBSP}</span>foo()' in xhtml

    def test_numbers_right_align_to_the_widest(self, tmp_path: Path) -> None:
        """Single-digit numbers are no-break-space padded to the width of the listing's widest number."""
        xhtml: Final[str] = self._baked(tmp_path)
        assert f'<span class="line-number">{_NBSP}3{_NBSP}</span>' in xhtml

    def test_per_line_spans_and_anchors_are_dissolved(self, tmp_path: Path) -> None:
        """The per-line spans and their self-link anchors are gone; highlight-token spans survive."""
        xhtml: Final[str] = self._baked(tmp_path)
        assert '<span id="cb1-' not in xhtml
        assert "<a href=" not in xhtml
        assert '<span class="cf">return</span>' in xhtml

    def test_gutter_classes_are_dropped(self, tmp_path: Path) -> None:
        """numberSource/numberLines leave the pre, and sourceCode leaves the code element."""
        xhtml: Final[str] = self._baked(tmp_path)
        assert "numberSource" not in xhtml
        assert "numberLines" not in xhtml
        assert '<pre class="sourceCode python"><code class="python">' in xhtml

    def test_document_without_listing_is_untouched(self, tmp_path: Path) -> None:
        """A document with no numberSource listing passes through byte-identical."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _PLAIN_DOC})
        bake_code_line_numbers(epub)
        with zipfile.ZipFile(epub) as archive:
            xhtml: Final[str] = archive.read("EPUB/text/ch001.xhtml").decode("utf-8")
        assert xhtml == _PLAIN_DOC

    def test_mimetype_stays_first_and_stored(self, tmp_path: Path) -> None:
        """Repackaging preserves the EPUB's mimetype-first, uncompressed requirement."""
        epub: Final[Path] = tmp_path / "book.epub"
        _write_epub(epub, {"EPUB/text/ch001.xhtml": _NUMBERED_LISTING_DOC})
        bake_code_line_numbers(epub)
        with zipfile.ZipFile(epub) as archive:
            infos: Final[list[zipfile.ZipInfo]] = archive.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
