"""Tests for guffin.render.epub_rendering.

Each distinct EPUB is rendered once via a module-scoped fixture and shared across the assertion
tests, so the (slow) Pandoc subprocess is spawned per artifact rather than per assertion.
"""

import zipfile
from pathlib import Path
from typing import Final

import pytest
import regex
from conftest import article5_node_tree

from guffin.common.code_language import CodeLanguage
from guffin.common.filenames import shell_safe_filename
from guffin.common.provenance import Provenance
from guffin.model.attribute import Attribute, AttributeAssignment, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import CodeBlockVertex, HeadingVertex, PageVertex, TextVertex
from guffin.model.vertex_tree import VertexTree
from guffin.render.epub_rendering import render
from guffin.render.project import BookProfile, DefaultProfile, ProjectProfile
from guffin.render.render_options import EpubRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.transcribe.roam_tree_to_guffin import build_view_map, transcribe

_ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")
_ARTICLE5_STEM: Final[str] = shell_safe_filename("[[Test Article]] 5")


def _article5_bundle() -> RenderBundle:
    """Build the image-free ``[[Test Article]] 5`` render bundle (keeps the test offline)."""
    node_tree = article5_node_tree()
    return RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))


def _multi_level_bundle() -> RenderBundle:
    """A page with two level-1 headings, each containing a level-2 heading (for split tests)."""
    page: Final[PageVertex] = PageVertex(uid="page00001", title="Doc", children=["chap00001", "chap00002"])
    chap1: Final[HeadingVertex] = HeadingVertex(
        uid="chap00001", text="Chapter One", heading_level=1, children=["sec000001"]
    )
    sec1: Final[HeadingVertex] = HeadingVertex(uid="sec000001", text="Section A", heading_level=2)
    chap2: Final[HeadingVertex] = HeadingVertex(
        uid="chap00002", text="Chapter Two", heading_level=1, children=["sec000002"]
    )
    sec2: Final[HeadingVertex] = HeadingVertex(uid="sec000002", text="Section B", heading_level=2)
    return RenderBundle(content=VertexTree(tree_vertices=[page, chap1, sec1, chap2, sec2]))


def _render_epub(
    out_dir: Path,
    bundle: RenderBundle,
    profile: ProjectProfile,
    stem: str,
    suppress_attributes: bool = False,
    include_preamble: bool | None = None,
    emit_colophon: bool = False,
    number_sections: bool | None = None,
) -> Path:
    """Render *bundle* to ``<out_dir>/<stem>.epub`` and return the path."""
    render(
        bundle,
        profile=profile,
        filename_stem=stem,
        api_endpoint=_ENDPOINT,
        options=EpubRenderOptions(
            output_dir=out_dir,
            suppress_attributes=suppress_attributes,
            include_preamble=include_preamble,
            emit_colophon=emit_colophon,
            number_sections=number_sections,
        ),
    )
    return out_dir / f"{stem}.epub"


# --- Module-scoped rendered EPUB artifacts (each rendered exactly once) ------------------------


@pytest.fixture(scope="module")
def article5_default_epub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """``[[Test Article]] 5`` rendered with the default (article) profile."""
    return _render_epub(tmp_path_factory.mktemp("a5_default"), _article5_bundle(), DefaultProfile(), _ARTICLE5_STEM)


@pytest.fixture(scope="module")
def article5_suppressed_epub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """``[[Test Article]] 5`` rendered with attribute assignments suppressed."""
    return _render_epub(
        tmp_path_factory.mktemp("a5_suppressed"),
        _article5_bundle(),
        DefaultProfile(),
        _ARTICLE5_STEM,
        suppress_attributes=True,
    )


@pytest.fixture(scope="module")
def article5_book_epub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """``[[Test Article]] 5`` rendered with the book profile (which emits a title page)."""
    return _render_epub(tmp_path_factory.mktemp("a5_book"), _article5_bundle(), BookProfile(), _ARTICLE5_STEM)


@pytest.fixture(scope="module")
def code_epub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A single fenced-code-block document rendered to EPUB."""
    page: Final[PageVertex] = PageVertex(uid="page00001", title="Code", children=["codeaaaaa"])
    code: Final[CodeBlockVertex] = CodeBlockVertex(
        uid="codeaaaaa", code="print(1)\nprint(2)\nprint(3)", language=CodeLanguage.PYTHON
    )
    bundle: Final[RenderBundle] = RenderBundle(content=VertexTree(tree_vertices=[page, code]))
    return _render_epub(tmp_path_factory.mktemp("code"), bundle, DefaultProfile(), "code")


@pytest.fixture(scope="module")
def multi_level_epubs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The multi-level bundle rendered under three profiles, keyed ``article`` / ``book`` / ``parts``."""
    out: Final[Path] = tmp_path_factory.mktemp("multi_level")
    bundle: Final[RenderBundle] = _multi_level_bundle()
    return {
        "article": _render_epub(out, bundle, DefaultProfile(), "article"),  # SECTION -> split-level 1
        "book": _render_epub(out, bundle, BookProfile(), "book"),  # CHAPTER -> split-level 1
        "parts": _render_epub(out, bundle, BookProfile(with_parts=True), "parts"),  # PART -> split-level 2
        # number_sections option overrides of the profile policy:
        "book_unnumbered": _render_epub(out, bundle, BookProfile(), "book_unnumbered", number_sections=False),
        "article_numbered": _render_epub(out, bundle, DefaultProfile(), "article_numbered", number_sections=True),
    }


def _preamble_bundle() -> RenderBundle:
    """A page with a loose leading block ahead of its two chapter headings (for preamble tests)."""
    page: Final[PageVertex] = PageVertex(
        uid="page00002", title="Preamble Doc", children=["loose0001", "chap00001", "chap00002"]
    )
    loose: Final[TextVertex] = TextVertex(uid="loose0001", text="Loose preamble content")
    chap1: Final[HeadingVertex] = HeadingVertex(
        uid="chap00001", text="Chapter One", heading_level=1, children=["body00001"]
    )
    body1: Final[TextVertex] = TextVertex(uid="body00001", text="Chapter one body")
    chap2: Final[HeadingVertex] = HeadingVertex(uid="chap00002", text="Chapter Two", heading_level=1)
    return RenderBundle(content=VertexTree(tree_vertices=[page, loose, chap1, body1, chap2]))


def _meta_bundle() -> RenderBundle:
    """A one-chapter page carrying every recognised guffin-domain metadata attribute."""
    link: Final[VertexLink] = VertexLink(kind=VertexLinkKind.REFERENCE, uid="metapage1")

    def _meta(name: str, value: str) -> AttributeAssignment:
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
            values=(LiteralValue(value=value),),
        )

    page: Final[PageVertex] = PageVertex(
        uid="page00003",
        title="Meta Doc",
        children=["chap00001"],
        attribute_assignments=[
            _meta("title", "Voyage of the Beagle"),
            _meta("subtitle", "A Naturalist Abroad"),
            _meta("authors", "Charles Darwin"),
            _meta("date", "1839-01-01"),
            _meta("publisher", "Henry Colburn"),
            _meta("rights", "Public domain"),
            _meta("identifier", "urn:isbn:9780"),
        ],
    )
    chap: Final[HeadingVertex] = HeadingVertex(uid="chap00001", text="Chapter One", heading_level=1)
    return RenderBundle(content=VertexTree(tree_vertices=[page, chap]))


@pytest.fixture(scope="module")
def meta_book_epub(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The metadata bundle rendered as a book (which emits a title page)."""
    return _render_epub(tmp_path_factory.mktemp("meta_book"), _meta_bundle(), BookProfile(), "meta_book")


_PROVENANCE: Final[Provenance] = Provenance(commit="abc123", dirty=False)
_PROVENANCE_SUMMARY: Final[str] = _PROVENANCE.summary()


@pytest.fixture(scope="module")
def colophon_epubs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """A provenance-carrying bundle rendered with the colophon on, keyed ``book`` / ``article``."""
    out: Final[Path] = tmp_path_factory.mktemp("colophon")
    bundle: Final[RenderBundle] = _multi_level_bundle().with_provenance(_PROVENANCE)
    return {
        "book": _render_epub(out, bundle, BookProfile(), "book", emit_colophon=True),
        "article": _render_epub(out, bundle, DefaultProfile(), "article", emit_colophon=True),
    }


@pytest.fixture(scope="module")
def preamble_epubs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The preamble bundle rendered three ways, keyed ``book`` / ``book_kept`` / ``article``.

    A book (policy drop), a book with the preamble forced back in (``include_preamble=True``),
    and a default article (policy keep).
    """
    out: Final[Path] = tmp_path_factory.mktemp("preamble")
    bundle: Final[RenderBundle] = _preamble_bundle()
    return {
        "book": _render_epub(out, bundle, BookProfile(), "book"),
        "book_kept": _render_epub(out, bundle, BookProfile(), "book_kept", include_preamble=True),
        "article": _render_epub(out, bundle, DefaultProfile(), "article"),
    }


# --- EPUB content accessors -------------------------------------------------------------------


def _chapter_xhtml(epub_path: Path) -> str:
    """Return the first split content document (``chNNN.xhtml``) of *epub_path*."""
    with zipfile.ZipFile(epub_path) as zf:
        return next(zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith(".xhtml") and "ch" in name)


def _all_text(epub_path: Path) -> str:
    """Return every XHTML and CSS document of *epub_path* joined into one string."""
    with zipfile.ZipFile(epub_path) as zf:
        return "\n".join(zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith((".xhtml", ".css")))


def _content_file_count(epub_path: Path) -> int:
    """Count the EPUB's split content documents (``chNNN.xhtml`` spine entries)."""
    with zipfile.ZipFile(epub_path) as zf:
        return sum(1 for name in zf.namelist() if name.endswith(".xhtml") and "ch" in name)


def _has_section_numbers(epub_path: Path) -> bool:
    """Whether any EPUB content document carries Pandoc heading-numbering markup."""
    with zipfile.ZipFile(epub_path) as zf:
        xhtml: Final[str] = "\n".join(
            zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith(".xhtml")
        )
    return "header-section-number" in xhtml


def _has_title_page(epub_path: Path) -> bool:
    """Whether the EPUB package includes a generated title-page document."""
    with zipfile.ZipFile(epub_path) as zf:
        return any("title_page" in name for name in zf.namelist())


def _title_page_xhtml(epub_path: Path) -> str:
    """Return the generated title-page document of *epub_path*."""
    with zipfile.ZipFile(epub_path) as zf:
        return next(zf.read(name).decode("utf-8") for name in zf.namelist() if "title_page" in name)


def _opf(epub_path: Path) -> str:
    """Return the EPUB package document (``.opf``) of *epub_path*."""
    with zipfile.ZipFile(epub_path) as zf:
        return next(zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith(".opf"))


class TestRenderEpub:
    """Integration tests for the epub_rendering Pandoc output path.

    ``[[Test Article]] 5`` contains no images, so :func:`~guffin.render.epub_rendering.render`
    fetches nothing and the supplied :class:`~guffin.roam.local_api.ApiEndpoint` is never called.
    """

    def test_produces_valid_epub_package(self, article5_default_epub: Path) -> None:
        """Rendering article5 yields a well-formed EPUB OCF container with metadata from guffin-meta."""
        assert article5_default_epub.is_file()
        with zipfile.ZipFile(article5_default_epub) as zf:
            # OCF requires a literal `application/epub+zip` mimetype entry.
            assert zf.read("mimetype") == b"application/epub+zip"
            names: Final[list[str]] = zf.namelist()
            assert any(name.endswith("nav.xhtml") for name in names)
            assert any(name.endswith(".opf") for name in names)
            assert any(name.endswith(".xhtml") and "ch" in name for name in names)
            opf: Final[str] = zf.read(next(name for name in names if name.endswith(".opf"))).decode("utf-8")
            # The guffin-meta title attribute overrides the Roam page title, and the other
            # metadata-domain attributes populate the EPUB dc:* fields.
            assert "Source Code For Humans" in opf and "Test Article 5" not in opf
            assert "Joe Panico" in opf and "Emi Panico" in opf  # authors -> dc:creator (one each)
            assert "2027-01-01" in opf  # date -> dc:date
            assert "978-1788399081" in opf  # identifier -> dc:identifier

    def test_preserves_pill_styling(self, article5_default_epub: Path) -> None:
        """Attribute reference values render as inline-styled pill spans in the EPUB XHTML."""
        assert "background-color: #FF851C" in _chapter_xhtml(article5_default_epub)

    def test_callout_title_gets_icon(self, article5_default_epub: Path) -> None:
        """The shared SVG icon is prepended into the callout title header (no separate label)."""
        chapter: Final[str] = _chapter_xhtml(article5_default_epub)
        # The icon is inlined into the callout-title header; there is no callout-label.
        title_idx: Final[int] = chapter.find('class="callout-title"')
        assert title_idx != -1
        assert "<svg" in chapter[title_idx : title_idx + 200]
        assert "callout-label" not in chapter

    def test_code_block_gets_line_numbers(self, code_epub: Path) -> None:
        """Fenced code blocks are emitted with Pandoc line numbering (skylighting numberSource)."""
        # Pandoc may place the line-number counter CSS in the chapter <style> or a stylesheet.
        assert "numberSource" in _chapter_xhtml(code_epub)
        assert "counter(source-line)" in _all_text(code_epub)

    def test_suppress_attributes_drops_pills(self, article5_suppressed_epub: Path) -> None:
        """With suppress_attributes, the attribute pills are absent from the EPUB."""
        assert "background-color: #FF851C" not in _chapter_xhtml(article5_suppressed_epub)


class TestSplitLevel:
    """The EPUB ``--split-level`` is derived from the profile's top-level division.

    Verified through the public ``render`` by counting the EPUB's split content files: an article
    (sections) and a book without parts both keep their top-level unit at heading level 1 and split
    there (equal chunking), while a book *with* parts puts chapters at level 2 and splits deeper.
    """

    def test_split_level_follows_top_level_division(self, multi_level_epubs: dict[str, Path]) -> None:
        """SECTION and CHAPTER chunk identically (level 1); a parts-based book chunks deeper."""
        article: Final[int] = _content_file_count(multi_level_epubs["article"])
        book: Final[int] = _content_file_count(multi_level_epubs["book"])
        parts: Final[int] = _content_file_count(multi_level_epubs["parts"])
        assert article == book  # both split at heading level 1
        assert parts > book  # the parts-based book also splits at level 2


class TestNumberSections:
    """Heading numbering follows the profile's policy and the ``number_sections`` option override."""

    def test_book_numbers_headings_default_does_not(self, multi_level_epubs: dict[str, Path]) -> None:
        """A book (number_sections=True) numbers headings; the default article does not."""
        assert _has_section_numbers(multi_level_epubs["book"])
        assert not _has_section_numbers(multi_level_epubs["article"])

    def test_number_sections_option_overrides_policy(self, multi_level_epubs: dict[str, Path]) -> None:
        """number_sections=False unnumbers a book; number_sections=True numbers an article."""
        assert not _has_section_numbers(multi_level_epubs["book_unnumbered"])
        assert _has_section_numbers(multi_level_epubs["article_numbered"])


class TestTitlePage:
    """The EPUB title page follows the profile's ``emit_title_page`` (Pandoc ``--epub-title-page``)."""

    def test_book_has_title_page_default_does_not(self, article5_default_epub: Path, article5_book_epub: Path) -> None:
        """A book (emit_title_page=True) includes a title page; the default article omits it."""
        assert _has_title_page(article5_book_epub)
        assert not _has_title_page(article5_default_epub)


class TestTitlePageFields:
    """The guffin-meta metadata fields render on the generated EPUB title page and in the OPF."""

    def test_title_page_carries_all_visible_fields(self, meta_book_epub: Path) -> None:
        """Title, subtitle, author, publisher, date, and rights all render on the title page."""
        title_page: Final[str] = _title_page_xhtml(meta_book_epub)
        assert '<h1 class="title">Voyage of the Beagle</h1>' in title_page
        assert '<p class="subtitle">A Naturalist Abroad</p>' in title_page
        assert '<p class="author">Charles Darwin</p>' in title_page
        assert '<p class="publisher">Henry Colburn</p>' in title_page
        assert '<p class="date">1839-01-01</p>' in title_page
        assert '<div class="rights">Public domain</div>' in title_page

    def test_publisher_and_rights_reach_package_metadata(self, meta_book_epub: Path) -> None:
        """Publisher and rights also populate the OPF dc:* catalog metadata."""
        opf: Final[str] = _opf(meta_book_epub)
        assert "<dc:publisher>Henry Colburn</dc:publisher>" in opf
        assert "<dc:rights>Public domain</dc:rights>" in opf


class TestColophonPlacement:
    """The provenance colophon rides the title page when one is emitted, else ends the document."""

    def test_book_colophon_rides_title_page(self, colophon_epubs: dict[str, Path]) -> None:
        """A book's provenance is stamped as a paragraph at the foot of the title page."""
        title_page: Final[str] = _title_page_xhtml(colophon_epubs["book"])
        assert f'<p class="provenance">{_PROVENANCE_SUMMARY}</p>' in title_page

    def test_book_has_no_end_of_document_colophon(self, colophon_epubs: dict[str, Path]) -> None:
        """With the provenance on the title page, no colophon block trails the body content."""
        assert _all_text(colophon_epubs["book"]).count(_PROVENANCE_SUMMARY) == 1  # title page only

    def test_article_colophon_is_end_of_document(self, colophon_epubs: dict[str, Path]) -> None:
        """Without a title page, the provenance falls back to the end-of-document block."""
        assert not _has_title_page(colophon_epubs["article"])
        assert _PROVENANCE_SUMMARY in _all_text(colophon_epubs["article"])


class TestPreambleDrop:
    """The root page's loose preamble follows ``drop_preamble`` and its ``include_preamble`` override.

    Loose preamble ahead of the first heading would otherwise surface as a spurious synthetic
    chapter that Pandoc's EPUB writer titles with the document title — duplicating the title page.
    """

    def test_book_drops_preamble_by_default(self, preamble_epubs: dict[str, Path]) -> None:
        """A book's loose preamble is pruned: its text is absent and no extra chapter is split."""
        assert "Loose preamble content" not in _all_text(preamble_epubs["book"])
        assert _content_file_count(preamble_epubs["book"]) == 2  # the two chapters only

    def test_book_drop_removes_synthetic_title_chapter(self, preamble_epubs: dict[str, Path]) -> None:
        """Without preamble, no body chapter carries the document title (only the title page does)."""
        first_chapter: Final[str] = _chapter_xhtml(preamble_epubs["book"])
        assert "Chapter One" in first_chapter
        assert "Preamble Doc" not in first_chapter

    def test_include_preamble_overrides_book_drop(self, preamble_epubs: dict[str, Path]) -> None:
        """include_preamble=True forces the loose preamble back into a book render."""
        assert "Loose preamble content" in _all_text(preamble_epubs["book_kept"])
        assert _content_file_count(preamble_epubs["book_kept"]) == 3  # synthetic chapter + two chapters

    def test_article_keeps_preamble_by_default(self, preamble_epubs: dict[str, Path]) -> None:
        """A default (article) profile does not drop the preamble."""
        assert "Loose preamble content" in _all_text(preamble_epubs["article"])


def _tagged_heading(uid: str, text: str, name: str, value: str) -> HeadingVertex:
    """Build a level-1 HeadingVertex carrying a single ``<name> = value`` guffin-domain tag."""
    link: Final[VertexLink] = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
    return HeadingVertex(
        uid=uid,
        text=text,
        heading_level=1,
        attribute_assignments=[
            AttributeAssignment(
                attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
                values=(LiteralValue(value=value),),
            )
        ],
    )


_SECTION_ID_RE: Final[regex.Pattern[str]] = regex.compile(r'<section\b[^>]*\bid="([^"]*)"')
_BODY_DIVISION_RE: Final[regex.Pattern[str]] = regex.compile(r'<body\b[^>]*\bepub:type="([^"]*)"')


def _body_division_by_section_id(epub_path: Path) -> dict[str, str]:
    """Map each split content document's first ``<section>`` id to its ``<body>`` division."""
    result: Final[dict[str, str]] = {}
    with zipfile.ZipFile(epub_path) as archive:
        for name in archive.namelist():
            if not (name.endswith(".xhtml") and "ch" in name):
                continue
            xhtml: str = archive.read(name).decode("utf-8")
            section: regex.Match[str] | None = _SECTION_ID_RE.search(xhtml)
            body: regex.Match[str] | None = _BODY_DIVISION_RE.search(xhtml)
            if section is not None and body is not None:
                result[section.group(1)] = body.group(1)
    return result


class TestBodyDivisionRestoration:
    """The post-processing pass sets each content document's <body> division to its CMOS matter."""

    @pytest.fixture(scope="class")
    def tagged_book_epub(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """A book whose three chapters are an introduction, a bespoke back-matter, and a body chapter."""
        page: Final[PageVertex] = PageVertex(
            uid="page00001", title="Doc", children=["head0001a", "head0002b", "head0003c"]
        )
        bundle: Final[RenderBundle] = RenderBundle(
            content=VertexTree(
                tree_vertices=[
                    page,
                    _tagged_heading("head0001a", "Front Intro", "element-type", "introduction"),
                    _tagged_heading("head0002b", "Back Notes", "matter", "back-matter"),
                    _tagged_heading("head0003c", "Body Chapter", "element-type", "chapter"),
                ]
            )
        )
        return _render_epub(tmp_path_factory.mktemp("divisions"), bundle, BookProfile(), "divisions")

    def test_element_type_overrides_pandoc_default(self, tagged_book_epub: Path) -> None:
        """An introduction (CMOS front matter) becomes frontmatter, not Pandoc's default bodymatter."""
        assert _body_division_by_section_id(tagged_book_epub)["front-intro"] == "frontmatter"

    def test_bespoke_matter_tag_sets_division(self, tagged_book_epub: Path) -> None:
        """A bespoke matter:: back-matter section (no epub:type) becomes backmatter."""
        assert _body_division_by_section_id(tagged_book_epub)["back-notes"] == "backmatter"

    def test_body_matter_stays_bodymatter(self, tagged_book_epub: Path) -> None:
        """A body-matter chapter keeps the bodymatter division."""
        assert _body_division_by_section_id(tagged_book_epub)["body-chapter"] == "bodymatter"

    def test_scaffold_attribute_is_stripped(self, tagged_book_epub: Path) -> None:
        """The data-guffin-matter scaffold never reaches the packaged e-book."""
        assert "data-guffin-matter" not in _all_text(tagged_book_epub)
