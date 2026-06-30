"""Roam Research normalized graph vertex types.

A :data:`Vertex` is the normalized (transcribed) form of a single
:class:`~guffin.roam.node.RoamNode`.

Normalization (transcription) means:

- Datomic-internal numeric entity ids (:attr:`~guffin.roam.node.RoamNode.id`) are
  eliminated.
- Raw :class:`~guffin.roam.primitives.IdObject` stubs in ``children`` and ``refs`` are
  resolved to stable ``:block/uid`` strings.
- The raw ``string`` / ``title`` field distinction is collapsed into a single ``text``
  field.
- Each node is classified into a :class:`VertexType`.
- The result is self-contained and portable — no Datomic dependencies remain.

Normalization is performed by :func:`~guffin.transcribe.roam_tree_to_guffin.transcribe` (for a full
:class:`~guffin.roam.node_tree.NodeTree`) or
:func:`~guffin.transcribe.roam_tree_to_guffin.transcribe_standalone_node` (for a single
:class:`~guffin.roam.node.RoamNode`).

Public symbols:

- :data:`VertexChildren` — normalized form of
  :attr:`~guffin.roam.node.RoamNode.children`: ordered child UIDs.
- :data:`VertexRefs` — normalized form of :attr:`~guffin.roam.node.RoamNode.refs`:
  referenced UIDs.
- :class:`VertexType` — string enum classifying each vertex by the shape of its source
  :class:`~guffin.roam.node.RoamNode`.
- :class:`PageVertex` — normalized (transcribed) form of a Roam Page node.
- :class:`HeadingVertex` — normalized (transcribed) form of a Roam Heading block node.
- :class:`TextVertex` — normalized (transcribed) form of a plain-text Roam Block
  node.
- :class:`ImageVertex` — normalized (transcribed) form of a Roam Firestore image block
  node.
- :class:`CalloutVertex` — normalized (transcribed) form of a Roam callout block node.
- :class:`CodeBlockVertex` — normalized (transcribed) form of a Roam fenced code block
  node.
- :class:`BlockQuoteVertex` — normalized (transcribed) form of a Roam block-quote block node.
- :class:`TableVertex` — normalized (transcribed) form of a Roam native table node.
- :class:`BlockEmbedVertex` — normalized (transcribed) form of a Roam block embed node.
- :data:`Vertex` — union of all nine concrete vertex types.
- :data:`vertex_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for validating a
  :data:`Vertex` from a raw dict.
- :func:`find_attribute_assignment` — find a vertex's folded attribute assignment by name and domain.
- :func:`find_guffin_attribute` — find a vertex's :class:`~guffin.model.attribute.GuffinAttribute`
  assignment (the Guffin domain is supplied automatically).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator, validate_call

from guffin.common.code_language import CodeLanguage
from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType, is_image_type
from guffin.common.table import Table, TableStyle
from guffin.common.markdown import HeadingLevel
from guffin.model.attribute import AttributeAssignment, GuffinAttribute
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.primitives import Uid

type VertexChildren = list[Uid]
"""Normalized form of :attr:`~guffin.roam.node.RoamNode.children`.

Raw :class:`~guffin.roam.primitives.IdObject` stubs are resolved to stable ``:block/uid``
strings and sorted by ``:block/order`` during transcription.
"""

type VertexRefs = list[Uid]
"""Normalized form of :attr:`~guffin.roam.node.RoamNode.refs`.

Raw :class:`~guffin.roam.primitives.IdObject` stubs are resolved to stable ``:block/uid``
strings during transcription.
"""


class VertexType(StrEnum):
    """Classification assigned to each vertex during transcription.

    Every :class:`~guffin.roam.node.RoamNode` is classified into exactly one
    ``VertexType`` based on the shape of its raw fields.  The values are
    string-valued so they serialize cleanly to/from JSON without extra conversion.

    Values:
        PAGE: Normalized form of a Roam *Page* node — ``:node/title`` is
            present; ``:block/string`` is absent.
        TEXT: Normalized form of a Roam *Block* node that has no
            ``heading`` property — i.e. normal body text.
        HEADING: Normalized form of a Roam *Block* node that carries a
            ``heading`` property (value 1, 2, or 3).
        IMAGE: Normalized form of a Roam *Block* node whose
            ``:block/string`` embeds a Cloud Firestore URL pointing to a
            Roam-managed image upload.
        CALLOUT: Normalized form of a Roam *Block* node whose
            ``:block/string`` starts with ``[[>]] [[!<TYPE>]]`` — a Roam callout marker.
        CODE_BLOCK: Normalized form of a Roam *Block* node whose
            ``:block/string`` is a CommonMark fenced code block.
        BLOCK_QUOTE: Normalized form of a Roam *Block* node whose
            ``:block/string`` is a standard Markdown block quote (``> text``) or a
            Roam-specific block quote (``[[>]] text``).
        TABLE: Normalized form of a Roam native table node — a block whose
            ``:block/string`` equals ``{{table}}``, with its child blocks forming the
            rows and each child's children forming the cells.
        BLOCK_EMBED: Normalized form of a Roam *Block* node whose
            ``:block/string`` is wholly a block embed (``{{embed: ((<uid>))}}``),
            transcluding the referenced block.
    """

    PAGE = "guffin/page"
    TEXT = "guffin/text"
    HEADING = "guffin/heading"
    IMAGE = "guffin/image"
    CALLOUT = "guffin/callout"
    CODE_BLOCK = "guffin/code-block"
    BLOCK_QUOTE = "guffin/block-quote"
    TABLE = "guffin/table"
    BLOCK_EMBED = "guffin/block-embed"


class _BaseVertex[VT: VertexType](BaseModel):
    """Shared fields inherited by all nine concrete vertex types.

    Not instantiated directly — use :class:`PageVertex`, :class:`HeadingVertex`,
    :class:`TextVertex`, :class:`ImageVertex`, :class:`CalloutVertex`,
    :class:`CodeBlockVertex`, :class:`BlockQuoteVertex`, :class:`TableVertex`, or
    :class:`BlockEmbedVertex`.

    Type Parameters:
        VT: The :class:`VertexType` literal for the concrete subtype (e.g.
            ``Literal[VertexType.PAGE]``).

    Attributes:
        vertex_type: Discriminator field identifying the concrete subtype.
            Narrowed to a :class:`~typing.Literal` in each subclass.
        uid: Nine-character stable ``:block/uid`` identifier. Required.
        children: Ordered child UIDs resolved from raw
            :class:`~guffin.roam.primitives.IdObject` stubs. ``None`` when the
            source node has no children.
        refs: Referenced UIDs resolved from raw
            :class:`~guffin.roam.primitives.IdObject` stubs. ``None`` when the
            source node has no refs.
        attribute_assignments: Roam attribute assignments (``<attribute>:: <value>, …``)
            declared directly on this vertex, in source order. Sourced during
            transcription from the node's attribute-block children, which are folded into
            this field rather than transcribed as separate vertices. ``None`` when the
            source node has no attribute-block children.
            Serialized as ``'attribute-assignments'``.
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    vertex_type: VT
    uid: Uid = Field(..., description="Nine-character stable block/page identifier.")
    children: VertexChildren | None = Field(
        default=None, description="Ordered child UIDs resolved from raw IdObject stubs."
    )
    refs: VertexRefs | None = Field(default=None, description="Referenced UIDs resolved from raw IdObject stubs.")
    attribute_assignments: list[AttributeAssignment] | None = Field(
        default=None,
        serialization_alias="attribute-assignments",
        description="Roam attribute assignments declared on this vertex (from its attribute-block children).",
    )


class PageVertex(_BaseVertex[Literal[VertexType.PAGE]]):
    """Normalized (transcribed) form of a Roam Page node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has
    ``:node/title`` set (i.e. ``node.title is not None``).  The ``title`` field
    is collapsed into :attr:`text`.

    Attributes:
        vertex_type: Always :attr:`~VertexType.PAGE`.
            Serialized as ``'vertex-type'``.
        title: Page title from the source node's ``title`` field.
    """

    vertex_type: Literal[VertexType.PAGE] = Field(
        default=VertexType.PAGE,
        serialization_alias="vertex-type",
        description="Always VertexType.PAGE (serialized as 'vertex-type').",
    )
    title: str = Field(..., description="Page title from the source node's title field.")


class HeadingVertex(_BaseVertex[Literal[VertexType.HEADING]]):
    """Normalized (transcribed) form of a Roam Heading block node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has an
    effective heading level — either a native ``heading`` value (1–3) or an
    Augmented Headings ``props['ah-level']`` value (h4–h6).

    Attributes:
        vertex_type: Always :attr:`~VertexType.HEADING`.
            Serialized as ``'vertex-type'``.
        text: Block string from the source node's ``string`` field.
        heading_level: Effective heading level in the range 1–6.
    """

    vertex_type: Literal[VertexType.HEADING] = Field(
        default=VertexType.HEADING,
        serialization_alias="vertex-type",
        description="Always VertexType.HEADING (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="Block string from the source node's string field.")
    heading_level: HeadingLevel = Field(..., description="Effective heading level (1–6).")


class TextVertex(_BaseVertex[Literal[VertexType.TEXT]]):
    """Normalized (transcribed) form of a plain-text Roam Block node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has
    ``:block/string`` set with no heading property and no embedded Firestore URL.

    Attributes:
        vertex_type: Always :attr:`~VertexType.TEXT`.
            Serialized as ``'vertex-type'``.
        text: Block string from the source node's ``string`` field.
    """

    vertex_type: Literal[VertexType.TEXT] = Field(
        default=VertexType.TEXT,
        serialization_alias="vertex-type",
        description="Always VertexType.TEXT (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="Block string from the source node's string field.")


class ImageVertex(_BaseVertex[Literal[VertexType.IMAGE]]):
    """Normalized (transcribed) form of a Roam Cloud Firestore image block node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has a
    ``:block/string`` that embeds a Cloud Firestore storage URL.

    Attributes:
        vertex_type: Always :attr:`~VertexType.IMAGE`.
            Serialized as ``'vertex-type'``.
        source: Cloud Firestore storage URL for the image file.
        alt_text: Alt text extracted from the Markdown image link
            (``![<alt_text>](<url>)``), stripped of leading/trailing whitespace.
            ``None`` when the alt text is absent or empty.
            Serialized as ``'alt-text'``.
        file_name: Original filename decoded from *source*. ``None`` if the
            filename cannot be extracted.
        media_type: IANA media type inferred from *file_name*'s extension.
            Serialized as ``'media-type'``.
        scaled_image_size: Pixel dimensions from the source node's ``image-size`` block
            prop. Both axes are ``None`` when no ``image-size`` prop is recorded.
            Serialized as ``'image-size'``.
        original_image_size: Native pixel dimensions of the image file before any
            Roam scaling is applied. ``None`` when the original size is unknown.
            Serialized as ``'original-image-size'``.
    """

    vertex_type: Literal[VertexType.IMAGE] = Field(
        default=VertexType.IMAGE,
        serialization_alias="vertex-type",
        description="Always VertexType.IMAGE (serialized as 'vertex-type').",
    )
    source: HttpUrl = Field(..., description="Cloud Firestore storage URL for the image file.")
    alt_text: str | None = Field(
        default=None,
        serialization_alias="alt-text",
        description="Alt text from the Markdown image link, stripped. None when absent or empty.",
    )
    file_name: str | None = Field(default=None, description="Original filename decoded from source.")
    media_type: MediaType = Field(
        ...,
        serialization_alias="media-type",
        description="IANA media type inferred from file_name's extension (serialized as 'media-type').",
    )
    scaled_image_size: ImageSize = Field(
        ...,
        serialization_alias="image-size",
        description="Pixel dimensions from the node's image-size prop (serialized as 'image-size').",
    )
    original_image_size: ImageSize | None = Field(
        default=None,
        serialization_alias="original-image-size",
        description="Native dimensions before Roam scaling. None when unknown (serialized as 'original-image-size').",
    )

    @field_validator("media_type")
    @classmethod
    def media_type_must_be_image(cls, val: MediaType) -> MediaType:
        """Reject any non-image MediaType.

        Args:
            val: The candidate media type value.

        Returns:
            *val* unchanged when it is an image MIME type.

        Raises:
            ValueError: If *val* is a non-image :class:`~guffin.common.media_type.MediaType`.
        """
        if not is_image_type(val):
            raise ValueError(f"media_type must be an image MIME type; got {val!r}")
        return val


class CalloutVertex(_BaseVertex[Literal[VertexType.CALLOUT]]):
    """Normalized (transcribed) form of a Roam callout block node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has a
    ``:block/string`` that starts with ``[[>]] [[!<TYPE>]]`` — a Roam callout marker.

    Attributes:
        vertex_type: Always :attr:`~VertexType.CALLOUT`.
            Serialized as ``'vertex-type'``.
        callout_type: Callout category, one of the twelve recognised callout type keywords.
            Serialized as ``'callout-type'``.
        title: Callout heading text — the remainder of the first block string after the
            ``[[>]] [[!<TYPE>]]`` marker, stripped of leading/trailing whitespace.
        body: Callout body text accumulated from the block's child nodes.
    """

    class CalloutType(StrEnum):
        """Callout category keyword, matching the twelve types in the Roam callout marker."""

        INFO = "info"
        QUOTE = "quote"
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
    title: str = Field(..., description="Callout heading text, stripped of the leading marker.")
    body: str = Field(..., description="Callout body text accumulated from child nodes.")


class CodeBlockVertex(_BaseVertex[Literal[VertexType.CODE_BLOCK]]):
    """Normalized (transcribed) form of a Roam fenced code block node.

    Corresponds to a source :class:`~guffin.roam.node.RoamNode` classified as
    :attr:`~guffin.roam.node.NodeType.CODE_BLOCK` — its ``:block/string`` is
    a CommonMark fenced code block.

    Attributes:
        vertex_type: Always :attr:`~VertexType.CODE_BLOCK`.
            Serialized as ``'vertex-type'``.
        code: Code content of the fenced block — the lines between the fences.
        language: Programming language of the code block
            (:class:`~guffin.common.code_language.CodeLanguage`).
    """

    vertex_type: Literal[VertexType.CODE_BLOCK] = Field(
        default=VertexType.CODE_BLOCK,
        serialization_alias="vertex-type",
        description="Always VertexType.CODE_BLOCK (serialized as 'vertex-type').",
    )
    code: str = Field(..., description="Code content of the fenced block (the lines between the fences).")
    language: CodeLanguage = Field(..., description="Programming language of the fenced code block.")


class BlockQuoteVertex(_BaseVertex[Literal[VertexType.BLOCK_QUOTE]]):
    """Normalized (transcribed) form of a Roam block-quote node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has a
    ``:block/string`` that is a standard Markdown block quote (``> text``) or a
    Roam-specific block quote (``[[>]] text``).

    Attributes:
        vertex_type: Always :attr:`~VertexType.BLOCK_QUOTE`.
            Serialized as ``'vertex-type'``.
        text: Block string with the leading block-quote marker stripped.
    """

    vertex_type: Literal[VertexType.BLOCK_QUOTE] = Field(
        default=VertexType.BLOCK_QUOTE,
        serialization_alias="vertex-type",
        description="Always VertexType.BLOCK_QUOTE (serialized as 'vertex-type').",
    )
    text: str = Field(..., description="Block string with the leading block-quote marker stripped.")


class TableVertex(_BaseVertex[Literal[VertexType.TABLE]]):
    """Normalized (transcribed) form of a Roam native table node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has a
    ``:block/string`` equal to ``{{table}}``, with its child blocks forming the
    rows and each child's children forming the cells.

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


class BlockEmbedVertex(_BaseVertex[Literal[VertexType.BLOCK_EMBED]]):
    """Normalized (transcribed) form of a Roam block embed node.

    Produced when the source :class:`~guffin.roam.node.RoamNode` has a
    ``:block/string`` that is wholly a block embed (``{{embed: ((<uid>))}}``),
    transcluding the referenced block.

    Attributes:
        vertex_type: Always :attr:`~VertexType.BLOCK_EMBED`.
            Serialized as ``'vertex-type'``.
        vertex_link: Link to the embedded (transcluded) vertex; its
            :attr:`~guffin.model.link.VertexLink.kind` is always
            :attr:`~guffin.model.link.VertexLinkKind.EMBED`.
    """

    vertex_type: Literal[VertexType.BLOCK_EMBED] = Field(
        default=VertexType.BLOCK_EMBED,
        serialization_alias="vertex-type",
        description="Always VertexType.BLOCK_EMBED (serialized as 'vertex-type').",
    )
    vertex_link: VertexLink = Field(..., description="Embed link to the transcluded vertex (kind is always EMBED).")

    @field_validator("vertex_link")
    @classmethod
    def _validate_embed_kind(cls, value: VertexLink) -> VertexLink:
        if value.kind is not VertexLinkKind.EMBED:
            raise ValueError(f"vertex_link.kind must be VertexLinkKind.EMBED; got {value.kind!r}")
        return value


type Vertex = (
    PageVertex
    | HeadingVertex
    | TextVertex
    | ImageVertex
    | CalloutVertex
    | CodeBlockVertex
    | BlockQuoteVertex
    | TableVertex
    | BlockEmbedVertex
)
"""Union of all nine concrete, normalized vertex types.

Use :data:`vertex_adapter` to validate a raw dict into the appropriate concrete
subtype.  Use :class:`~guffin.model.vertex_tree.VertexTree` to hold a validated collection of vertices.
"""

vertex_adapter: TypeAdapter[Vertex] = TypeAdapter(Annotated[Vertex, Field(discriminator="vertex_type")])
"""Pydantic :class:`~pydantic.TypeAdapter` for validating a raw dict into the correct :data:`Vertex` subtype.

Uses ``vertex_type`` as the discriminator field to select among :class:`PageVertex`,
:class:`HeadingVertex`, :class:`TextVertex`, :class:`ImageVertex`, :class:`CalloutVertex`,
:class:`CodeBlockVertex`, :class:`BlockQuoteVertex`, :class:`TableVertex`, and :class:`BlockEmbedVertex`.

Example::

    v = vertex_adapter.validate_python({"vertex_type": "guffin/page", "uid": "abc", "text": "My Page"})
    assert isinstance(v, PageVertex)
"""


@validate_call
def find_attribute_assignment(vertex: Vertex, attribute_name: str, attribute_domain: str) -> AttributeAssignment | None:
    """Return *vertex*'s attribute assignment named *attribute_name* in *attribute_domain*, or ``None``.

    Args:
        vertex: The vertex whose folded attribute assignments are searched.
        attribute_name: The attribute name to match (the page named before ``::``).
        attribute_domain: The domain the matched attribute must belong to.

    Returns:
        The first matching :class:`~guffin.model.attribute.AttributeAssignment`, or ``None`` when
        *vertex* has no attribute named *attribute_name* in *attribute_domain*.
    """
    for assignment in vertex.attribute_assignments or ():
        if assignment.attribute.name == attribute_name and assignment.attribute.domain == attribute_domain:
            return assignment
    return None


@validate_call
def find_guffin_attribute(vertex: Vertex, attribute: GuffinAttribute) -> AttributeAssignment | None:
    """Return *vertex*'s assignment for the Guffin *attribute*, or ``None``.

    Convenience over :func:`find_attribute_assignment` that supplies
    :attr:`~guffin.model.attribute.GuffinAttribute.DOMAIN` as the domain, so callers neither restate
    nor risk mismatching it.

    Args:
        vertex: The vertex whose folded attribute assignments are searched.
        attribute: The Guffin attribute to look up.

    Returns:
        The matching :class:`~guffin.model.attribute.AttributeAssignment`, or ``None`` when *vertex*
        has no such Guffin attribute.
    """
    return find_attribute_assignment(vertex, attribute, GuffinAttribute.DOMAIN)
