"""Tests for guffin.render.epigraph_page, and the book epigraph's page in each rendered format."""

import re
import zipfile
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pytest
from pypdf import PdfReader

from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import HeadingVertex, PageVertex, QuoteBlockVertex, QuoteType, TextVertex, Vertex
from guffin.model.vertex_link import VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree
from guffin.render.epigraph_page import BOOK_EPIGRAPH_CLASS, lift_leading_epigraphs
from guffin.render.epub_rendering import render as render_epub
from guffin.render.pandoc_rendering import EPIGRAPH_CLASS
from guffin.render.pdf_rendering import render as render_pdf
from guffin.render.project import ArticleProfile, BookProfile
from guffin.render.render_options import EpubRenderOptions, PdfRenderOptions
from guffin.roam.local_api import ApiEndpoint

pytestmark = pytest.mark.pandoc

_ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")
_BOOK_EPIGRAPH: Final[str] = "Programming is an unnatural act."
_CHAPTER_EPIGRAPH: Final[str] = "Within a computer natural language is unnatural."


def _epigraph_div(text: str) -> pf.Div:
    return pf.Div(pf.Div(pf.Para(pf.Str(text)), classes=["epigraph-text"]), classes=[EPIGRAPH_CLASS])


def _book_tree(*, by_reference: bool = False) -> VertexTree:
    """A one-chapter book opening on an epigraph, with a second epigraph under the chapter heading.

    With *by_reference*, the leading block is a standalone block reference to the epigraph, which
    lives on another page (a referenced vertex), as a collection page's epigraph is referenced.
    """
    lead: Final[str] = "epiref001" if by_reference else "epigr0001"
    page: Final[PageVertex] = PageVertex(uid="page00001", title="Epigraph Book", children=[lead, "chap00001"])
    epigraph: Final[QuoteBlockVertex] = QuoteBlockVertex(
        uid="epigr0001", quote_type=QuoteType.EPIGRAPH, quote=_BOOK_EPIGRAPH, attribution="Alan Perlis"
    )
    chapter: Final[HeadingVertex] = HeadingVertex(
        uid="chap00001", text="The First Chapter", heading_level=1, children=["chapepi01", "body00001"]
    )
    chapter_epigraph: Final[QuoteBlockVertex] = QuoteBlockVertex(
        uid="chapepi01", quote_type=QuoteType.EPIGRAPH, quote=_CHAPTER_EPIGRAPH, attribution="Alan Perlis"
    )
    body: Final[TextVertex] = TextVertex(uid="body00001", text="The chapter's first paragraph.")
    tree_vertices: Final[list[Vertex]] = [page, chapter, chapter_epigraph, body]
    if by_reference:
        reference: Final[TextVertex] = TextVertex(
            uid="epiref001", text=f"[{_BOOK_EPIGRAPH}]({vertex_link_url('epigr0001', VertexLinkKind.REFERENCE)})"
        )
        return VertexTree(tree_vertices=[*tree_vertices, reference], ref_vertices=[epigraph])
    return VertexTree(tree_vertices=[*tree_vertices, epigraph])


class TestLiftLeadingEpigraphs:
    """lift_leading_epigraphs takes the run of epigraph Divs at the head of a document."""

    def test_lifts_the_leading_run_and_stops_at_the_first_other_block(self) -> None:
        """Two leading epigraphs are lifted in order; the heading and what follows stay."""
        first, second = _epigraph_div("One"), _epigraph_div("Two")
        header: Final[pf.Header] = pf.Header(pf.Str("Chapter"), level=1)
        trailing: Final[pf.Div] = _epigraph_div("Under the chapter")
        doc: Final[pf.Doc] = pf.Doc(first, second, header, trailing)
        lifted: Final[list[pf.Block]] = lift_leading_epigraphs(doc)
        assert lifted == [first, second]
        assert list(doc.content) == [header, trailing]

    def test_nothing_lifted_when_the_document_opens_on_another_block(self) -> None:
        """A paragraph or heading first means no epigraph leads: the document is untouched."""
        para: Final[pf.Para] = pf.Para(pf.Str("A loose paragraph."))
        epigraph: Final[pf.Div] = _epigraph_div("Not leading")
        doc: Final[pf.Doc] = pf.Doc(para, epigraph)
        assert lift_leading_epigraphs(doc) == []
        assert list(doc.content) == [para, epigraph]

    def test_empty_document(self) -> None:
        """An empty document lifts nothing."""
        assert lift_leading_epigraphs(pf.Doc()) == []


def _page_texts(pdf_path: Path) -> list[str]:
    return [" ".join((page.extract_text() or "").split()) for page in PdfReader(pdf_path).pages]


class TestBookEpigraphPdf:
    """A book PDF sets the leading epigraph on a page of its own between the title page and the contents."""

    @pytest.mark.parametrize("by_reference", [False, True], ids=["authored", "referenced"])
    def test_epigraph_page_precedes_the_contents(self, tmp_path: Path, by_reference: bool) -> None:
        """Page 2 holds the book epigraph alone; the contents open on page 3; the chapter epigraph stays put."""
        render_pdf(
            RenderBundle(content=_book_tree(by_reference=by_reference), view={}),
            profile=BookProfile(),
            filename_stem="epi",
            api_endpoint=_ENDPOINT,
            options=PdfRenderOptions(output_dir=tmp_path),
        )
        pages: Final[list[str]] = _page_texts(tmp_path / "epi.pdf")
        assert "Epigraph Book" in pages[0]
        assert _BOOK_EPIGRAPH in pages[1] and "Alan Perlis" in pages[1]
        assert "Table of contents" not in pages[1] and "The First Chapter" not in pages[1]
        assert "Table of contents" in pages[2]
        assert [index for index, text in enumerate(pages) if _BOOK_EPIGRAPH in text] == [1]
        chapter_page: Final[int] = next(index for index, text in enumerate(pages) if "first paragraph" in text)
        assert _CHAPTER_EPIGRAPH in pages[chapter_page]

    def test_article_keeps_the_epigraph_in_the_flow(self, tmp_path: Path) -> None:
        """An article has no front matter to set it in: the epigraph opens the body, under the title."""
        render_pdf(
            RenderBundle(content=_book_tree(), view={}),
            profile=ArticleProfile(),
            filename_stem="epi",
            api_endpoint=_ENDPOINT,
            options=PdfRenderOptions(output_dir=tmp_path),
        )
        pages: Final[list[str]] = _page_texts(tmp_path / "epi.pdf")
        assert "Epigraph Book" in pages[0] and _BOOK_EPIGRAPH in pages[0] and "The First Chapter" in pages[0]


def _entries(epub_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(epub_path) as package:
        return {name: package.read(name).decode("utf-8") for name in package.namelist() if not name.endswith(".png")}


def _content_documents(entries: dict[str, str]) -> dict[str, str]:
    """The split content documents (``EPUB/text/chNNN.xhtml``), leaving out the nav, title page, and styles."""
    return {name: text for name, text in entries.items() if "/text/ch" in name and name.endswith(".xhtml")}


def _epigraph_document(entries: dict[str, str]) -> tuple[str, str]:
    """The content document holding the book-epigraph Div, as ``(name, xhtml)``."""
    marker: Final[str] = f'<div class="{BOOK_EPIGRAPH_CLASS}"'
    return next((name, text) for name, text in _content_documents(entries).items() if marker in text)


def _spine_hrefs(opf: str) -> list[str]:
    hrefs: Final[dict[str, str]] = {}
    for item in re.findall(r"<item\b[^>]*>", opf):
        item_id, href = re.search(r'id="([^"]+)"', item), re.search(r'href="([^"]+)"', item)
        if item_id and href:
            hrefs[item_id.group(1)] = href.group(1)
    return [hrefs[idref] for idref in re.findall(r'<itemref\b[^>]*idref="([^"]+)"', opf)]


class TestBookEpigraphEpub:
    """A book EPUB gives the leading epigraph a front-matter document of its own, unlisted in the navigation."""

    @pytest.fixture(scope="class")
    def entries(self, tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
        """The one-chapter book, its epigraph a block reference, rendered as a book EPUB and unpacked."""
        out_dir: Final[Path] = tmp_path_factory.mktemp("epigraph-epub")
        render_epub(
            RenderBundle(content=_book_tree(by_reference=True), view={}),
            profile=BookProfile(),
            filename_stem="epi",
            api_endpoint=_ENDPOINT,
            options=EpubRenderOptions(output_dir=out_dir),
        )
        return _entries(out_dir / "epi.epub")

    def test_document_follows_the_title_page_in_the_spine(self, entries: dict[str, str]) -> None:
        """The spine runs title page, epigraph document, then the chapter."""
        opf: Final[str] = next(text for name, text in entries.items() if name.endswith(".opf"))
        hrefs: Final[list[str]] = _spine_hrefs(opf)
        assert hrefs[0].endswith("title_page.xhtml")
        assert f"EPUB/{hrefs[1]}" == _epigraph_document(entries)[0]
        assert "The First Chapter" in entries[f"EPUB/{hrefs[2]}"]

    def test_document_is_front_matter_typed_epigraph_without_a_heading(self, entries: dict[str, str]) -> None:
        """The body is frontmatter, the section epigraph, and Pandoc's title heading is gone."""
        document: Final[str] = _epigraph_document(entries)[1]
        assert '<body epub:type="frontmatter">' in document
        assert '<section epub:type="epigraph">' in document
        assert "<h1" not in document
        assert _BOOK_EPIGRAPH in document and "Epigraph Book" not in document.split("<body", 1)[1]

    def test_document_is_unlisted_in_the_nav_and_the_ncx(self, entries: dict[str, str]) -> None:
        """Neither the nav document nor the NCX links to the epigraph's document; the chapter stays listed."""
        basename: Final[str] = _epigraph_document(entries)[0].rsplit("/", 1)[1]
        nav: Final[str] = entries["EPUB/nav.xhtml"]
        ncx: Final[str] = next(text for name, text in entries.items() if name.endswith(".ncx"))
        assert basename not in nav and basename not in ncx
        assert "The First Chapter" in nav and "The First Chapter" in ncx

    def test_chapter_epigraph_stays_in_its_chapter(self, entries: dict[str, str]) -> None:
        """The epigraph under the chapter heading is untouched."""
        chapter: Final[str] = next(
            text for text in _content_documents(entries).values() if "The First Chapter" in text and "<h1" in text
        )
        assert _CHAPTER_EPIGRAPH in chapter and BOOK_EPIGRAPH_CLASS not in chapter
