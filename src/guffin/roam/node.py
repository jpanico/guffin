"""Roam Research raw node data model.

Public symbols:

- :class:`NodeType` — ``StrEnum`` of pull-block entity types: ``PAGE``, ``PLAIN_BLOCK``,
  ``IMAGE_BLOCK``, ``HEADING_BLOCK``, ``CALLOUT_BLOCK``,
  ``CODE_BLOCK``, ``BLOCK_QUOTE``, ``NATIVE_TABLE``, ``EMBED_BLOCK``.
- :class:`RoamNode` — raw shape of a pull-block as returned by the Roam Local API.
- :func:`node_type` — return the :class:`NodeType` of a :class:`RoamNode`.
- :func:`effective_heading_level` — return the effective heading level for a
  :class:`RoamNode`, or ``None`` if it is not a heading.
- :func:`effective_children_view_type` — return a :class:`RoamNode`'s children view type,
  falling back to :data:`DEFAULT_CHILDREN_VIEW_TYPE` when unset.
- :func:`image_size` — return the :class:`~guffin.common.geometry.ImageSize` recorded in
  a :attr:`NodeType.IMAGE_BLOCK` node's ``image-size`` prop, or ``None`` if the node
  is not an image block.
- :data:`NodesByUid` — ``dict`` mapping each :attr:`~RoamNode.uid` to its :class:`RoamNode`.
- :data:`DEFAULT_CHILDREN_VIEW_TYPE` — fallback :class:`~guffin.roam.primitives.ChildrenViewType`
  for a block whose ``children_view_type`` is unset.
"""

import enum
import logging
from typing import Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
    validate_call,
)

from guffin.common.geometry import ImageSize
from guffin.common.markdown import HeadingLevel, is_fenced_code_block
from guffin.roam.markdown import (
    BLOCK_EMBED_RE,
    CALLOUT_RE,
    IMAGE_LINK_RE,
    ROAM_NATIVE_TABLE_MARKER,
    is_roam_block_quote,
)
from guffin.roam.primitives import (
    ChildrenViewType,
    Id,
    IdObject,
    LinkObject,
    Order,
    PageTitle,
    RawChildren,
    RawRefs,
    Uid,
)
from guffin.roam.schema import SchemaAttribute

logger = logging.getLogger(__name__)

DEFAULT_CHILDREN_VIEW_TYPE: Final[ChildrenViewType] = ChildrenViewType.BULLET
"""Fallback :class:`~guffin.roam.primitives.ChildrenViewType` for an unset ``children_view_type``."""

_IMAGE_SIZE_PROP_ADAPTER: Final[TypeAdapter[dict[str, dict[str, int | None]]]] = TypeAdapter(
    dict[str, dict[str, int | None]]
)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating the ``image-size`` block prop.

The ``image-size`` prop maps an image URL string to a ``{"width": int|None, "height": int|None}``
dict.  Used by :func:`image_size` to extract dimensions without Unknown-type propagation.
"""


class NodeType(enum.StrEnum):
    """Entity type of a Roam pull-block.

    - **PAGE**: ``title`` is a string, ``string`` is ``None``.
    - **PLAIN_BLOCK**: ``string`` is set, ``title`` is ``None``, no special Roam properties.
    - **HEADING_BLOCK**: ``heading`` (levels 1–3) or ``props['ah-level']`` (levels 4–6) is set; the entire
      block content is the heading text.
    - **IMAGE_BLOCK**: ``string`` consists solely of a single Markdown image link to a Cloud Firestore URL.
      Produced by drag-and-drop into the Roam UI; supports image-resize properties via ``props``.
    - **CALLOUT_BLOCK**: ``string`` starts with ``[[>]] [[!<TYPE>]]`` where ``<TYPE>`` is one of the twelve
      recognised callout type keywords (``INFO``, ``QUOTE``, ``EXAMPLE``, ``NOTE``, ``WARNING``, ``DANGER``,
      ``TIP``, ``SUMMARY``, ``SUCCESS``, ``QUESTION``, ``FAILURE``, ``BUG``).
    - **CODE_BLOCK**: ``string``, with surrounding whitespace trimmed, is a CommonMark fenced code
      block (opened by a ```` ``` ```` or ``~~~`` fence).
    - **BLOCK_QUOTE**: ``string`` starts with ``[[>]]`` but does *not* match the callout marker
      pattern ``[[>]] [[!<TYPE>]]`` — i.e. a plain ``[[>]]``-prefixed blockquote.
    - **NATIVE_TABLE**: ``string``, with surrounding whitespace trimmed, equals
      :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKER` (``"{{table}}"``); its child blocks
      form the table rows.
    - **EMBED_BLOCK**: ``title`` is ``None`` and ``string``, with surrounding whitespace
      trimmed, is wholly a Roam block embed ``{{embed: ((<uid>))}}`` (matched by
      :data:`~guffin.roam.markdown.BLOCK_EMBED_RE`).
    """

    PAGE = "roam/page"
    PLAIN_BLOCK = "roam/plain-block"
    HEADING_BLOCK = "roam/heading-block"
    IMAGE_BLOCK = "roam/image-block"
    CALLOUT_BLOCK = "roam/callout-block"
    CODE_BLOCK = "roam/code-block"
    BLOCK_QUOTE = "roam/quote-block"
    NATIVE_TABLE = "roam/table"
    EMBED_BLOCK = "roam/embed-block"


class RoamNode(BaseModel):
    """Raw shape of a "pull-block" as returned by ``roamAlphaAPI.data.q`` / ``pull [*]``.

    This is the *un-normalized* form — property names mirror the raw Datomic
    attribute names, and nested refs are still IdObject stubs rather than resolved UIDs.

    Every pull-block is one of two mutually exclusive entity types, discriminated by
    ``title``.  The following invariants are enforced at construction time by
    :meth:`_validate_entity_type`:

    - **Page**: ``title`` set, so ``string`` and ``page`` are ``None``.
    - **Block**: ``title`` ``None``, so ``string`` and ``page`` are set.

    All remaining fields (``parents``, ``children``, ``heading``, ``open``,
    ``refs``, etc.) are optional and vary by entity type and feature usage.

    Attributes:
        uid: Nine-character stable block/page identifier (BLOCK_UID). Required.
        id: Datomic internal numeric entity id (:db/id). Ephemeral and not stable
            across exports. Required.
        string: Block text content (BLOCK_STRING). Present only on Block entities.
        title: Page title (NODE_TITLE). Present only on Page entities.
        order: Zero-based sibling order (BLOCK_ORDER). Present only on child Blocks.
        heading: HeadingLevel (BLOCK_HEADING). Present only on heading Blocks.
        children: Raw child block stubs (BLOCK_CHILDREN). Present on Blocks and Pages with children.
        refs: Raw page/block reference stubs (BLOCK_REFS).
        page: IdObject stub for the containing page (BLOCK_PAGE). Present only on Blocks.
        open: Whether the block is expanded (BLOCK_OPEN). Present only on Blocks.
        children_view_type: How this block's children are rendered (CHILDREN_VIEW_TYPE). Present
            only on Blocks.
        parents: IdObject stubs for all ancestor blocks (BLOCK_PARENTS). Present only on Blocks.
        props: Block property key-value map (BLOCK_PROPS). Present only on Blocks that have block
            properties set (e.g. ``ah-level`` from the Augmented Headings extension).
        attrs: Structured attribute assertions (ENTITY_ATTRS).
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    uid: Uid = Field(..., description=f"{SchemaAttribute.BLOCK_UID} — stable identifier (synthetic or daily-note)")
    id: Id = Field(..., description=":db/id — Datomic internal entity id (ephemeral)")

    # Block-only fields
    string: str | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_STRING} — block text; present only on Blocks"
    )
    order: Order | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_ORDER} — sibling order; present only on child Blocks"
    )
    heading: HeadingLevel | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_HEADING} — heading level; present only on heading Blocks"
    )
    children: RawChildren | None = Field(
        default=None,
        description=f"{SchemaAttribute.BLOCK_CHILDREN} — raw child stubs; present on Blocks and Pages with children",
    )
    refs: RawRefs | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_REFS} — raw reference stubs; present only on Blocks"
    )
    page: IdObject | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_PAGE} — containing page stub; present only on Blocks"
    )
    open: bool | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_OPEN} — expanded/collapsed state; present only on Blocks"
    )
    children_view_type: ChildrenViewType | None = Field(
        default=None,
        alias="view-type",
        description=f"{SchemaAttribute.CHILDREN_VIEW_TYPE} — how this block's children are rendered",
    )
    parents: list[IdObject] | None = Field(
        default=None, description=f"{SchemaAttribute.BLOCK_PARENTS} — all ancestor stubs; present only on Blocks"
    )
    props: dict[str, object] | None = Field(
        default=None,
        description=(
            f"{SchemaAttribute.BLOCK_PROPS} — block property key-value map; "
            "present only on Blocks that have block properties set (e.g. ``ah-level`` from Augmented Headings)."
        ),
    )

    # Page fields
    title: PageTitle | None = Field(
        default=None,
        description=f"{SchemaAttribute.NODE_TITLE} — page title; present only on Page entities",
    )

    # Sparse / metadata fields
    attrs: list[list[LinkObject]] | None = Field(
        default=None, description=f"{SchemaAttribute.ENTITY_ATTRS} — structured attribute assertions"
    )

    @field_validator("heading", mode="before")
    @classmethod
    def _coerce_zero_heading(cls, val: object) -> object:
        # Roam API *can* return heading=0 for non-heading blocks instead of omitting the field.
        return None if val == 0 else val

    @model_validator(mode="after")
    def _validate_entity_type(self) -> RoamNode:
        """Enforce the Page/Block entity-type invariants.

        A pull-block is exactly one of two entity types, discriminated by ``title``:

        - **Page** — ``title`` is set, so ``string`` and ``page`` are ``None``.
        - **Block** — ``title`` is ``None``, so ``string`` and ``page`` are set.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the instance violates the Page or Block field invariants, or if
                neither ``title`` nor ``string`` is set.
        """
        if self.title is not None:
            page_violations: Final[list[str]] = []
            if self.string is not None:
                page_violations.append(f"string must be None; got {self.string!r}")
            if self.page is not None:
                page_violations.append("page must be None")
            if page_violations:
                raise ValueError(f"Page entity (uid={self.uid!r}) constraint violations: {'; '.join(page_violations)}")
        elif self.string is not None:
            if self.page is None:
                raise ValueError(f"Block entity (uid={self.uid!r}) constraint violations: page must be set")
        else:
            raise ValueError(
                f"RoamNode (uid={self.uid!r}) must be a Page (title set) or a Block (string set); "
                "got title=None, string=None"
            )
        return self


@validate_call
def effective_heading_level(node: RoamNode) -> HeadingLevel | None:
    """Return the effective heading level for *node*, or ``None`` if it is not a heading.

    Checks native heading first (``node.heading``, levels 1–3), then falls back
    to the Augmented Headings extension (``node.props['ah-level']``, levels 4–6).

    Args:
        node: The node to inspect.

    Returns:
        An integer heading level in the range 1–6, or ``None``.
    """
    if node.heading is not None:
        return node.heading
    if node.props is not None:
        ah_level = node.props.get("ah-level")
        if isinstance(ah_level, str) and len(ah_level) == 2 and ah_level[0] == "h":
            try:
                level = int(ah_level[1])
                if 1 <= level <= 6:
                    return level
            except ValueError:
                pass
    return None


@validate_call
def effective_children_view_type(node: RoamNode) -> ChildrenViewType:
    """Return *node*'s children view type, falling back to the default when unset.

    Args:
        node: The node to inspect.

    Returns:
        :attr:`~RoamNode.children_view_type` if set, otherwise
        :data:`DEFAULT_CHILDREN_VIEW_TYPE`.
    """
    if node.children_view_type is None:
        return DEFAULT_CHILDREN_VIEW_TYPE
    return node.children_view_type


@validate_call
def image_size(node: RoamNode) -> ImageSize | None:
    """Return the pixel dimensions recorded in *node*'s ``image-size`` block property.

    Args:
        node: The node to inspect.

    Returns:
        ``None`` if *node* is not a :attr:`~NodeType.IMAGE_BLOCK`.
        An :class:`~guffin.common.geometry.ImageSize` with both dimensions ``None``
        if the node has no ``image-size`` prop or the prop is an empty map.
        Otherwise an :class:`~guffin.common.geometry.ImageSize` populated from the
        first URL entry in the ``image-size`` map.

    Raises:
        ValidationError: If the ``image-size`` prop exists but does not match the
            expected ``{url: {width, height}}`` structure.
    """
    if node_type(node) != NodeType.IMAGE_BLOCK:
        return None
    if node.props is None:
        return ImageSize()
    raw: Final[object | None] = node.props.get("image-size")
    if raw is None:
        return ImageSize()
    size_map: Final[dict[str, dict[str, int | None]]] = _IMAGE_SIZE_PROP_ADAPTER.validate_python(raw)
    first_entry: Final[dict[str, int | None] | None] = next(iter(size_map.values()), None)
    if first_entry is None:
        return ImageSize()
    return ImageSize(
        width=first_entry.get("width"),
        height=first_entry.get("height"),
    )


type NodesByUid = dict[Uid, RoamNode]
"""``dict`` mapping each :attr:`~RoamNode.uid` to its :class:`RoamNode`."""


@validate_call
def node_type(node: RoamNode) -> NodeType:
    """Return the :class:`NodeType` of *node*.

    Discriminates first on :attr:`~RoamNode.title`: returns :attr:`NodeType.PAGE` when
    ``title`` is a non-``None`` string.  For title-less nodes (blocks), returns
    :attr:`NodeType.IMAGE_BLOCK` when ``string`` consists solely of a single Markdown image
    link (as matched by :data:`~guffin.roam.markdown.IMAGE_LINK_RE`),
    :attr:`NodeType.HEADING_BLOCK` when :func:`effective_heading_level` is non-``None``,
    :attr:`NodeType.CALLOUT_BLOCK` when ``string`` matches the full callout marker pattern
    (as matched by :data:`~guffin.roam.markdown.CALLOUT_RE`),
    :attr:`NodeType.BLOCK_QUOTE` when :func:`~guffin.roam.primitives.is_roam_block_quote`
    returns ``True`` for ``string`` — i.e. a Roam ``[[>]]``-prefixed blockquote or a standard
    Markdown ``>``-prefixed blockquote,
    :attr:`NodeType.CODE_BLOCK` when the trimmed ``string`` is a fenced code block
    (as determined by :func:`~guffin.common.markdown.is_fenced_code_block`),
    :attr:`NodeType.NATIVE_TABLE` when the trimmed ``string`` equals
    :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKER`,
    :attr:`NodeType.EMBED_BLOCK` when the trimmed ``string`` is wholly a Roam block embed
    (as matched by :data:`~guffin.roam.markdown.BLOCK_EMBED_RE`),
    and :attr:`NodeType.PLAIN_BLOCK` otherwise.

    Args:
        node: The node whose entity type to determine.

    Returns:
        :attr:`NodeType.PAGE` if ``title`` is set;
        :attr:`NodeType.IMAGE_BLOCK` if ``string`` is solely a single Markdown image link;
        :attr:`NodeType.HEADING_BLOCK` if ``heading`` or ``props['ah-level']`` is set;
        :attr:`NodeType.CALLOUT_BLOCK` if ``string`` matches ``[[>]] [[!<TYPE>]]``;
        :attr:`NodeType.BLOCK_QUOTE` if :func:`~guffin.roam.primitives.is_roam_block_quote` is ``True``;
        :attr:`NodeType.CODE_BLOCK` if the trimmed ``string`` is a CommonMark fenced code block;
        :attr:`NodeType.NATIVE_TABLE` if the trimmed ``string`` equals
        :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKER`;
        :attr:`NodeType.EMBED_BLOCK` if the trimmed ``string`` is wholly a Roam block embed;
        :attr:`NodeType.PLAIN_BLOCK` otherwise.
    """
    if node.title is not None:
        return NodeType.PAGE
    # A title-less pull-block is a Block, so its string is set (enforced by _validate_entity_type).
    assert node.string is not None
    string: Final[str] = node.string
    if IMAGE_LINK_RE.fullmatch(string.strip()):
        return NodeType.IMAGE_BLOCK
    if effective_heading_level(node) is not None:
        return NodeType.HEADING_BLOCK
    if CALLOUT_RE.match(string):
        return NodeType.CALLOUT_BLOCK
    if is_roam_block_quote(string):
        return NodeType.BLOCK_QUOTE
    if is_fenced_code_block(string.strip()):
        return NodeType.CODE_BLOCK
    if string.strip() == ROAM_NATIVE_TABLE_MARKER:
        return NodeType.NATIVE_TABLE
    if BLOCK_EMBED_RE.fullmatch(string.strip()):
        return NodeType.EMBED_BLOCK
    return NodeType.PLAIN_BLOCK
