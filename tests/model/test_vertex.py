"""Unit tests for guffin.model.vertex.BlockEmbedVertex."""

import pytest
from pydantic import ValidationError

from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import BlockEmbedVertex, VertexType, vertex_adapter

# A representative embed link to a 9-character destination UID.
_EMBED_LINK = VertexLink(kind=VertexLinkKind.EMBED, uid="tgt000001")


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
        """vertex_adapter selects BlockEmbedVertex from a dumped dict via its vertex_type discriminator."""
        vertex = BlockEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK)
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, BlockEmbedVertex)
        assert restored == vertex
