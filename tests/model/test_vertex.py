"""Unit tests for guffin.model.vertex concrete vertex types."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import Attribute, AttributeAssignment, LiteralValue, ReferenceValue
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import AttributeAssignmentVertex, BlockEmbedVertex, VertexType, vertex_adapter

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


class TestAttributeAssignmentVertex:
    """Tests for the AttributeAssignmentVertex concrete vertex type."""

    @staticmethod
    def _assignment() -> AttributeAssignment:
        return AttributeAssignment(
            attribute=Attribute(name="attribute1", link=_REF_LINK),
            values=(LiteralValue(value="5"), ReferenceValue(name="callouts demo", link=_REF_LINK)),
        )

    def test_valid_construction(self) -> None:
        """An AttributeAssignmentVertex carries its discriminator and assignment."""
        vertex = AttributeAssignmentVertex(uid="block0001", assignment=self._assignment())
        assert vertex.vertex_type is VertexType.ATTRIBUTE_ASSIGNMENT
        assert vertex.uid == "block0001"
        assert vertex.assignment.attribute.name == "attribute1"

    def test_adapter_round_trips_via_discriminator(self) -> None:
        """Vertex_adapter selects AttributeAssignmentVertex (and its value union) from a dumped dict."""
        vertex = AttributeAssignmentVertex(uid="block0001", assignment=self._assignment())
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, AttributeAssignmentVertex)
        assert restored == vertex
