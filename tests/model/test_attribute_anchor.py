"""Tests for guffin.model.attribute_anchor."""

from guffin.model.attribute_anchor import AttributeAnchor, TreePosition
from guffin.model.vertex import VertexType


class TestAnchorVertexTypes:
    """AttributeAnchor members carry the vertex-type sets they attach to."""

    def test_single_type_anchors(self) -> None:
        """The page, heading, and pdf anchors each cover exactly their one vertex type."""
        assert AttributeAnchor.PAGE.vertex_types == frozenset({VertexType.PAGE})
        assert AttributeAnchor.HEADING.vertex_types == frozenset({VertexType.HEADING})
        assert AttributeAnchor.PDF.vertex_types == frozenset({VertexType.PDF})

    def test_block_anchor_covers_every_type_except_page(self) -> None:
        """The block anchor covers every vertex type but PAGE."""
        assert VertexType.PAGE not in AttributeAnchor.BLOCK.vertex_types
        assert AttributeAnchor.BLOCK.vertex_types == frozenset(VertexType) - {VertexType.PAGE}

    def test_any_anchor_covers_every_type(self) -> None:
        """The any anchor covers every vertex type, page included."""
        assert AttributeAnchor.ANY.vertex_types == frozenset(VertexType)

    def test_root_anchor_covers_every_type_at_the_root(self) -> None:
        """The root anchor is positional: every vertex type, but only at the tree's root."""
        assert AttributeAnchor.ROOT.vertex_types == frozenset(VertexType)
        assert AttributeAnchor.ROOT.tree_position is TreePosition.ROOT

    def test_every_other_anchor_is_positionally_unconstrained(self) -> None:
        """All anchors except ROOT carry the ANYWHERE tree position."""
        for member in AttributeAnchor:
            if member is not AttributeAnchor.ROOT:
                assert member.tree_position is TreePosition.ANYWHERE, member

    def test_only_the_pdf_anchor_sees_through_standalone_links(self) -> None:
        """PDF alone may be satisfied through a standalone vertex link to a matching target."""
        for member in AttributeAnchor:
            assert member.through_standalone_links is (member is AttributeAnchor.PDF), member
