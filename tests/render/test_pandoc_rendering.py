"""Unit tests for guffin.render.pandoc_rendering."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; all six rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.
# pyright: reportPrivateUsage=false
# Rationale: these unit tests deliberately exercise module-private helpers (e.g.
# _effective_layout, _attribute_assignment_text) directly.

import logging
from datetime import UTC, date, datetime
from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
import pytest
from conftest import article1_vertex_tree
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.provenance import Provenance
from guffin.common.revision import Revision
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.vertex import (
    BlockEmbedVertex,
    BlockQuoteVertex,
    HeadingVertex,
    ImageVertex,
    PageEmbedVertex,
    PageVertex,
    PdfVertex,
    TextVertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, VertexView
from guffin.render.date_format import DateFormat
from guffin.render.epub_semantics import MATTER_DATA_ATTRIBUTE
from guffin.render.pandoc_ast import parse_inline_md
from guffin.render.pandoc_rendering import (
    _attribute_assignment_text,
    _effective_layout,
    build_child_blocks,
    colophon_summary,
    make_resolver,
    vertex_tree_to_pandoc,
)

pytestmark = pytest.mark.pandoc


class TestMakeResolverDailyNote:
    """make_resolver formats a daily-note-page reference's date per the chosen DateFormat."""

    _LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="01-01-2026")
    _DAILY = PageVertex(uid="01-01-2026", title="January 1st, 2026", daily_note_date=date(2026, 1, 1))

    def test_iso_format_reformats_the_reference(self) -> None:
        """With ISO, a daily-note reference renders as the ISO date, not the Roam title."""
        result = make_resolver({}, DateFormat.ISO)(self._LINK, self._DAILY, [pf.Str("January 1st, 2026")])
        assert pf.stringify(pf.Para(*result)).strip() == "2026-01-01"

    def test_roam_long_keeps_the_title(self) -> None:
        """ROAM_LONG (default) leaves the reference as the page's own title."""
        result = make_resolver({}, DateFormat.ROAM_LONG)(self._LINK, self._DAILY, [pf.Str("January 1st, 2026")])
        assert pf.stringify(pf.Para(*result)).strip() == "January 1st, 2026"

    def test_synthetic_page_unaffected_by_format(self) -> None:
        """A non-daily-note page reference is unaffected even under a date format."""
        page = PageVertex(uid="pageuid01", title="Some Page")
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="pageuid01")
        result = make_resolver({}, DateFormat.ISO)(link, page, [pf.Str("Some Page")])
        assert pf.stringify(pf.Para(*result)).strip() == "Some Page"


_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")
_PDF_URL: HttpUrl = HttpUrl("https://example.com/pdfs/paper.pdf")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_text(element: pf.Element) -> str:
    """Reconstruct plain text from panflute Str, Space, and SoftBreak inlines."""
    parts: list[str] = []
    for inline in element.content:
        if isinstance(inline, pf.Str):
            parts.append(inline.text)
        elif isinstance(inline, (pf.Space, pf.SoftBreak)):
            parts.append(" ")
    return "".join(parts)


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocPageVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocPageVertex:
    """Tests for vertex_tree_to_pandoc() — PageVertex root behaviour."""

    def test_page_title_set_in_metadata(self) -> None:
        """Page title appears as the Pandoc metadata title (default title_in_header=False)."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="My Page")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert "title" in doc.metadata
        assert _collect_text(doc.metadata["title"]) == "My Page"

    def test_page_with_no_children_produces_no_blocks(self) -> None:
        """A bare PageVertex with no children produces an empty document body."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="Empty")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert list(doc.content) == []

    def test_non_page_root_produces_no_metadata_title(self) -> None:
        """When the root is not a PageVertex, no metadata title is set."""
        tree = VertexTree(tree_vertices=[HeadingVertex(uid="head00001", text="Intro", heading_level=1)])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert "title" not in doc.metadata

    def test_all_metadata_attributes_reach_doc_metadata(self) -> None:
        """Every recognised guffin-domain metadata attribute lands under its Pandoc key."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="metapage1")

        def _meta(name: str, value: str) -> AttributeAssignment:
            return AttributeAssignment(
                attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
                values=(LiteralValue(value=value),),
            )

        page = PageVertex(
            uid="page00001",
            title="Roam Title",
            attribute_assignments=[
                _meta("title", "Real Title"),
                _meta("subtitle", "A Subtitle"),
                _meta("authors", "An Author"),
                _meta("date", "2026-07-02"),
                _meta("publisher", "A Publisher"),
                _meta("rights", "All rights reserved"),
                _meta("identifier", "urn:isbn:1"),
            ],
        )
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page]), {}, {})
        assert _collect_text(doc.metadata["title"]) == "Real Title"  # overrides the Roam page title
        assert _collect_text(doc.metadata["subtitle"]) == "A Subtitle"
        assert _collect_text(doc.metadata["date"]) == "2026-07-02"
        assert _collect_text(doc.metadata["publisher"]) == "A Publisher"
        assert _collect_text(doc.metadata["rights"]) == "All rights reserved"
        assert _collect_text(doc.metadata["identifier"]) == "urn:isbn:1"
        assert [_collect_text(entry) for entry in doc.metadata["author"].content] == ["An Author"]

    def test_metadata_values_are_smart_parsed(self) -> None:
        """Metadata gets the same inline parse as body text — smart punctuation included.

        A straight apostrophe left raw in the metadata inlines is escaped by the Typst
        writer (backslash-apostrophe), which Bergfink's string-literal context then shows
        verbatim in the PDF; the smart parse turns it into its curly form up front.
        """
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="metapage1")
        publisher = AttributeAssignment(
            attribute=AttributeInstance(
                definition=Attribute(name="publisher", domain=AttributeDomain.GUFFIN), link=link
            ),
            values=(LiteralValue(value="Lippincott's Monthly Magazine"),),
        )
        page = PageVertex(uid="page00001", title="Doc", attribute_assignments=[publisher])
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page]), {}, {})
        assert _collect_text(doc.metadata["publisher"]) == "Lippincott’s Monthly Magazine"

    def test_title_in_header_renders_h1_and_metadata(self) -> None:
        """title_in_header=True renders the title as an H1 body block and in the metadata."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="My Page")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {}, title_in_header=True)
        assert _collect_text(doc.metadata["title"]) == "My Page"
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 1
        assert _collect_text(blocks[0]) == "My Page"

    def test_title_in_header_includes_children_after_h1(self) -> None:
        """title_in_header=True: H1 is followed by rendered children."""
        page = PageVertex(uid="page00001", title="Doc", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section", heading_level=2)
        tree = VertexTree(tree_vertices=[page, heading])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {}, title_in_header=True)
        blocks = list(doc.content)
        assert len(blocks) == 2
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 1
        assert isinstance(blocks[1], pf.Header)
        assert blocks[1].level == 2


class TestVertexTreeToPandocSubtreeRootMetadata:
    """A non-page export root's metadata-domain attributes are consumed like a page root's."""

    @staticmethod
    def _meta(name: str, value: str) -> AttributeAssignment:
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="metapage1")
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
            values=(LiteralValue(value=value),),
        )

    def _tree(self, assignments: list[AttributeAssignment] | None) -> VertexTree:
        """Build a heading-rooted subtree carrying *assignments* on its root."""
        root = HeadingVertex(
            uid="head00001",
            text="A Section",
            heading_level=1,
            children=["txt00001a"],
            attribute_assignments=assignments,
        )
        return VertexTree(tree_vertices=[root, TextVertex(uid="txt00001a", text="body")])

    def test_subtree_root_metadata_reaches_doc_metadata(self) -> None:
        """title/authors on a heading root populate the Pandoc metadata."""
        tree = self._tree([self._meta("title", "A Real Title"), self._meta("authors", "An Author")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert _collect_text(doc.metadata["title"]) == "A Real Title"
        assert [_collect_text(entry) for entry in doc.metadata["author"].content] == ["An Author"]

    def test_subtree_root_title_renders_as_header_when_requested(self) -> None:
        """title_in_header=True renders the title attribute as a leading H1."""
        tree = self._tree([self._meta("title", "A Real Title")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {}, title_in_header=True)
        first = list(doc.content)[0]
        assert isinstance(first, pf.Header)
        assert first.level == 1
        assert _collect_text(first) == "A Real Title"

    def test_untagged_subtree_root_has_no_title(self) -> None:
        """Without a title attribute, a non-page root contributes no document title."""
        doc, _ = vertex_tree_to_pandoc(self._tree(None), {}, {})
        assert "title" not in doc.metadata

    def test_non_page_root_is_a_transparent_container(self) -> None:
        """The root renders no block of its own; only its children form the document body."""
        doc, _ = vertex_tree_to_pandoc(self._tree(None), {}, {})
        blocks = list(doc.content)
        # The heading root's own Header is absent; the sole block is its child's bullet list.
        assert not any(isinstance(block, pf.Header) for block in blocks)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)


class TestVertexTreeToPandocColophon:
    """vertex_tree_to_pandoc() appends a provenance colophon only when provenance is provided."""

    def test_no_colophon_without_provenance(self) -> None:
        """With no provenance (the default), no horizontal-rule colophon is appended."""
        tree = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["head0001a"]),
                HeadingVertex(uid="head0001a", text="Section", heading_level=2),
            ]
        )
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert not any(isinstance(block, pf.HorizontalRule) for block in doc.content)

    def test_colophon_appended_with_provenance(self) -> None:
        """Provenance appends a trailing HorizontalRule and an emphasized summary line."""
        provenance = Provenance(
            commit="abc123def456",
            dirty=True,
            committed_at=datetime(2026, 6, 29, 14, 2, 11, tzinfo=UTC),
            exported_at=datetime(2026, 6, 29, 22, 40, 3, tzinfo=UTC),
        )
        tree = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["head0001a"]),
                HeadingVertex(uid="head0001a", text="Section", heading_level=2),
            ]
        )
        doc, _ = vertex_tree_to_pandoc(tree, {}, {}, title_in_header=True, provenance=provenance)
        blocks = list(doc.content)
        # The body (H1 + H2) is followed by the colophon: a rule and an inline-styled HTML line
        # carrying the verbatim summary at a reduced (0.7em) size.
        assert isinstance(blocks[-2], pf.HorizontalRule)
        colophon = blocks[-1]
        assert isinstance(colophon, pf.RawBlock)
        assert colophon.format == "html"
        assert "font-size: 0.7em" in colophon.text
        assert provenance.summary() in colophon.text

    def test_colophon_appended_with_revision_alone(self) -> None:
        """A content revision without software provenance still produces the colophon."""
        revision = Revision(content_hash="d8666f090982" + "0" * 52, label="draft-3")
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="Doc")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {}, revision=revision)
        blocks = list(doc.content)
        assert isinstance(blocks[-2], pf.HorizontalRule)
        assert isinstance(blocks[-1], pf.RawBlock)
        assert "rev d8666f090982" in blocks[-1].text
        assert "label draft-3" in blocks[-1].text


class TestColophonSummary:
    """colophon_summary() joins the software and content halves into one line."""

    _PROVENANCE = Provenance(commit="abc123def456")
    _REVISION = Revision(content_hash="d8666f090982" + "0" * 52)

    def test_both_halves(self) -> None:
        """Provenance leads, revision follows, dot-joined."""
        assert colophon_summary(self._PROVENANCE, self._REVISION) == "guffin · abc123d · rev d8666f090982"

    def test_provenance_only(self) -> None:
        """A missing revision leaves the provenance summary alone."""
        assert colophon_summary(self._PROVENANCE, None) == "guffin · abc123d"

    def test_revision_only(self) -> None:
        """A missing provenance leaves the revision summary alone."""
        assert colophon_summary(None, self._REVISION) == "rev d8666f090982"

    def test_neither_is_empty(self) -> None:
        """Both absent yields the empty string."""
        assert colophon_summary(None, None) == ""


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocHeadingVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocHeadingVertex:
    """Tests for vertex_tree_to_pandoc() — HeadingVertex rendering."""

    def test_heading_level_preserved(self) -> None:
        """HeadingVertex produces a Header block at the recorded heading level."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section 1", heading_level=2)
        tree = VertexTree(tree_vertices=[page, heading])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 2
        assert _collect_text(blocks[0]) == "Section 1"

    def test_h3_heading(self) -> None:
        """HeadingVertex at level 3 produces an H3 Header."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Subsection", heading_level=3)
        tree = VertexTree(tree_vertices=[page, heading])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 3

    def test_h4_through_h6(self) -> None:
        """HeadingVertices at levels 4, 5, 6 produce Headers at the correct levels."""
        page = PageVertex(uid="page00001", title="P", children=["head0004a", "head0005a", "head0006a"])
        h4 = HeadingVertex(uid="head0004a", text="H4", heading_level=4)
        h5 = HeadingVertex(uid="head0005a", text="H5", heading_level=5)
        h6 = HeadingVertex(uid="head0006a", text="H6", heading_level=6)
        tree = VertexTree(tree_vertices=[page, h4, h5, h6])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        assert [b.level for b in blocks] == [4, 5, 6]

    def test_nested_headings_flattened_into_document(self) -> None:
        """Children of a HeadingVertex are rendered as sibling blocks, not nested."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        h2 = HeadingVertex(uid="head0001a", text="Chapter", heading_level=2, children=["head0001b"])
        h3 = HeadingVertex(uid="head0001b", text="Section", heading_level=3)
        tree = VertexTree(tree_vertices=[page, h2, h3])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        assert len(blocks) == 2
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 2
        assert _collect_text(blocks[0]) == "Chapter"
        assert isinstance(blocks[1], pf.Header)
        assert blocks[1].level == 3
        assert _collect_text(blocks[1]) == "Section"


class TestVertexTreeToPandocHeadingSemantics:
    """A heading's element-type / matter tags drive its Header's epub:type and unnumbered class."""

    def _tree_with_heading_tags(self, tags: list[tuple[str, str]]) -> VertexTree:
        """Build a VertexTree whose single H1 carries each ``(name, value)`` as a guffin-domain tag."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        heading = HeadingVertex(
            uid="head0001a",
            text="Section",
            heading_level=1,
            attribute_assignments=[
                AttributeAssignment(
                    attribute=AttributeInstance(
                        definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link
                    ),
                    values=(LiteralValue(value=value),),
                )
                for name, value in tags
            ],
        )
        return VertexTree(tree_vertices=[PageVertex(uid="page00001", title="Doc", children=["head0001a"]), heading])

    def _heading_with_tag(self, name: str, value: str) -> pf.Header:
        """Render an H1 tagged with ``<name> = value`` (guffin domain) and return its Header."""
        doc, _ = vertex_tree_to_pandoc(self._tree_with_heading_tags([(name, value)]), {}, {})
        return next(block for block in doc.content if isinstance(block, pf.Header))

    def _heading_with_element_type(self, term: str) -> pf.Header:
        """Render an H1 tagged with ``element-type = term``."""
        return self._heading_with_tag("element-type", term)

    def _matter_warned(self, caplog: pytest.LogCaptureFixture) -> bool:
        """Whether a WARNING mentioning the matter override/conflict was logged."""
        return any(record.levelno == logging.WARNING and "matter" in record.getMessage() for record in caplog.records)

    def test_mapped_element_stamps_epub_type(self) -> None:
        """A mapped element stamps the corresponding epub:type, bridging label divergences."""
        assert self._heading_with_element_type("colophon").attributes["epub:type"] == "colophon"
        assert self._heading_with_element_type("table-of-contents").attributes["epub:type"] == "toc"

    def test_unmapped_element_stamps_nothing(self) -> None:
        """An element with no EPUB counterpart (title-page) leaves the Header without epub:type."""
        assert "epub:type" not in self._heading_with_element_type("title-page").attributes

    def test_unknown_element_is_ignored(self) -> None:
        """An unrecognised element-type value is dropped (no epub:type), not raised."""
        assert "epub:type" not in self._heading_with_element_type("not-an-element").attributes

    def test_non_body_matter_is_unnumbered(self) -> None:
        """Front- and back-matter elements mark the Header unnumbered (excluded from --number-sections)."""
        assert "unnumbered" in self._heading_with_element_type("acknowledgments").classes  # front matter
        assert "unnumbered" in self._heading_with_element_type("colophon").classes  # back matter
        assert "unnumbered" in self._heading_with_element_type("title-page").classes  # front, no epub:type

    def test_body_matter_is_numbered(self) -> None:
        """A body-matter element leaves the Header numbered (no unnumbered class)."""
        assert "unnumbered" not in self._heading_with_element_type("chapter").classes

    def test_untagged_heading_is_numbered(self) -> None:
        """An untagged heading is not marked unnumbered."""
        page = PageVertex(uid="page00001", title="Doc", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Plain", heading_level=1)
        tree = VertexTree(tree_vertices=[page, heading])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        header = next(block for block in doc.content if isinstance(block, pf.Header))
        assert "unnumbered" not in header.classes

    def test_bare_matter_tag_unnumbers_without_epub_type(self) -> None:
        """A bespoke section tagged with a bare front-/back-matter is unnumbered and has no epub:type."""
        front = self._heading_with_tag("matter", "front-matter")
        assert "unnumbered" in front.classes
        assert "epub:type" not in front.attributes
        assert "unnumbered" in self._heading_with_tag("matter", "back-matter").classes

    def test_bare_body_matter_tag_is_numbered(self) -> None:
        """A bare body-matter tag leaves the heading numbered."""
        assert "unnumbered" not in self._heading_with_tag("matter", "body-matter").classes

    def test_matter_tag_overrides_conflicting_element_type(self, caplog: pytest.LogCaptureFixture) -> None:
        """A conflicting matter:: tag overrides the element-type's matter, with a warning logged."""
        tree = self._tree_with_heading_tags([("element-type", "chapter"), ("matter", "front-matter")])
        with caplog.at_level(logging.WARNING):
            doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        header = next(block for block in doc.content if isinstance(block, pf.Header))
        # matter:: front-matter overrides chapter's body matter -> unnumbered; epub:type still from element-type.
        assert "unnumbered" in header.classes
        assert header.attributes["epub:type"] == "chapter"
        assert self._matter_warned(caplog)

    def test_agreeing_matter_tag_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        """A matter:: tag that agrees with the element-type's matter is redundant, not a conflict."""
        tree = self._tree_with_heading_tags([("element-type", "chapter"), ("matter", "body-matter")])
        with caplog.at_level(logging.WARNING):
            doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        header = next(block for block in doc.content if isinstance(block, pf.Header))
        assert "unnumbered" not in header.classes
        assert not self._matter_warned(caplog)

    def test_matter_data_attribute_carries_cmos_division(self) -> None:
        """A tagged heading stamps its CMOS matter as the data-guffin-matter <body> division."""
        assert self._heading_with_element_type("introduction").attributes[MATTER_DATA_ATTRIBUTE] == "frontmatter"
        assert self._heading_with_element_type("chapter").attributes[MATTER_DATA_ATTRIBUTE] == "bodymatter"
        assert self._heading_with_element_type("colophon").attributes[MATTER_DATA_ATTRIBUTE] == "backmatter"

    def test_bare_matter_tag_carries_division(self) -> None:
        """A bespoke matter:: tag stamps its division in data-guffin-matter (with no epub:type)."""
        header = self._heading_with_tag("matter", "back-matter")
        assert header.attributes[MATTER_DATA_ATTRIBUTE] == "backmatter"
        assert "epub:type" not in header.attributes

    def test_untagged_heading_has_no_matter_attribute(self) -> None:
        """A heading whose matter does not resolve carries no data-guffin-matter attribute."""
        assert MATTER_DATA_ATTRIBUTE not in self._heading_with_element_type("not-an-element").attributes


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocText
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocText:
    """Tests for vertex_tree_to_pandoc() — TextVertex rendering."""

    def test_depth_1_default_layout_is_bullet(self) -> None:
        """Under the default (BULLET) page layout, a direct child text renders as a bullet item."""
        page = PageVertex(uid="page00001", title="P", children=["txt00001a"])
        block = TextVertex(uid="txt00001a", text="Hello world")
        tree = VertexTree(tree_vertices=[page, block])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        item = list(blocks[0].content)[0]
        assert _collect_text(list(item.content)[0]) == "Hello world"

    def test_document_layout_renders_para(self) -> None:
        """With a DOCUMENT layout on the page, a direct child text renders as a flowing Para."""
        page = PageVertex(uid="page00001", title="P", children=["txt00001a"])
        block = TextVertex(uid="txt00001a", text="Hello world")
        tree = VertexTree(tree_vertices=[page, block])
        view_map = {"page00001": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        _doc, _ = vertex_tree_to_pandoc(tree, {}, view_map)
        blocks = list(_doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        assert _collect_text(blocks[0]) == "Hello world"

    def test_numbered_layout_renders_ordered_list(self) -> None:
        """With a NUMBERED layout on the page, direct child texts render as an OrderedList."""
        page = PageVertex(uid="page00001", title="P", children=["txt00001a", "txt00001b"])
        b1 = TextVertex(uid="txt00001a", text="One")
        b2 = TextVertex(uid="txt00001b", text="Two")
        tree = VertexTree(tree_vertices=[page, b1, b2])
        view_map = {"page00001": VertexView(children_layout=ChildrenLayout.NUMBERED)}
        _doc, _ = vertex_tree_to_pandoc(tree, {}, view_map)
        blocks = list(_doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.OrderedList)
        assert len(list(blocks[0].content)) == 2

    def test_depth_2_text_under_heading_is_bullet(self) -> None:
        """A TextVertex under a HeadingVertex (depth 2) renders as a BulletList."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section", heading_level=2, children=["txt00001a"])
        block = TextVertex(uid="txt00001a", text="Body text")
        tree = VertexTree(tree_vertices=[page, heading, block])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        assert len(blocks) == 2
        assert isinstance(blocks[1], pf.BulletList)
        items = list(blocks[1].content)
        assert len(items) == 1
        assert isinstance(items[0], pf.ListItem)
        item_blocks = list(items[0].content)
        assert isinstance(item_blocks[0], pf.Plain)
        assert _collect_text(item_blocks[0]) == "Body text"

    def test_nested_text_produces_nested_bullet_list(self) -> None:
        """A TextVertex child of another TextVertex renders as a nested BulletList."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="S", heading_level=2, children=["txt00001a"])
        parent = TextVertex(uid="txt00001a", text="Parent", children=["txt00001b"])
        child = TextVertex(uid="txt00001b", text="Child")
        tree = VertexTree(tree_vertices=[page, heading, parent, child])
        _doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(_doc.content)
        bullet_list = blocks[1]
        assert isinstance(bullet_list, pf.BulletList)
        parent_item = list(bullet_list.content)[0]
        parent_item_blocks = list(parent_item.content)
        assert len(parent_item_blocks) == 2
        nested_list = parent_item_blocks[1]
        assert isinstance(nested_list, pf.BulletList)
        child_item = list(nested_list.content)[0]
        assert _collect_text(list(child_item.content)[0]) == "Child"


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocImageVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocImageVertex:
    """Tests for vertex_tree_to_pandoc() — ImageVertex rendering."""

    def test_fetched_image_is_embedded(self, tmp_path: Path) -> None:
        """When asset_files has an entry for the vertex, a pf.Image is used."""
        fake_img = tmp_path / "photo.jpg"
        fake_img.write_bytes(b"")
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            alt_text="A flower",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {"img00001a": fake_img}, {})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        inline = list(blocks[0].content)[0]
        assert isinstance(inline, pf.Image)
        assert inline.url == str(fake_img)

    def test_unfetched_image_falls_back_to_link(self) -> None:
        """When asset_files has no entry for the vertex, a pf.Link is used."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            alt_text="A flower",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        inline = list(blocks[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert inline.url == str(_IMAGE_URL)

    def test_unfetched_image_link_label_uses_alt_text(self) -> None:
        """The fallback link label uses alt_text when present."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            alt_text="A flower",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        inline = list(list(doc.content)[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert _collect_text(inline) == "A flower"

    def test_unfetched_image_link_label_falls_back_to_file_name(self) -> None:
        """The fallback link label uses file_name when alt_text is absent."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            file_name="photo.jpg",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        inline = list(list(doc.content)[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert _collect_text(inline) == "photo.jpg"


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocPdfVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocPdfVertex:
    """Tests for vertex_tree_to_pandoc() — PdfVertex rendering.

    A link-placed PDF embed follows its parent's children layout like a text sibling, so under
    the default BULLET layout the link paragraph renders inside a bulleted list item.
    """

    def _tree(self, file_name: str | None = "paper.pdf.enc") -> VertexTree:
        """Build a page-rooted tree containing a single PdfVertex."""
        page = PageVertex(uid="page00001", title="P", children=["pdf00001a"])
        pdf = PdfVertex(uid="pdf00001a", source=_PDF_URL, file_name=file_name)
        return VertexTree(tree_vertices=[page, pdf])

    @staticmethod
    def _bulleted_link(doc: pf.Doc) -> pf.Link:
        """Extract the PDF link from the single bulleted list item it renders inside."""
        blocks = list(doc.content)
        assert len(blocks) == 1
        bullet = blocks[0]
        assert isinstance(bullet, pf.BulletList)
        para = list(list(bullet.content)[0].content)[0]
        assert isinstance(para, pf.Para)
        inline = list(para.content)[0]
        assert isinstance(inline, pf.Link)
        return inline

    def test_fetched_pdf_links_to_local_path(self, tmp_path: Path) -> None:
        """When asset_files has an entry for the vertex, the link targets the local path."""
        fake_pdf = tmp_path / "paper.pdf"
        fake_pdf.write_bytes(b"")
        doc, _ = vertex_tree_to_pandoc(self._tree(), {"pdf00001a": fake_pdf}, {})
        assert self._bulleted_link(doc).url == str(fake_pdf)

    def test_unfetched_pdf_falls_back_to_source_url(self) -> None:
        """When asset_files has no entry for the vertex, the link targets the remote source URL."""
        doc, _ = vertex_tree_to_pandoc(self._tree(), {}, {})
        assert self._bulleted_link(doc).url == str(_PDF_URL)

    def test_link_label_strips_encryption_suffix(self) -> None:
        """The link label is the storage filename with Roam's .enc suffix stripped."""
        doc, _ = vertex_tree_to_pandoc(self._tree(file_name="paper.pdf.enc"), {}, {})
        assert _collect_text(self._bulleted_link(doc)) == "paper.pdf"

    def test_link_label_prefers_original_file_name(self) -> None:
        """When the originally uploaded filename is known, it labels the link."""
        page = PageVertex(uid="page00001", title="P", children=["pdf00001a"])
        pdf = PdfVertex(
            uid="pdf00001a", source=_PDF_URL, file_name="u-F9pv-nvn.pdf.enc", original_file_name="dummy.pdf"
        )
        tree = VertexTree(tree_vertices=[page, pdf])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert _collect_text(self._bulleted_link(doc)) == "dummy.pdf"

    def test_link_label_falls_back_to_source_url(self) -> None:
        """When no filename is known, the link label is the source URL."""
        doc, _ = vertex_tree_to_pandoc(self._tree(file_name=None), {}, {})
        assert _collect_text(self._bulleted_link(doc)) == str(_PDF_URL)

    def test_inline_placed_pdf_stays_structural(self) -> None:
        """A pdf-render:: inline embed does not join the sibling list; it stays a standalone Para."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        inline_tag = AttributeAssignment(
            attribute=AttributeInstance(
                definition=Attribute(name="pdf-render", domain=AttributeDomain.GUFFIN), link=link
            ),
            values=(LiteralValue(value="inline"),),
        )
        page = PageVertex(uid="page00001", title="P", children=["pdf00001a"])
        pdf = PdfVertex(uid="pdf00001a", source=_PDF_URL, file_name="paper.pdf.enc", attribute_assignments=[inline_tag])
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, pdf]), {}, {})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)


# ---------------------------------------------------------------------------
# TestBuildBlocksCoalescing
# ---------------------------------------------------------------------------


class TestBuildBlocksCoalescing:
    """Tests for build_child_blocks() — sibling TextVertex (and link-placed PDF) coalescing."""

    def test_consecutive_text_siblings_coalesced_into_one_bullet_list(self) -> None:
        """Under a BULLET layout, consecutive TextVertex siblings produce a single BulletList."""
        t1 = TextVertex(uid="txt000001", text="Item 1")
        t2 = TextVertex(uid="txt000002", text="Item 2")
        blocks = build_child_blocks(
            ["txt000001", "txt000002"], VertexTree(tree_vertices=[t1, t2]), {}, {}, {}, ChildrenLayout.BULLET, depth=2
        )
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        assert len(list(blocks[0].content)) == 2

    def test_link_placed_pdf_coalesces_with_text_siblings(self) -> None:
        """A link-placed PDF embed joins the same BulletList as its text siblings."""
        text = TextVertex(uid="txt000001", text="the following block is a PDF")
        pdf = PdfVertex(uid="pdf000001", source=_PDF_URL, file_name="paper.pdf.enc")
        blocks = build_child_blocks(
            ["txt000001", "pdf000001"],
            VertexTree(tree_vertices=[text, pdf]),
            {},
            {},
            {},
            ChildrenLayout.BULLET,
            depth=2,
        )
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        items = list(blocks[0].content)
        assert len(items) == 2
        pdf_para = list(items[1].content)[0]
        assert isinstance(pdf_para, pf.Para)
        assert isinstance(list(pdf_para.content)[0], pf.Link)

    def test_numbered_layout_coalesces_into_ordered_list(self) -> None:
        """Under a NUMBERED layout, consecutive TextVertex siblings produce a single OrderedList."""
        t1 = TextVertex(uid="txt000001", text="Item 1")
        t2 = TextVertex(uid="txt000002", text="Item 2")
        blocks = build_child_blocks(
            ["txt000001", "txt000002"], VertexTree(tree_vertices=[t1, t2]), {}, {}, {}, ChildrenLayout.NUMBERED, depth=2
        )
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.OrderedList)
        assert len(list(blocks[0].content)) == 2

    def test_heading_between_text_siblings_splits_bullet_lists(self) -> None:
        """A HeadingVertex between two TextContentVertices produces two separate BulletLists."""
        t1 = TextVertex(uid="txt000001", text="Before")
        h = HeadingVertex(uid="head00001", text="Break", heading_level=3)
        t2 = TextVertex(uid="txt000002", text="After")
        blocks = build_child_blocks(
            ["txt000001", "head00001", "txt000002"],
            VertexTree(tree_vertices=[t1, h, t2]),
            {},
            {},
            {},
            ChildrenLayout.BULLET,
            depth=2,
        )
        assert len(blocks) == 3
        assert isinstance(blocks[0], pf.BulletList)
        assert isinstance(blocks[1], pf.Header)
        assert isinstance(blocks[2], pf.BulletList)

    def test_document_layout_text_is_not_coalesced(self) -> None:
        """Under a DOCUMENT layout, text siblings render as separate Paras, not a list."""
        t1 = TextVertex(uid="txt000001", text="Para 1")
        t2 = TextVertex(uid="txt000002", text="Para 2")
        blocks = build_child_blocks(
            ["txt000001", "txt000002"], VertexTree(tree_vertices=[t1, t2]), {}, {}, {}, ChildrenLayout.DOCUMENT, depth=1
        )
        assert len(blocks) == 2
        assert all(isinstance(b, pf.Para) for b in blocks)

    def test_unknown_uid_is_skipped(self) -> None:
        """A UID absent from vertex_tree is silently skipped."""
        t1 = TextVertex(uid="txt000001", text="Present")
        blocks = build_child_blocks(
            ["missingXY", "txt000001"], VertexTree(tree_vertices=[t1]), {}, {}, {}, ChildrenLayout.DOCUMENT, depth=1
        )
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocArticleFixture
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocArticleFixture:
    """Integration tests for vertex_tree_to_pandoc() using the Test Article 1 fixture."""

    @pytest.fixture(scope="class")
    def doc(self) -> pf.Doc:
        """Render the Test Article 1 fixture once and share the read-only Doc across the class.

        The tests below only inspect the result, so a single Pandoc invocation suffices for all of
        them (the call is the dominant cost in this module).
        """
        rendered, _ = vertex_tree_to_pandoc(article1_vertex_tree(), {}, {})
        return rendered

    def test_metadata_title_is_test_article_1(self, doc: pf.Doc) -> None:
        """Doc metadata title matches the page title from the fixture."""
        assert _collect_text(doc.metadata["title"]) == "Test Article 1"

    def test_block_count(self, doc: pf.Doc) -> None:
        """The fixture produces the expected number of top-level blocks."""
        # 1 Div(callout) + 3 H1s + 6 H2s + 3 H3s + 1 H4 + 3 Para(Link) + 6 BulletList = 23
        # (the link-placed Section 3.1 PDF embed lists with its text sibling; the inline-placed
        # Section 3.2 embed stays a standalone Para.  The unpublished Section 3.1_5 is included:
        # this builds straight from the vertex tree; drop_unpublished is a renderer prepare step)
        assert len(list(doc.content)) == 23

    def test_first_block_is_section_1_header(self, doc: pf.Doc) -> None:
        """The second block is an H1 Header for 'Section 1' (first block is the callout Para)."""
        second = list(doc.content)[1]
        assert isinstance(second, pf.Header)
        assert second.level == 1
        assert _collect_text(second) == "Section 1"

    def test_image_renders_as_fallback_link_when_no_asset_files(self, doc: pf.Doc) -> None:
        """The ImageVertex in the fixture renders as a pf.Link when asset_files is empty."""
        blocks = list(doc.content)
        image_para = next(
            (b for b in blocks if isinstance(b, pf.Para) and isinstance(list(b.content)[0], pf.Link)), None
        )
        assert image_para is not None

    def test_text_content_vertex_renders_as_bullet_list(self, doc: pf.Doc) -> None:
        """Each TextVertex renders as a top-level BulletList."""
        blocks = list(doc.content)
        bullet_lists = [b for b in blocks if isinstance(b, pf.BulletList)]
        assert len(bullet_lists) == 6
        items = list(bullet_lists[1].content)
        assert len(items) == 1
        assert _collect_text(list(items[0].content)[0]) == "AI assistant (Claude Opus 4.6):"


# ---------------------------------------------------------------------------
# TestAttributeAssignmentText
# ---------------------------------------------------------------------------


class TestAttributeAssignmentText:
    """Tests for _attribute_assignment_text — the reconstructed attribute-assignment Markdown line."""

    @staticmethod
    def _assignment() -> AttributeAssignment:
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="attribute1"), link=link),
            values=(LiteralValue(value="5"),),
        )

    def test_attribute_name_wrapped_in_bold_italic_underline_markup(self) -> None:
        """The label is [***<domain>/<name>***]{.underline} and the '::' separator collapses to ':'."""
        text = _attribute_assignment_text(self._assignment())
        assert text == "[***default/attribute1***]{.underline}: 5"

    def test_markup_parses_to_underline_bold_italic(self) -> None:
        """The reconstructed line parses so the attribute name is Underline > Strong > Emph."""
        text = _attribute_assignment_text(self._assignment())
        inlines = parse_inline_md([text])[text]
        underline = inlines[0]
        assert isinstance(underline, pf.Underline)
        strong = list(underline.content)[0]
        assert isinstance(strong, pf.Strong)
        emph = list(strong.content)[0]
        assert isinstance(emph, pf.Emph)
        assert _collect_text(emph) == "default/attribute1"


class TestBlockQuoteRendering:
    """A block quote's soft line-breaks render as hard breaks inside a single paragraph."""

    @staticmethod
    def _quote_blocks(text: str) -> list[pf.Block]:
        """Render a one-quote tree and return the blocks inside its BlockQuote."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["quote0001"])
        quote = BlockQuoteVertex(uid="quote0001", text=text)
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, quote]), {}, {})
        quotes = [block for block in doc.content if isinstance(block, pf.BlockQuote)]
        assert len(quotes) == 1
        return list(quotes[0].content)

    def test_single_line_is_one_paragraph(self) -> None:
        """A single-line quote is one Para with no line breaks."""
        blocks = self._quote_blocks("just one line")
        assert [type(block) for block in blocks] == [pf.Para]
        assert not any(isinstance(inline, pf.LineBreak) for inline in blocks[0].content)

    def test_soft_breaks_become_hard_breaks_in_one_paragraph(self) -> None:
        """Consecutive plain lines stay one Para, separated by LineBreak elements."""
        blocks = self._quote_blocks("May you do good.\nMay you forgive.\nMay you share.")
        assert [type(block) for block in blocks] == [pf.Para]
        line_breaks = [inline for inline in blocks[0].content if isinstance(inline, pf.LineBreak)]
        assert len(line_breaks) == 2

    def test_embedded_list_line_stays_a_list(self) -> None:
        """A bullet line inside the quote parses as a BulletList, not a paragraph continuation."""
        blocks = self._quote_blocks("first line\nsecond line\n- a list item")
        assert [type(block) for block in blocks] == [pf.Para, pf.BulletList]
        line_breaks = [inline for inline in blocks[0].content if isinstance(inline, pf.LineBreak)]
        assert len(line_breaks) == 1  # between the two plain lines only

    def test_blank_source_line_stays_a_paragraph_boundary(self) -> None:
        """An authored blank line still splits the quote into two paragraphs."""
        blocks = self._quote_blocks("first paragraph\n\nsecond paragraph")
        assert [type(block) for block in blocks] == [pf.Para, pf.Para]


class TestEffectiveLayout:
    """_effective_layout applies the tri-state rule: explicit entry, else inherited, else default."""

    _VIEW_MAP: dict[str, VertexView] = {"aaaaaaaaa": VertexView(children_layout=ChildrenLayout.DOCUMENT)}

    def test_explicit_entry_wins(self) -> None:
        """A vertex with its own explicit entry keeps that layout, whatever is inherited."""
        assert _effective_layout("aaaaaaaaa", self._VIEW_MAP, ChildrenLayout.NUMBERED) is ChildrenLayout.DOCUMENT

    def test_absent_entry_adopts_inherited(self) -> None:
        """A vertex with no explicit entry adopts the inherited layout."""
        assert _effective_layout("bbbbbbbbb", self._VIEW_MAP, ChildrenLayout.NUMBERED) is ChildrenLayout.NUMBERED

    def test_explicit_bullet_is_distinct_from_absent(self) -> None:
        """An explicit BULLET entry stops inheritance rather than being conflated with unset."""
        view_map = {"aaaaaaaaa": VertexView(children_layout=ChildrenLayout.BULLET)}
        assert _effective_layout("aaaaaaaaa", view_map, ChildrenLayout.DOCUMENT) is ChildrenLayout.BULLET


class TestLayoutInheritanceRendering:
    """End-to-end: the tri-state effective-layout rules govern the rendered document."""

    def test_inherited_layout_flows_descendant_children_in_rendered_doc(self) -> None:
        """A heading inheriting DOCUMENT lays its text children out as flowing Paras."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["sect00001"])
        sect = HeadingVertex(uid="sect00001", text="Part", heading_level=1, children=["sub000001"])
        sub = HeadingVertex(uid="sub000001", text="Chapter", heading_level=2, children=["texta0001", "textb0001"])
        text_a = TextVertex(uid="texta0001", text="para a")
        text_b = TextVertex(uid="textb0001", text="para b")
        tree = VertexTree(tree_vertices=[page, sect, sub, text_a, text_b])
        # Only the ancestor (sect00001) is DOCUMENT; sub000001 inherits it.
        view_map = {"sect00001": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        doc, _ = vertex_tree_to_pandoc(tree, {}, view_map)
        blocks = list(doc.content)
        assert not any(isinstance(block, pf.BulletList) for block in blocks)  # would bullet without inheritance
        paras = [block for block in blocks if isinstance(block, pf.Para)]
        assert [_collect_text(para) for para in paras] == ["para a", "para b"]

    def test_no_explicit_entries_render_default_bullets(self) -> None:
        """With an empty view map, children render in the default BULLET layout."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["texta0001", "textb0001"])
        text_a = TextVertex(uid="texta0001", text="item a")
        text_b = TextVertex(uid="textb0001", text="item b")
        tree = VertexTree(tree_vertices=[page, text_a, text_b])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        assert any(isinstance(block, pf.BulletList) for block in doc.content)

    def test_embedded_page_own_explicit_layout_applies(self) -> None:
        """A page-embed target's own explicit DOCUMENT entry lays its children out as Paras."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["embed0001"])
        embed = PageEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="refpage01"))
        target = PageVertex(uid="refpage01", title="Embedded", children=["refpara01", "refpara02"])
        para_1 = TextVertex(uid="refpara01", text="embedded para 1")
        para_2 = TextVertex(uid="refpara02", text="embedded para 2")
        tree = VertexTree(tree_vertices=[page, embed], ref_vertices=[target, para_1, para_2])
        view_map = {"refpage01": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        doc, _ = vertex_tree_to_pandoc(tree, {}, view_map)
        blocks = list(doc.content)
        assert not any(isinstance(block, pf.BulletList) for block in blocks)
        paras = [block for block in blocks if isinstance(block, pf.Para)]
        assert [_collect_text(para) for para in paras] == ["embedded para 1", "embedded para 2"]

    def test_transcluded_tree_inherits_through_embed_site(self) -> None:
        """The transclusion-parent rule: an embed's target inherits the embed's effective layout."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["sect00001"])
        sect = HeadingVertex(uid="sect00001", text="Section", heading_level=1, children=["embed0001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="reftext01"))
        target = TextVertex(uid="reftext01", text="transcluded root", children=["refchild1"])
        child = TextVertex(uid="refchild1", text="transcluded child")
        tree = VertexTree(tree_vertices=[page, sect, embed], ref_vertices=[target, child])
        # DOCUMENT on the section flows through the embed into the transcluded subtree.
        view_map = {"sect00001": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        doc, _ = vertex_tree_to_pandoc(tree, {}, view_map)
        assert not any(isinstance(block, pf.BulletList) for block in doc.content)

    def test_transcluded_tree_ignores_original_host_parent(self) -> None:
        """The transclusion-parent rule: the target's original host-page parent contributes nothing."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["sect00001"])
        sect = HeadingVertex(uid="sect00001", text="Section", heading_level=1, children=["embed0001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="reftext01"))
        # The target's original parent (present among the refs, NUMBERED) must not leak in.
        host_parent = TextVertex(uid="refhost01", text="original host parent", children=["reftext01"])
        target = TextVertex(uid="reftext01", text="transcluded root", children=["refchild1"])
        child = TextVertex(uid="refchild1", text="transcluded child")
        tree = VertexTree(tree_vertices=[page, sect, embed], ref_vertices=[host_parent, target, child])
        view_map = {
            "sect00001": VertexView(children_layout=ChildrenLayout.DOCUMENT),
            "refhost01": VertexView(children_layout=ChildrenLayout.NUMBERED),
        }
        doc, _ = vertex_tree_to_pandoc(tree, {}, view_map)
        # The embed site's DOCUMENT governs: no list of any kind in the output.
        assert not any(isinstance(block, (pf.BulletList, pf.OrderedList)) for block in doc.content)
