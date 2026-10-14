"""Tests for guffin.render.notes_rendering, and the notes in each rendered format."""

import zipfile
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pytest
from pypdf import PdfReader

from guffin.common.provenance import Provenance
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.publishing_semantics import NoteForm
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import HeadingVertex, NotesVertex, PageVertex, TextVertex, Vertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree
from guffin.render.epub_rendering import render as render_epub
from guffin.render.md_rendering import render as render_md
from guffin.render.notes_rendering import (
    ENDNOTE_CLASS,
    NOTE_BACKLINK_CLASS,
    NOTE_REF_CLASS,
    NOTES_GROUP_CLASS,
    endnote_identifier,
    insert_notes_section,
    note_anchor,
    note_lead_in_renderer,
)
from guffin.render.pandoc_rendering import HEADING_LINK_CLASS, vertex_tree_to_pandoc
from guffin.render.pdf_rendering import render as render_pdf
from guffin.render.project import BookProfile, TopLevelDivision
from guffin.render.render_options import (
    EpubRenderOptions,
    MarkdownRenderOptions,
    OutputFormat,
    PdfRenderOptions,
)
from guffin.roam.local_api import ApiEndpoint

pytestmark = pytest.mark.pandoc

_ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")


def _tag(name: str, value: str) -> list[AttributeAssignment]:
    """Return a single ``<name>:: <value>`` guffin-domain tag."""
    link: Final[VertexLink] = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
    return [
        AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
            values=(LiteralValue(value=value),),
        )
    ]


def _note_link(lead_in: str, uid: str) -> str:
    """Return a Pandoc-Markdown note link with *lead_in* as its display, pointing at *uid*."""
    return f"[{lead_in}]({vertex_link_url(uid, VertexLinkKind.NOTE)})"


_FILLER: Final[str] = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 30


def _noted_book(*, with_notes_heading: bool = True) -> VertexTree:
    """A two-chapter book: notes cited before, in, and between sections, and a Notes section.

    The notes live in a container per chapter; one note is cited by nothing (an orphan), and two
    notes in different sections share a lead-in.  One note has a short form, and the Notes
    section's intro has a block limited to the short notes.
    """
    root_children: Final[list[str]] = ["chap00001", "chap00002", *(["notesh001"] if with_notes_heading else [])]
    vertices: Final[list[Vertex]] = [
        PageVertex(uid="page00001", title="Noted Book", children=root_children),
        HeadingVertex(
            uid="chap00001",
            text="The Stored Program",
            heading_level=1,
            children=["pre000001", "sect00001", "sect00002"],
        ),
        TextVertex(uid="pre000001", text=f"The Baby {_note_link('ran its first program', 'note00001')} in 1948."),
        HeadingVertex(uid="sect00001", text="The First Program", heading_level=2, children=["texta0001", "notes0001"]),
        TextVertex(
            uid="texta0001", text=f"{_FILLER}It ran for {_note_link('a 52-minute run', 'note00002')}. {_FILLER}"
        ),
        NotesVertex(uid="notes0001", children=["note00001", "note00002", "note00003"]),
        TextVertex(uid="note00001", text="Williams and Kilburn, *Nature* 162 (1948): 487."),
        TextVertex(uid="note00002", text="Lavington, *A History*, 12.", children=["short0001", "cont00001"]),
        TextVertex(uid="short0001", text="Lavington, 12.", attribute_assignments=_tag("note-form", "short")),
        TextVertex(uid="cont00001", text="A continuation of the second note."),
        TextVertex(uid="note00003", text="An orphan note."),
        HeadingVertex(uid="sect00002", text="The Reconstruction", heading_level=2, children=["textb0001"]),
        TextVertex(uid="textb0001", text=f"Tootill rebuilt {_note_link('the original version', 'note00004')}."),
        HeadingVertex(uid="chap00002", text="Design Universals", heading_level=1, children=["textc0001", "notes0002"]),
        TextVertex(uid="textc0001", text=f"Here is {_note_link('the original version', 'note00005')} again."),
        NotesVertex(uid="notes0002", children=["note00004", "note00005"]),
        TextVertex(uid="note00004", text="Tootill, *Resurrection* 20 (1998)."),
        TextVertex(uid="note00005", text="A note in chapter two."),
    ]
    if with_notes_heading:
        vertices.extend(
            [
                HeadingVertex(
                    uid="notesh001",
                    text="Notes",
                    heading_level=1,
                    children=["intro0001", "intro0002"],
                    attribute_assignments=_tag("element-type", "endnotes"),
                ),
                TextVertex(uid="intro0001", text="The complete notes are online."),
                TextVertex(
                    uid="intro0002", text="Only in the short notes.", attribute_assignments=_tag("note-form", "short")
                ),
            ]
        )
    return VertexTree(tree_vertices=vertices)


def _built(
    tree: VertexTree,
    output_format: OutputFormat,
    *,
    note_form: NoteForm = NoteForm.FULL,
    notes_only: bool = False,
    title_header: bool = False,
) -> tuple[pf.Doc, frozenset[str]]:
    """Build *tree*'s document and its Notes section for *output_format*."""
    doc, inline_map = vertex_tree_to_pandoc(tree, {}, {}, title_in_header=title_header)
    entered: Final[frozenset[str]] = insert_notes_section(
        doc,
        tree,
        inline_map,
        {},
        {},
        TopLevelDivision.CHAPTER,
        output_format,
        heading_links=True,
        note_form=note_form,
        notes_only=notes_only,
        title_header=title_header,
    )
    return doc, entered


def _entry_text(doc: pf.Doc, note_uid: str) -> str:
    """Return the stringified entry for *note_uid* (a PDF or EPUB entry ``Div``)."""
    return pf.stringify(
        next(
            block
            for block in doc.content
            if isinstance(block, pf.Div) and block.identifier == endnote_identifier(note_uid)
        )
    ).strip()


class TestColophon:
    """The Notes section ends before the end-of-document colophon."""

    def test_entries_precede_the_colophon(self) -> None:
        """With a colophon appended, the entries are inserted before it, which stays last."""
        tree: Final[VertexTree] = _noted_book()
        doc, inline_map = vertex_tree_to_pandoc(
            tree, {}, {}, provenance=Provenance(version="1.2.3", commit="abc123def456")
        )
        insert_notes_section(
            doc, tree, inline_map, {}, {}, TopLevelDivision.CHAPTER, OutputFormat.EPUB, heading_links=True
        )
        blocks: Final[list[pf.Block]] = list(doc.content)
        assert isinstance(blocks[-2], pf.HorizontalRule)
        assert isinstance(blocks[-1], pf.RawBlock)
        assert isinstance(blocks[-3], pf.Div)
        assert blocks[-3].identifier == endnote_identifier("note00005")


class TestNoteForms:
    """insert_notes_section renders each note in the requested form."""

    def test_full_form_leaves_out_the_short_form(self) -> None:
        """The full form is the note and its continuation, without the child tagged short."""
        doc, _entered = _built(_noted_book(), OutputFormat.PDF)
        entry: Final[str] = _entry_text(doc, "note00002")
        assert "Lavington, A History, 12." in entry
        assert "A continuation of the second note." in entry
        assert "Lavington, 12." not in entry

    def test_short_form_replaces_the_note(self) -> None:
        """The short form is the child tagged short, without the note's continuation."""
        doc, _entered = _built(_noted_book(), OutputFormat.PDF, note_form=NoteForm.SHORT)
        entry: Final[str] = _entry_text(doc, "note00002")
        assert entry.endswith("a 52-minute run: Lavington, 12.")
        assert "A History" not in entry
        assert "continuation" not in entry

    def test_short_export_of_a_note_without_short_form_is_full(self) -> None:
        """A note with no short form renders in full in a short export."""
        doc, _entered = _built(_noted_book(), OutputFormat.PDF, note_form=NoteForm.SHORT)
        assert _entry_text(doc, "note00001").endswith("Williams and Kilburn, Nature 162 (1948): 487.")


class TestNotesOnly:
    """With notes_only, the document is cut down to the Notes section, which links to nothing."""

    def test_document_is_only_the_notes_section(self) -> None:
        """Only the title Header and the Notes section remain."""
        doc, _entered = _built(_noted_book(), OutputFormat.MARKDOWN, notes_only=True, title_header=True)
        headers: Final[list[str]] = [pf.stringify(block) for block in doc.content if isinstance(block, pf.Header)]
        assert headers[:2] == ["Noted Book", "Notes"]
        assert "It ran for" not in pf.stringify(doc)
        assert "Lavington, A History, 12." in pf.stringify(doc)

    def test_group_headings_and_entries_carry_no_links(self) -> None:
        """No group heading links to its section, and no entry has a locator or a back-link."""
        for output_format in (OutputFormat.MARKDOWN, OutputFormat.EPUB, OutputFormat.PDF):
            doc, _entered = _built(_noted_book(), output_format, notes_only=True)
            links: list[pf.Link] = []
            raws: list[pf.RawInline] = []

            def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
                if isinstance(elem, pf.Link):
                    links.append(elem)
                elif isinstance(elem, pf.RawInline):
                    raws.append(elem)

            doc.walk(_collect)
            assert links == [], output_format
            assert raws == [], output_format

    def test_without_notes_heading_raises(self) -> None:
        """A notes-only build of a tree with no Notes heading has nothing to export."""
        with pytest.raises(ValueError, match="notes-only"):
            _built(_noted_book(with_notes_heading=False), OutputFormat.MARKDOWN, notes_only=True)


def _notes_blocks(doc: pf.Doc) -> list[pf.Block]:
    """Return the top-level blocks from the Notes heading to the end of *doc*."""
    blocks: Final[list[pf.Block]] = list(doc.content)
    start: Final[int] = next(
        index for index, block in enumerate(blocks) if isinstance(block, pf.Header) and pf.stringify(block) == "Notes"
    )
    return blocks[start:]


class TestIdentifiers:
    """note_anchor and endnote_identifier name a note's passage and entry."""

    def test_identifiers(self) -> None:
        """Both are prefixed by kind and carry the note's UID."""
        assert note_anchor("note00001") == "guffin-note-note00001"
        assert endnote_identifier("note00001") == "guffin-endnote-note00001"


class TestInsertNotesSection:
    """insert_notes_section builds the Notes section into the document."""

    def test_enters_every_cited_contained_note(self) -> None:
        """Every cited note is entered; the orphan is not."""
        _doc, entered = _built(_noted_book(), OutputFormat.PDF)
        assert entered == frozenset({"note00001", "note00002", "note00004", "note00005"})

    def test_no_notes_heading_enters_nothing(self) -> None:
        """Without an element-type:: endnotes heading, nothing is built."""
        doc, entered = _built(_noted_book(with_notes_heading=False), OutputFormat.PDF)
        assert entered == frozenset()
        assert not any(ENDNOTE_CLASS in getattr(block, "classes", []) for block in doc.content)

    def test_pdf_groups_by_chapter_only(self) -> None:
        """A PDF groups notes under chapter headings only, in reading order, after the intro."""
        doc, _entered = _built(_noted_book(), OutputFormat.PDF)
        blocks: Final[list[pf.Block]] = _notes_blocks(doc)
        headers: Final[list[pf.Header]] = [block for block in blocks[1:] if isinstance(block, pf.Header)]
        assert [(pf.stringify(header), header.level) for header in headers] == [
            ("The Stored Program", 2),
            ("Design Universals", 2),
        ]
        assert all({"unnumbered", "unlisted", NOTES_GROUP_CLASS} <= set(header.classes) for header in headers)
        entries: Final[list[str]] = [block.identifier for block in blocks if isinstance(block, pf.Div)]
        assert entries == [endnote_identifier(uid) for uid in ("note00001", "note00002", "note00004", "note00005")]
        assert "The complete notes are online." in pf.stringify(blocks[1])

    def test_pdf_entry_opens_with_page_locator(self) -> None:
        """A PDF entry opens with a raw Typst page locator for its passage, then the italic lead-in."""
        doc, _entered = _built(_noted_book(), OutputFormat.PDF)
        entry: Final[pf.Div] = next(
            block
            for block in _notes_blocks(doc)
            if isinstance(block, pf.Div) and block.identifier.endswith("note00002")
        )
        opening: Final[pf.Para] = entry.content[0]
        assert isinstance(opening.content[0], pf.RawInline)
        assert opening.content[0].format == "typst"
        assert f"locate(<{note_anchor('note00002')}>)" in opening.content[0].text
        assert isinstance(opening.content[2], pf.Emph)
        assert pf.stringify(entry).strip().endswith("A continuation of the second note.")

    def test_epub_groups_by_chapter_and_section(self) -> None:
        """An EPUB groups notes by chapter and then section, a note before any section under its chapter."""
        doc, _entered = _built(_noted_book(), OutputFormat.EPUB)
        headers: Final[list[pf.Header]] = [block for block in _notes_blocks(doc)[1:] if isinstance(block, pf.Header)]
        assert [(pf.stringify(header), header.level) for header in headers] == [
            ("The Stored Program", 2),
            ("The First Program", 3),
            ("The Reconstruction", 3),
            ("Design Universals", 2),
        ]

    def test_epub_lead_in_links_back_to_passage(self) -> None:
        """An EPUB entry's italic lead-in links back to its passage."""
        doc, _entered = _built(_noted_book(), OutputFormat.EPUB)
        entry: Final[pf.Div] = next(block for block in _notes_blocks(doc) if isinstance(block, pf.Div))
        lead: Final[pf.Link] = entry.content[0].content[0]
        assert isinstance(lead, pf.Link)
        assert lead.url == f"#{note_anchor('note00001')}"
        assert NOTE_BACKLINK_CLASS in lead.classes

    def test_markdown_entries_are_bare_and_section_groups_link(self) -> None:
        """Markdown entries are bare paragraphs, and a section group's heading links to its section."""
        doc, _entered = _built(_noted_book(), OutputFormat.MARKDOWN)
        blocks: Final[list[pf.Block]] = _notes_blocks(doc)
        assert not any(isinstance(block, pf.Div) for block in blocks)
        section_header: Final[pf.Header] = next(
            block for block in blocks if isinstance(block, pf.Header) and pf.stringify(block) == "The First Program"
        )
        link: Final[pf.Link] = section_header.content[0]
        assert isinstance(link, pf.Link)
        assert link.url == "#vertex-sect00001"
        assert HEADING_LINK_CLASS in link.classes
        chapter_header: Final[pf.Header] = next(
            block for block in blocks if isinstance(block, pf.Header) and pf.stringify(block) == "The Stored Program"
        )
        assert not isinstance(chapter_header.content[0], pf.Link)


class TestNoteLeadInRenderer:
    """note_lead_in_renderer renders a lead-in in the running text per format."""

    _LEAD_IN: Final[list[pf.Inline]] = [pf.Str("lead")]

    def test_pdf_anchors_and_links(self) -> None:
        """PDF: a zero-width Typst anchor, then the lead-in linked to its entry."""
        rendered = note_lead_in_renderer(OutputFormat.PDF, frozenset({"note00001"}))("note00001", self._LEAD_IN)
        assert rendered[0].format == "typst"
        assert rendered[0].text == f"#metadata(none)<{note_anchor('note00001')}>"
        assert isinstance(rendered[1], pf.Link)
        assert rendered[1].url == f"#{endnote_identifier('note00001')}"

    def test_epub_links_inside_an_anchored_span(self) -> None:
        """EPUB: the lead-in linked to its entry, inside a span carrying the passage's anchor."""
        rendered = note_lead_in_renderer(OutputFormat.EPUB, frozenset({"note00001"}))("note00001", self._LEAD_IN)
        span: Final[pf.Span] = rendered[0]
        assert span.identifier == note_anchor("note00001")
        assert NOTE_REF_CLASS in span.content[0].classes

    def test_markdown_is_bare(self) -> None:
        """Markdown: the bare lead-in."""
        rendered = note_lead_in_renderer(OutputFormat.MARKDOWN, frozenset({"note00001"}))("note00001", self._LEAD_IN)
        assert rendered == self._LEAD_IN

    @pytest.mark.parametrize("output_format", list(OutputFormat))
    def test_note_without_entry_is_bare(self, output_format: OutputFormat) -> None:
        """A note with no entry renders its bare lead-in, so no link dangles."""
        assert note_lead_in_renderer(output_format, frozenset())("note00001", self._LEAD_IN) == self._LEAD_IN


class TestRenderedNotes:
    """Each format renders the Notes section end to end."""

    @staticmethod
    def _bundle() -> RenderBundle:
        return RenderBundle(content=_noted_book(), view={})

    def test_markdown(self, tmp_path: Path) -> None:
        """Markdown: bare lead-ins in the text; grouped, linked section headings; entries; no HTML."""
        render_md(
            self._bundle(),
            profile=BookProfile(),
            filename_stem="noted",
            api_endpoint=_ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        text: Final[str] = (tmp_path / "noted.md").read_text(encoding="utf-8")
        notes: Final[str] = text[text.index("## Notes") :]
        assert "It ran for a 52-minute run." in text
        assert "### The Stored Program\n\n*ran its first program*: Williams and Kilburn" in notes
        assert "#### [The First Program](#the-first-program)\n\n*a 52-minute run*: Lavington" in notes
        assert "A continuation of the second note." in notes
        assert "An orphan note." not in text
        assert "Only in the short notes." not in text
        assert "<div" not in text
        assert "<a id=" not in text

    def test_markdown_short_notes_only(self, tmp_path: Path) -> None:
        """Markdown, short and notes only: the short-only intro block, short forms, and no running text."""
        render_md(
            self._bundle(),
            profile=BookProfile(),
            filename_stem="noted",
            api_endpoint=_ENDPOINT,
            options=MarkdownRenderOptions(
                output_dir=tmp_path, should_bundle=False, note_form=NoteForm.SHORT, notes_only=True
            ),
        )
        text: Final[str] = (tmp_path / "noted.md").read_text(encoding="utf-8")
        assert "Only in the short notes." in text
        assert "*a 52-minute run*: Lavington, 12." in text
        assert "#### The First Program\n" in text
        assert "It ran for" not in text
        assert "](#" not in text

    def test_epub(self, tmp_path: Path) -> None:
        """EPUB: passage and entry link to each other across chapter files; the Notes file is back matter."""
        render_epub(
            self._bundle(),
            profile=BookProfile(),
            filename_stem="noted",
            api_endpoint=_ENDPOINT,
            options=EpubRenderOptions(output_dir=tmp_path),
        )
        with zipfile.ZipFile(tmp_path / "noted.epub") as package:
            documents: Final[dict[str, str]] = {
                name: package.read(name).decode("utf-8")
                for name in package.namelist()
                if name.startswith("EPUB/text/ch") and name.endswith(".xhtml")
            }
        notes_name: Final[str] = next(name for name, xhtml in documents.items() if 'epub:type="endnotes"' in xhtml)
        notes_file: Final[str] = notes_name.rsplit("/", 1)[1]
        passage_name: Final[str] = next(
            name for name, xhtml in documents.items() if 'id="guffin-note-note00002"' in xhtml
        )
        passage_file: Final[str] = passage_name.rsplit("/", 1)[1]
        assert f'href="{notes_file}#guffin-endnote-note00002" class="guffin-note-ref"' in documents[passage_name]
        assert f'href="{passage_file}#guffin-note-note00002" class="guffin-note-backlink"' in documents[notes_name]
        assert '<body epub:type="backmatter">' in documents[notes_name]

    def test_pdf(self, tmp_path: Path) -> None:
        """PDF: one Notes page with chapter groups (no page break at a group) and passage page numbers."""
        render_pdf(
            self._bundle(),
            profile=BookProfile(),
            filename_stem="noted",
            api_endpoint=_ENDPOINT,
            options=PdfRenderOptions(output_dir=tmp_path),
        )
        reader: Final[PdfReader] = PdfReader(tmp_path / "noted.pdf")
        # Whitespace collapsed, so a line break inside a phrase does not hide it.
        pages: Final[list[str]] = [" ".join((page.extract_text() or "").split()) for page in reader.pages]
        notes_page: Final[str] = pages[-1]
        assert "Notes" in notes_page
        assert "The Stored Program" in notes_page
        assert "Design Universals" in notes_page
        passage_page: Final[str] = next(page for page in pages if "It ran for a 52-minute run" in page)
        # The page's displayed number is the last text on it, in the footer.
        displayed: Final[str] = passage_page.split()[-1]
        assert f"{displayed} a 52-minute run: Lavington" in notes_page
