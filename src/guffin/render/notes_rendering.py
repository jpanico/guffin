"""Rendering of notes: the Notes section, and each note's lead-in in the running text.

A work presents its notes in one of two styles (:class:`~guffin.render.project.NoteStyle`).
*Numbered* notes are each format's own: a superscript number after the lead-in, linked to a
footnote, an endnote, or a GitHub footnote (see :func:`native_note_renderer`).  The rest of this
module serves the other style, *invisible endnotes*.

An invisible endnote's call site carries no mark; its *lead-in*, a phrase
of the passage, is the key that ties the note to its passage.  The notes gather in the Notes
section, the back-matter section an author opens with an ``element-type:: endnotes`` heading,
grouped by the headings their passages fall under.  What the grouping is, and what links tie a
note to its passage, depend on the output format:

- **PDF** keys a note by page number and lead-in, so its notes are grouped by chapter only.  Each
  entry opens with the passage's page number, linked to the passage; the lead-in in the running
  text links to the entry.  Both links are unstyled, so a printed page shows neither.
- **EPUB** has no pages, so a note is keyed by its section and lead-in: grouped by chapter and
  then by section.  Each entry's lead-in links back to the passage, and the lead-in in the
  running text links to the entry (lightly styled by the EPUB stylesheet).
- **Markdown** groups like EPUB, and links each section group's heading to its section.  It
  places no anchors and no links between passage and note.

Public symbols:

- **Constants**: :data:`ENDNOTE_CLASS` — the class of a note's entry in the Notes section;
  :data:`NOTE_REF_CLASS` — the class of a lead-in's link from the running text to its entry;
  :data:`NOTE_BACKLINK_CLASS` — the class of an entry's link back to its passage;
  :data:`NOTES_GROUP_CLASS` — the class of a heading the Notes section generates for a group.
- **Functions**: :func:`note_anchor` — the identifier of a note's passage;
  :func:`endnote_identifier` — the identifier of a note's entry; :func:`insert_notes_section` —
  build the Notes section into a document; :func:`note_lead_in_renderer` — how a format renders a
  lead-in in the running text; :func:`native_note_renderer` — how numbered notes render, as native
  notes; :func:`prepare_notes` — prepare a document's notes in the style its policy sets.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids cascading false-positive errors without relaxing any other strict checks.

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
from pydantic import ConfigDict, validate_call

from guffin.model.chicago_structure import StructuralElement
from guffin.model.notes import PlacedNoteCitation, contained_note_uids, is_numbered_lead_in, placed_note_citations
from guffin.model.primitives import Uid
from guffin.model.publishing_semantics import NoteForm, element_type_of_vertex, note_form_of_vertex
from guffin.model.vertex import HeadingVertex, TextVertex, Vertex
from guffin.model.vertex_link import VertexLinkKind, parse_vertex_link
from guffin.model.vertex_tree import VertexTree, transcluded_vertices
from guffin.model.vertex_view import ChildrenLayout, ViewMap
from guffin.render.epub_semantics import MATTER_DATA_ATTRIBUTE
from guffin.render.pandoc_ast import InlineMap, detached_copy, strip_links
from guffin.render.pandoc_rendering import (
    HEADING_LINK_CLASS,
    NoteLeadInRenderer,
    build_child_blocks,
    heading_anchor,
)
from guffin.render.project import NoteStyle, StructuralPolicy, TopLevelDivision
from guffin.render.render_options import OutputFormat

logger: Final[logging.Logger] = logging.getLogger(__name__)

ENDNOTE_CLASS: Final[str] = "guffin-endnote"
"""The class of a note's entry (a ``Div``) in the Notes section."""

NOTE_REF_CLASS: Final[str] = "guffin-note-ref"
"""The class of a lead-in's link from the running text to its note's entry."""

NOTE_BACKLINK_CLASS: Final[str] = "guffin-note-backlink"
"""The class of an entry's link back to its note's passage."""

NOTES_GROUP_CLASS: Final[str] = "guffin-notes-group"
"""The class of a heading the Notes section generates for a group of notes.

Such a heading repeats the text of the chapter or section heading it stands for.
"""

_NOTE_ANCHOR_PREFIX: Final[str] = "guffin-note-"
"""The prefix of every :func:`note_anchor`."""

_ENDNOTE_PREFIX: Final[str] = "guffin-endnote-"
"""The prefix of every :func:`endnote_identifier`."""


@validate_call
def note_anchor(uid: Uid) -> str:
    """Return the identifier of the passage annotated by the note *uid*.

    Args:
        uid: The note's UID.

    Returns:
        The identifier, the target of a link from the note's entry back to its passage.
    """
    return f"{_NOTE_ANCHOR_PREFIX}{uid}"


@validate_call
def endnote_identifier(uid: Uid) -> str:
    """Return the identifier of the note *uid*'s entry in the Notes section.

    Args:
        uid: The note's UID.

    Returns:
        The identifier, the target of a link from the note's passage to its entry.
    """
    return f"{_ENDNOTE_PREFIX}{uid}"


def _typst_raw_inline(text: str) -> pf.RawInline:
    """Return a Pandoc raw inline of Typst markup, passed through verbatim by the Typst writer only.

    Panflute's ``RawInline`` constructor validates its format against a fixed set that predates
    Pandoc's Typst support, so the format is assigned after construction (a plain attribute,
    validated only in the constructor).
    """
    raw: Final[pf.RawInline] = pf.RawInline(text, format="html")
    raw.format = "typst"
    return raw


def _typst_page_locator(uid: Uid) -> str:
    """Return Typst source printing the displayed page number of the note *uid*'s passage, linked to it.

    The number is formatted with the page numbering in force at the passage, so a passage in
    roman-numbered front matter shows a roman numeral.
    """
    anchor: Final[str] = note_anchor(uid)
    return (
        f"#context {{ let loc = locate(<{anchor}>); link(loc, numbering("
        'if loc.page-numbering() == none { "1" } else { loc.page-numbering() }, '
        "..counter(page).at(loc))) }"
    )


def _notes_heading(tree: VertexTree) -> HeadingVertex | None:
    """Return the first render-visible heading tagged ``element-type:: endnotes``, or ``None``."""
    for vertex in transcluded_vertices(tree):
        if isinstance(vertex, HeadingVertex) and element_type_of_vertex(vertex) is StructuralElement.ENDNOTES:
            return vertex
    return None


def _entry_citations(tree: VertexTree) -> list[PlacedNoteCitation]:
    """Return the note links that get an entry, in reading order.

    A note link gets an entry when it points at a note held by a notes container; a note cited
    more than once gets its entry from its first citation only.
    """
    contained: Final[frozenset[Uid]] = contained_note_uids(tree)
    entered: Final[set[Uid]] = set()
    citations: Final[list[PlacedNoteCitation]] = []
    for placed in placed_note_citations(tree):
        note_uid: Uid = placed.citation.note_uid
        if note_uid in contained and note_uid in tree.uid_map and note_uid not in entered:
            entered.add(note_uid)
            citations.append(placed)
    return citations


def _group_levels(division: TopLevelDivision, output_format: OutputFormat) -> tuple[int, ...]:
    """Return the heading levels a format groups notes by, outermost first.

    A note is keyed by page in PDF, so chapters suffice there; elsewhere it is keyed by section, so
    the section level joins the chapter level.
    """
    chapter_level: Final[int | None] = division.chapter_heading_level
    if output_format is OutputFormat.PDF:
        return () if chapter_level is None else (chapter_level,)
    section_level: Final[int] = division.section_heading_level
    return (section_level,) if chapter_level is None else (chapter_level, section_level)


def _group_path(placed: PlacedNoteCitation, levels: Sequence[int]) -> tuple[HeadingVertex, ...]:
    """Return the group headings a note link falls under, outermost first.

    One heading per level, the deepest governing heading at that level or above; a level with no
    such heading, or whose heading repeats the previous level's (a note before its chapter's first
    section), adds none.
    """
    path: list[HeadingVertex] = []
    for level in levels:
        heading: HeadingVertex | None = placed.group_heading(level)
        if heading is not None and (not path or path[-1].uid != heading.uid):
            path.append(heading)
    return tuple(path)


def _note_lead_ins(doc: pf.Doc) -> dict[Uid, list[pf.Inline]]:
    """Return, per note UID, the inlines of the first note link to it in *doc* (still unresolved)."""
    lead_ins: Final[dict[Uid, list[pf.Inline]]] = {}

    def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
        if isinstance(elem, pf.Link):
            link = parse_vertex_link(elem.url)
            if link is not None and link.kind is VertexLinkKind.NOTE and link.uid not in lead_ins:
                lead_ins[link.uid] = detached_copy(list(elem.content))

    doc.walk(_collect)
    return lead_ins


def _headers_by_identifier(doc: pf.Doc) -> dict[str, pf.Header]:
    """Return *doc*'s identified Headers, keyed by identifier."""
    headers: Final[dict[str, pf.Header]] = {}

    def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
        if isinstance(elem, pf.Header) and elem.identifier:
            headers.setdefault(elem.identifier, elem)

    doc.walk(_collect)
    return headers


def _group_header(
    heading: HeadingVertex,
    level: int,
    headers: Mapping[str, pf.Header],
    inline_map: InlineMap,
    attributes: Mapping[str, str],
    *,
    link_to_heading: bool,
) -> pf.Header:
    """Return the Header for a group of notes under *heading*, repeating its rendered text.

    The text is taken from the heading's own rendered Header when *headers* has it, else from its
    converted text.  The Header is unnumbered and unlisted, so it adds neither a number nor a table
    of contents entry.
    """
    rendered: Final[pf.Header | None] = headers.get(heading_anchor(heading.uid))
    source: Final[list[pf.Inline]] = (
        list(rendered.content) if rendered is not None else inline_map.get(heading.text, [pf.Str(heading.text)])
    )
    text: Final[list[pf.Inline]] = strip_links(detached_copy(source))
    content: Final[list[pf.Inline]] = (
        [pf.Link(*text, url=f"#{heading_anchor(heading.uid)}", classes=[HEADING_LINK_CLASS])]
        if link_to_heading and rendered is not None
        else text
    )
    return pf.Header(
        *content,
        level=min(level, 6),
        classes=["unnumbered", "unlisted", NOTES_GROUP_CLASS],
        attributes=dict(attributes),
    )


def _is_short_form(uid: Uid, tree: VertexTree) -> bool:
    """Return whether the vertex *uid* is tagged ``note-form:: short``."""
    vertex: Final[Vertex | None] = tree.uid_map.get(uid)
    return vertex is not None and note_form_of_vertex(vertex) is NoteForm.SHORT


def _entry(
    placed: PlacedNoteCitation,
    tree: VertexTree,
    lead_ins: Mapping[Uid, list[pf.Inline]],
    asset_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    output_format: OutputFormat,
    note_form: NoteForm,
    *,
    linked: bool,
) -> list[pf.Block]:
    """Return the Notes-section entry for the note *placed* cites, in *note_form*.

    The entry opens with the locator (PDF: the passage's page number, linked to it), then the
    lead-in in italics (EPUB: linked back to the passage), a colon, and the note's text.  Without
    *linked* (the passages are absent) there is no locator and no link.  The full form is the note
    and its children, as continuation paragraphs, less any child tagged ``note-form:: short``; the
    short form, when the note has such a child, is that child and its own children, and otherwise
    the full form.  In PDF and EPUB the entry is a ``Div`` carrying the note's
    :func:`endnote_identifier` (the target of the passage's link); Markdown, which links no passage
    to its note, gets the bare blocks, since the GFM writer would emit a ``Div`` as HTML.
    """
    note_uid: Final[Uid] = placed.citation.note_uid
    lead_in: Final[list[pf.Inline]] = detached_copy(lead_ins.get(note_uid) or [pf.Str(placed.citation.lead_in)])
    emphasized: Final[pf.Inline] = pf.Emph(*lead_in)
    lead: Final[pf.Inline] = (
        pf.Link(emphasized, url=f"#{note_anchor(note_uid)}", classes=[NOTE_BACKLINK_CLASS])
        if linked and output_format is OutputFormat.EPUB
        else emphasized
    )
    locator: Final[list[pf.Inline]] = (
        [_typst_raw_inline(_typst_page_locator(note_uid)), pf.Space()]
        if linked and output_format is OutputFormat.PDF
        else []
    )
    opening: Final[list[pf.Inline]] = [*locator, lead, pf.Str(":")]
    blocks: Final[list[pf.Block]] = _note_blocks(
        note_uid, tree, asset_files, inline_map, view_map, note_form, opening=opening
    )
    if output_format is OutputFormat.MARKDOWN:
        return blocks
    return [pf.Div(*blocks, identifier=endnote_identifier(note_uid), classes=[ENDNOTE_CLASS])]


def _note_blocks(
    note_uid: Uid,
    tree: VertexTree,
    asset_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    note_form: NoteForm,
    *,
    opening: Sequence[pf.Inline] = (),
) -> list[pf.Block]:
    """Return the blocks of the note *note_uid* in *note_form*, its first paragraph led by *opening*.

    The full form is the note and its children, as continuation paragraphs, less any child tagged
    ``note-form:: short``; the short form, when the note has such a child, is that child and its own
    children, and otherwise the full form.  A non-empty *opening* is followed by a space when the
    note's text joins it in one paragraph; a note that is not a text block keeps *opening* as a
    paragraph of its own (omitted when empty) and renders as its blocks after it.
    """
    note: Final[Vertex] = tree.uid_map[note_uid]
    short_form_uid: Final[Uid | None] = next((uid for uid in note.children or () if _is_short_form(uid, tree)), None)
    body: Final[Vertex] = (
        tree.uid_map[short_form_uid] if note_form is NoteForm.SHORT and short_form_uid is not None else note
    )
    continuation: Final[list[Uid]] = [
        uid for uid in body.children or () if body is not note or not _is_short_form(uid, tree)
    ]
    if isinstance(body, TextVertex):
        text: Final[list[pf.Inline]] = detached_copy(inline_map.get(body.text, [pf.Str(body.text)]))
        separator: Final[list[pf.Inline]] = [pf.Space()] if opening else []
        return [
            pf.Para(*opening, *separator, *text),
            *build_child_blocks(
                continuation, tree, asset_files, inline_map, view_map, ChildrenLayout.DOCUMENT, depth=1
            ),
        ]
    return [
        *([pf.Para(*opening)] if opening else []),
        *build_child_blocks([body.uid], tree, asset_files, inline_map, view_map, ChildrenLayout.DOCUMENT, depth=1),
    ]


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def insert_notes_section(
    doc: pf.Doc,
    tree: VertexTree,
    inline_map: InlineMap,
    view_map: ViewMap,
    asset_files: dict[Uid, Path],
    division: TopLevelDivision,
    output_format: OutputFormat,
    *,
    heading_links: bool,
    note_form: NoteForm = NoteForm.FULL,
    notes_only: bool = False,
    title_header: bool = False,
) -> frozenset[Uid]:
    """Build the Notes section into *doc*, in place, and return the UIDs of the notes it holds.

    The section's home is the first render-visible heading tagged ``element-type:: endnotes``; its
    Header must already be in *doc* (built from *tree*), and its own children render as the
    section's intro.  Its notes follow the intro: one entry per note link pointing at a note in a
    notes container, in reading order (a note cited twice is entered once), in *note_form*, grouped
    under generated headings per *output_format* and *division* (see the module docstring).  A
    group's heading sits one level below the Notes heading, and a section group's one level below
    its chapter's; it repeats the rendered text of the heading it stands for, carries the Notes
    heading's matter attribute, and is unnumbered and unlisted.  For Markdown with
    *heading_links*, a section group's heading links to its section.

    With *notes_only*, *doc* is then cut down to the Notes section alone (after its leading title
    Header, kept when *title_header* says *doc* opens with one), and since the text the notes
    annotate is gone, no entry or group heading links to it and no PDF entry has a page locator.

    Must run before *doc*'s vertex links are resolved: each entry's lead-in is copied from the note
    link's own display inlines.  Blocks tagged with the other form are expected to be pruned from
    *tree* already (see :func:`~guffin.model.publishing_semantics.drop_other_note_forms`).

    Args:
        doc: The document built from *tree*, with its vertex links still unresolved.
        tree: The vertex tree *doc* was built from.
        inline_map: Mapping from text string to parsed inline elements, as *doc* was built with.
        view_map: Presentation view map, as *doc* was built with.
        asset_files: Mapping from asset vertex UID to local asset file, as *doc* was built with.
        division: The top-level division of the work, which fixes its chapter and section levels.
        output_format: The format *doc* will be rendered to.
        heading_links: Whether a reference to a heading links to it.
        note_form: Which form of the notes to enter (default the full form).
        notes_only: Whether to cut *doc* down to the Notes section (default ``False``).
        title_header: Whether *doc* opens with a title Header to keep when *notes_only* cuts it
            down (default ``False``).

    Returns:
        The UIDs of the notes given an entry; empty when *tree* has no Notes heading (or *doc* lacks
        its Header) or no note to enter.

    Raises:
        ValueError: If *notes_only* is set and *tree* has no Notes heading, or *doc* lacks its
            Header, as there is then nothing to export.
    """
    notes_heading: Final[HeadingVertex | None] = _notes_heading(tree)
    headers: Final[dict[str, pf.Header]] = _headers_by_identifier(doc)
    notes_header: Final[pf.Header | None] = (
        None if notes_heading is None else headers.get(heading_anchor(notes_heading.uid))
    )
    if notes_header is None:
        if notes_only:
            raise ValueError("a notes-only export needs a rendered heading tagged element-type:: endnotes")
        if notes_heading is not None:
            logger.warning("the Notes heading uid=%r did not render; no notes are entered", notes_heading.uid)
        return frozenset()
    citations: Final[list[PlacedNoteCitation]] = _entry_citations(tree)
    lead_ins: Final[dict[Uid, list[pf.Inline]]] = _note_lead_ins(doc)
    levels: Final[tuple[int, ...]] = _group_levels(division, output_format)
    attributes: Final[dict[str, str]] = (
        {MATTER_DATA_ATTRIBUTE: notes_header.attributes[MATTER_DATA_ATTRIBUTE]}
        if MATTER_DATA_ATTRIBUTE in notes_header.attributes
        else {}
    )
    blocks: Final[list[pf.Block]] = []
    previous_path: tuple[HeadingVertex, ...] = ()
    for placed in citations:
        path: tuple[HeadingVertex, ...] = _group_path(placed, levels)
        shared: int = 0
        while shared < min(len(path), len(previous_path)) and path[shared].uid == previous_path[shared].uid:
            shared += 1
        for depth in range(shared, len(path)):
            blocks.append(
                _group_header(
                    path[depth],
                    notes_header.level + 1 + depth,
                    headers,
                    inline_map,
                    attributes,
                    link_to_heading=not notes_only
                    and output_format is OutputFormat.MARKDOWN
                    and heading_links
                    and depth == len(levels) - 1,
                )
            )
        blocks.extend(
            _entry(
                placed,
                tree,
                lead_ins,
                asset_files,
                inline_map,
                view_map,
                output_format,
                note_form,
                linked=not notes_only,
            )
        )
        previous_path = path
    # The section runs from its Header to the next Header at its level or above among its siblings.
    siblings: Final[pf.ListContainer] = notes_header.parent.content
    start: Final[int] = notes_header.index
    end: int = start + 1
    while end < len(siblings) and not (
        isinstance(siblings[end], pf.Header) and siblings[end].level <= notes_header.level
    ):
        end += 1
    for offset, block in enumerate(blocks):
        siblings.insert(end + offset, block)
    if notes_only:
        section: Final[list[pf.Block]] = list(siblings[start : end + len(blocks)])
        leading: Final[list[pf.Block]] = [
            block for block in list(doc.content)[:1] if title_header and isinstance(block, pf.Header)
        ]
        doc.content = [*leading, *section]
    return frozenset(placed.citation.note_uid for placed in citations)


@validate_call
def note_lead_in_renderer(output_format: OutputFormat, entered: frozenset[Uid]) -> NoteLeadInRenderer:
    """Return how *output_format* renders a note's lead-in in the running text.

    - **PDF** — a zero-width Typst anchor at the start of the lead-in (the target of the entry's
      page locator), then the lead-in as a link to the note's entry.  The template styles only
      links to URLs, so the link is invisible on the page.
    - **EPUB** — the lead-in as a link (:data:`NOTE_REF_CLASS`) to the note's entry, inside a span
      carrying the passage's :func:`note_anchor` identifier.
    - **Markdown** — the bare lead-in.

    A note with no entry renders its bare lead-in in every format, since its links would dangle.

    Args:
        output_format: The format being rendered.
        entered: The UIDs of the notes the Notes section holds (see :func:`insert_notes_section`).

    Returns:
        The renderer, for :func:`~guffin.render.pandoc_rendering.make_doc_resolver`.
    """

    def _render(uid: Uid, lead_in: list[pf.Inline]) -> list[pf.Inline]:
        if uid not in entered:
            return lead_in
        target: Final[str] = f"#{endnote_identifier(uid)}"
        match output_format:
            case OutputFormat.PDF:
                return [
                    _typst_raw_inline(f"#metadata(none)<{note_anchor(uid)}>"),
                    pf.Link(*lead_in, url=target),
                ]
            case OutputFormat.EPUB:
                return [pf.Span(pf.Link(*lead_in, url=target, classes=[NOTE_REF_CLASS]), identifier=note_anchor(uid))]
            case OutputFormat.MARKDOWN:
                return lead_in

    return _render


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def native_note_renderer(
    tree: VertexTree,
    inline_map: InlineMap,
    view_map: ViewMap,
    asset_files: dict[Uid, Path],
    note_form: NoteForm,
) -> NoteLeadInRenderer:
    """Return the renderer of numbered notes: each note link becomes its lead-in and a native note.

    The note is a Pandoc ``Note`` holding the note's blocks in *note_form* (see :func:`insert_notes_section`
    for the forms), placed right after the lead-in, so each format renders its own numbered note
    there: a superscript number linked to a footnote at the foot of the page in PDF, to an endnote
    in EPUB, to a GitHub footnote in Markdown.  The lead-in stays in the running text; a lead-in that
    is only a number (an unrenamed numbered marker, such as ``(1)``) is the extension's own note
    number, so it is dropped and the format's number alone remains.  A link to a vertex absent from
    *tree* keeps its bare lead-in.

    Args:
        tree: The vertex tree the document was built from, holding the notes.
        inline_map: Mapping from text string to parsed inline elements, as the document was built with.
        view_map: Presentation view map, as the document was built with.
        asset_files: Mapping from asset vertex UID to local asset file, as the document was built with.
        note_form: Which form of each note to render.

    Returns:
        The renderer, for :func:`~guffin.render.pandoc_rendering.make_doc_resolver`.
    """

    def _render(uid: Uid, lead_in: list[pf.Inline]) -> list[pf.Inline]:
        if uid not in tree.uid_map:
            return lead_in
        note: Final[pf.Note] = pf.Note(*_note_blocks(uid, tree, asset_files, inline_map, view_map, note_form))
        shown: Final[str] = "".join(pf.stringify(inline) for inline in lead_in)
        return [note] if is_numbered_lead_in(shown) else [*lead_in, note]

    return _render


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def prepare_notes(
    doc: pf.Doc,
    tree: VertexTree,
    inline_map: InlineMap,
    view_map: ViewMap,
    asset_files: dict[Uid, Path],
    policy: StructuralPolicy,
    output_format: OutputFormat,
    *,
    heading_links: bool,
    note_form: NoteForm = NoteForm.FULL,
    notes_only: bool = False,
    title_header: bool = False,
) -> NoteLeadInRenderer:
    """Prepare *doc*'s notes in the style *policy* sets, and return how its note links render.

    With :attr:`~guffin.render.project.NoteStyle.INVISIBLE_ENDNOTES`, the Notes section is built into
    *doc* (see :func:`insert_notes_section`, which receives the remaining arguments) and the lead-ins
    render per :func:`note_lead_in_renderer`.  With :attr:`~guffin.render.project.NoteStyle.NUMBERED`,
    *doc* is left as it is and each note link renders as a native note (see
    :func:`native_note_renderer`).  Must run before *doc*'s vertex links are resolved.

    Args:
        doc: The document built from *tree*, with its vertex links still unresolved.
        tree: The vertex tree *doc* was built from.
        inline_map: Mapping from text string to parsed inline elements, as *doc* was built with.
        view_map: Presentation view map, as *doc* was built with.
        asset_files: Mapping from asset vertex UID to local asset file, as *doc* was built with.
        policy: The structural policy of the work, giving its note style and top-level division.
        output_format: The format *doc* will be rendered to.
        heading_links: Whether a reference to a heading links to it.
        note_form: Which form of the notes to render (default the full form).
        notes_only: Whether to cut *doc* down to the Notes section (invisible endnotes only).
        title_header: Whether *doc* opens with a title Header to keep when *notes_only* cuts it down.

    Returns:
        The renderer of note links, for :func:`~guffin.render.pandoc_rendering.make_doc_resolver`.

    Raises:
        ValueError: If *notes_only* is set for numbered notes, which have no Notes section to export,
            or for a tree with no Notes heading (see :func:`insert_notes_section`).
    """
    match policy.note_style:
        case NoteStyle.INVISIBLE_ENDNOTES:
            entered: Final[frozenset[Uid]] = insert_notes_section(
                doc,
                tree,
                inline_map,
                view_map,
                asset_files,
                policy.top_level_division,
                output_format,
                heading_links=heading_links,
                note_form=note_form,
                notes_only=notes_only,
                title_header=title_header,
            )
            return note_lead_in_renderer(output_format, entered)
        case NoteStyle.NUMBERED:
            if notes_only:
                raise ValueError("a notes-only export needs invisible endnotes, which numbered notes are not")
            return native_note_renderer(tree, inline_map, view_map, asset_files, note_form)
