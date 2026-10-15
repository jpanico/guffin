"""Unit tests for guffin.model.notes."""

from typing import Final

from guffin.common.table import Table, TableStyle
from guffin.model.alternative import Alternative
from guffin.model.notes import (
    NoteCitation,
    contained_note_uids,
    is_numbered_lead_in,
    note_citations,
    note_links_in_text,
    notes_containers,
    orphan_note_uids,
    placed_note_citations,
    strip_note_links,
    vertex_texts,
)
from guffin.model.vertex import (
    BlockEmbedVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    NotesVertex,
    PageVertex,
    QuoteBlockVertex,
    QuoteType,
    TableVertex,
    TextVertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree


def _note_link(lead_in: str, uid: str) -> str:
    """Return a Pandoc-Markdown note link with *lead_in* as its display, pointing at *uid*."""
    return f"[{lead_in}]({vertex_link_url(uid, VertexLinkKind.NOTE)})"


class TestNoteLinksInText:
    """note_links_in_text finds every note link in a text, in text order."""

    def test_finds_lead_in_and_uid(self) -> None:
        """A note link yields its lead-in and the note's uid."""
        assert note_links_in_text(f"It ran for {_note_link('a 52-minute run', 'note00001')} and stopped.") == [
            ("a 52-minute run", "note00001")
        ]

    def test_finds_every_link_in_order(self) -> None:
        """Several note links come back in text order."""
        text: Final[str] = f"{_note_link('first', 'note00001')} then {_note_link('second', 'note00002')}"
        assert note_links_in_text(text) == [("first", "note00001"), ("second", "note00002")]

    def test_ignores_other_vertex_links(self) -> None:
        """Reference and embed links are not note links."""
        text: Final[str] = (
            f"[ref]({vertex_link_url('refer0001', VertexLinkKind.REFERENCE)}) "
            f"[emb]({vertex_link_url('embed0001', VertexLinkKind.EMBED)})"
        )
        assert note_links_in_text(text) == []


class TestVertexTexts:
    """vertex_texts returns the inline texts a vertex renders."""

    def test_text_vertex_uses_selected_wording(self) -> None:
        """A text vertex contributes its own text."""
        assert vertex_texts(TextVertex(uid="text00001", text="Body.")) == ("Body.",)

    def test_callout_contributes_title_and_body(self) -> None:
        """A callout contributes its title and its body."""
        callout = CalloutVertex(
            uid="call00001", callout_type=CalloutVertex.CalloutType.INFO, title="Title", body="Body"
        )
        assert vertex_texts(callout) == ("Title", "Body")

    def test_quote_contributes_quote_and_attribution(self) -> None:
        """A block quotation contributes its quotation and its attribution."""
        quote = QuoteBlockVertex(uid="quot00001", quote_type=QuoteType.BLOCK, quote="Words.", attribution="Someone")
        assert vertex_texts(quote) == ("Words.", "Someone")

    def test_table_contributes_every_cell(self) -> None:
        """A table contributes its cells in row order."""
        table = TableVertex(uid="tabl00001", table=Table(rows=(("a", "b"), ("c", "d"))), table_style=TableStyle())
        assert vertex_texts(table) == ("a", "b", "c", "d")

    def test_code_block_contributes_nothing(self) -> None:
        """A code listing is literal, never inline text."""
        assert vertex_texts(CodeBlockVertex(uid="code00001", code="x = 1", language="python")) == ()


def _noted_tree() -> VertexTree:
    """A page: a chapter heading with two sections, notes cited in each, and a notes container."""
    page = PageVertex(uid="page00001", title="Doc", children=["chap00001", "notes0001"])
    chapter = HeadingVertex(
        uid="chap00001", text="Chapter", heading_level=1, children=["pre000001", "sect00001", "sect00002"]
    )
    preface = TextVertex(uid="pre000001", text=f"Before {_note_link('the sections', 'note00001')}.")
    section_a = HeadingVertex(uid="sect00001", text="A", heading_level=2, children=["texta0001"])
    text_a = TextVertex(uid="texta0001", text=f"In A {_note_link('a phrase', 'note00002')}.")
    section_b = HeadingVertex(uid="sect00002", text="B", heading_level=2, children=["textb0001"])
    text_b = TextVertex(uid="textb0001", text=f"In B {_note_link('a phrase', 'note00003')}.")
    notes = NotesVertex(uid="notes0001", children=["note00001", "note00002", "note00003", "note00004"])
    note_vertices: Final[list[TextVertex]] = [
        TextVertex(uid=f"note0000{index}", text=f"Note {index}.") for index in range(1, 5)
    ]
    return VertexTree(
        tree_vertices=[page, chapter, preface, section_a, text_a, section_b, text_b, notes, *note_vertices]
    )


class TestNoteCitations:
    """note_citations lists every note link in the render-visible document."""

    def test_lists_every_citation(self) -> None:
        """Each note link becomes a citation naming its citing vertex, lead-in, and note."""
        assert set(note_citations(_noted_tree())) == {
            NoteCitation(citing_uid="pre000001", lead_in="the sections", note_uid="note00001"),
            NoteCitation(citing_uid="texta0001", lead_in="a phrase", note_uid="note00002"),
            NoteCitation(citing_uid="textb0001", lead_in="a phrase", note_uid="note00003"),
        }


class TestPlacedNoteCitations:
    """placed_note_citations returns note links in reading order with their governing headings."""

    def test_reading_order(self) -> None:
        """Citations come back in the order the rendered document reads them."""
        assert [placed.citation.note_uid for placed in placed_note_citations(_noted_tree())] == [
            "note00001",
            "note00002",
            "note00003",
        ]

    def test_governing_headings(self) -> None:
        """A citation carries the chapter and, inside a section, the section heading."""
        placed = placed_note_citations(_noted_tree())
        assert [[heading.uid for heading in item.headings] for item in placed] == [
            ["chap00001"],
            ["chap00001", "sect00001"],
            ["chap00001", "sect00002"],
        ]

    def test_group_heading_at_section_level(self) -> None:
        """At the section level, a citation before the first section groups under its chapter."""
        placed = placed_note_citations(_noted_tree())
        groups = [item.group_heading(2) for item in placed]
        assert [group.uid if group is not None else None for group in groups] == [
            "chap00001",
            "sect00001",
            "sect00002",
        ]

    def test_following_sibling_is_governed_by_preceding_heading(self) -> None:
        """Content after a heading in reading order is governed by it, even when not nested under it."""
        page = PageVertex(uid="page00001", title="Doc", children=["head00001", "text00001"])
        heading = HeadingVertex(uid="head00001", text="H", heading_level=1)
        text = TextVertex(uid="text00001", text=_note_link("lead", "note00001"))
        tree = VertexTree(tree_vertices=[page, heading, text])
        assert [heading.uid for heading in placed_note_citations(tree)[0].headings] == ["head00001"]

    def test_embedded_content_is_placed_at_the_embed(self) -> None:
        """A citation inside transcluded content is governed by the headings around the embed."""
        page = PageVertex(uid="page00001", title="Doc", children=["head00001"])
        heading = HeadingVertex(uid="head00001", text="H", heading_level=1, children=["embed0001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="srce00001"))
        source = TextVertex(uid="srce00001", text=_note_link("lead", "note00001"))
        tree = VertexTree(tree_vertices=[page, heading, embed], ref_vertices=[source])
        placed = placed_note_citations(tree)
        assert [item.citation.citing_uid for item in placed] == ["srce00001"]
        assert [heading.uid for heading in placed[0].headings] == ["head00001"]

    def test_notes_container_is_not_walked(self) -> None:
        """A note link inside a note does not count as running text."""
        page = PageVertex(uid="page00001", title="Doc", children=["notes0001"])
        notes = NotesVertex(uid="notes0001", children=["note00001"])
        note = TextVertex(uid="note00001", text=_note_link("inner", "note00002"))
        tree = VertexTree(tree_vertices=[page, notes, note])
        assert placed_note_citations(tree) == []


class TestNotesContainers:
    """notes_containers, contained_note_uids, and orphan_note_uids work over the notes containers."""

    def test_containers(self) -> None:
        """The notes container is found."""
        assert [container.uid for container in notes_containers(_noted_tree())] == ["notes0001"]

    def test_contained_note_uids(self) -> None:
        """Every child of a notes container is a contained note."""
        assert contained_note_uids(_noted_tree()) == frozenset({"note00001", "note00002", "note00003", "note00004"})

    def test_orphans_are_the_uncited_notes(self) -> None:
        """A note no citation points at is an orphan."""
        tree: Final[VertexTree] = _noted_tree()
        assert orphan_note_uids(tree, note_citations(tree)) == ["note00004"]


class TestIsNumberedLeadIn:
    """is_numbered_lead_in() recognizes an unrenamed numbered marker's label."""

    def test_digits_are_numbered(self) -> None:
        """One or more digits, whitespace aside, are a note number."""
        assert is_numbered_lead_in("1")
        assert is_numbered_lead_in(" 12 ")

    def test_phrases_are_not(self) -> None:
        """A phrase, a number within a phrase, or nothing at all is not a note number."""
        assert not is_numbered_lead_in("a 52-minute run")
        assert not is_numbered_lead_in("in 1948")
        assert not is_numbered_lead_in("")


def _stripped_text(text: str) -> str:
    """Return *text* as a text vertex's after strip_note_links."""
    page: Final[PageVertex] = PageVertex(uid="page00001", title="Doc", children=["text00001"])
    stripped: Final[VertexTree] = strip_note_links(
        VertexTree(tree_vertices=[page, TextVertex(uid="text00001", text=text)])
    )
    vertex = stripped.uid_map["text00001"]
    assert isinstance(vertex, TextVertex)
    return vertex.text


class TestStripNoteLinks:
    """strip_note_links() reduces every note link to plain text, for notes that are left out."""

    def test_a_phrase_lead_in_stays_as_plain_text(self) -> None:
        """The lead-in stays in the sentence, unlinked."""
        assert (
            _stripped_text(f"It ran for {_note_link('a 52-minute run', 'note00001')}.") == "It ran for a 52-minute run."
        )

    def test_a_numbered_marker_goes_with_the_space_before_it(self) -> None:
        """A number names no phrase of the passage, so it goes, leaving no gap before a word or punctuation."""
        assert _stripped_text(f"A word {_note_link('1', 'note00001')} here.") == "A word here."
        assert _stripped_text(f"A word{_note_link('2', 'note00002')} here.") == "A word here."
        assert _stripped_text(f"The end {_note_link('3', 'note00003')}.") == "The end."

    def test_a_numbered_marker_between_letters_keeps_the_words_apart(self) -> None:
        """When a letter follows the marker directly, the space before it stays, so two words do not join."""
        assert _stripped_text(f"a {_note_link('1', 'note00001')}b") == "a b"

    def test_other_links_are_untouched(self) -> None:
        """A reference link is not a note link."""
        reference: Final[str] = f"[Page]({vertex_link_url('page00002', VertexLinkKind.REFERENCE)})"
        assert _stripped_text(f"See {reference}.") == f"See {reference}."

    def test_every_inline_text_is_reduced(self) -> None:
        """Alternative wordings and table cells lose their note links too."""
        page = PageVertex(uid="page00001", title="Doc", children=["text00001", "tabl00001"])
        text = TextVertex(
            uid="text00001",
            text=f"Main {_note_link('lead', 'note00001')}.",
            alternatives=(Alternative(uid="altr00001", text=f"Other {_note_link('lead', 'note00001')}."),),
        )
        table = TableVertex(
            uid="tabl00001",
            table=Table(rows=((f"Cell {_note_link('7', 'note00002')}.", "b"),)),
            table_style=TableStyle(),
        )
        stripped: Final[VertexTree] = strip_note_links(VertexTree(tree_vertices=[page, text, table]))
        stripped_text = stripped.uid_map["text00001"]
        stripped_table = stripped.uid_map["tabl00001"]
        assert isinstance(stripped_text, TextVertex)
        assert isinstance(stripped_table, TableVertex)
        assert stripped_text.text == "Main lead."
        assert stripped_text.alternatives is not None
        assert stripped_text.alternatives[0].text == "Other lead."
        assert stripped_table.table.rows == (("Cell.", "b"),)

    def test_tree_without_note_links_passes_through(self) -> None:
        """A tree with no note links is returned unchanged (the same object)."""
        tree: Final[VertexTree] = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["text00001"]),
                TextVertex(uid="text00001", text="No notes here."),
            ]
        )
        assert strip_note_links(tree) is tree
