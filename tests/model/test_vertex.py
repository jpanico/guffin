"""Unit tests for guffin.model.vertex concrete vertex types."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import Attribute, AttributeAssignment, AttributeInstance, LiteralValue, ReferenceValue
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import BlockEmbedVertex, TextVertex, VertexType, vertex_adapter

# A representative embed link to a 9-character destination UID.
_EMBED_LINK = VertexLink(kind=VertexLinkKind.EMBED, uid="tgt000001")
_REF_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="tgt000001")


class TestBlockEmbedVertex:
    """Tests for the BlockEmbedVertex concrete vertex type."""

    def test_valid_construction(self) -> None:
        """A BlockEmbedVertex with an EMBED-kind link has the expected fields."""
        vertex = BlockEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK)
        assert vertex.vertex_type is VertexType.BLOCK_EMBED
        assert vertex.uid == "block0001"
        assert vertex.vertex_link == _EMBED_LINK
        assert vertex.vertex_link.kind is VertexLinkKind.EMBED

    def test_rejects_reference_kind(self) -> None:
        """A vertex_link whose kind is REFERENCE (not EMBED) is rejected."""
        ref_link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="tgt000001")
        with pytest.raises(ValidationError):
            BlockEmbedVertex(uid="block0001", vertex_link=ref_link)

    def test_adapter_round_trips_via_discriminator(self) -> None:
        """Vertex_adapter selects BlockEmbedVertex from a dumped dict via its vertex_type discriminator."""
        vertex = BlockEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK)
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, BlockEmbedVertex)
        assert restored == vertex


class TestAttributeAssignmentsField:
    """Tests for the attribute_assignments field shared by every vertex type (on _BaseVertex)."""

    @staticmethod
    def _assignment() -> AttributeAssignment:
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="attribute1"), link=_REF_LINK),
            values=(LiteralValue(value="5"), ReferenceValue(name="callouts demo", link=_REF_LINK)),
        )

    def test_defaults_to_none(self) -> None:
        """A vertex with no folded attributes has attribute_assignments == None."""
        vertex = TextVertex(uid="block0001", text="hello")
        assert vertex.attribute_assignments is None

    def test_carries_assignments(self) -> None:
        """A vertex records its folded attribute assignments in order."""
        vertex = TextVertex(uid="block0001", text="hello", attribute_assignments=[self._assignment()])
        assert vertex.attribute_assignments is not None
        assert vertex.attribute_assignments[0].attribute.definition.name == "attribute1"

    def test_adapter_round_trips_with_assignments(self) -> None:
        """Vertex_adapter round-trips a vertex carrying attribute assignments (and their value union)."""
        vertex = TextVertex(uid="block0001", text="hello", attribute_assignments=[self._assignment()])
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, TextVertex)
        assert restored == vertex
