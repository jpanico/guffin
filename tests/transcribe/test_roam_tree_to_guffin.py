"""Tests for the roam_tree_to_guffin module."""

import json

import pytest
import yaml
from pydantic import ValidationError

from guffin.model.attribute import LiteralValue, ReferenceValue
from guffin.model.vertex import (
    AttributeAssignmentVertex,
    BlockQuoteVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
    VertexType,
    vertex_adapter,
)
from guffin.common.code_language import CodeLanguage
from guffin.roam.node_network import min_effective_heading_level
from guffin.roam.node import RoamNode
from guffin.transcribe.roam_tree_to_guffin import (
    build_view_map,
    to_attribute_assignment_vertex,
    to_block_quote_vertex,
    to_callout_vertex,
    to_code_block_vertex,
    to_heading_vertex,
    to_image_vertex,
    to_page_vertex,
    to_render_bundle,
    to_table_vertex,
    to_text_vertex,
    transcribe,
    transcribe_standalone_node,
    vertex_type,
)
from guffin.roam.markdown import ROAM_NATIVE_TABLE_MARKER
from guffin.model.render_bundle import RenderBundle
from guffin.model.view import ChildrenLayout, VertexView
from guffin.roam.node_tree import NodeTree
from guffin.roam.primitives import ChildrenViewType, IdObject

# A real Firestore URL whose path yields a predictable file_name and media_type:
#   file_name  = "photo.jpeg"
#   media_type = "image/jpeg"
_FIRESTORE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING = f"![A flower]({_FIRESTORE_URL})"
_CALLOUT_STRING: str = "[[>]] [[!NOTE]] This is a note"
# Raw Roam form: closing fence attached to the final content line (no separating newline).
_CODE_STRING: str = "```python\ndef f():\n    pass```"

from conftest import FIXTURES_JSON_DIR, FIXTURES_YAML_DIR, article1_node_tree, article5_node_tree

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_page(uid: str = "pageuid01", node_id: int = 100, title: str = "My Page") -> RoamNode:
    """Return a minimal page RoamNode."""
    return RoamNode(uid=uid, id=node_id, title=title, children=[])


def _make_image(uid: str = "imageuid1", node_id: int = 101, string: str = _IMAGE_STRING) -> RoamNode:
    """Return a minimal Firestore image-block RoamNode."""
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
        assert vertex_type(_make_block_quote(string="> quoted text")) is VertexType.BLOCK_QUOTE

    def test_roam_block_quote_returns_guffin_block_quote(self) -> None:
        """Test that a Roam-style block-quote node classifies as BLOCK_QUOTE."""
        assert vertex_type(_make_block_quote(string="[[>]] quoted text")) is VertexType.BLOCK_QUOTE

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
        """Test that the vertex source URL points to the Firestore host."""
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

    def test_file_name_extracted_from_url(self) -> None:
        """Test that the filename is percent-decoded from the Firestore URL path."""
        assert to_image_vertex(_make_image(), _node_tree(_make_image())).file_name == "photo.jpeg"

    def test_media_type_inferred_from_file_name(self) -> None:
        """Test that the IANA media type is inferred from the extracted filename extension."""
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
        """Test that a string with a non-Firestore https URL raises ValueError."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string="![alt](https://example.com/image.jpg)",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        with pytest.raises(ValueError, match="contains no Firestore URL"):
            to_image_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_image_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


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
        raw: list[dict[str, object]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text())
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "qnCiceZgk")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        assert to_callout_vertex(fixture_node, tree).callout_type is CalloutVertex.CalloutType.INFO

    def test_article_0_fixture_title(self) -> None:
        """Test that the Article 0 callout node (qnCiceZgk) yields the expected title.

        The title is the first line after the marker and contains a U+2013 en dash.
        """
        raw: list[dict[str, object]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text())
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "qnCiceZgk")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        expected: str = "THIS PAGE IS USED FOR TESTING [GUFFIN](https://github.com/jpanico/guffin) – DO NOT REMOVE"
        assert to_callout_vertex(fixture_node, tree).title == expected

    def test_article_0_fixture_body(self) -> None:
        """Test that the Article 0 callout node (qnCiceZgk) yields the expected body.

        The body is everything after the first newline in the block string, stripped.
        """
        raw: list[dict[str, object]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text())
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "qnCiceZgk")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        expected: str = (
            "A baseline Roam document, with almost no features\n"
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
            "- Markdown single line block quote\n"
            "- Markdown multi-line block quote\n"
            "- Roam-native single line block quote\n"
            "- Roam-native multi-line block quote\n"
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
        """Test that the opening fence's info string maps to a CodeLanguage."""
        node = _make_code()
        assert to_code_block_vertex(node, _node_tree(node)).language is CodeLanguage.PYTHON

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
        raw: list[dict[str, object]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_0_nodes.yaml").read_text())
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "C6xVTMnsh")
        tree: NodeTree = NodeTree.build(fixture_node, nodes)
        vertex: CodeBlockVertex = to_code_block_vertex(fixture_node, tree)
        assert vertex.language is CodeLanguage.PYTHON
        assert vertex.code.startswith("def fizz_buzz(limit: int = 100):")


# ---------------------------------------------------------------------------
# TestToBlockQuoteVertex
# ---------------------------------------------------------------------------


class TestToBlockQuoteVertex:
    """Tests for to_block_quote_vertex."""

    def test_returns_block_quote_vertex(self) -> None:
        """Test that a block-quote node builds a BlockQuoteVertex."""
        node = _make_block_quote()
        assert isinstance(to_block_quote_vertex(node, _node_tree(node)), BlockQuoteVertex)

    def test_vertex_type_is_guffin_block_quote(self) -> None:
        """Test that the vertex_type is BLOCK_QUOTE."""
        node = _make_block_quote()
        assert to_block_quote_vertex(node, _node_tree(node)).vertex_type is VertexType.BLOCK_QUOTE

    def test_uid_preserved(self) -> None:
        """Test that the vertex uid matches the source node uid."""
        node = _make_block_quote(uid="bquid0002")
        assert to_block_quote_vertex(node, _node_tree(node)).uid == "bquid0002"

    def test_md_marker_stripped_from_text(self) -> None:
        """Test that the standard Markdown > marker is stripped, leaving only the content."""
        node = _make_block_quote(string="> Hello, world!")
        assert to_block_quote_vertex(node, _node_tree(node)).text == "Hello, world!"

    def test_roam_marker_stripped_from_text(self) -> None:
        """Test that the Roam [[>]] marker is stripped, leaving only the content."""
        node = _make_block_quote(string="[[>]] Hello, world!")
        assert to_block_quote_vertex(node, _node_tree(node)).text == "Hello, world!"

    def test_children_none_when_no_children(self) -> None:
        """Test that children is None when the node has no children."""
        node = _make_block_quote()
        assert to_block_quote_vertex(node, _node_tree(node)).children is None

    def test_refs_none_when_no_refs(self) -> None:
        """Test that refs is None when the node has no refs."""
        node = _make_block_quote()
        assert to_block_quote_vertex(node, _node_tree(node)).refs is None

    def test_missing_string_raises_value_error(self) -> None:
        """Test that a node without a string raises ValueError."""
        node = _make_page()
        with pytest.raises(ValueError, match="no 'string'"):
            to_block_quote_vertex(node, _node_tree(node))

    def test_non_quote_string_raises_value_error(self) -> None:
        """Test that a plain string that is not a block quote raises ValueError."""
        node = _make_block_quote(string="Just plain text")
        with pytest.raises(ValueError):
            to_block_quote_vertex(node, _node_tree(node))

    def test_null_node_raises_validation_error(self) -> None:
        """Test that passing None as node raises a ValidationError."""
        with pytest.raises(ValidationError):
            to_block_quote_vertex(None, _node_tree(_make_page()))  # type: ignore[arg-type]


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
        assert v.file_name == "photo.jpeg"
        assert v.media_type == "image/jpeg"

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

    def test_transcribes_block_quote_node(self) -> None:
        """Test that a block-quote node is transcribed to a BLOCK_QUOTE vertex."""
        node = _make_block_quote(string="> Quoted content")
        v = transcribe_standalone_node(node, _node_tree(node))
        assert isinstance(v, BlockQuoteVertex)
        assert v.vertex_type is VertexType.BLOCK_QUOTE
        assert v.text == "Quoted content"

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
        assert v.file_name == "-9owRBegJ8.jpeg.enc"


# ---------------------------------------------------------------------------
# TestToAttributeAssignmentVertex
# ---------------------------------------------------------------------------


class TestToAttributeAssignmentVertex:
    """Tests for to_attribute_assignment_vertex using the Test Article 5 fixture."""

    def test_resolves_attribute_and_values(self) -> None:
        """The 'attribute1:: 5, #[[callouts demo]], #v01' node resolves to a structured assignment."""
        tree = article5_node_tree()
        vertex = to_attribute_assignment_vertex(tree.uid_map["v3WbOVP7U"], tree)
        assert isinstance(vertex, AttributeAssignmentVertex)
        assignment = vertex.assignment
        assert assignment.attribute.name == "attribute1"
        assert assignment.attribute.link.uid == "-gG94Gziw"
        literal, ref_cd, ref_v01 = assignment.values
        assert isinstance(literal, LiteralValue) and literal.value == "5"
        assert isinstance(ref_cd, ReferenceValue) and (ref_cd.name, ref_cd.link.uid) == ("callouts demo", "d87aKN4hh")
        assert isinstance(ref_v01, ReferenceValue) and (ref_v01.name, ref_v01.link.uid) == ("v01", "igM26JNa2")

    def test_dispatched_via_transcribe_standalone_node(self) -> None:
        """Transcribe_standalone_node routes an attribute-assignment node to an AttributeAssignmentVertex."""
        tree = article5_node_tree()
        vertex = transcribe_standalone_node(tree.uid_map["Up9F5BMq9"], tree)
        assert isinstance(vertex, AttributeAssignmentVertex)
        assert vertex.assignment.attribute.name == "tags"
        names = [v.name for v in vertex.assignment.values if isinstance(v, ReferenceValue)]
        assert names == ["Guffin", "Better Bullets"]

    def test_non_attribute_node_raises(self) -> None:
        """A node whose string is not an attribute assignment is rejected."""
        tree = article5_node_tree()
        with pytest.raises(ValueError):
            to_attribute_assignment_vertex(tree.uid_map["AKAMsYfSW"], tree)  # 'hello world!'


# ---------------------------------------------------------------------------
# TestTranscribeArticleFixture
# ---------------------------------------------------------------------------


class TestTranscribeArticleFixture:
    """End-to-end fixture test: transcribe the Test Article NodeNetwork and compare to the vertex fixture."""

    def test_transcribe_article_nodes_matches_vertex_fixture(self) -> None:
        """Test that transcribing test_article_1_nodes.yaml produces the vertices in test_article_1_vertices.yaml."""
        node_tree = article1_node_tree()
        nodes = list(node_tree.tree_network)
        min_level = min_effective_heading_level(node_tree.tree_network)
        heading_offset: int = (1 - min_level) if min_level is not None else 0

        actual_vertices: list[Vertex] = [transcribe_standalone_node(n, node_tree, heading_offset) for n in nodes]

        raw_vertices: list[dict[str, object]] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
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

        raw_vertices: list[dict[str, object]] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text()
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
        string=ROAM_NATIVE_TABLE_MARKER,
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
            string=ROAM_NATIVE_TABLE_MARKER,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        with pytest.raises(ValueError, match="no children"):
            to_table_vertex(root, _node_tree(root))


# ---------------------------------------------------------------------------
# TestBuildViewMap
# ---------------------------------------------------------------------------


class TestBuildViewMap:
    """Tests for build_view_map."""

    def test_records_only_non_default_layouts(self) -> None:
        """Build_view_map records non-default children-view-types and omits default (bullet) ones."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2), IdObject(id=3), IdObject(id=4)])
        # BULLET equals the default, so this node is omitted from the sparse map.
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
            "numberd01": VertexView(children_layout=ChildrenLayout.NUMBERED),
            "documnt01": VertexView(children_layout=ChildrenLayout.DOCUMENT),
        }

    def test_empty_when_all_default(self) -> None:
        """A tree whose nodes all carry the default (bullet) view-type yields an empty map."""
        root = RoamNode(uid="page00001", id=1, title="P", children=[IdObject(id=2)])
        child = RoamNode(
            uid="child0001",
            id=2,
            string="child",
            children_view_type=ChildrenViewType.BULLET,
            parents=[IdObject(id=1)],
            page=IdObject(id=1),
        )
        assert build_view_map(_node_tree(root, child)) == {}


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
