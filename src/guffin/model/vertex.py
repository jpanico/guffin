"""Normalized graph vertex types — the source-agnostic content model.

A :data:`Vertex` is one node of the normalized content model: the self-contained,
portable form a source graph's node takes after transcription.

Normalization (transcription) means:

- Source-internal numeric entity ids are eliminated.
- Raw child and reference stubs are resolved to stable UID strings.
- Source-specific markup and component syntax is translated away; what remains is the
  content itself, typed by what it *is*.
- Each node is classified into a :class:`VertexType`.
- The result is self-contained and portable — no source dependencies remain.

Public symbols:

- :data:`VertexChildren` — a vertex's ordered child UIDs.
- :data:`VertexRefs` — a vertex's referenced UIDs.
- :class:`VertexType` — string enum classifying each vertex by the kind of content it
  carries.
- :class:`PageVertex` — a titled page, the top-level container vertex.
- :class:`HeadingVertex` — a section heading (levels 1–6).
- :class:`TextVertex` — plain body text.
- :class:`TodoState` — the two states of a TODO item (``TODO`` open, ``DONE`` completed).
- :class:`TodoVertex` — a checkbox (TODO) item: a state plus the item text.
- :class:`AssetVertex` — a hosted asset: the general asset vertex (an asset of
  unspecified kind) and the shared base of the asset vertex types, carrying its
  :class:`~guffin.model.asset_storage.AssetStorage` plus optional media type and filename.
- :class:`ImageVertex` — a hosted image asset displayed in the document
  (an :class:`AssetVertex` subclass).
- :class:`PdfVertex` — a hosted PDF asset displayed in the document
  (an :class:`AssetVertex` subclass).
- :class:`CalloutVertex` — a callout (admonition) with a category, title, and body.
- :class:`CodeBlockVertex` — a fenced code listing.
- :class:`QuoteType` — how a quote block is presented (``BLOCK`` vs ``PULL``).
- :class:`QuoteBlockVertex` — a quotation, presented as a plain block quote or a
  decorated pull quote.
- :class:`TableVertex` — a table: a cell grid plus its styling overlay.
- :class:`BlockEmbedVertex` — a transclusion of another block at this position.
- :class:`PageEmbedVertex` — a transclusion of a whole page at this position.
- :data:`Vertex` — union of the twelve concrete vertex types transcription currently
  produces (:class:`AssetVertex` deliberately excluded until its rendering design lands).
- :data:`AssetBearingVertex` — union of the asset-bearing vertex types
  (:class:`ImageVertex` | :class:`PdfVertex`).
- :data:`EmbedVertex` — union of the transcluding vertex types
  (:class:`BlockEmbedVertex` | :class:`PageEmbedVertex`).
- :data:`vertex_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for validating a
  :data:`Vertex` from a raw dict.
- :func:`is_asset_bearing_vertex` — whether a vertex is asset-bearing, narrowing it to
  :data:`AssetBearingVertex`.
- :func:`is_embed_vertex` — whether a vertex is transcluding, narrowing it to
  :data:`EmbedVertex`.
- :func:`find_attribute_assignment` — find a vertex's folded attribute assignment for an
  :class:`~guffin.model.attribute.Attribute`.
"""

import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal, TypeIs, get_args

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, validate_call

from guffin.common.geometry import ImageSize
from guffin.common.markdown import HeadingLevel
from guffin.common.media_type import MediaType, is_image_type
from guffin.common.programming_language import CodeLanguageId
from guffin.common.table import Table, TableStyle
from guffin.model.asset_storage import AssetStorage
from guffin.model.attribute import Attribute
from guffin.model.attribute_assignment import AttributeAssignment, find_assignment_for
from guffin.model.code_source import CodeSource
from guffin.model.primitives import Uid
from guffin.model.vertex_link import VertexLink, VertexLinkKind


class VertexType(StrEnum):
    """Classification assigned to each vertex during transcription.

    Every source node is classified into exactly one ``VertexType`` by the kind of
    content it carries.  The values are string-valued so they serialize cleanly
    to/from JSON without extra conversion.

    Values:
        PAGE: A titled page — the top-level container vertex.
        TEXT: Plain body text.
        TODO: A checkbox (TODO) item — a state (open or completed) plus the item
            text.
        HEADING: A section heading, with an effective level 1–6.
        IMAGE: A hosted image asset displayed in the document.
        PDF: A hosted PDF asset displayed in the document.
        ASSET: A hosted asset of unspecified kind — an upload that is neither an
            image nor a PDF component (e.g. an audio file, archive, or pass).
        CALLOUT: A callout (admonition) — a categorised aside with a title and
            body.
        CODE_BLOCK: A fenced code listing.
        QUOTE_BLOCK: A quotation — presented as a plain block quote or a
            decorated pull quote.
        TABLE: A table — a cell grid whose rows come from the vertex's child
            subtree.
        BLOCK_EMBED: A transclusion of another block at this position.
        PAGE_EMBED: A transclusion of a whole page at this position.
    """

    PAGE = "guffin/page"
    TEXT = "guffin/text"
    TODO = "guffin/todo"
    HEADING = "guffin/heading"
    IMAGE = "guffin/image"
    PDF = "guffin/pdf"
    ASSET = "guffin/asset"
    CALLOUT = "guffin/callout"
    CODE_BLOCK = "guffin/code-block"
    QUOTE_BLOCK = "guffin/quote-block"
    TABLE = "guffin/table"
    BLOCK_EMBED = "guffin/block-embed"
    PAGE_EMBED = "guffin/page-embed"


type VertexChildren = list[Uid]
"""A vertex's ordered child UIDs.

Resolved from the source's raw child stubs to stable UID strings, in the source's
sibling order.
"""

type VertexRefs = list[Uid]
"""A vertex's referenced UIDs.

Resolved from the source's raw reference stubs to stable UID strings.
"""


class _BaseVertex[VT: VertexType](BaseModel):
    """Shared fields inherited by all thirteen concrete vertex types.

    Not instantiated directly — use :class:`PageVertex`, :class:`HeadingVertex`,
    :class:`TextVertex`, :class:`TodoVertex`, :class:`ImageVertex`, :class:`PdfVertex`,
    :class:`AssetVertex`, :class:`CalloutVertex`, :class:`CodeBlockVertex`,
    :class:`QuoteBlockVertex`, :class:`TableVertex`, :class:`BlockEmbedVertex`, or
    :class:`PageEmbedVertex`.

    Type Parameters:
        VT: The :class:`VertexType` literal for the concrete subtype (e.g.
            ``Literal[VertexType.PAGE]``).

    Attributes:
        vertex_type: Discriminator field identifying the concrete subtype.
            Narrowed to a :class:`~typing.Literal` in each subclass.
        uid: Stable identifier of the vertex. Required.
        children: Ordered child UIDs. ``None`` when the vertex has no children.
        refs: Referenced UIDs. ``None`` when the vertex references nothing.
        attribute_assignments: Attribute assignments (``<attribute>:: <value>, …``)
            declared directly on this vertex, in source order — folded onto the
            vertex rather than carried as separate child vertices. ``None`` when
            the vertex declares none.
            Serialized as ``'attribute-assignments'``.
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    vertex_type: VT
    uid: Uid = Field(..., description="Stable block/page identifier.")
    children: VertexChildren | None = Field(default=None, description="Ordered child UIDs.")
    refs: VertexRefs | None = Field(default=None, description="Referenced UIDs.")
    attribute_assignments: list[AttributeAssignment] | None = Field(
        default=None,
        serialization_alias="attribute-assignments",
        description="Attribute assignments declared directly on this vertex, in source order.",
    )


class PageVertex(_BaseVertex[Literal[VertexType.PAGE]]):
    """A titled page — the top-level container vertex.

    Attributes:
        vertex_type: Always :attr:`~VertexType.PAGE`.
            Serialized as ``'vertex-type'``.
        title: The page title.
        daily_note_date: The calendar date this page represents when it is a daily-note page
            (its ``uid`` is an ``MM-DD-YYYY`` date), else ``None``.  Lets a renderer format
            references to daily notes by date instead of relying on the source-authored ``title``.
            Serialized as ``'daily-note-date'``.
    """

    vertex_type: Literal[VertexType.PAGE] = Field(
        default=VertexType.PAGE,
        serialization_alias="vertex-type",
        description="Always VertexType.PAGE (serialized as 'vertex-type').",
    )
    title: str = Field(..., description="The page title.")
    daily_note_date: datetime.date | None = Field(
        default=None,
        serialization_alias="daily-note-date",
        description="Calendar date of a daily-note page (uid is MM-DD-YYYY), else None.",
    )


class HeadingVertex(_BaseVertex[Literal[VertexType.HEADING]]):
    """A section heading.

    Attributes:
        vertex_type: Always :attr:`~VertexType.HEADING`.
            Serialized as ``'vertex-type'``.
        text: The heading text.
        heading_level: Effective heading level in the range 1–6.
    """

    vertex_type: Literal[VertexType.HEADING] = Field(
        default=VertexType.HEADING,
        serialization_alias="vertex-type",
        description="Always VertexType.HEADING (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="The heading text.")
    heading_level: HeadingLevel = Field(..., description="Effective heading level (1–6).")


class TextVertex(_BaseVertex[Literal[VertexType.TEXT]]):
    """Plain body text — a vertex whose content is ordinary prose.

    Attributes:
        vertex_type: Always :attr:`~VertexType.TEXT`.
            Serialized as ``'vertex-type'``.
        text: The body text.
    """

    vertex_type: Literal[VertexType.TEXT] = Field(
        default=VertexType.TEXT,
        serialization_alias="vertex-type",
        description="Always VertexType.TEXT (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="The body text.")


class TodoState(StrEnum):
    """State of a TODO item.

    Attributes:
        TODO: The item is open (unchecked).
        DONE: The item is completed (checked).
    """

    TODO = "todo"
    DONE = "done"


class TodoVertex(_BaseVertex[Literal[VertexType.TODO]]):
    """A checkbox (TODO) item.

    The source's state marker is translated away at transcription: its keyword
    becomes :attr:`todo_state` and the remaining item text becomes :attr:`text`.

    Attributes:
        vertex_type: Always :attr:`~VertexType.TODO`.
            Serialized as ``'vertex-type'``.
        todo_state: The item's state — :attr:`TodoState.TODO` (open) or
            :attr:`TodoState.DONE` (completed).
            Serialized as ``'todo-state'``.
        text: The item text, marker-free.
    """

    vertex_type: Literal[VertexType.TODO] = Field(
        default=VertexType.TODO,
        serialization_alias="vertex-type",
        description="Always VertexType.TODO (serialized as 'vertex-type').",
    )
    todo_state: TodoState = Field(
        ...,
        serialization_alias="todo-state",
        description="The item's state: open (TODO) or completed (DONE).",
    )
    text: str = Field(..., description="The item text, marker-free.")


class AssetVertex[VT: VertexType = Literal[VertexType.ASSET]](_BaseVertex[VT]):
    """A hosted asset — the general asset vertex and the shared base of the asset vertex types.

    Every asset vertex's content is a hosted file rather than inline text, described by
    the same three facts: where the binary lives (:attr:`storage`), what kind of content
    it is (:attr:`media_type`), and what the file is called (:attr:`file_name`).
    :class:`ImageVertex` and :class:`PdfVertex` subclass this type, adding what their
    specific kinds know.  Used directly — unparameterized — it is the vertex of a hosted
    asset of *unspecified* kind: an uploaded file that is neither an image nor a PDF
    component (e.g. an audio file, archive, or pass), with ``vertex_type``
    :attr:`~VertexType.ASSET`.

    Attributes:
        vertex_type: :attr:`~VertexType.ASSET` when the class is used directly; each
            subclass narrows it to its own member.  Serialized as ``'vertex-type'``.
        storage: The :class:`~guffin.model.asset_storage.AssetStorage` holding the
            asset's binary — its location, storing service, and encryption state.
        media_type: IANA media type of the asset, or ``None`` when it cannot be
            determined.  Serialized as ``'media-type'``.
        file_name: The asset's filename, or ``None`` when no name is known.  Never
            derived from the storage location — populated only by an authority that
            actually knows the name (e.g. asset fetching reading upload metadata).
            Serialized as ``'file-name'``.
    """

    # The ASSET default is sound only for the unparameterized class (VT unbound, so the
    # PEP 696 default Literal[VertexType.ASSET] applies); every subclass overrides the
    # field with its own literal and default, which the type system cannot express here.
    vertex_type: VT = Field(  # pyright: ignore[reportAssignmentType]
        default=VertexType.ASSET,
        serialization_alias="vertex-type",
        description="VertexType.ASSET when the class is used directly (serialized as 'vertex-type').",
    )
    storage: AssetStorage = Field(
        ..., description="The storage holding the asset's binary: location, service, and encryption state."
    )
    media_type: MediaType | None = Field(
        default=None,
        serialization_alias="media-type",
        description="IANA media type of the asset. None when undeterminable (serialized as 'media-type').",
    )
    file_name: str | None = Field(
        default=None,
        serialization_alias="file-name",
        description="The asset's filename. None when no name is known (serialized as 'file-name').",
    )


class ImageVertex(AssetVertex[Literal[VertexType.IMAGE]]):
    """A hosted image asset displayed in the document.

    Attributes:
        vertex_type: Always :attr:`~VertexType.IMAGE`.
            Serialized as ``'vertex-type'``.
        media_type: IANA media type of the image — always known for an image, and
            always an image MIME type (enforced at construction).
            Serialized as ``'media-type'``.
        alt_text: The image's alt text, stripped of leading/trailing whitespace.
            ``None`` when the alt text is absent or empty.
            Serialized as ``'alt-text'``.
        scaled_image_size: Display pixel dimensions recorded by the source (an authored
            resize). Both axes are ``None`` when no display size is recorded.
            Serialized as ``'image-size'``.
        original_image_size: Native pixel dimensions of the image file before any
            display scaling is applied. ``None`` when the original size is unknown.
            Serialized as ``'original-image-size'``.
    """

    vertex_type: Literal[VertexType.IMAGE] = Field(
        default=VertexType.IMAGE,
        serialization_alias="vertex-type",
        description="Always VertexType.IMAGE (serialized as 'vertex-type').",
    )
    alt_text: str | None = Field(
        default=None,
        serialization_alias="alt-text",
        description="The image's alt text, stripped. None when absent or empty.",
    )
    scaled_image_size: ImageSize = Field(
        ...,
        serialization_alias="image-size",
        description="Display pixel dimensions recorded by the source (serialized as 'image-size').",
    )
    original_image_size: ImageSize | None = Field(
        default=None,
        serialization_alias="original-image-size",
        description="Native dimensions before display scaling. None when unknown "
        "(serialized as 'original-image-size').",
    )

    @field_validator("media_type")
    @classmethod
    def media_type_must_be_image(cls, val: MediaType | None) -> MediaType:
        """Require a present, image-kind media type.

        Args:
            val: The candidate media type value.

        Returns:
            *val* unchanged when it is an image MIME type.

        Raises:
            ValueError: If *val* is ``None`` or a non-image
                :class:`~guffin.common.media_type.MediaType`.
        """
        if val is None or not is_image_type(val):
            raise ValueError(f"media_type must be an image MIME type; got {val!r}")
        return val


class PdfVertex(AssetVertex[Literal[VertexType.PDF]]):
    """A hosted PDF asset displayed in the document.

    Attributes:
        vertex_type: Always :attr:`~VertexType.PDF`.
            Serialized as ``'vertex-type'``.
        file_name: The filename the PDF was originally uploaded under. ``None``
            when unknown (populated by asset fetching, which reads it from the asset
            metadata rather than the storage location).
            Serialized as ``'file-name'``.
    """

    vertex_type: Literal[VertexType.PDF] = Field(
        default=VertexType.PDF,
        serialization_alias="vertex-type",
        description="Always VertexType.PDF (serialized as 'vertex-type').",
    )


class CalloutVertex(_BaseVertex[Literal[VertexType.CALLOUT]]):
    """A callout (admonition) — a categorised aside with a title and body.

    Attributes:
        vertex_type: Always :attr:`~VertexType.CALLOUT`.
            Serialized as ``'vertex-type'``.
        callout_type: Callout category, one of the recognised :class:`CalloutType` keywords.
            Serialized as ``'callout-type'``.
        title: Callout heading text, marker-free and stripped of leading/trailing whitespace.
        body: Callout body text accumulated from the vertex's children.
    """

    class CalloutType(StrEnum):
        """Callout category keyword — the eleven recognised callout categories.

        Note ``quote`` is deliberately absent: a quote-marked block is a pull quote,
        transcribed to a :class:`QuoteBlockVertex` (see :class:`QuoteType`), not a callout.
        """

        INFO = "info"
        EXAMPLE = "example"
        NOTE = "note"
        WARNING = "warning"
        DANGER = "danger"
        TIP = "tip"
        SUMMARY = "summary"
        SUCCESS = "success"
        QUESTION = "question"
        FAILURE = "failure"
        BUG = "bug"

    vertex_type: Literal[VertexType.CALLOUT] = Field(
        default=VertexType.CALLOUT,
        serialization_alias="vertex-type",
        description="Always VertexType.CALLOUT (serialized as 'vertex-type').",
    )
    callout_type: CalloutType = Field(
        ...,
        serialization_alias="callout-type",
        description="Callout category keyword (serialized as 'callout-type').",
    )
    title: str = Field(..., description="Callout heading text, marker-free.")
    body: str = Field(..., description="Callout body text accumulated from the vertex's children.")


class CodeBlockVertex(_BaseVertex[Literal[VertexType.CODE_BLOCK]]):
    """A fenced code listing.

    Attributes:
        vertex_type: Always :attr:`~VertexType.CODE_BLOCK`.
            Serialized as ``'vertex-type'``.
        code: Code content of the fenced block — the lines between the fences.
        language: Programming language of the code block, as a canonical language id
            (:data:`~guffin.common.programming_language.CodeLanguageId`).
        code_source: The GitHub source reference the code was snapshotted from
            (:class:`~guffin.model.code_source.CodeSource`), or ``None`` when the content has
            no recorded provenance.  Serialized as ``'code-source'``.
    """

    vertex_type: Literal[VertexType.CODE_BLOCK] = Field(
        default=VertexType.CODE_BLOCK,
        serialization_alias="vertex-type",
        description="Always VertexType.CODE_BLOCK (serialized as 'vertex-type').",
    )
    code: str = Field(..., description="Code content of the fenced block (the lines between the fences).")
    language: CodeLanguageId = Field(
        ..., description="Programming language of the fenced code block, as a canonical language id."
    )
    code_source: CodeSource | None = Field(
        default=None,
        serialization_alias="code-source",
        description="GitHub source reference the code was snapshotted from; None when unsourced "
        "(serialized as 'code-source').",
    )


class QuoteType(StrEnum):
    """How a quote block is presented — the source-agnostic rendering intent.

    Attributes:
        BLOCK: A plain block quote, rendered with the conventional left rule.
        PULL: A pull quote, rendered with the decorated treatment — an oversize
            opening quotation mark, a bold quotation, and an optional italic
            attribution.
    """

    BLOCK = "block"
    PULL = "pull"


class QuoteBlockVertex(_BaseVertex[Literal[VertexType.QUOTE_BLOCK]]):
    """A quotation — a plain block quote or a decorated pull quote.

    :attr:`quote_type` records which presentation applies; the source's quote
    markers are translated away at transcription.

    Attributes:
        vertex_type: Always :attr:`~VertexType.QUOTE_BLOCK`.
            Serialized as ``'vertex-type'``.
        quote_type: :attr:`QuoteType.BLOCK` for a plain block quote, :attr:`QuoteType.PULL` for a
            pull quote (the decorated treatment).
        quote: The quotation text, marker-free.
        attribution: The attribution text — a pull quote's body lines after the first — or ``None``;
            always ``None`` for a plain block quote.
    """

    vertex_type: Literal[VertexType.QUOTE_BLOCK] = Field(
        default=VertexType.QUOTE_BLOCK,
        serialization_alias="vertex-type",
        description="Always VertexType.QUOTE_BLOCK (serialized as 'vertex-type').",
    )
    quote_type: QuoteType = Field(
        default=QuoteType.BLOCK,
        description="Whether this is a plain block quote (BLOCK) or a pull quote (PULL).",
    )
    quote: str = Field(..., description="The quotation text, marker-free.")
    attribution: str | None = Field(
        default=None,
        description="The attribution text (pull quotes only), or None.",
    )


class TableVertex(_BaseVertex[Literal[VertexType.TABLE]]):
    """A table — a cell grid plus its styling overlay.

    The grid is reconstructed at transcription from the source's table structure
    (rows and cells carried as the table's child subtree).

    Attributes:
        vertex_type: Always :attr:`~VertexType.TABLE`.
            Serialized as ``'vertex-type'``.
        table: Data model for the table grid, row/column header flags, and cell content.
        table_style: View/styling overlay for the table.
    """

    vertex_type: Literal[VertexType.TABLE] = Field(
        default=VertexType.TABLE,
        serialization_alias="vertex-type",
        description="Always VertexType.TABLE (serialized as 'vertex-type').",
    )
    table: Table = Field(..., description="Data model for the table grid and cell content.")
    table_style: TableStyle = Field(..., description="View/styling overlay for the table.")


class _BaseEmbedVertex[VT: VertexType](_BaseVertex[VT]):
    """Shared shape of the transcluding (embed) vertex types.

    Not instantiated directly — use :class:`BlockEmbedVertex` or :class:`PageEmbedVertex`.
    An embed vertex carries no content of its own; its content is the target of its
    :attr:`vertex_link`, reproduced (transcluded) at the embed site.

    Attributes:
        vertex_link: Link to the embedded (transcluded) vertex; its
            :attr:`~guffin.model.vertex_link.VertexLink.kind` is always
            :attr:`~guffin.model.vertex_link.VertexLinkKind.EMBED`.
    """

    vertex_link: VertexLink = Field(..., description="Embed link to the transcluded vertex (kind is always EMBED).")

    @field_validator("vertex_link")
    @classmethod
    def _validate_embed_kind(cls, value: VertexLink) -> VertexLink:
        if value.kind is not VertexLinkKind.EMBED:
            raise ValueError(f"vertex_link.kind must be VertexLinkKind.EMBED; got {value.kind!r}")
        return value


class BlockEmbedVertex(_BaseEmbedVertex[Literal[VertexType.BLOCK_EMBED]]):
    """A transclusion of another block at this position.

    Attributes:
        vertex_type: Always :attr:`~VertexType.BLOCK_EMBED`.
            Serialized as ``'vertex-type'``.
    """

    vertex_type: Literal[VertexType.BLOCK_EMBED] = Field(
        default=VertexType.BLOCK_EMBED,
        serialization_alias="vertex-type",
        description="Always VertexType.BLOCK_EMBED (serialized as 'vertex-type').",
    )


class PageEmbedVertex(_BaseEmbedVertex[Literal[VertexType.PAGE_EMBED]]):
    """A transclusion of a whole page at this position.

    A source's title-form page embed is resolved to the page's UID at
    transcription, so :attr:`~_BaseEmbedVertex.vertex_link` targets the page
    vertex directly.

    Attributes:
        vertex_type: Always :attr:`~VertexType.PAGE_EMBED`.
            Serialized as ``'vertex-type'``.
    """

    vertex_type: Literal[VertexType.PAGE_EMBED] = Field(
        default=VertexType.PAGE_EMBED,
        serialization_alias="vertex-type",
        description="Always VertexType.PAGE_EMBED (serialized as 'vertex-type').",
    )


type Vertex = (
    PageVertex
    | HeadingVertex
    | TextVertex
    | TodoVertex
    | ImageVertex
    | PdfVertex
    | CalloutVertex
    | CodeBlockVertex
    | QuoteBlockVertex
    | TableVertex
    | BlockEmbedVertex
    | PageEmbedVertex
)
"""Union of the twelve concrete, normalized vertex types transcription currently produces.

:class:`AssetVertex` is deliberately not yet a member: a bare-asset block still
transcribes as :class:`TextVertex` while the asset rendering design is settled, so
admitting the type here would declare a vertex nothing yet produces or consumes.

Use :data:`vertex_adapter` to validate a raw dict into the appropriate concrete
subtype.  Use :class:`~guffin.model.vertex_tree.VertexTree` to hold a validated collection of vertices.
"""

type AssetBearingVertex = ImageVertex | PdfVertex
"""Union of the asset vertex types the asset pipeline fetches and enriches.

Each member's content is a hosted file, located by its ``storage``, that the
pipeline downloads and treats specially — an image is reproduced in the output,
a PDF is placed per its ``pdf-render`` resolution.  The unparameterized
:class:`AssetVertex` (an asset of unspecified kind) is deliberately not a member:
it is never fetched.  Use :func:`is_asset_bearing_vertex` to classify (and
statically narrow) a :data:`Vertex`.

This union is the single source of truth for pipeline membership; the runtime
classification is derived mechanically from it.
"""

_ASSET_BEARING_VERTEX_CLASSES: Final[tuple[type[ImageVertex] | type[PdfVertex], ...]] = get_args(
    AssetBearingVertex.__value__
)
"""The :data:`AssetBearingVertex` union members as a runtime tuple, derived from the union itself."""

type EmbedVertex = BlockEmbedVertex | PageEmbedVertex
"""Union of the transcluding (embed) vertex types.

An embed vertex carries no content of its own: it holds an EMBED-kind
:class:`~guffin.model.vertex_link.VertexLink` whose target vertex — a block for
:class:`BlockEmbedVertex`, a page for :class:`PageEmbedVertex` — is reproduced
(transcluded) at the embed site.  Use :func:`is_embed_vertex` to classify (and
statically narrow) a :data:`Vertex`.

This union is the single source of truth for embed-ness; the runtime
classification is derived mechanically from it.
"""

_EMBED_VERTEX_CLASSES: Final[tuple[type[BlockEmbedVertex] | type[PageEmbedVertex], ...]] = get_args(
    EmbedVertex.__value__
)
"""The :data:`EmbedVertex` union members as a runtime tuple, derived from the union itself."""

vertex_adapter: TypeAdapter[Vertex] = TypeAdapter(Annotated[Vertex, Field(discriminator="vertex_type")])
"""Pydantic :class:`~pydantic.TypeAdapter` for validating a raw dict into the correct :data:`Vertex` subtype.

Uses ``vertex_type`` as the discriminator field to select among :class:`PageVertex`,
:class:`HeadingVertex`, :class:`TextVertex`, :class:`TodoVertex`, :class:`ImageVertex`,
:class:`PdfVertex`, :class:`CalloutVertex`, :class:`CodeBlockVertex`, :class:`QuoteBlockVertex`,
:class:`TableVertex`, :class:`BlockEmbedVertex`, and :class:`PageEmbedVertex`.

Example::

    v = vertex_adapter.validate_python({"vertex_type": "guffin/page", "uid": "abc", "text": "My Page"})
    assert isinstance(v, PageVertex)
"""


@validate_call
def is_asset_bearing_vertex(vertex: Vertex) -> TypeIs[AssetBearingVertex]:
    """Whether *vertex* is asset-bearing.

    Being asset-bearing is an inherent property of the vertex type: the
    vertex's content is a Firebase Storage-hosted file rather than inline
    text.  Membership is declared solely by the :data:`AssetBearingVertex` union;
    the check runs against the runtime tuple derived from it.

    Args:
        vertex: The vertex to classify.

    Returns:
        ``True`` when *vertex* is one of the :data:`AssetBearingVertex` member
        types, narrowing it to :data:`AssetBearingVertex`.
    """
    return isinstance(vertex, _ASSET_BEARING_VERTEX_CLASSES)


@validate_call
def is_embed_vertex(vertex: Vertex) -> TypeIs[EmbedVertex]:
    """Whether *vertex* is transcluding.

    Being transcluding is an inherent property of the vertex type: the vertex's
    content is the target of its EMBED-kind link, reproduced at the embed site,
    rather than anything the vertex carries itself.  Membership is declared
    solely by the :data:`EmbedVertex` union; the check runs against the runtime
    tuple derived from it.

    Args:
        vertex: The vertex to classify.

    Returns:
        ``True`` when *vertex* is one of the :data:`EmbedVertex` member types,
        narrowing it to :data:`EmbedVertex`.
    """
    return isinstance(vertex, _EMBED_VERTEX_CLASSES)


@validate_call
def find_attribute_assignment(vertex: Vertex, attribute: Attribute) -> AttributeAssignment | None:
    """Return *vertex*'s attribute assignment for *attribute*, or ``None``.

    Convenience over :func:`~guffin.model.attribute_assignment.find_assignment_for` that searches the
    vertex's folded attribute assignments (matching by attribute identity: name + domain).

    Args:
        vertex: The vertex whose folded attribute assignments are searched.
        attribute: The attribute to match.

    Returns:
        The first matching :class:`~guffin.model.attribute_assignment.AttributeAssignment`, or ``None`` when
        *vertex* has no assignment for *attribute*.
    """
    return find_assignment_for(vertex.attribute_assignments, attribute)
