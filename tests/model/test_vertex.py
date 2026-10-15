"""Unit tests for guffin.model.vertex concrete vertex types."""

import pytest
from conftest import asset_storage
from pydantic import HttpUrl, ValidationError

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.alternative import Alternative
from guffin.model.asset_storage import AssetStorage, StoreType
from guffin.model.attribute import Attribute, AttributeInstance, LiteralValue, ReferenceValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.code_source import CodeSource
from guffin.model.vertex import (
    AssetVertex,
    BlockEmbedVertex,
    CodeBlockVertex,
    ImageVertex,
    PageEmbedVertex,
    PageVertex,
    PdfVertex,
    QuoteBlockVertex,
    QuoteType,
    TextVertex,
    TodoState,
    TodoVertex,
    VertexType,
    find_attribute_assignment,
    is_embed_vertex,
    is_epigraph,
    is_renderable_asset_vertex,
    vertex_adapter,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind

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


class TestPageEmbedVertex:
    """Tests for the PageEmbedVertex concrete vertex type."""

    def test_valid_construction(self) -> None:
        """A PageEmbedVertex with an EMBED-kind link has the expected fields."""
        vertex = PageEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK)
        assert vertex.vertex_type is VertexType.PAGE_EMBED
        assert vertex.uid == "block0001"
        assert vertex.vertex_link == _EMBED_LINK
        assert vertex.vertex_link.kind is VertexLinkKind.EMBED

    def test_rejects_reference_kind(self) -> None:
        """A vertex_link whose kind is REFERENCE (not EMBED) is rejected."""
        with pytest.raises(ValidationError):
            PageEmbedVertex(uid="block0001", vertex_link=_REF_LINK)

    def test_adapter_round_trips_via_discriminator(self) -> None:
        """Vertex_adapter selects PageEmbedVertex from a dumped dict via its vertex_type discriminator."""
        vertex = PageEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK)
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, PageEmbedVertex)
        assert restored == vertex


class TestCodeBlockVertex:
    """Tests for the CodeBlockVertex concrete vertex type."""

    _SOURCE = CodeSource(
        url="https://github.com/psf/requests/blob/main/setup.py#L1-L5",
        commit_sha="0d9ca427f7d7dbe92694284d4a6249178255036e",
        fetched_date="2026-07-17",
    )

    def test_code_source_defaults_to_none(self) -> None:
        """An unsourced code block carries no provenance."""
        vertex = CodeBlockVertex(uid="code00001", code="print(1)", language="python")
        assert vertex.code_source is None

    def test_code_source_serializes_under_kebab_alias(self) -> None:
        """A sourced code block dumps its provenance under the 'code-source' alias."""
        vertex = CodeBlockVertex(uid="code00001", code="print(1)", language="python", code_source=self._SOURCE)
        dumped = vertex.model_dump(by_alias=True)
        assert dumped["code-source"]["commit-sha"] == self._SOURCE.commit_sha

    def test_adapter_round_trips_via_discriminator(self) -> None:
        """Vertex_adapter selects CodeBlockVertex from a dumped dict, provenance intact."""
        vertex = CodeBlockVertex(uid="code00001", code="print(1)", language="python", code_source=self._SOURCE)
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, CodeBlockVertex)
        assert restored == vertex
        assert restored.code_source == self._SOURCE


class TestTodoVertex:
    """Tests for the TodoVertex concrete vertex type and its TodoState enum."""

    def test_todo_state_has_exactly_two_members(self) -> None:
        """TodoState has exactly the TODO and DONE members."""
        assert set(TodoState) == {TodoState.TODO, TodoState.DONE}

    def test_valid_construction(self) -> None:
        """A TodoVertex has the expected fields."""
        vertex = TodoVertex(uid="todo00001", todo_state=TodoState.TODO, text="an open item")
        assert vertex.vertex_type is VertexType.TODO
        assert vertex.todo_state is TodoState.TODO
        assert vertex.text == "an open item"

    def test_todo_state_is_required(self) -> None:
        """A TodoVertex without a todo_state is rejected."""
        with pytest.raises(ValidationError):
            TodoVertex(uid="todo00001", text="an item")  # type: ignore[call-arg]

    def test_todo_state_serializes_under_kebab_alias(self) -> None:
        """A TodoVertex dumps its state under the 'todo-state' alias."""
        vertex = TodoVertex(uid="todo00001", todo_state=TodoState.DONE, text="a completed item")
        dumped = vertex.model_dump(by_alias=True)
        assert dumped["todo-state"] == "done"
        assert dumped["vertex-type"] == "guffin/todo"

    def test_adapter_round_trips_via_discriminator(self) -> None:
        """Vertex_adapter selects TodoVertex from a dumped dict via its vertex_type discriminator."""
        vertex = TodoVertex(uid="todo00001", todo_state=TodoState.DONE, text="a completed item")
        restored = vertex_adapter.validate_python(vertex.model_dump())
        assert isinstance(restored, TodoVertex)
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


class TestFindAttributeAssignment:
    """find_attribute_assignment() searches a vertex's folded assignments for an Attribute."""

    @staticmethod
    def _assignment(name: str) -> AttributeAssignment:
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name=name), link=_REF_LINK), values=()
        )

    def test_finds_matching_assignment(self) -> None:
        """The assignment for the sought attribute is returned."""
        vertex = TextVertex(
            uid="block0001", text="hello", attribute_assignments=[self._assignment("a"), self._assignment("b")]
        )
        result = find_attribute_assignment(vertex, Attribute(name="b"))
        assert result is not None
        assert result.attribute.definition.name == "b"

    def test_none_when_no_match(self) -> None:
        """A vertex without an assignment for the attribute yields None."""
        vertex = TextVertex(uid="block0001", text="hello", attribute_assignments=[self._assignment("a")])
        assert find_attribute_assignment(vertex, Attribute(name="b")) is None

    def test_none_when_vertex_has_no_assignments(self) -> None:
        """A vertex with no folded assignments at all yields None."""
        vertex = TextVertex(uid="block0001", text="hello")
        assert find_attribute_assignment(vertex, Attribute(name="a")) is None


class TestIsRenderableAssetVertex:
    """Tests for the is_renderable_asset_vertex() renderability classification predicate."""

    def test_image_vertex_is_renderable(self) -> None:
        """An ImageVertex is a renderable asset."""
        vertex = ImageVertex(
            uid="img00001a",
            storage=asset_storage(HttpUrl("https://example.com/imgs/photo.jpeg")),
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        assert is_renderable_asset_vertex(vertex)

    def test_pdf_vertex_is_renderable(self) -> None:
        """A PdfVertex is a renderable asset."""
        vertex = PdfVertex(uid="pdf00001a", storage=asset_storage(HttpUrl("https://example.com/pdfs/paper.pdf")))
        assert is_renderable_asset_vertex(vertex)

    def test_non_asset_vertices_are_not_renderable_assets(self) -> None:
        """Page and text vertices are not renderable assets."""
        assert not is_renderable_asset_vertex(PageVertex(uid="page00001", title="P"))
        assert not is_renderable_asset_vertex(TextVertex(uid="txt00001a", text="hello"))


class TestAssetVertex:
    """Tests for the AssetVertex concrete vertex type."""

    _STORAGE = AssetStorage(
        location="https://firebasestorage.googleapis.com/v0/b/test.appspot.com"
        "/o/imgs%2FfJoSdh65Ry.pkpass.enc?alt=media&token=abc123",
        store_type=StoreType.FIREBASE_STORAGE,
        is_encrypted=True,
    )

    def test_valid_construction(self) -> None:
        """An AssetVertex carries its storage plus optional media type and filename."""
        vertex = AssetVertex(
            uid="asset0001",
            storage=self._STORAGE,
            media_type=MediaType.PDF,
            file_name="booking.pdf",
        )
        assert vertex.vertex_type is VertexType.ASSET
        assert vertex.storage == self._STORAGE
        assert vertex.media_type is MediaType.PDF
        assert vertex.file_name == "booking.pdf"

    def test_media_type_and_file_name_default_to_none(self) -> None:
        """An asset of unrecognizable kind constructs with no media type and no filename."""
        vertex = AssetVertex(uid="asset0001", storage=self._STORAGE)
        assert vertex.media_type is None
        assert vertex.file_name is None

    def test_storage_is_required(self) -> None:
        """An AssetVertex without a storage is rejected."""
        with pytest.raises(ValidationError, match="storage"):
            AssetVertex(uid="asset0001")  # type: ignore[call-arg]

    def test_serializes_with_kebab_case_aliases(self) -> None:
        """The media type and filename fields serialize under their kebab-case aliases."""
        vertex = AssetVertex(uid="asset0001", storage=self._STORAGE, media_type=MediaType.PDF, file_name="a.pdf")
        dumped = vertex.model_dump(by_alias=True)
        assert dumped["vertex-type"] is VertexType.ASSET
        assert dumped["media-type"] is MediaType.PDF
        assert dumped["file-name"] == "a.pdf"


class TestIsEmbedVertex:
    """Tests for the is_embed_vertex() transcluding classification predicate."""

    def test_block_embed_vertex_is_embed(self) -> None:
        """A BlockEmbedVertex is transcluding."""
        assert is_embed_vertex(BlockEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK))

    def test_page_embed_vertex_is_embed(self) -> None:
        """A PageEmbedVertex is transcluding."""
        assert is_embed_vertex(PageEmbedVertex(uid="block0001", vertex_link=_EMBED_LINK))

    def test_non_embed_vertices_are_not_embeds(self) -> None:
        """Page and text vertices are not transcluding."""
        assert not is_embed_vertex(PageVertex(uid="page00001", title="P"))
        assert not is_embed_vertex(TextVertex(uid="txt00001a", text="hello"))


class TestIsEpigraph:
    """Tests for the is_epigraph() classification predicate."""

    def test_epigraph_quote_block_is_an_epigraph(self) -> None:
        """A quote block of quote type EPIGRAPH is an epigraph."""
        assert is_epigraph(QuoteBlockVertex(uid="epigr0001", quote_type=QuoteType.EPIGRAPH, quote="Q."))

    @pytest.mark.parametrize("quote_type", [QuoteType.BLOCK, QuoteType.PULL])
    def test_other_quote_blocks_are_not(self, quote_type: QuoteType) -> None:
        """A block quotation or a pull quote is not an epigraph."""
        assert not is_epigraph(QuoteBlockVertex(uid="quote0001", quote_type=quote_type, quote="Q."))

    def test_other_vertex_types_are_not(self) -> None:
        """A vertex that is not a quote block is not an epigraph."""
        assert not is_epigraph(TextVertex(uid="txt00001a", text="hello"))


class TestAlternatives:
    """Tests for the alternatives affordance: TextVertex carries them, nothing else does."""

    def test_only_text_supports_alternatives(self) -> None:
        """VertexType.supports_alternatives is True for TEXT alone."""
        assert {vertex_type for vertex_type in VertexType if vertex_type.supports_alternatives} == {VertexType.TEXT}

    def test_support_is_derived_from_the_class(self) -> None:
        """The property answers from the vertex class, so it agrees with the field's presence."""
        assert "alternatives" in TextVertex.model_fields
        assert "alternatives" not in PageVertex.model_fields
        assert "alternatives" not in TodoVertex.model_fields
        assert VertexType.TEXT.supports_alternatives
        assert not VertexType.TODO.supports_alternatives

    def test_text_vertex_has_no_alternatives_by_default(self) -> None:
        """A text written one way carries None and reports no alternatives."""
        vertex = TextVertex(uid="textuid01", text="the one wording")
        assert vertex.alternatives is None
        assert not vertex.has_alternatives

    def test_text_vertex_with_alternatives(self) -> None:
        """Alternatives are kept in the given order and has_alternatives reports them."""
        alternatives = (Alternative(uid="altuid001", text="first"), Alternative(uid="altuid002", text="second"))
        vertex = TextVertex(uid="textuid01", text="selected", alternatives=alternatives)
        assert vertex.alternatives == alternatives
        assert vertex.has_alternatives

    def test_empty_alternatives_means_none(self) -> None:
        """An empty tuple is allowed and reports no alternatives, like None."""
        assert not TextVertex(uid="textuid01", text="x", alternatives=()).has_alternatives

    def test_alternatives_are_omitted_from_a_none_excluding_dump(self) -> None:
        """Without alternatives the field vanishes from an exclude_none dump, so unversioned fixtures are unchanged."""
        dumped = TextVertex(uid="textuid01", text="x").model_dump(mode="json", exclude_none=True)
        assert "alternatives" not in dumped

    def test_alternatives_round_trip_through_the_adapter(self) -> None:
        """A dumped text vertex with alternatives validates back to an equal vertex."""
        vertex = TextVertex(
            uid="textuid01", text="selected", alternatives=(Alternative(uid="altuid001", text="other"),)
        )
        dumped = vertex.model_dump(mode="json", exclude_none=True)
        assert dumped["alternatives"] == [{"uid": "altuid001", "text": "other"}]
        restored = vertex_adapter.validate_python(dumped)
        assert isinstance(restored, TextVertex)
        assert restored == vertex

    def test_no_other_vertex_carries_alternatives(self) -> None:
        """A vertex type without the affordance has no alternatives field and no has_alternatives property."""
        page = PageVertex(uid="pageuid01", title="P")
        assert "alternatives" not in PageVertex.model_fields
        assert not hasattr(page, "alternatives")
        assert not hasattr(page, "has_alternatives")
