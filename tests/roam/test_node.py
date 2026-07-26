"""Tests for the roam_node module."""

import pytest
import yaml
from conftest import FIXTURES_YAML_DIR
from pydantic import ValidationError

from guffin.common.geometry import ImageSize
from guffin.roam.better_bullet import BetterBulletType
from guffin.roam.node import (
    NodeType,
    RoamNode,
    better_bullet_type,
    effective_children_view_type,
    image_size,
    node_type,
)
from guffin.roam.primitives import DEFAULT_CHILDREN_VIEW_TYPE, ChildrenViewType, IdObject

_FIRESTORE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)
_IMAGE_STRING = f"![A flower]({_FIRESTORE_URL})"


def _make_image(uid: str = "imageuid1", node_id: int = 101, string: str = _IMAGE_STRING) -> RoamNode:
    """Return a minimal Firestore image-block RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_heading(uid: str = "headnguid", node_id: int = 102, string: str = "Section One", level: int = 2) -> RoamNode:
    """Return a minimal native-heading RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        heading=level,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_callout(uid: str = "callutuid", node_id: int = 105, callout_type: str = "INFO", suffix: str = "") -> RoamNode:
    """Return a minimal callout RoamNode with the given callout type."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=f"[[>]] [[!{callout_type}]]{suffix}",
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_text(uid: str = "textuid01", node_id: int = 104, string: str = "Some plain text") -> RoamNode:
    """Return a minimal plain-text RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_block_quote(uid: str = "blkqtuid1", node_id: int = 107, text: str = "Some quoted text") -> RoamNode:
    """Return a minimal block-quote RoamNode (``[[>]] <text>``)."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=f"[[>]] {text}",
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


def _make_code(uid: str = "codeuid01", node_id: int = 106, string: str = "```python\nx = 1\n```") -> RoamNode:
    """Return a minimal fenced-code-block RoamNode."""
    return RoamNode(
        uid=uid,
        id=node_id,
        string=string,
        parents=[IdObject(id=99)],
        page=IdObject(id=99),
    )


# ---------------------------------------------------------------------------
# TestRoamNodeProps
# ---------------------------------------------------------------------------


class TestRoamNodeProps:
    """Tests for the RoamNode.props field (block properties / :block/props)."""

    def test_props_defaults_to_none(self) -> None:
        """Test that props is None when not supplied."""
        node = RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node.props is None

    def test_props_accepts_string_values(self) -> None:
        """Test that props stores a string-valued block property map."""
        node = RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"ah-level": "h4"},
        )
        assert node.props == {"ah-level": "h4"}

    def test_props_accepts_multiple_entries(self) -> None:
        """Test that props can hold multiple block property entries."""
        node = RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"ah-level": "h5", ":some-other": "value"},
        )
        assert node.props is not None
        assert node.props["ah-level"] == "h5"
        assert node.props[":some-other"] == "value"

    def test_props_round_trips_through_model_validate(self) -> None:
        """Test that props survives a model_validate round-trip from a raw dict."""
        raw: dict[str, object] = {
            "uid": "block0001",
            "id": 1,
            "string": "stub",
            "parents": [{"id": 99}],
            "page": {"id": 99},
            "props": {"ah-level": "h6"},
        }
        node = RoamNode.model_validate(raw)
        assert node.props == {"ah-level": "h6"}

    def test_props_none_round_trips_through_model_validate(self) -> None:
        """Test that a missing props key in raw dict produces props=None."""
        raw: dict[str, object] = {
            "uid": "block0001",
            "id": 1,
            "string": "stub",
            "parents": [{"id": 99}],
            "page": {"id": 99},
        }
        node = RoamNode.model_validate(raw)
        assert node.props is None

    def test_node_with_props_is_frozen(self) -> None:
        """Test that a node with props set is immutable."""
        node = RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"ah-level": "h4"},
        )
        with pytest.raises(Exception):
            node.props = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestNodeType
# ---------------------------------------------------------------------------


class TestNodeType:
    """Tests for the NodeType enum."""

    def test_exactly_twelve_members(self) -> None:
        """Test that NodeType has exactly twelve members."""
        assert set(NodeType) == {
            NodeType.PAGE,
            NodeType.PLAIN_BLOCK,
            NodeType.IMAGE_BLOCK,
            NodeType.HEADING_BLOCK,
            NodeType.CALLOUT_BLOCK,
            NodeType.CODE_BLOCK,
            NodeType.QUOTE_BLOCK,
            NodeType.NATIVE_TABLE,
            NodeType.EMBED_BLOCK,
            NodeType.EMBED_PAGE,
            NodeType.PDF_BLOCK,
            NodeType.ATTRIBUTE_BLOCK,
        }


# ---------------------------------------------------------------------------
# TestNodeTypeFunction
# ---------------------------------------------------------------------------


class TestNodeTypeFunction:
    """Tests for the node_type() function."""

    def test_page_node_returns_page(self) -> None:
        """Test that a node with title set returns NodeType.PAGE."""
        node = RoamNode(uid="page00001", id=1, title="My Page", children=[])
        assert node_type(node) is NodeType.PAGE

    def test_block_node_returns_block(self) -> None:
        """Test that a node with string set returns NodeType.PLAIN_BLOCK."""
        node = RoamNode(
            uid="block0001",
            id=2,
            string="block text",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_page_node_is_not_block(self) -> None:
        """Test that a page node does not return NodeType.PLAIN_BLOCK."""
        node = RoamNode(uid="page00001", id=1, title="My Page", children=[])
        assert node_type(node) is not NodeType.PLAIN_BLOCK

    def test_block_node_is_not_page(self) -> None:
        """Test that a block node does not return NodeType.PAGE."""
        node = RoamNode(
            uid="block0001",
            id=2,
            string="block text",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is not NodeType.PAGE

    def test_image_node_returns_image(self) -> None:
        """Test that a bare Firestore image block returns NodeType.IMAGE_BLOCK."""
        assert node_type(_make_image()) is NodeType.IMAGE_BLOCK

    def test_image_node_is_not_block(self) -> None:
        """Test that an image node does not return NodeType.PLAIN_BLOCK."""
        assert node_type(_make_image()) is not NodeType.PLAIN_BLOCK

    def test_image_node_with_surrounding_whitespace_returns_image(self) -> None:
        """Test that leading/trailing whitespace around the image link is tolerated."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string=f"  {_IMAGE_STRING}  ",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.IMAGE_BLOCK

    def test_image_node_with_empty_alt_text_returns_image(self) -> None:
        """Test that an image link with empty alt text returns NodeType.IMAGE_BLOCK."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string=f"![]({_FIRESTORE_URL})",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.IMAGE_BLOCK

    def test_text_before_image_returns_block(self) -> None:
        """Test that text before the image link yields NodeType.PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string=f"see: {_IMAGE_STRING}",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_text_after_image_returns_block(self) -> None:
        """Test that text after the image link yields NodeType.PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string=f"{_IMAGE_STRING} caption",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_two_image_links_returns_block(self) -> None:
        """Test that a string with two image links yields NodeType.PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string=_IMAGE_STRING * 2,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_relative_url_image_returns_block(self) -> None:
        """Test that a Markdown image with a relative URL yields NodeType.PLAIN_BLOCK, not Image."""
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string="![alt](relative/path.jpg)",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_heading_node_returns_heading(self) -> None:
        """Test that a native heading block (heading=2) returns NodeType.HEADING_BLOCK."""
        assert node_type(_make_heading()) is NodeType.HEADING_BLOCK

    def test_heading_node_is_not_block(self) -> None:
        """Test that a heading node does not return NodeType.PLAIN_BLOCK."""
        assert node_type(_make_heading()) is not NodeType.PLAIN_BLOCK

    def test_augmented_heading_returns_heading(self) -> None:
        """Test that a block with props['ah-level'] set returns NodeType.HEADING_BLOCK."""
        node = RoamNode(
            uid="headnguid",
            id=102,
            string="Deep Section",
            props={"ah-level": "h4"},
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node_type(node) is NodeType.HEADING_BLOCK

    def test_plain_text_block_is_not_heading(self) -> None:
        """Test that a plain text block does not return NodeType.HEADING_BLOCK."""
        assert node_type(_make_text()) is not NodeType.HEADING_BLOCK

    def test_callout_node_returns_callout(self) -> None:
        """Test that a block with a valid callout marker returns NodeType.CALLOUT_BLOCK."""
        assert node_type(_make_callout()) is NodeType.CALLOUT_BLOCK

    def test_callout_node_is_not_plain_block(self) -> None:
        """Test that a callout node does not return NodeType.PLAIN_BLOCK."""
        assert node_type(_make_callout()) is not NodeType.PLAIN_BLOCK

    def test_callout_with_suffix_content_returns_callout(self) -> None:
        """Test that a callout marker with trailing content still returns NodeType.CALLOUT_BLOCK."""
        assert node_type(_make_callout(suffix=" some callout body")) is NodeType.CALLOUT_BLOCK

    def test_all_callout_types_return_callout(self) -> None:
        """Test that each of the eleven valid callout types returns NodeType.CALLOUT_BLOCK."""
        valid_types = [
            "INFO",
            "EXAMPLE",
            "NOTE",
            "WARNING",
            "DANGER",
            "TIP",
            "SUMMARY",
            "SUCCESS",
            "QUESTION",
            "FAILURE",
            "BUG",
        ]
        for callout_type in valid_types:
            assert node_type(_make_callout(callout_type=callout_type)) is NodeType.CALLOUT_BLOCK

    def test_quote_callout_marker_is_a_quote_block(self) -> None:
        """[[>]] [[!QUOTE]] is a pull quote (QUOTE_BLOCK), not a callout."""
        assert node_type(_make_callout(callout_type="QUOTE")) is NodeType.QUOTE_BLOCK

    def test_fenced_code_block_returns_code_block(self) -> None:
        """Test that a string fenced with ``` at both ends returns NodeType.CODE_BLOCK."""
        assert node_type(_make_code()) is NodeType.CODE_BLOCK

    def test_code_block_is_not_plain_block(self) -> None:
        """Test that a fenced code block does not return NodeType.PLAIN_BLOCK."""
        assert node_type(_make_code()) is not NodeType.PLAIN_BLOCK

    def test_code_block_with_surrounding_whitespace_returns_code_block(self) -> None:
        """Test that surrounding whitespace is trimmed before the fence check."""
        assert node_type(_make_code(string="  \n```\ncode\n```  \n")) is NodeType.CODE_BLOCK

    def test_code_block_without_language_returns_code_block(self) -> None:
        """Test that a fence with no language/info string is still a code block."""
        assert node_type(_make_code(string="```\nplain code\n```")) is NodeType.CODE_BLOCK

    def test_unterminated_fence_returns_code_block(self) -> None:
        """Test that an opening fence with no closing fence is still a code block (closing optional)."""
        assert node_type(_make_code(string="```python\nx = 1")) is NodeType.CODE_BLOCK

    def test_inline_code_is_plain_block(self) -> None:
        """Test that single-backtick inline code is not classified as a code block."""
        assert node_type(_make_code(string="`inline`")) is NodeType.PLAIN_BLOCK

    def test_block_quote_node_returns_block_quote(self) -> None:
        """Test that a [[>]]-prefixed block without a callout type returns QUOTE_BLOCK."""
        assert node_type(_make_block_quote()) is NodeType.QUOTE_BLOCK

    def test_block_quote_is_not_plain_block(self) -> None:
        """Test that a block quote node does not return PLAIN_BLOCK."""
        assert node_type(_make_block_quote()) is not NodeType.PLAIN_BLOCK

    def test_bare_block_quote_prefix_returns_block_quote(self) -> None:
        """Test that bare '[[>]]' with no following text returns QUOTE_BLOCK."""
        node = _make_text(string="[[>]]")
        assert node_type(node) is NodeType.QUOTE_BLOCK

    def test_invalid_callout_type_classified_as_block_quote(self) -> None:
        """Test that [[>]] with an unrecognised type keyword is classified as QUOTE_BLOCK."""
        node = _make_text(string="[[>]] [[!INVALID]] text")
        assert node_type(node) is NodeType.QUOTE_BLOCK

    def test_bare_table_marker_returns_native_table(self) -> None:
        """Test that a block whose string is the bare {{table}} marker returns NATIVE_TABLE."""
        node = _make_text(string="{{table}}")
        assert node_type(node) is NodeType.NATIVE_TABLE

    def test_page_ref_table_marker_returns_native_table(self) -> None:
        """Test that the page-reference marker form {{[[table]]}} also returns NATIVE_TABLE."""
        node = _make_text(string="{{[[table]]}}")
        assert node_type(node) is NodeType.NATIVE_TABLE

    def test_table_marker_with_surrounding_whitespace_returns_native_table(self) -> None:
        """Test that surrounding whitespace around a table marker is tolerated."""
        node = _make_text(string="  {{[[table]]}}  ")
        assert node_type(node) is NodeType.NATIVE_TABLE

    def test_table_marker_mixed_with_text_is_plain_block(self) -> None:
        """Test that a table marker mixed with surrounding text is not a NATIVE_TABLE."""
        node = _make_text(string="see {{table}} here")
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_embed_block_returns_embed(self) -> None:
        """Test that a block whose entire string is a block embed returns EMBED_BLOCK."""
        node = _make_text(string="{{embed: ((wjN-kVF3B))}}")
        assert node_type(node) is NodeType.EMBED_BLOCK

    def test_embed_block_with_surrounding_whitespace_returns_embed(self) -> None:
        """Test that surrounding whitespace around a block embed is tolerated."""
        node = _make_text(string="  {{embed: ((wjN-kVF3B))}}  ")
        assert node_type(node) is NodeType.EMBED_BLOCK

    def test_embed_mixed_with_text_is_plain_block(self) -> None:
        """Test that an embed mixed with surrounding text is not a EMBED_BLOCK."""
        node = _make_text(string="see {{embed: ((wjN-kVF3B))}} here")
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_page_embed_returns_embed_page(self) -> None:
        """Test that a block whose entire string is a page embed returns EMBED_PAGE."""
        node = _make_text(string="{{embed: [[Some Page]]}}")
        assert node_type(node) is NodeType.EMBED_PAGE

    def test_page_embed_with_surrounding_whitespace_returns_embed_page(self) -> None:
        """Test that surrounding whitespace around a page embed is tolerated."""
        node = _make_text(string="  {{embed: [[Some Page]]}}  ")
        assert node_type(node) is NodeType.EMBED_PAGE

    def test_page_embed_mixed_with_text_is_plain_block(self) -> None:
        """Test that a page embed mixed with surrounding text is not an EMBED_PAGE."""
        node = _make_text(string="see {{embed: [[Some Page]]}} here")
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_pdf_component_returns_pdf_block(self) -> None:
        """Test that a block whose entire string is a Firestore PDF component returns PDF_BLOCK."""
        node = _make_text(string="{{pdf: https://firebasestorage.googleapis.com/v0/b/t/o/p.pdf.enc?alt=media}}")
        assert node_type(node) is NodeType.PDF_BLOCK

    def test_page_ref_pdf_component_returns_pdf_block(self) -> None:
        """Test that the page-reference form {{[[pdf]]: <url>}} also returns PDF_BLOCK."""
        node = _make_text(string="{{[[pdf]]: https://firebasestorage.googleapis.com/v0/b/t/o/p.pdf?alt=media}}")
        assert node_type(node) is NodeType.PDF_BLOCK

    def test_pdf_component_with_surrounding_whitespace_returns_pdf_block(self) -> None:
        """Test that surrounding whitespace around a PDF component is tolerated."""
        node = _make_text(string="  {{pdf: https://firebasestorage.googleapis.com/v0/b/t/o/p.pdf?alt=media}}  ")
        assert node_type(node) is NodeType.PDF_BLOCK

    def test_pdf_component_mixed_with_text_is_plain_block(self) -> None:
        """Test that a PDF component mixed with surrounding text is not a PDF_BLOCK."""
        node = _make_text(string="see {{pdf: https://firebasestorage.googleapis.com/v0/b/t/o/p.pdf}} here")
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_non_firestore_pdf_component_is_plain_block(self) -> None:
        """Test that a PDF component pointing outside Firestore is not a PDF_BLOCK."""
        node = _make_text(string="{{pdf: https://example.com/paper.pdf}}")
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_attribute_assignment_returns_attribute_block(self) -> None:
        """Test that a block whose entire string is an attribute assignment returns ATTRIBUTE_BLOCK."""
        node = _make_text(string="attribute1:: 5, #[[callouts demo]], #v01")
        assert node_type(node) is NodeType.ATTRIBUTE_BLOCK

    def test_attribute_block_with_surrounding_whitespace_returns_attribute_block(self) -> None:
        """Test that surrounding whitespace around an attribute assignment is tolerated."""
        node = _make_text(string="  tags:: #Guffin,#[[Better Bullets]]  ")
        assert node_type(node) is NodeType.ATTRIBUTE_BLOCK

    def test_attribute_like_prose_is_plain_block(self) -> None:
        """Test that 'attr:: free prose' (values not a comma list) is not an ATTRIBUTE_BLOCK."""
        node = _make_text(string="Note:: this is a sentence")
        assert node_type(node) is NodeType.PLAIN_BLOCK

    def test_result_is_str_enum(self) -> None:
        """Test that the returned value is a NodeType StrEnum member."""
        node = RoamNode(uid="page00001", id=1, title="My Page", children=[])
        result = node_type(node)
        assert isinstance(result, NodeType)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestRoamNodeCalloutValidation
# ---------------------------------------------------------------------------


class TestRoamNodeCalloutValidation:
    """Tests for RoamNode validation of callout block strings."""

    def _make_block(self, string: str) -> RoamNode:
        return RoamNode(
            uid="callutuid",
            id=105,
            string=string,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )

    def test_valid_callout_string_accepted(self) -> None:
        """Test that a well-formed callout marker string is accepted."""
        node = self._make_block("[[>]] [[!INFO]]")
        assert node.string == "[[>]] [[!INFO]]"

    def test_valid_callout_with_body_accepted(self) -> None:
        """Test that a callout marker followed by body text is accepted."""
        node = self._make_block("[[>]] [[!WARNING]] Watch out!")
        assert node.string == "[[>]] [[!WARNING]] Watch out!"

    def test_invalid_callout_type_accepted_as_block_quote(self) -> None:
        """Test that an unrecognised callout type is accepted (classified as QUOTE_BLOCK)."""
        node = self._make_block("[[>]] [[!INVALID]]")
        assert node.string == "[[>]] [[!INVALID]]"

    def test_missing_type_accepted_as_block_quote(self) -> None:
        """Test that bare '[[>]]' is accepted (classified as QUOTE_BLOCK)."""
        node = self._make_block("[[>]]")
        assert node.string == "[[>]]"

    def test_bare_prefix_with_text_accepted_as_block_quote(self) -> None:
        """Test that '[[>]] text' with no type block is accepted (classified as QUOTE_BLOCK)."""
        node = self._make_block("[[>]] some text without type")
        assert node.string == "[[>]] some text without type"

    def test_lowercase_callout_type_accepted_as_block_quote(self) -> None:
        """Test that a lowercase callout type is accepted (classified as QUOTE_BLOCK)."""
        node = self._make_block("[[>]] [[!info]]")
        assert node.string == "[[>]] [[!info]]"

    def test_partial_type_block_accepted_as_block_quote(self) -> None:
        """Test that a malformed type block like '[[!INFO' is accepted (classified as QUOTE_BLOCK)."""
        node = self._make_block("[[>]] [[!INFO")
        assert node.string == "[[>]] [[!INFO"

    def test_string_without_prefix_accepted(self) -> None:
        """Test that a plain block string with no '[[>]]' prefix is not affected."""
        node = self._make_block("just some text")
        assert node.string == "just some text"


# ---------------------------------------------------------------------------
# TestImageSize
# ---------------------------------------------------------------------------


class TestImageSize:
    """Tests for the image_size() function."""

    def test_returns_none_for_non_image_node(self) -> None:
        """Test that image_size returns None for any non-IMAGE_BLOCK node."""
        assert image_size(_make_text()) is None

    def test_returns_empty_image_size_when_no_image_size_prop(self) -> None:
        """Test that image_size returns ImageSize() when the node has no image-size prop."""
        assert image_size(_make_image()) == ImageSize()

    def test_returns_dimensions_from_fixture(self) -> None:
        """Test that image_size extracts width and height from the Article 1 fixture node zZG-BfWvs.

        zZG-BfWvs has ``image-size: {<url>: {width: 257, height: null}}``, so the expected
        result is ``ImageSize(width=257, height=None)``.
        """
        raw: list[dict[str, object]] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_1_nodes.yaml").read_text())
        nodes: list[RoamNode] = [RoamNode.model_validate(r) for r in raw]
        fixture_node: RoamNode = next(n for n in nodes if n.uid == "zZG-BfWvs")
        assert image_size(fixture_node) == ImageSize(width=257, height=None)

    def test_raises_validation_error_for_invalid_image_size_prop(self) -> None:
        """Test that image_size raises ValidationError when image-size prop has an invalid structure.

        The expected structure is ``dict[str, dict[str, int | None]]``; passing a plain
        string value triggers ``IMAGE_SIZE_PROP_ADAPTER.validate_python`` to raise
        ``ValidationError``.
        """
        node = RoamNode(
            uid="imageuid1",
            id=101,
            string=_IMAGE_STRING,
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props={"image-size": "not-a-dict"},
        )
        with pytest.raises(ValidationError):
            image_size(node)


# ---------------------------------------------------------------------------
# TestEffectiveChildrenViewType
# ---------------------------------------------------------------------------


class TestEffectiveChildrenViewType:
    """Tests for the effective_children_view_type() function."""

    def test_returns_default_when_unset(self) -> None:
        """Test that DEFAULT_CHILDREN_VIEW_TYPE is returned when children_view_type is None."""
        node = RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
        )
        assert node.children_view_type is None
        assert effective_children_view_type(node) == DEFAULT_CHILDREN_VIEW_TYPE

    @pytest.mark.parametrize("view_type", list(ChildrenViewType))
    def test_returns_own_value_when_set(self, view_type: ChildrenViewType) -> None:
        """Test that the node's own children_view_type is returned when it is set."""
        node = RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            children_view_type=view_type,
        )
        assert effective_children_view_type(node) == view_type

    def test_unknown_view_type_value_is_tolerated_as_unset(self) -> None:
        """The block-level view-type bookkeeping ("outline") flattens onto the same wire key; it parses as unset."""
        node = RoamNode.model_validate(
            {
                "uid": "block0001",
                "id": 1,
                "string": "stub",
                "parents": [{"id": 99}],
                "page": {"id": 99},
                "view-type": "outline",
            }
        )
        assert node.children_view_type is None
        assert effective_children_view_type(node) == DEFAULT_CHILDREN_VIEW_TYPE


class TestBetterBulletType:
    """Tests for the better_bullet_type() function."""

    @staticmethod
    def _node(props: dict[str, object] | None) -> RoamNode:
        """Build a minimal block node carrying *props*."""
        return RoamNode(
            uid="block0001",
            id=1,
            string="stub",
            parents=[IdObject(id=99)],
            page=IdObject(id=99),
            props=props,
        )

    @pytest.mark.parametrize("member", list(BetterBulletType))
    def test_recognized_type_prop_resolves_to_its_member(self, member: BetterBulletType) -> None:
        """A 'type' prop holding a persisted Better Bullets identifier resolves to its member."""
        assert better_bullet_type(self._node({"type": member.id})) is member

    def test_no_props_resolves_to_none(self) -> None:
        """A node with no property map carries no Better Bullet."""
        assert better_bullet_type(self._node(None)) is None

    def test_no_type_entry_resolves_to_none(self) -> None:
        """A property map without a 'type' entry carries no Better Bullet."""
        assert better_bullet_type(self._node({"ah-level": "4"})) is None

    def test_unrecognized_identifier_rejected_at_construction(self) -> None:
        """A 'type' value outside the Better Bullets vocabulary fails RoamNode validation."""
        with pytest.raises(ValidationError, match="unrecognized Better Bullets"):
            self._node({"type": "somethingElse"})

    def test_non_string_type_prop_rejected_at_construction(self) -> None:
        """A non-string 'type' value fails RoamNode validation."""
        with pytest.raises(ValidationError, match="unrecognized Better Bullets"):
            self._node({"type": 7})

    def test_article_4_fixture_covers_every_member(self) -> None:
        """The [[Test Article]] 4 Better Bullets section's children resolve to all eleven members.

        The fixture records the identifiers the extension actually persists (including the
        divergent ``doubleArrow`` and ``plus`` spellings), so this pins the enum's ids to the
        live vocabulary.
        """
        raw = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_4_nodes.yaml").read_text())
        nodes: dict[int, RoamNode] = {}

        def _walk(item: object) -> None:
            if isinstance(item, dict):
                if "id" in item and ("string" in item or "title" in item):
                    nodes[item["id"]] = RoamNode.model_validate(item)
                for value in item.values():
                    _walk(value)
            elif isinstance(item, list):
                for value in item:
                    _walk(value)

        _walk(raw)
        section = nodes[15252]
        assert section.children is not None
        resolved = [better_bullet_type(nodes[stub.id]) for stub in section.children]
        assert resolved == list(BetterBulletType)


class TestDailyNoteTitleValidation:
    """A daily-note-UID (MM-DD-YYYY) page's title must be the verbose date the UID encodes."""

    def test_matching_title_is_accepted(self) -> None:
        """A daily-note page whose title is the correct verbose date validates."""
        node = RoamNode(uid="01-01-2026", id=1, title="January 1st, 2026")
        assert node.title == "January 1st, 2026"

    @pytest.mark.parametrize(
        ("uid", "title"),
        [
            ("08-24-2026", "August 24th, 2026"),
            ("01-01-2026", "January 1st, 2026"),
            ("01-02-2026", "January 2nd, 2026"),
            ("01-03-2026", "January 3rd, 2026"),
            ("01-04-2026", "January 4th, 2026"),
            ("01-11-2026", "January 11th, 2026"),
            ("01-12-2026", "January 12th, 2026"),
            ("01-13-2026", "January 13th, 2026"),
            ("01-21-2026", "January 21st, 2026"),
            ("01-22-2026", "January 22nd, 2026"),
            ("01-23-2026", "January 23rd, 2026"),
            ("01-31-2026", "January 31st, 2026"),
            ("12-25-2025", "December 25th, 2025"),
        ],
    )
    def test_ordinal_and_month_forms(self, uid: str, title: str) -> None:
        """The expected title covers each ordinal suffix (st/nd/rd/th, incl. the 11-13 exception)."""
        assert RoamNode(uid=uid, id=1, title=title).title == title

    def test_wrong_title_is_rejected(self) -> None:
        """A daily-note page whose title is not the verbose date is rejected."""
        with pytest.raises(ValidationError, match="must have title 'January 1st, 2026'"):
            RoamNode(uid="01-01-2026", id=1, title="Jan 1 2026")

    def test_title_for_a_different_date_is_rejected(self) -> None:
        """A daily-note page titled with a different date than its UID is rejected."""
        with pytest.raises(ValidationError, match="must have title"):
            RoamNode(uid="01-01-2026", id=1, title="January 2nd, 2026")

    def test_impossible_date_uid_is_rejected(self) -> None:
        """A daily-note-shaped UID encoding an impossible calendar date is rejected."""
        with pytest.raises(ValidationError):
            RoamNode(uid="13-45-2026", id=1, title="whatever")

    def test_synthetic_uid_title_is_unconstrained(self) -> None:
        """A page with a synthetic UID may carry any title."""
        node = RoamNode(uid="abc123xyz", id=1, title="An Arbitrary Page Title")
        assert node.title == "An Arbitrary Page Title"
