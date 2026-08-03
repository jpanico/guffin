"""Tests for the roam_tree_to_guffin module."""

import datetime
import json
import logging

import pytest
import yaml
from pydantic import ValidationError

from guffin.model.attribute import AttributeDomain, LiteralValue, ReferenceValue
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import (
    BlockEmbedVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageEmbedVertex,
    PageVertex,
    PdfVertex,
    QuoteBlockVertex,
    QuoteType,
    TableVertex,
    TextVertex,
    TodoState,
    Vertex,
    VertexType,
    vertex_adapter,
)
from guffin.model.vertex_link import VertexLinkKind
from guffin.model.vertex_view import ChildrenLayout, Semantic, SourceChannel, VertexView
from guffin.roam.better_bullet import BetterBulletProvenance, BetterBulletType
from guffin.roam.markdown import ROAM_NATIVE_TABLE_RAW_MARKER
from guffin.roam.node import NodeType, RoamNode, node_type
from guffin.roam.node_network import min_effective_heading_level
from guffin.roam.node_tree import NodeTree, NodeTreeDFSIterator
from guffin.roam.primitives import ChildrenViewType, Id, IdObject
from guffin.roam.todo import TodoState as RoamTodoState
from guffin.transcribe.roam_tree_to_guffin import (
    SEMANTIC_BY_BULLET_TYPE,
    SOURCE_CHANNEL_BY_PROVENANCE,
    TODO_STATE_BY_ROAM_STATE,
    _is_meta_block,
    build_view_map,
    to_block_embed_vertex,
    to_callout_vertex,
    to_code_block_vertex,
    to_heading_vertex,
    to_image_vertex,
    to_page_embed_vertex,
    to_page_vertex,
    to_pdf_vertex,
    to_quote_block_vertex,
    to_render_bundle,
    to_table_vertex,
    to_text_vertex,
    to_todo_vertex,
    transcribe,
    transcribe_standalone_node,
    vertex_type,
)

# A real Firebase Storage URL whose path encodes the filename "photo.jpeg" (media_type "image/jpeg"):
_FIRESTORE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING = f"![A flower]({_FIRESTORE_URL})"
# A real Firebase Storage URL whose path encodes the filename "paper.pdf.enc":
_FIRESTORE_PDF_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/pdfs%2Fpaper.pdf.enc?alt=media&token=abc123"
)
_PDF_STRING = f"{{{{pdf: {_FIRESTORE_PDF_URL}}}}}"
_CALLOUT_STRING: str = "[[>]] [[!NOTE]] This is a note"
# Raw Roam form: closing fence attached to the final content line (no separating newline).
_CODE_STRING: str = "```python\ndef f():\n    pass```"

from conftest import (
    FIXTURES_JSON_DIR,
    FIXTURES_YAML_DIR,
    YamlFixtureLoader,
    article0_node_tree,
    article1_node_tree,
    article4_node_tree,
    article5_node_tree,
)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_page(uid: str = "pageuid01", node_id: int = 100, title: str = "My Page") -> RoamNode:
    """Return a minimal page RoamNode."""
    return RoamNode(uid=uid, id=node_id, title=title, children=[])


def _make_image(uid: str = "imageuid1", node_id: int = 101, string: str = _IMAGE_STRING) -> RoamNode:
    """Return a minimal Firebase Storage image-block RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_pdf(uid: str = "pdfuid001", node_id: int = 108, string: str = _PDF_STRING) -> RoamNode:
    """Return a minimal Firebase Storage PDF-block RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_heading(
    uid: str = "headuid01",
    node_id: int = 102,
    string: str = "Chapter One",
    heading: int = 2,
) -> RoamNode:
    """Return a minimal native-heading RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        heading=heading,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_ah_heading(
    uid: str = "ahheaduid",
    node_id: int = 103,
    string: str = "Deep Heading",
    level: str = "h4",
) -> RoamNode:
    """Return a minimal Augmented Headings RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        props={"ah-level": level},
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_text(
    uid: str = "textuid01",
    node_id: int = 104,
    string: str = "Some plain text",
) -> RoamNode:
    """Return a minimal plain-text RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_callout(
    uid: str = "caluid001",
    node_id: int = 105,
    string: str = _CALLOUT_STRING,
) -> RoamNode:
    """Return a minimal callout block RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_code(
    uid: str = "codeuid01",
    node_id: int = 106,
    string: str = _CODE_STRING,
) -> RoamNode:
    """Return a minimal fenced code block RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_block_quote(
    uid: str = "bquid0001",
    node_id: int = 107,
    string: str = "> A quoted line",
) -> RoamNode:
    """Return a minimal block-quote RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _node_tree(*nodes: RoamNode) -> NodeTree:
    """Build a NodeTree rooted at the first node, with all *nodes* as the super_network."""
    return NodeTree.build(super_network=list(nodes), root_node=nodes[0])


# ---------------------------------------------------------------------------
# TestVertexType
# ---------------------------------------------------------------------------


class TestVertexType:
    """Tests for vertex_type."""

    def test_page_node_returns_roam_page(self) -> None:
        """Test that a page node classifies as PAGE."""
        assert vertex_type(_make_page()) is VertexType.PAGE

    def test_image_node_returns_roam_image(self) -> None:
        """Test that an image block node classifies as IMAGE."""
        assert vertex_type(_make_image()) is VertexType.IMAGE

    def test_pdf_node_returns_guffin_pdf(self) -> None:
        """Test that a PDF component block node classifies as PDF."""
        assert vertex_type(_make_pdf()) is VertexType.PDF

    def test_native_heading_node_returns_roam_heading(self) -> None:
        """Test that a native heading block node classifies as HEADING."""
        assert vertex_type(_make_heading()) is VertexType.HEADING

    def test_ah_level_heading_node_returns_roam_heading(self) -> None:
        """Test that an Augmented Headings block node classifies as HEADING."""
        assert vertex_type(_make_ah_heading()) is VertexType.HEADING

    def test_plain_text_node_returns_roam_text_content(self) -> None:
        """Test that a plain text block node classifies as TEXT."""
        assert vertex_type(_make_text()) is VertexType.TEXT

    def test_code_block_node_returns_guffin_code_block(self) -> None:
        """Test that a fenced code block node classifies as CODE_BLOCK."""
        assert vertex_type(_make_code()) is VertexType.CODE_BLOCK

    def test_md_block_quote_returns_guffin_block_quote(self) -> None:
        """Test that a standard Markdown block-quote node classifies as BLOCK_QUOTE."""
        assert vertex_type(_make_block_quote(string="> quoted text")) is VertexType.QUOTE_BLOCK

    def test_roam_block_quote_returns_guffin_block_quote(self) -> None:
        """Test that a Roam-style block-quote node classifies as BLOCK_QUOTE."""
        assert vertex_type(_make_block_quote(string="[[>]] quoted text")) is VertexType.QUOTE_BLOCK

    def test_bare_table_marker_returns_guffin_table(self) -> None:
        """Test that a bare {{table}} marker node classifies as TABLE."""
        assert vertex_type(_make_text(string="{{table}}")) is VertexType.TABLE

    def test_page_ref_table_marker_returns_guffin_table(self) -> None:
        """Test that the page-reference marker form {{[[table]]}} classifies as TABLE."""
        assert vertex_type(_make_text(string="{{[[table]]}}")) is VertexType.TABLE

    def test_open_todo_block_returns_guffin_todo(self) -> None:
        """Test that a {{[[TODO]]}}-led block node classifies as TODO."""
        assert vertex_type(_make_text(string="{{[[TODO]]}} an open item")) is VertexType.TODO

    def test_done_todo_block_returns_guffin_todo(self) -> None:
        """Test that a {{[[DONE]]}}-led block node classifies as TODO."""
        assert vertex_type(_make_text(string="{{[[DONE]]}} a completed item")) is VertexType.TODO

    def test_block_embed_returns_guffin_block_embed(self) -> None:
        """Test that a block-embed node classifies as BLOCK_EMBED."""
        assert vertex_type(_make_text(string="{{embed: ((wdMgyBiP9))}}")) is VertexType.BLOCK_EMBED

    def test_page_embed_returns_guffin_page_embed(self) -> None:
        """Test that a page-embed node classifies as PAGE_EMBED."""
        assert vertex_type(_make_text(string="{{embed: [[Some Page]]}}")) is VertexType.PAGE_EMBED

    def test_node_with_neither_title_nor_string_raises_validation_error(self) -> None:
        """Test that constructing a node missing both title and string raises ValidationError."""
        with pytest.raises(ValidationError):
            RoamNode(uid="badnode01", id=999)

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None raises a ValidationError."""
        with pytest.raises(ValidationError):
            vertex_type(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToPageVertex
# ---------------------------------------------------------------------------


class TestToPageVertex:
    """Tests for to_page_vertex."""

    def test_returns_roam_page_vertex_type(self) -> None:
        """Test that to_page_vertex produces a vertex with type PAGE."""
        node = _make_page()
        assert to_page_vertex(node, _node_tree(node)).vertex_type is VertexType.PAGE

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_page(uid="pageuid01")
        assert to_page_vertex(node, _node_tree(node)).uid == "pageuid01"

    def test_title_equals_node_title(self) -> None:
        """Test that the vertex title equals the source node's title."""
        node = _make_page(title="Section 1")
        assert to_page_vertex(node, _node_tree(node)).title == "Section 1"

    def test_daily_note_page_carries_its_date(self) -> None:
        """A daily-note page (MM-DD-YYYY uid) gets its calendar date on the vertex."""
        node = _make_page(uid="01-01-2026", title="January 1st, 2026")
        assert to_page_vertex(node, _node_tree(node)).daily_note_date == datetime.date(2026, 1, 1)

    def test_synthetic_page_has_no_daily_note_date(self) -> None:
        """A synthetic-uid page carries no daily-note date."""
        node = _make_page(uid="pageuid01", title="Some Page")
        assert to_page_vertex(node, _node_tree(node)).daily_note_date is None

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_page()
        assert to_page_vertex(node, _node_tree(node)).children is None

    def test_children_resolved_and_ordered_by_order_field(self) -> None:
        """Test that children are resolved from id_map and sorted ascending by their order field."""
        child1 = RoamNode(
            uid="child0001",
            id=201,
            string="c1",
            order=1,
            parents=[IdObject(id=100)],
            page=IdObject(id=100),
        )
        child2 = RoamNode(
            uid="child0002",
            id=202,
            string="c2",
            order=0,
            parents=[IdObject(id=100)],
            page=IdObject(id=100),
        )
        page = RoamNode(
            uid="pageuid01",
            id=100,
            title="My Page",
            children=[IdObject(id=201), IdObject(id=202)],
        )
        v = to_page_vertex(page, _node_tree(page, child1, child2))
        assert v.children == ["child0002", "child0001"]

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_page()
        assert to_page_vertex(node, _node_tree(node)).refs is None

    def test_refs_resolved_to_uids(self) -> None:
        """Test that ref stubs are resolved to UIDs via id_map."""
        ref_node = _make_text(uid="refnode01", node_id=301)
        page = RoamNode(
            uid="pageuid01",
            id=100,
            title="My Page",
            children=[],
            refs=[IdObject(id=301)],
        )
        v = to_page_vertex(page, _node_tree(page, ref_node))
        assert v.refs == ["refnode01"]

    def test_missing_title_raises_value_error(self) -> None:
        """Test that a node without a title raises ValueError."""
        node = _make_text()
        with pytest.raises(ValueError, match="no 'title'"):
            to_page_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_page_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToImageVertex
# ---------------------------------------------------------------------------


class TestToImageVertex:
    """Tests for to_image_vertex."""

    def test_returns_roam_image_vertex_type(self) -> None:
        """Test that to_image_vertex produces a vertex with type IMAGE."""
        node = _make_image()
        assert to_image_vertex(node, _node_tree(node)).vertex_type is VertexType.IMAGE

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_image(uid="imageuid1")
        assert to_image_vertex(node, _node_tree(node)).uid == "imageuid1"

    def test_source_host_is_firestore(self) -> None:
        """Test that the vertex source URL points to the Firebase Storage host."""
        v = to_image_vertex(_make_image(), _node_tree(_make_image()))
        assert v.source.host == "firebasestorage.googleapis.com"

    def test_alt_text_extracted_from_string(self) -> None:
        """Test that alt text is extracted and stripped from the Markdown image link."""
        node = _make_image(string=f"![My Photo]({_FIRESTORE_URL})")
        assert to_image_vertex(node, _node_tree(node)).alt_text == "My Photo"

    def test_alt_text_stripped_of_whitespace(self) -> None:
        """Test that leading/trailing whitespace (including newlines) is stripped from alt text."""
        node = _make_image(string=f"![A flower\n        ]({_FIRESTORE_URL})")
        assert to_image_vertex(node, _node_tree(node)).alt_text == "A flower"

    def test_alt_text_none_when_empty(self) -> None:
        """Test that empty alt text produces None rather than an empty string."""
        node = _make_image(string=f"![]({_FIRESTORE_URL})")
        assert to_image_vertex(node, _node_tree(node)).alt_text is None

    def test_media_type_inferred_from_source_url(self) -> None:
        """Test that the IANA media type is inferred from the source URL filename's extension."""
        assert to_image_vertex(_make_image(), _node_tree(_make_image())).media_type == "image/jpeg"

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the image node has no children."""
        node = _make_image()
        assert to_image_vertex(node, _node_tree(node)).children is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_image_vertex(node, _node_tree(node))

    def test_non_firestore_url_raises_value_error(self) -> None:
        """Test that a string with a non-Firebase Storage https URL raises ValueError."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string="![alt](https://example.com/image.jpg)",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        with pytest.raises(ValueError, match="contains no Firebase Storage URL"):
            to_image_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_image_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToPdfVertex
# ---------------------------------------------------------------------------


class TestToPdfVertex:
    """Tests for to_pdf_vertex."""

    def test_returns_guffin_pdf_vertex_type(self) -> None:
        """Test that to_pdf_vertex produces a vertex with type PDF."""
        node = _make_pdf()
        assert to_pdf_vertex(node, _node_tree(node)).vertex_type is VertexType.PDF

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_pdf(uid="pdfuid001")
        assert to_pdf_vertex(node, _node_tree(node)).uid == "pdfuid001"

    def test_source_host_is_firestore(self) -> None:
        """Test that the vertex source URL points to the Firebase Storage host."""
        v = to_pdf_vertex(_make_pdf(), _node_tree(_make_pdf()))
        assert v.source.host == "firebasestorage.googleapis.com"

    def test_page_reference_form_accepted(self) -> None:
        """Test that the {{[[pdf]]: <url>}} page-reference form transcribes identically."""
        node = _make_pdf(string=f"{{{{[[pdf]]: {_FIRESTORE_PDF_URL}}}}}")
        assert str(to_pdf_vertex(node, _node_tree(node)).source) == _FIRESTORE_PDF_URL

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the PDF node has no children."""
        node = _make_pdf()
        assert to_pdf_vertex(node, _node_tree(node)).children is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_pdf_vertex(node, _node_tree(node))

    def test_non_firestore_url_raises_value_error(self) -> None:
        """Test that a PDF component with a non-Firebase Storage https URL raises ValueError."""
        node = _make_pdf(string="{{pdf: https://example.com/paper.pdf}}")
        with pytest.raises(ValueError, match="contains no Firebase Storage PDF component"):
            to_pdf_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_pdf_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToHeadingVertex
# ---------------------------------------------------------------------------


class TestToHeadingVertex:
    """Tests for to_heading_vertex."""

    def test_returns_roam_heading_vertex_type(self) -> None:
        """Test that to_heading_vertex produces a vertex with type HEADING."""
        node = _make_heading()
        assert to_heading_vertex(node, _node_tree(node)).vertex_type is VertexType.HEADING

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_heading(uid="headuid01")
        assert to_heading_vertex(node, _node_tree(node)).uid == "headuid01"

    def test_text_equals_string(self) -> None:
        """Test that the vertex text equals the node's block string."""
        node = _make_heading(string="Introduction")
        assert to_heading_vertex(node, _node_tree(node)).text == "Introduction"

    def test_native_heading_levels_preserved(self) -> None:
        """Test that native heading levels 1–3 are preserved in the vertex."""
        for level in (1, 2, 3):
            node = _make_heading(heading=level)
            assert to_heading_vertex(node, _node_tree(node)).heading_level == level

    def test_ah_level_heading_levels_resolved(self) -> None:
        """Test that Augmented Headings levels h4–h6 are resolved to integers 4–6."""
        for level_str, expected in (("h4", 4), ("h5", 5), ("h6", 6)):
            node = _make_ah_heading(level=level_str)
            assert to_heading_vertex(node, _node_tree(node)).heading_level == expected

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the heading node has no children."""
        node = _make_heading()
        assert to_heading_vertex(node, _node_tree(node)).children is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_heading_vertex(node, _node_tree(node))

    def test_no_heading_raises_value_error(self) -> None:
        """Test that a node with no effective heading level raises ValueError."""
        node = _make_text()
        with pytest.raises(ValueError, match="no effective heading level"):
            to_heading_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_heading_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToTextVertex
# ---------------------------------------------------------------------------


class TestToTextVertex:
    """Tests for to_text_vertex."""

    def test_returns_roam_text_content_vertex_type(self) -> None:
        """Test that to_text_vertex produces a vertex with type TEXT."""
        node = _make_text()
        assert to_text_vertex(node, _node_tree(node)).vertex_type is VertexType.TEXT

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_text(uid="textuid01")
        assert to_text_vertex(node, _node_tree(node)).uid == "textuid01"

    def test_text_equals_string(self) -> None:
        """Test that the vertex text equals the node's block string."""
        node = _make_text(string="Hello, world!")
        assert to_text_vertex(node, _node_tree(node)).text == "Hello, world!"

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_text()
        assert to_text_vertex(node, _node_tree(node)).children is None

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_text()
        assert to_text_vertex(node, _node_tree(node)).refs is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_text_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_text_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestToTodoVertex
# ---------------------------------------------------------------------------


class TestToTodoVertex:
    """Tests for to_todo_vertex and the TODO_STATE_BY_ROAM_STATE boundary map."""

    def test_returns_guffin_todo_vertex_type(self) -> None:
        """Test that to_todo_vertex produces a vertex with type TODO."""
        node = _make_text(string="{{[[TODO]]}} an open item")
        assert to_todo_vertex(node, _node_tree(node)).vertex_type is VertexType.TODO

    def test_open_marker_yields_todo_state(self) -> None:
        """Test that a {{[[TODO]]}} marker yields TodoState.TODO."""
        node = _make_text(string="{{[[TODO]]}} an open item")
        assert to_todo_vertex(node, _node_tree(node)).todo_state is TodoState.TODO

    def test_done_marker_yields_done_state(self) -> None:
        """Test that a {{[[DONE]]}} marker yields TodoState.DONE."""
        node = _make_text(string="{{[[DONE]]}} a completed item")
        assert to_todo_vertex(node, _node_tree(node)).todo_state is TodoState.DONE

    def test_marker_is_stripped_from_text(self) -> None:
        """Test that the vertex text is the item text with the leading marker stripped."""
        node = _make_text(string="{{[[TODO]]}} an open item")
        assert to_todo_vertex(node, _node_tree(node)).text == "an open item"

    def test_marker_alone_yields_empty_text(self) -> None:
        """Test that a string that is exactly the marker yields an empty item text."""
        node = _make_text(string="{{[[TODO]]}}")
        assert to_todo_vertex(node, _node_tree(node)).text == ""

    def test_item_text_is_normalized_to_pandoc_md(self) -> None:
        """Test that the item text passes through Roam→Pandoc Markdown normalization."""
        node = _make_text(string="{{[[DONE]]}} finished the __italic__ part")
        assert to_todo_vertex(node, _node_tree(node)).text == "finished the *italic* part"

    def test_marker_inside_leading_markup_keeps_the_markup_on_the_text(self) -> None:
        """Test that a marker excised from inside formatting markup leaves the markup wrapping the text."""
        node = _make_text(string="#c:FUCHSIA **{{[[TODO]]}} a bold fuchsia item**")
        vertex = to_todo_vertex(node, _node_tree(node))
        assert vertex.todo_state is TodoState.TODO
        assert vertex.text == '[**a bold fuchsia item**]{color="fuchsia"}'

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_text(uid="todouid01", string="{{[[TODO]]}} an item")
        assert to_todo_vertex(node, _node_tree(node)).uid == "todouid01"

    def test_string_without_marker_raises_value_error(self) -> None:
        """Test that a block string leading with no TODO marker raises ValueError."""
        node = _make_text(string="just plain text")
        with pytest.raises(ValueError, match="no TODO marker"):
            to_todo_vertex(node, _node_tree(node))

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_todo_vertex(node, _node_tree(node))

    def test_todo_state_by_roam_state_is_total(self) -> None:
        """Every Roam TODO marker state maps to a model TodoState."""
        assert set(TODO_STATE_BY_ROAM_STATE) == set(RoamTodoState)


# ---------------------------------------------------------------------------
# TestToCalloutVertex
# ---------------------------------------------------------------------------


class TestToCalloutVertex:
    """Tests for to_callout_vertex."""

    def test_returns_guffin_callout_vertex_type(self) -> None:
        """Test that to_callout_vertex produces a vertex with type CALLOUT."""
        node = _make_callout()
        assert to_callout_vertex(node, _node_tree(node)).vertex_type is VertexType.CALLOUT

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_callout(uid="caluid002")
        assert to_callout_vertex(node, _node_tree(node)).uid == "caluid002"

    def test_callout_type_parsed(self) -> None:
        """Test that the callout type is extracted from the marker keyword."""
        node = _make_callout(string="[[>]] [[!WARNING]] Watch out")
        assert to_callout_vertex(node, _node_tree(node)).callout_type is CalloutVertex.CalloutType.WARNING

    def test_title_extracted(self) -> None:
        """Test that the title is the text following the callout marker."""
        node = _make_callout()
        assert to_callout_vertex(node, _node_tree(node)).title == "This is a note"

    def test_title_stripped_of_surrounding_whitespace(self) -> None:
        """Test that leading and trailing whitespace is stripped from the title."""
        node = _make_callout(string="[[>]] [[!NOTE]] Hello World  ")
        assert to_callout_vertex(node, _node_tree(node)).title == "Hello World"

    def test_body_is_empty_string(self) -> None:
        """Test that body is always an empty string (populated later, not by this function)."""
        node = _make_callout()
        assert to_callout_vertex(node, _node_tree(node)).body == ""

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_callout()
        assert to_callout_vertex(node, _node_tree(node)).children is None

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_callout()
        assert to_callout_vertex(node, _node_tree(node)).refs is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_callout_vertex(node, _node_tree(node))

    def test_non_callout_string_raises_value_error(self) -> None:
        """Test that a string not matching the callout marker raises ValueError."""
        node = _make_callout(string="Just a plain block")
        with pytest.raises(ValueError, match="does not match callout marker"):
            to_callout_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_callout_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]

    def test_article_0_fixture_callout_type(self) -> None:
        """Test that the Article 0 callout node (qnCiceZgk) yields CalloutType.INFO."""
        raw: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text(), Loader=YamlFixtureLoader
        )
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "qnCiceZgk")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        assert to_callout_vertex(fixture_node, tree).callout_type is CalloutVertex.CalloutType.INFO

    def test_article_0_fixture_title(self) -> None:
        """Test that the Article 0 callout node (qnCiceZgk) yields the expected title.

        The title is the first line after the marker and contains a U+2013 en dash.
        """
        raw: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text(), Loader=YamlFixtureLoader
        )
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "qnCiceZgk")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        expected: str = "THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE"
        assert to_callout_vertex(fixture_node, tree).title == expected

    def test_article_0_fixture_body(self) -> None:
        """Test that the Article 0 callout node (qnCiceZgk) yields the expected body.

        The body is everything after the first newline in the block string, stripped.
        """
        raw: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text(), Loader=YamlFixtureLoader
        )
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "qnCiceZgk")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        expected: str = (
            "Features:\n"
            "- 3 top-level blocks\n"
            "- nested blocks\n"
            "- *italics* text\n"
            "- **bold** text\n"
            "- ~~strikethrough~~\n"
            "- [highlight]{.mark}\n"
            "- `inline-code`\n"
            "- fenced code mixed with text, block\n"
            "- isolated fenced code block\n"
            "- isolated fenced code block whose `plain text` fence language is overridden by a "
            "`code-language:: FORTRAN` tag\n"
            "- Markdown single line block quote\n"
            "- Markdown multi-line block quote\n"
            "- Roam-native single line block quote\n"
            "- Roam-native multi-line block quote\n"
            "- Roam-native single line pull quote\n"
            "- Roam-native multi-line pull quote\n"
            "- Roam-native TODO item (open and done)\n"
            "- Roam-native table (3x3)\n"
            "- this INFO `Callout box`, which contains Roam `page references`"
        )
        assert to_callout_vertex(fixture_node, tree).body == expected


# ---------------------------------------------------------------------------
# TestToCodeBlockVertex
# ---------------------------------------------------------------------------


class TestToCodeBlockVertex:
    """Tests for to_code_block_vertex."""

    def test_returns_code_block_vertex(self) -> None:
        """Test that a fenced code block node builds a CodeBlockVertex."""
        node = _make_code()
        assert isinstance(to_code_block_vertex(node, _node_tree(node)), CodeBlockVertex)

    def test_language_from_info_string(self) -> None:
        """Test that the opening fence's info string maps to a canonical language id."""
        node = _make_code()
        assert to_code_block_vertex(node, _node_tree(node)).language == "python"

    def test_code_excludes_fences(self) -> None:
        """Test that the code content excludes the opening and closing fences."""
        node = _make_code()
        assert to_code_block_vertex(node, _node_tree(node)).code == "def f():\n    pass"

    def test_unrecognised_language_raises(self) -> None:
        """Test that an info string outside CodeLanguage raises ValueError."""
        node = _make_code(string="```fortran\nprint *, 1\n```")
        with pytest.raises(ValueError):
            to_code_block_vertex(node, _node_tree(node))

    def test_article_0_fixture_code_block(self) -> None:
        """Test that the Article 0 isolated code block (C6xVTMnsh) yields PYTHON CodeBlockVertex."""
        raw: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text(), Loader=YamlFixtureLoader
        )
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "C6xVTMnsh")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        vertex: CodeBlockVertex = to_code_block_vertex(fixture_node, tree)
        assert vertex.language == "python"
        assert vertex.code.startswith("def fizz_buzz(limit: int = 100):")

    def test_article_0_fixture_code_source(self) -> None:
        """The Article 0 sourced code block (H_9tvN3-X) folds its authored code-source:: tag.

        Covers the real Roam-authored shape end to end — the ``guffin-meta::`` child, the
        ``code-source::`` grandchild with the space-before-comma separator, and the wire
        format the Local API actually returns — where the hand-built cases above use
        synthetic nodes.  Loads the with-refs fixture: folding needs the ``code-source``
        attribute *page* in :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id`, which the
        anchor-only nodes fixture deliberately omits.
        """
        raw_by_uid: dict[str, dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_0_nodes_by_uid.yaml").read_text(), Loader=YamlFixtureLoader
        )
        all_nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw_by_uid.values()]
        root_node: RoamNode = next(n for n in all_nodes if n.title == "[[Test Article]] 0")
        tree: NodeTree = NodeTree.build(super_network=all_nodes, root_node=root_node)
        fixture_node: RoamNode = tree.id_map[next(n.id for n in all_nodes if n.uid == "H_9tvN3-X")]
        vertex: CodeBlockVertex = to_code_block_vertex(fixture_node, tree)
        assert vertex.code_source is not None
        assert vertex.code_source.url == (
            "https://github.com/jpanico/guffin/blob/refs/heads/main/src/guffin/common/validation.py"
        )
        assert len(vertex.code_source.commit_sha) == 40
        assert vertex.code_source.file_ref().ref_name == "main"


# ---------------------------------------------------------------------------
# TestCodeLanguageOverride
# ---------------------------------------------------------------------------


class TestCodeLanguageOverride:
    """A ``code-language::`` guffin-meta tag overrides the fence language at transcription."""

    @staticmethod
    def _code_with_override(value: str) -> tuple[RoamNode, NodeTree]:
        """A python-fenced code node whose guffin-meta child tags ``code-language:: <value>``."""
        code = RoamNode(
            uid="codeuid01",
            id=106,
            string=_CODE_STRING,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            children=[IdObject(id=107)],
        )
        meta = RoamNode(
            uid="metauid01",
            id=107,
            string="guffin-meta:: #.rm-g",
            order=0,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            children=[IdObject(id=108)],
        )
        tag = RoamNode(
            uid="claguid01",
            id=108,
            string=f"code-language:: {value}",
            order=0,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            refs=[IdObject(id=109)],
        )
        attribute_page = RoamNode(uid="clpage001", id=109, title="code-language")
        return code, _node_tree(code, meta, tag, attribute_page)

    def test_legal_override_replaces_fence_language(self) -> None:
        """A legal code-language value (any case) replaces the fence's language with its canonical id."""
        node, tree = self._code_with_override("FORTRAN")
        assert to_code_block_vertex(node, tree).language == "fortran"

    def test_alias_override_resolves_to_canonical_id(self) -> None:
        """A vocabulary alias resolves to the canonical id."""
        node, tree = self._code_with_override("gnu asm")
        assert to_code_block_vertex(node, tree).language == "unix assembly"

    def test_illegal_override_falls_back_to_fence_language(self, caplog: pytest.LogCaptureFixture) -> None:
        """A value outside the vocabulary is ignored with a warning; the fence language stands."""
        node, tree = self._code_with_override("edsac")
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert to_code_block_vertex(node, tree).language == "python"
        assert "ignoring code-language" in caplog.text

    def test_override_assignment_stays_folded(self) -> None:
        """The code-language assignment remains folded on the vertex for the vocabulary validators."""
        node, tree = self._code_with_override("FORTRAN")
        vertex = to_code_block_vertex(node, tree)
        assert vertex.attribute_assignments is not None
        assert any(a.attribute.definition.name == "code-language" for a in vertex.attribute_assignments)


class TestCodeSourceFold:
    """A ``code-source::`` guffin-meta tag populates the code block's provenance at transcription."""

    _URL = "https://github.com/psf/requests/blob/main/src/requests/api.py#L14-L60"
    _SHA = "0d9ca427f7d7dbe92694284d4a6249178255036e"
    _DATE = "2026-07-17"

    @classmethod
    def _code_with_source(cls, sha: str, url_separator: str = ", ") -> tuple[RoamNode, NodeTree]:
        """A python-fenced code node whose guffin-meta child tags ``code-source:: <url>, <sha>, <date>``."""
        code = RoamNode(
            uid="codeuid01",
            id=106,
            string=_CODE_STRING,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            children=[IdObject(id=107)],
        )
        meta = RoamNode(
            uid="metauid01",
            id=107,
            string="guffin-meta:: #.rm-g",
            order=0,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            children=[IdObject(id=108)],
        )
        tag = RoamNode(
            uid="csrcuid01",
            id=108,
            string=f"code-source:: {cls._URL}{url_separator}{sha}, {cls._DATE}",
            order=0,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            refs=[IdObject(id=109)],
        )
        attribute_page = RoamNode(uid="cspage001", id=109, title="code-source")
        return code, _node_tree(code, meta, tag, attribute_page)

    def test_legal_source_populates_provenance(self) -> None:
        """A legal three-valued tag lands as the vertex's parsed CodeSource."""
        node, tree = self._code_with_source(self._SHA)
        vertex = to_code_block_vertex(node, tree)
        assert vertex.code_source is not None
        assert vertex.code_source.url == self._URL

    def test_space_before_first_comma_parses_identically(self) -> None:
        """The authoring form puts a space before the URL's comma (so Roam's auto-linker stops at the URL)."""
        node, tree = self._code_with_source(self._SHA, url_separator=" , ")
        vertex = to_code_block_vertex(node, tree)
        assert vertex.code_source is not None
        assert vertex.code_source.url == self._URL
        assert vertex.code_source.commit_sha == self._SHA
        assert vertex.code_source.commit_sha == self._SHA
        assert vertex.code_source.fetched_date.isoformat() == self._DATE

    def test_untagged_code_block_has_no_provenance(self) -> None:
        """A code block without a code-source tag transcribes with code_source None."""
        node = _make_code()
        assert to_code_block_vertex(node, _node_tree(node)).code_source is None

    def test_illegal_source_ignored_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """An illegal value (abbreviated SHA) is ignored with a warning; provenance stays None."""
        node, tree = self._code_with_source("0d9ca42")
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert to_code_block_vertex(node, tree).code_source is None
        assert "ignoring code-source" in caplog.text

    def test_source_assignment_stays_folded(self) -> None:
        """The code-source assignment remains folded on the vertex for the vocabulary validators."""
        node, tree = self._code_with_source(self._SHA)
        vertex = to_code_block_vertex(node, tree)
        assert vertex.attribute_assignments is not None
        assert any(a.attribute.definition.name == "code-source" for a in vertex.attribute_assignments)


# ---------------------------------------------------------------------------
# TestToQuoteBlockVertex
# ---------------------------------------------------------------------------


class TestToQuoteBlockVertex:
    """Tests for to_quote_block_vertex."""

    def test_returns_block_quote_vertex(self) -> None:
        """Test that a block-quote node builds a QuoteBlockVertex."""
        node = _make_block_quote()
        assert isinstance(to_quote_block_vertex(node, _node_tree(node)), QuoteBlockVertex)

    def test_vertex_type_is_guffin_quote_block(self) -> None:
        """Test that the vertex_type is QUOTE_BLOCK."""
        node = _make_block_quote()
        assert to_quote_block_vertex(node, _node_tree(node)).vertex_type is VertexType.QUOTE_BLOCK

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_block_quote(uid="bquid0002")
        assert to_quote_block_vertex(node, _node_tree(node)).uid == "bquid0002"

    def test_md_marker_stripped_into_quote(self) -> None:
        """Test that the standard Markdown > marker is stripped, leaving only the quotation."""
        node = _make_block_quote(string="> Hello, world!")
        vtx = to_quote_block_vertex(node, _node_tree(node))
        assert vtx.quote == "Hello, world!"
        assert vtx.attribution is None

    def test_roam_marker_stripped_into_quote(self) -> None:
        """Test that the Roam [[>]] marker is stripped, leaving only the quotation."""
        node = _make_block_quote(string="[[>]] Hello, world!")
        assert to_quote_block_vertex(node, _node_tree(node)).quote == "Hello, world!"

    def test_standard_markdown_quote_is_block(self) -> None:
        """Test that a standard Markdown > block quote is QuoteType.BLOCK."""
        node = _make_block_quote(string="> Hello, world!")
        assert to_quote_block_vertex(node, _node_tree(node)).quote_type is QuoteType.BLOCK

    def test_roam_native_quote_is_block(self) -> None:
        """Test that a Roam-native [[>]] block quote is QuoteType.BLOCK (not a pull quote)."""
        node = _make_block_quote(string="[[>]] Hello, world!")
        assert to_quote_block_vertex(node, _node_tree(node)).quote_type is QuoteType.BLOCK

    def test_pull_quote_is_pull_with_quote_and_attribution(self) -> None:
        """Test that a [[>]] [[!QUOTE]] block is QuoteType.PULL with split quote/attribution."""
        node = _make_block_quote(string="[[>]] [[!QUOTE]] The quotation\n— Someone")
        vtx = to_quote_block_vertex(node, _node_tree(node))
        assert vtx.quote_type is QuoteType.PULL
        assert vtx.quote == "The quotation"
        assert vtx.attribution == "— Someone"

    def test_pull_quote_without_attribution(self) -> None:
        """Test that a single-line pull quote has no attribution."""
        node = _make_block_quote(string="[[>]] [[!QUOTE]] Just the quote")
        vtx = to_quote_block_vertex(node, _node_tree(node))
        assert vtx.quote_type is QuoteType.PULL
        assert vtx.quote == "Just the quote"
        assert vtx.attribution is None

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_block_quote()
        assert to_quote_block_vertex(node, _node_tree(node)).children is None

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_block_quote()
        assert to_quote_block_vertex(node, _node_tree(node)).refs is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_quote_block_vertex(node, _node_tree(node))

    def test_non_quote_string_raises_value_error(self) -> None:
        """Test that a plain string that is not a block quote raises ValueError."""
        node = _make_block_quote(string="Just plain text")
        with pytest.raises(ValueError):
            to_quote_block_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_quote_block_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestTranscribeNode
# ---------------------------------------------------------------------------


class TestTranscribeNode:
    """Integration tests for transcribe_standalone_node — verifies correct dispatch to each vertex builder."""

    def test_transcribes_page_node(self) -> None:
        """Test that a page node is transcribed to a PAGE vertex with correct fields."""
        node = _make_page(title="My Page")
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, PageVertex)
        assert v.vertex_type is VertexType.PAGE
        assert v.title == "My Page"

    def test_transcribes_image_node(self) -> None:
        """Test that an image block node is transcribed to a IMAGE vertex with correct fields."""
        node = _make_image()
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, ImageVertex)
        assert v.vertex_type is VertexType.IMAGE
        assert v.media_type == "image/jpeg"

    def test_transcribes_pdf_node(self) -> None:
        """Test that a PDF component block node is transcribed to a PDF vertex with correct fields."""
        node = _make_pdf()
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, PdfVertex)
        assert v.vertex_type is VertexType.PDF
        assert str(v.source) == _FIRESTORE_PDF_URL

    def test_transcribes_heading_node(self) -> None:
        """Test that a heading block node is transcribed to a HEADING vertex with correct fields."""
        node = _make_heading(string="Intro", heading=1)
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, HeadingVertex)
        assert v.vertex_type is VertexType.HEADING
        assert v.text == "Intro"
        assert v.heading_level == 1

    def test_transcribes_text_content_node(self) -> None:
        """Test that a plain text block node is transcribed to a TEXT vertex."""
        node = _make_text(string="Body text")
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, TextVertex)
        assert v.vertex_type is VertexType.TEXT
        assert v.text == "Body text"

    def test_transcribes_quote_block_node(self) -> None:
        """Test that a quote-block node is transcribed to a QUOTE_BLOCK vertex."""
        node = _make_block_quote(string="> Quoted content")
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, QuoteBlockVertex)
        assert v.vertex_type is VertexType.QUOTE_BLOCK
        assert v.quote == "Quoted content"

    def test_children_resolved_via_id_map(self) -> None:
        """Test that transcribe_standalone_node resolves children through the id_map."""
        child = RoamNode(
            uid="child0001",
            id=201,
            string="child",
            order=0,
            parents=[IdObject(id=100)],
            page=IdObject(id=100),
        )
        page = RoamNode(
            uid="pageuid01",
            id=100,
            title="Page",
            children=[IdObject(id=201)],
        )
        v = transcribe_standalone_node(page, _node_tree(page, child))
        assert isinstance(v, PageVertex)
        assert v.children == ["child0001"]

    def test_node_with_neither_title_nor_string_raises_validation_error(self) -> None:
        """Test that constructing a node missing both title and string raises ValidationError."""
        with pytest.raises(ValidationError):
            RoamNode(uid="badnode01", id=999)

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            transcribe_standalone_node(None, _node_tree(_make_page()))  # type: ignore[arg-type]

    def test_transcribes_image_node_from_fixture(self) -> None:
        """Test transcription of a real-world image node loaded from the JSON fixture."""
        raw = json.loads((FIXTURES_JSON_DIR / "image_node.json").read_text())[0]
        node = RoamNode.model_validate(raw)
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, ImageVertex)
        assert v.vertex_type is VertexType.IMAGE
        assert v.uid == "mPCzedeKx"
        assert v.source.host == "firebasestorage.googleapis.com"
        assert v.alt_text == "A flower"


# ---------------------------------------------------------------------------
# TestAttributeAssignmentFolding
# ---------------------------------------------------------------------------


class TestAttributeAssignmentFolding:
    """Attribute-block children are folded onto the parent vertex (Test Article 5 fixture)."""

    def test_page_carries_folded_assignments(self) -> None:
        """The page's standard (Default-domain) attribute-block children fold in source order."""
        vtree = transcribe(article5_node_tree())
        page = next(v for v in vtree.tree_vertices if isinstance(v, PageVertex))
        assert page.attribute_assignments is not None
        default = [a for a in page.attribute_assignments if a.attribute.definition.domain == AttributeDomain.DEFAULT]
        assert [a.attribute.definition.name for a in default] == ["tags", "attribute1"]

        tags, attr1 = default
        assert [v.name for v in tags.values if isinstance(v, ReferenceValue)] == ["Guffin", "Better Bullets"]
        assert attr1.attribute.link.uid == "-gG94Gziw"
        literal, ref_cd, ref_v01 = attr1.values
        assert isinstance(literal, LiteralValue) and literal.value == "5"
        assert isinstance(ref_cd, ReferenceValue) and (ref_cd.name, ref_cd.link.uid) == ("callouts demo", "d87aKN4hh")
        assert isinstance(ref_v01, ReferenceValue) and (ref_v01.name, ref_v01.link.uid) == ("v01", "igM26JNa2")

    def test_attribute_blocks_are_not_standalone_vertices(self) -> None:
        """Attribute-block nodes are folded onto parents — never emitted as vertices or left in children."""
        tree = article5_node_tree()
        attr_block_uids = {n.uid for n in tree.tree_network if node_type(n) is NodeType.ATTRIBUTE_BLOCK}
        assert attr_block_uids  # sanity: the fixture has attribute blocks to fold
        vtree = transcribe(tree)
        tree_uids = {v.uid for v in vtree.tree_vertices}
        child_uids = {child for v in vtree.tree_vertices if v.children for child in v.children}
        assert attr_block_uids.isdisjoint(tree_uids)
        assert attr_block_uids.isdisjoint(child_uids)

    def test_vertex_type_rejects_attribute_block(self) -> None:
        """vertex_type raises for an attribute block — it has no standalone VertexType."""
        tree = article5_node_tree()
        with pytest.raises(ValueError):
            vertex_type(tree.uid_map["Up9F5BMq9"])


# ---------------------------------------------------------------------------
# TestMetaBlockFolding
# ---------------------------------------------------------------------------


class TestMetaBlockFolding:
    """A ``<domain>-meta::`` container folds its children onto the parent as domain attributes (TA5)."""

    def test_meta_children_fold_with_domain(self) -> None:
        """``guffin-meta`` children become guffin-domain attributes on the page; values are normalised."""
        vtree = transcribe(article5_node_tree())
        page = next(v for v in vtree.tree_vertices if isinstance(v, PageVertex))
        assert page.attribute_assignments is not None
        guffin = {
            a.attribute.definition.name: a
            for a in page.attribute_assignments
            if a.attribute.definition.domain == "guffin"
        }
        assert list(guffin) == ["title", "authors", "date", "identifier", "tags"]
        # Quoted literal -> surrounding quotes stripped, kept as one value.
        (title_value,) = guffin["title"].values
        assert isinstance(title_value, LiteralValue) and title_value.value == "Source Code For Humans"
        # Comma-separated RHS -> one literal value per trimmed token.
        assert [v.value for v in guffin["authors"].values if isinstance(v, LiteralValue)] == [
            "Joe Panico",
            "Emi Panico",
        ]
        # A tag value -> reference.
        assert [v.name for v in guffin["tags"].values if isinstance(v, ReferenceValue)] == ["Guffin"]

    def test_meta_block_and_children_consumed(self) -> None:
        """The meta block and its children are consumed — never vertices, never in any children list."""
        tree = article5_node_tree()
        meta = tree.uid_map["RjNKPZfjB"]
        subtree_uids = {meta.uid} | {tree.id_map[c.id].uid for c in (meta.children or []) if c.id in tree.id_map}
        vtree = transcribe(tree)
        tree_uids = {v.uid for v in vtree.tree_vertices}
        child_uids = {child for v in vtree.tree_vertices if v.children for child in v.children}
        assert subtree_uids.isdisjoint(tree_uids)
        assert subtree_uids.isdisjoint(child_uids)


# ---------------------------------------------------------------------------
# TestInTreeRefTranscription
# ---------------------------------------------------------------------------


class TestInTreeRefTranscription:
    """A ref target inside the anchor tree is transcribed once, by the tree pass alone."""

    @staticmethod
    def _self_referencing_tree() -> NodeTree:
        """Build a page whose text block references the page's own level-2 heading block."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2), IdObject(id=3)])
        heading = RoamNode(
            uid="headng001",
            id=2,
            string="Section",
            heading=2,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        referrer = RoamNode(
            uid="referrer1",
            id=3,
            string="see ((headng001))",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=2)],
        )
        return _node_tree(root, heading, referrer)

    def test_in_tree_ref_target_reaches_refs_by_id(self) -> None:
        """Sanity: the fetch model records the in-tree target in refs_by_id."""
        assert 2 in self._self_referencing_tree().refs_by_id

    def test_in_tree_ref_target_yields_no_ref_vertex(self) -> None:
        """An in-tree ref target is not transcribed again as a ref vertex."""
        vtree = transcribe(self._self_referencing_tree())
        assert [v.uid for v in vtree.ref_vertices] == []

    def test_uid_map_resolves_to_the_normalized_tree_vertex(self) -> None:
        """The by-uid map holds the tree vertex — heading normalized to H1, not shadowed at H2."""
        vtree = transcribe(self._self_referencing_tree())
        vertex = vtree.uid_map["headng001"]
        assert isinstance(vertex, HeadingVertex)
        assert vertex.heading_level == 1

    def test_foreign_ref_target_still_transcribed(self) -> None:
        """A ref target outside the anchor tree still yields a ref vertex."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        referrer = RoamNode(
            uid="referrer1",
            id=2,
            string="see [[Foreign]]",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=3)],
        )
        foreign = RoamNode(uid="refpage01", id=3, title="Foreign")
        vtree = transcribe(_node_tree(root, referrer, foreign))
        assert [v.uid for v in vtree.ref_vertices] == ["refpage01"]


# ---------------------------------------------------------------------------
# TestTranscribeArticleFixture
# ---------------------------------------------------------------------------


class TestTranscribeArticleFixture:
    """End-to-end fixture test: transcribe the Test Article NodeNetwork and compare to the vertex fixture."""

    def test_transcribe_article_nodes_matches_vertex_fixture(self) -> None:
        """Test that transcribing test_article_1_nodes.yaml produces the vertices in test_article_1_vertices.yaml.

        Attribute blocks and ``<domain>-meta::`` container blocks are skipped: full
        transcription folds them onto their parent vertex's ``attribute_assignments``
        rather than transcribing them standalone, so they have no counterpart in the
        vertices fixture.  A ``NATIVE_TABLE`` node and its row/cell descendants are
        consumed together into a single ``TableVertex`` via ``to_table_vertex``,
        mirroring ``transcribe()``.
        """
        node_tree = article1_node_tree()
        min_level = min_effective_heading_level(node_tree.tree_network)
        heading_offset: int = (1 - min_level) if min_level is not None else 0

        consumed: set[Id] = set()
        actual_vertices: list[Vertex] = []
        for node in NodeTreeDFSIterator(node_tree):
            if node.id in consumed or node_type(node) is NodeType.ATTRIBUTE_BLOCK or _is_meta_block(node):
                continue
            if node_type(node) is NodeType.NATIVE_TABLE:
                table_vertex, nodes_consumed = to_table_vertex(node, node_tree)
                consumed.update(nodes_consumed)
                actual_vertices.append(table_vertex)
            else:
                actual_vertices.append(transcribe_standalone_node(node, node_tree, heading_offset))

        raw_vertices: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text(), Loader=YamlFixtureLoader
        )
        expected_vertices: list[Vertex] = [vertex_adapter.validate_python(r) for r in raw_vertices]

        # Serialize both sides to plain dicts (mode='json' converts HttpUrl → str,
        # StrEnum → str) and sort by uid so the comparison is order-independent.
        def _as_dict(vtx: Vertex) -> dict[str, object]:
            return vtx.model_dump(mode="json", exclude_none=True)

        actual_by_uid = {d["uid"]: d for d in (_as_dict(vtx) for vtx in actual_vertices)}
        expected_by_uid = {d["uid"]: d for d in (_as_dict(vtx) for vtx in expected_vertices)}

        assert actual_by_uid == expected_by_uid

    def test_article_node_tree_transcribes_to_vertex_tree(self) -> None:
        """Transcribing the Test Article NodeTree via transcribe() produces the expected VertexTree."""
        node_tree = article1_node_tree()

        vertex_tree = transcribe(node_tree)

        raw_vertices: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text(), Loader=YamlFixtureLoader
        )
        expected: list[Vertex] = [vertex_adapter.validate_python(r) for r in raw_vertices]

        def _serialise(vtx: Vertex) -> dict[str, object]:
            return vtx.model_dump(mode="json", exclude_none=True)

        assert [_serialise(vtx) for vtx in vertex_tree.tree_vertices] == [_serialise(vtx) for vtx in expected]

    def test_article_0_node_tree_transcribes_to_vertex_tree(self) -> None:
        """Transcribing the Test Article 0 NodeTree via transcribe() produces the expected VertexTree.

        Article 0 is the basic-features article: block structure, inline styling, quote and
        callout forms, a native table, and the TODO items (``{{[[TODO]]}}`` / ``{{[[DONE]]}}``,
        classified as ``TODO_BLOCK`` nodes and transcribed as plain ``TEXT`` vertices).
        """
        node_tree = article0_node_tree()

        vertex_tree = transcribe(node_tree)

        raw_vertices: list[dict[str, object]] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_0_vertices.yaml").read_text(), Loader=YamlFixtureLoader
        )
        expected: list[Vertex] = [vertex_adapter.validate_python(r) for r in raw_vertices]

        def _serialise(vtx: Vertex) -> dict[str, object]:
            return vtx.model_dump(mode="json", exclude_none=True)

        assert [_serialise(vtx) for vtx in vertex_tree.tree_vertices] == [_serialise(vtx) for vtx in expected]


# ---------------------------------------------------------------------------
# TestToTable helpers
# ---------------------------------------------------------------------------


def _make_table_root(
    uid: str,
    node_id: int,
    row_ids: list[int],
) -> RoamNode:
    """Return a NATIVE_TABLE root RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=ROAM_NATIVE_TABLE_RAW_MARKER,
        parents=[IdObject(id=1)],
        page=IdObject(id=1),
        children=[IdObject(id=rid) for rid in row_ids],
    )


def _make_cell_node(
    uid: str,
    node_id: int,
    parent_id: int,
    string: str,
    order: int = 0,
    child_id: int | None = None,
) -> RoamNode:
    """Return a table-cell RoamNode.

    In Roam's native table structure every cell's sole child (when present) is the
    next-column cell in the same row; supply *child_id* to wire that link.
    """
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        order=order,
        parents=[IdObject(id=parent_id)],
        page=IdObject(id=1),
        children=[IdObject(id=child_id)] if child_id is not None else None,
    )


# ---------------------------------------------------------------------------
# TestToTableVertex
# ---------------------------------------------------------------------------


class TestToTableVertex:
    """Tests for to_table_vertex."""

    def _make_2x2_inputs(self) -> tuple[RoamNode, NodeTree]:
        """Return (root, tree) for a 2×2 table: row 1 = (A, B), row 2 = (C, D)."""
        root = _make_table_root("tabluid01", 10, [11, 12])
        col1_row1 = _make_cell_node("cel11uid1", 11, 10, "A", order=0, child_id=13)
        col1_row2 = _make_cell_node("cel12uid1", 12, 10, "C", order=1, child_id=14)
        col2_row1 = _make_cell_node("cel21uid1", 13, 11, "B", order=0)
        col2_row2 = _make_cell_node("cel22uid1", 14, 12, "D", order=0)
        return root, _node_tree(root, col1_row1, col1_row2, col2_row1, col2_row2)

    def test_returns_table_vertex(self) -> None:
        """To_table_vertex returns a TableVertex as the first element of the pair."""
        root, imap = self._make_2x2_inputs()
        vertex, _ = to_table_vertex(root, imap)
        assert isinstance(vertex, TableVertex)

    def test_vertex_type_is_guffin_table(self) -> None:
        """The returned vertex has vertex_type TABLE."""
        root, imap = self._make_2x2_inputs()
        vertex, _ = to_table_vertex(root, imap)
        assert vertex.vertex_type is VertexType.TABLE

    def test_uid_preserved(self) -> None:
        """The vertex uid matches the source node uid."""
        root, imap = self._make_2x2_inputs()
        vertex, _ = to_table_vertex(root, imap)
        assert vertex.uid == "tabluid01"

    def test_children_is_none(self) -> None:
        """Children is always None — descendants are consumed into the Table, not emitted as separate vertices."""
        root, imap = self._make_2x2_inputs()
        vertex, _ = to_table_vertex(root, imap)
        assert vertex.children is None

    def test_table_cell_content(self) -> None:
        """The embedded Table carries the correct 2-D cell grid."""
        root, imap = self._make_2x2_inputs()
        vertex, _ = to_table_vertex(root, imap)
        assert vertex.table.rows[0] == ("A", "B")
        assert vertex.table.rows[1] == ("C", "D")

    def test_consumed_ids_exact_set(self) -> None:
        """The frozenset equals the IDs of the root and all descendant cell nodes."""
        root, imap = self._make_2x2_inputs()
        _, consumed = to_table_vertex(root, imap)
        assert consumed == frozenset({10, 11, 12, 13, 14})

    def test_empty_table_raises_value_error(self) -> None:
        """A table root with no children raises ValueError."""
        root = RoamNode(
            uid="tabluid01",
            id=10,
            string=ROAM_NATIVE_TABLE_RAW_MARKER,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        with pytest.raises(ValueError, match="no children"):
            to_table_vertex(root, _node_tree(root))


# ---------------------------------------------------------------------------
# TestToPageEmbedVertex
# ---------------------------------------------------------------------------


class TestToPageEmbedVertex:
    """to_page_embed_vertex builds a PageEmbedVertex whose EMBED link targets the referenced page."""

    @staticmethod
    def _embed_and_tree() -> tuple[RoamNode, NodeTree]:
        """A page-embed block referencing a target page (present as a ref, so page_name_map resolves it)."""
        root = RoamNode(uid="rootpage1", id=1, title="Root", children=[IdObject(id=2)])
        embed = RoamNode(
            uid="embednode",
            id=2,
            string="{{embed: [[Target Page]]}}",
            page=IdObject(id=1),
            parents=[IdObject(id=1)],
            refs=[IdObject(id=3)],
        )
        target = RoamNode(uid="targetpag", id=3, title="Target Page")
        return embed, _node_tree(root, embed, target)

    def test_builds_a_page_embed_vertex(self) -> None:
        """A page embed transcribes to a PageEmbedVertex."""
        embed, tree = self._embed_and_tree()
        vertex = to_page_embed_vertex(embed, tree)
        assert isinstance(vertex, PageEmbedVertex)
        assert vertex.vertex_type is VertexType.PAGE_EMBED
        assert vertex.uid == "embednode"

    def test_embed_link_targets_the_page_uid(self) -> None:
        """The vertex_link is an EMBED-kind link resolved to the referenced page's UID."""
        embed, tree = self._embed_and_tree()
        vertex = to_page_embed_vertex(embed, tree)
        assert vertex.vertex_link.kind is VertexLinkKind.EMBED
        assert vertex.vertex_link.uid == "targetpag"

    def test_dispatched_through_transcribe_standalone_node(self) -> None:
        """transcribe_standalone_node routes a page-embed node to the page-embed builder."""
        embed, tree = self._embed_and_tree()
        vertex = transcribe_standalone_node(embed, tree)
        assert isinstance(vertex, PageEmbedVertex)
        assert vertex.vertex_link.uid == "targetpag"

    def test_distinct_type_from_block_embed(self) -> None:
        """A page embed and a block embed produce distinct vertex types sharing the EMBED link kind."""
        block_root = RoamNode(uid="rootpage2", id=1, title="Root", children=[IdObject(id=2)])
        block_embed = RoamNode(
            uid="blockemb1", id=2, string="{{embed: ((wdMgyBiP9))}}", page=IdObject(id=1), parents=[IdObject(id=1)]
        )
        block_vertex = to_block_embed_vertex(block_embed, _node_tree(block_root, block_embed))
        embed, tree = self._embed_and_tree()
        page_vertex = to_page_embed_vertex(embed, tree)
        assert isinstance(block_vertex, BlockEmbedVertex)
        assert isinstance(page_vertex, PageEmbedVertex)
        assert block_vertex.vertex_link.kind is page_vertex.vertex_link.kind is VertexLinkKind.EMBED

    def test_unknown_page_raises(self) -> None:
        """A page embed naming a page not present in the tree raises."""
        root = RoamNode(uid="rootpage3", id=1, title="Root", children=[IdObject(id=2)])
        embed = RoamNode(
            uid="embednode", id=2, string="{{embed: [[Missing Page]]}}", page=IdObject(id=1), parents=[IdObject(id=1)]
        )
        with pytest.raises(ValueError, match="unknown page"):
            to_page_embed_vertex(embed, _node_tree(root, embed))


# ---------------------------------------------------------------------------
# TestBuildViewMap
# ---------------------------------------------------------------------------


class TestBuildViewMap:
    """Tests for build_view_map."""

    def test_records_every_explicit_view_type_including_bullet(self) -> None:
        """Build_view_map records an entry for every explicit children-view-type, bullet included."""
        # The root has no explicit children_view_type (None), so it is absent from the sparse map.
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2), IdObject(id=3), IdObject(id=4)])
        # BULLET equals the default, but it is explicitly set, so it is recorded distinctly from unset.
        bullet = RoamNode(
            uid="bullet001",
            id=2,
            string="bullet parent",
            children_view_type=ChildrenViewType.BULLET,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        numbered = RoamNode(
            uid="numberd01",
            id=3,
            string="numbered parent",
            children_view_type=ChildrenViewType.NUMBERED,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        document = RoamNode(
            uid="documnt01",
            id=4,
            string="document parent",
            children_view_type=ChildrenViewType.DOCUMENT,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        view_map = build_view_map(_node_tree(root, bullet, numbered, document))
        assert view_map == {
            "bullet001": VertexView(children_layout=ChildrenLayout.BULLET),
            "numberd01": VertexView(children_layout=ChildrenLayout.NUMBERED),
            "documnt01": VertexView(children_layout=ChildrenLayout.DOCUMENT),
        }

    def test_omits_nodes_without_explicit_view_type(self) -> None:
        """A tree whose nodes carry no explicit children-view-type (None) yields an empty map."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        child = RoamNode(
            uid="child0001",
            id=2,
            string="child",
            children_view_type=None,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert build_view_map(_node_tree(root, child)) == {}

    def test_records_referenced_nodes_explicit_view_type(self) -> None:
        """A referenced node's explicit view-type is recorded, so transclusion carries presentation.

        The map covers the same node population as transcribe(): anchor subtree plus refs — an
        embedded page's authored layout must survive into the ViewMap.
        """
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        embed = RoamNode(
            uid="embednode",
            id=2,
            string="{{embed: [[Embedded Page]]}}",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            refs=[IdObject(id=3)],
        )
        ref_page = RoamNode(
            uid="refpage01",
            id=3,
            title="Embedded Page",
            children_view_type=ChildrenViewType.DOCUMENT,
        )
        view_map = build_view_map(_node_tree(root, embed, ref_page))
        assert view_map == {"refpage01": VertexView(children_layout=ChildrenLayout.DOCUMENT)}

    def test_semantic_by_bullet_type_is_total(self) -> None:
        """Every Better Bullets kind maps to a Semantic."""
        assert set(SEMANTIC_BY_BULLET_TYPE) == set(BetterBulletType)

    def test_source_channel_by_provenance_is_total(self) -> None:
        """Every Better Bullets provenance maps to a SourceChannel."""
        assert set(SOURCE_CHANNEL_BY_PROVENANCE) == set(BetterBulletProvenance)

    def test_records_bullet_type_as_semantic(self) -> None:
        """A node's persisted Better Bullets kind is recorded as the view's semantic."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        block = RoamNode(
            uid="bullet001",
            id=2,
            string="why though?",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            props={"type": "question"},
        )
        view_map = build_view_map(_node_tree(root, block))
        assert view_map == {"bullet001": VertexView(semantic=Semantic.QUESTION)}

    def test_records_provenance_as_source_channel(self) -> None:
        """A node's persisted provenance badge is recorded as the view's source channel.

        The divergent persisted spellings map across: ``phone`` → voice-call.
        """
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        block = RoamNode(
            uid="badge0001",
            id=2,
            string="call with the publisher",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            props={"provenance": "phone"},
        )
        view_map = build_view_map(_node_tree(root, block))
        assert view_map == {"badge0001": VertexView(source_channel=SourceChannel.VOICE_CALL)}

    def test_records_all_three_declarations_on_one_node(self) -> None:
        """Layout, semantic, and source channel co-exist on one recorded view."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        block = RoamNode(
            uid="fullhouse",
            id=2,
            string="decision from the call",
            children_view_type=ChildrenViewType.DOCUMENT,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            props={"type": "decision", "provenance": "phone"},
        )
        view_map = build_view_map(_node_tree(root, block))
        assert view_map == {
            "fullhouse": VertexView(
                children_layout=ChildrenLayout.DOCUMENT,
                semantic=Semantic.DECISION,
                source_channel=SourceChannel.VOICE_CALL,
            )
        }

    def test_declaration_order_does_not_change_the_recorded_view(self) -> None:
        """Two nodes declaring the same pair in opposite property order record the same view.

        Which key a block's property map happens to carry first reflects the order an author
        applied the markers in the Roam UI — the source's own bookkeeping, never a statement
        about the content — so it must not reach the recorded view.
        """
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        semantic_first = RoamNode(
            uid="semfirst1",
            id=2,
            string="marked as a definition, then badged",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            props={"type": "equal", "provenance": "calendar"},
        )
        channel_first = RoamNode(
            uid="chanfirst",
            id=2,
            string="badged, then marked as a definition",
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
            props={"provenance": "calendar", "type": "equal"},
        )
        expected = VertexView(semantic=Semantic.DEFINITION, source_channel=SourceChannel.CALENDAR_EVENT)
        assert build_view_map(_node_tree(root, semantic_first)) == {"semfirst1": expected}
        assert build_view_map(_node_tree(root, channel_first)) == {"chanfirst": expected}

    def test_article_4_fixture_records_semantics_and_source_channels(self) -> None:
        """The [[Test Article]] 4 fixture's Better Bullets sections enrich the ViewMap end to end."""
        view_map = build_view_map(article4_node_tree())
        semantics = [view.semantic for view in view_map.values() if view.semantic is not None]
        channels = [view.source_channel for view in view_map.values() if view.source_channel is not None]
        # Coverage, not exact counts: the article's Mixed section declares both axes on one
        # block, so a few members are declared more than once.
        assert set(semantics) == set(Semantic)
        assert set(channels) == set(SourceChannel)
        # The doubly classified block is its own render path (the semantic takes the marker,
        # leaving the badge to lead the content), so the fixture must keep exercising it.
        assert any(view.semantic is not None and view.source_channel is not None for view in view_map.values())


# ---------------------------------------------------------------------------
# TestToRenderBundle
# ---------------------------------------------------------------------------


class TestToRenderBundle:
    """Tests for to_render_bundle."""

    def test_bundles_transcribe_and_build_view_map(self) -> None:
        """To_render_bundle pairs transcribe() content with build_view_map() presentation."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        child = RoamNode(
            uid="numberd01",
            id=2,
            string="numbered parent",
            children_view_type=ChildrenViewType.NUMBERED,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        tree = _node_tree(root, child)
        render_bundle = to_render_bundle(tree)
        assert isinstance(render_bundle, RenderBundle)
        assert render_bundle.content == transcribe(tree)
        assert render_bundle.view == build_view_map(tree)
