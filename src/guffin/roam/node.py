"""Roam Research raw node data model.

Public symbols:

- :class:`NodeType` — ``StrEnum`` of pull-block entity types: ``PAGE``, ``TEXT_BLOCK``,
  ``IMAGE_BLOCK``, ``HEADING_BLOCK``, ``CALLOUT_BLOCK``,
  ``CODE_BLOCK``, ``QUOTE_BLOCK``, ``NATIVE_TABLE``, ``TODO_BLOCK``, ``EMBED_BLOCK``,
  ``EMBED_PAGE``, ``PDF_BLOCK``, ``ASSET_BLOCK``, ``ATTRIBUTE_BLOCK``.
- :class:`RoamNode` — raw shape of a pull-block as returned by the Roam Local API.
- :func:`node_type` — return the :class:`NodeType` of a :class:`RoamNode`.
- :func:`effective_heading_level` — return the effective heading level for a
  :class:`RoamNode`, or ``None`` if it is not a heading.
- :func:`effective_children_view_type` — return a :class:`RoamNode`'s children view type,
  falling back to :data:`~guffin.roam.primitives.DEFAULT_CHILDREN_VIEW_TYPE` when unset.
- :func:`image_size` — return the :class:`~guffin.common.geometry.ImageSize` recorded in
  a :attr:`NodeType.IMAGE_BLOCK` node's ``image-size`` prop, or ``None`` if the node
  is not an image block.
- :func:`better_bullet_type` — return the :class:`~guffin.roam.better_bullet.BetterBulletType`
  recorded in a node's ``type`` prop, or ``None`` if it carries none.
- :func:`better_bullet_provenance` — return the
  :class:`~guffin.roam.better_bullet.BetterBulletProvenance` recorded in a node's
  ``provenance`` prop, or ``None`` if it carries none.
- :data:`NodesByUid` — ``dict`` mapping each :attr:`~RoamNode.uid` to its :class:`RoamNode`.
"""

import datetime
import enum
import logging
from collections.abc import Mapping
from typing import Final

import regex
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    validate_call,
)

from guffin.common.geometry import ImageSize
from guffin.common.markdown import HeadingLevel, is_fenced_code_block
from guffin.roam.better_bullet import BetterBulletProvenance, BetterBulletType
from guffin.roam.blockquote import CALLOUT_RE, is_quote_block
from guffin.roam.markdown import (
    ATTRIBUTE_ASSIGNMENT_RE,
    BLOCK_EMBED_RE,
    FIREBASE_STORAGE_URL_RE,
    IMAGE_LINK_RE,
    PAGE_EMBED_RE,
    PDF_EMBED_RE,
    ROAM_NATIVE_TABLE_MARKERS,
)
from guffin.roam.primitives import (
    DEFAULT_CHILDREN_VIEW_TYPE,
    IMAGE_SIZE_PROP_ADAPTER,
    ChildrenViewType,
    Id,
    IdObject,
    LinkObject,
    Order,
    PageTitle,
    RawChildren,
    RawRefs,
    Uid,
    daily_note_title,
    parse_daily_note_uid,
)
from guffin.roam.schema import SchemaAttribute
from guffin.roam.todo import todo_state

logger = logging.getLogger(__name__)

_AH_LEVEL_RE: Final[regex.Pattern[str]] = regex.compile(r"h(?P<level>[1-6])")
"""Compiled regex matching an Augmented Headings ``ah-level`` block-prop value (``h1`` … ``h6``)."""


class NodeType(enum.StrEnum):
    """Entity type of a Roam pull-block.

    - **PAGE**: ``title`` is a string, ``string`` is ``None``.
    - **TEXT_BLOCK**: ``string`` is set, ``title`` is ``None``, no special Roam properties.
    - **HEADING_BLOCK**: ``heading`` (levels 1–3) or ``props['ah-level']`` (levels 4–6) is set; the entire
      block content is the heading text.
    - **IMAGE_BLOCK**: ``string`` is a standalone Markdown image link to a Firebase Storage URL
      (the link is the string's entire content).
      Produced by drag-and-drop into the Roam UI; supports image-resize properties via ``props``.
    - **CALLOUT_BLOCK**: ``string`` starts with ``[[>]] [[!<TYPE>]]`` where ``<TYPE>`` is one of the eleven
      recognised callout type keywords (``INFO``, ``EXAMPLE``, ``NOTE``, ``WARNING``, ``DANGER``,
      ``TIP``, ``SUMMARY``, ``SUCCESS``, ``QUESTION``, ``FAILURE``, ``BUG``).
    - **CODE_BLOCK**: ``string``, with surrounding whitespace trimmed, is a CommonMark fenced code
      block (opened by a ```` ``` ```` or ``~~~`` fence).
    - **QUOTE_BLOCK**: any quote block — ``string`` starts with ``>`` or ``[[>]]`` but does *not* match
      the callout marker ``[[>]] [[!<TYPE>]]``.  This includes the pull quote ``[[>]] [[!QUOTE]]`` (``QUOTE``
      is not a callout type), which the transcriber distinguishes from a plain block quote.
    - **NATIVE_TABLE**: ``string``, with surrounding whitespace trimmed, is one of
      :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKERS` (``"{{table}}"`` /
      ``"{{[[table]]}}"``); its child blocks form the table rows.
    - **TODO_BLOCK**: ``string``'s first content is a Roam TODO marker ``{{[[TODO]]}}`` /
      ``{{[[DONE]]}}``, seen through any leading formatting markup (as recognized by
      :func:`~guffin.roam.todo.todo_state`); the marker's keyword names the item's
      :class:`~guffin.roam.todo.TodoState`.
    - **EMBED_BLOCK**: ``title`` is ``None`` and ``string``, with surrounding whitespace
      trimmed, is wholly a Roam block embed ``{{embed: ((<uid>))}}`` /
      ``{{[[embed]]: ((<uid>))}}`` (matched by :data:`~guffin.roam.markdown.BLOCK_EMBED_RE`).
    - **EMBED_PAGE**: ``title`` is ``None`` and ``string``, with surrounding whitespace
      trimmed, is wholly a Roam page embed ``{{embed: [[<page_name>]]}}`` /
      ``{{[[embed]]: [[<page_name>]]}}`` (matched by :data:`~guffin.roam.markdown.PAGE_EMBED_RE`)
      — the page-reference sibling of EMBED_BLOCK.
    - **PDF_BLOCK**: ``string``, with surrounding whitespace trimmed, is wholly a Roam PDF
      component ``{{pdf: <url>}}`` / ``{{[[pdf]]: <url>}}`` whose URL is a Firebase Storage
      URL (matched in full by :data:`~guffin.roam.markdown.PDF_EMBED_RE`).
    - **ASSET_BLOCK**: ``string``, with surrounding whitespace trimmed, is wholly a bare
      Firebase Storage URL (matched in full by :data:`~guffin.roam.markdown.FIREBASE_STORAGE_URL_RE`)
      — the one Roam asset-URL form with no Markdown or Roam-component chrome around it.
    - **ATTRIBUTE_BLOCK**: ``string``, with surrounding whitespace trimmed, is wholly a Roam
      attribute assignment ``<attribute>:: <value>[, <value>]…`` (matched in full by
      :data:`~guffin.roam.markdown.ATTRIBUTE_ASSIGNMENT_RE`).
    """

    PAGE = "roam/page"
    TEXT_BLOCK = "roam/text-block"
    HEADING_BLOCK = "roam/heading-block"
    IMAGE_BLOCK = "roam/image-block"
    CALLOUT_BLOCK = "roam/callout-block"
    CODE_BLOCK = "roam/code-block"
    QUOTE_BLOCK = "roam/quote-block"
    NATIVE_TABLE = "roam/table"
    TODO_BLOCK = "roam/todo-block"
    EMBED_BLOCK = "roam/embed-block"
    EMBED_PAGE = "roam/embed-page"
    PDF_BLOCK = "roam/pdf-block"
    ASSET_BLOCK = "roam/asset-block"
    ATTRIBUTE_BLOCK = "roam/attribute-block"


class RoamNode(BaseModel):
    """Raw shape of a "pull-block" as returned by ``roamAlphaAPI.data.q`` / ``pull [*]``.

    This is the *un-normalized* form — property names mirror the raw Datomic
    attribute names, and nested refs are still IdObject stubs rather than resolved UIDs.

    Every pull-block is one of two mutually exclusive entity types, discriminated by
    ``title``.  The following invariants are enforced at construction time by
    :meth:`_validate_entity_type`:

    - **Page**: ``title`` set, so ``string`` and ``page`` are ``None``.
    - **Block**: ``title`` ``None``, so ``string`` and ``page`` are set.

    A further invariant, enforced by :meth:`_validate_daily_note_title`: a **daily-note page** —
    one whose ``uid`` is an ``MM-DD-YYYY`` date (:data:`~guffin.roam.primitives.DAILY_NOTE_UID_PATTERN`)
    — must carry that date's verbose ``title`` (e.g. ``01-01-2026`` → ``January 1st, 2026``).

    And two more, enforced by :meth:`_validate_better_bullet_type` and
    :meth:`_validate_better_bullet_provenance`: a ``type`` / ``provenance`` block property,
    when present, must hold a recognized
    :class:`~guffin.roam.better_bullet.BetterBulletType` /
    :class:`~guffin.roam.better_bullet.BetterBulletProvenance` identifier (the Better
    Bullets extension's persisted bullet kind and provenance badge).

    All remaining fields (``parents``, ``children``, ``heading``, ``refs``, etc.)
    are optional and vary by entity type and feature usage.

    Attributes:
        uid: Stable block/page identifier (BLOCK_UID) — a synthetic nine-character UID or an
            ``MM-DD-YYYY`` daily-note-page UID. Required.
        id: Datomic internal numeric entity id (:db/id). Ephemeral and not stable
            across exports. Required.
        string: Block text content (BLOCK_STRING). Present only on Block entities.
        title: Page title (NODE_TITLE). Present only on Page entities.
        order: Zero-based sibling order (BLOCK_ORDER). Present only on child Blocks.
        heading: HeadingLevel (BLOCK_HEADING). Present only on heading Blocks.
        children: Raw child block stubs (BLOCK_CHILDREN). Present on Blocks and Pages with children.
        refs: Raw page/block reference stubs (BLOCK_REFS).
        page: IdObject stub for the containing page (BLOCK_PAGE). Present only on Blocks.
        children_view_type: How this block's children are rendered (CHILDREN_VIEW_TYPE). Present
            only on Blocks.  Read from the ``children-view-type`` wire key, the alias the node
            queries pull it under so that ``:block/view-type`` cannot overwrite it.
        parents: IdObject stubs for all ancestor blocks (BLOCK_PARENTS). Present only on Blocks.
        props: Block property key-value map (BLOCK_PROPS). Present only on Blocks that have block
            properties set (e.g. ``ah-level`` from the Augmented Headings extension).
        attrs: Structured attribute assertions (ENTITY_ATTRS).
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

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
    children_view_type: ChildrenViewType | None = Field(
        default=None,
        alias="children-view-type",
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

    @field_validator("children_view_type", mode="before")
    @classmethod
    def _tolerate_unknown_view_type(cls, val: object) -> object:
        # The fetch pulls :children/view-type under its own alias, so this key can no longer
        # carry :block/view-type's display bookkeeping (see FetchRoamNodes.Request.PULL_PATTERN).
        # A value outside the vocabulary is therefore genuinely unrecognized — a children layout
        # Roam has added since: report it, but treat it as unset rather than failing the fetch.
        if val is None or val in {member.value for member in ChildrenViewType}:
            return val
        logger.warning("ignoring unrecognized view-type %r (not a children view type)", val)
        return None

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

    @model_validator(mode="after")
    def _validate_daily_note_title(self) -> RoamNode:
        """Require a daily-note-UID page's title to be the verbose date the UID encodes.

        A daily-note page's UID is ``MM-DD-YYYY``
        (:data:`~guffin.roam.primitives.DAILY_NOTE_UID_PATTERN`) and Roam fixes its title to that
        date's verbose form, e.g. ``01-01-2026`` → ``January 1st, 2026``.  Nodes with a synthetic
        UID carry no such constraint.

        Returns:
            The validated instance.

        Raises:
            ValueError: If *uid* is a daily-note UID whose encoded date is invalid, or whose page
                title is not that date's verbose form.
        """
        note_date: Final[datetime.date | None] = parse_daily_note_uid(self.uid)
        if note_date is None:
            return self
        expected: Final[str] = daily_note_title(note_date)
        if self.title != expected:
            raise ValueError(f"daily-note page uid={self.uid!r} must have title {expected!r}, got {self.title!r}")
        return self

    @model_validator(mode="after")
    def _validate_better_bullet_type(self) -> RoamNode:
        """Require a ``type`` block property, when present, to be a recognized Better Bullets id.

        The Better Bullets extension persists an applied bullet kind in the block's ``type``
        property as a :class:`~guffin.roam.better_bullet.BetterBulletType` identifier.  Nodes
        with no property map, or none carrying a ``type`` entry, are unconstrained.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the ``type`` property holds anything but a recognized
                :class:`~guffin.roam.better_bullet.BetterBulletType` identifier.
        """
        _parsed_better_bullet_type(self.props, self.uid)
        return self

    @model_validator(mode="after")
    def _validate_better_bullet_provenance(self) -> RoamNode:
        """Require a ``provenance`` block property, when present, to be a recognized provenance id.

        The Better Bullets extension persists an applied provenance badge in the block's
        ``provenance`` property as a
        :class:`~guffin.roam.better_bullet.BetterBulletProvenance` identifier.  Nodes with no
        property map, or none carrying a ``provenance`` entry, are unconstrained.

        Returns:
            The validated instance.

        Raises:
            ValueError: If the ``provenance`` property holds anything but a recognized
                :class:`~guffin.roam.better_bullet.BetterBulletProvenance` identifier.
        """
        _parsed_better_bullet_provenance(self.props, self.uid)
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
    ah_level: Final[object | None] = (node.props or {}).get("ah-level")
    if not isinstance(ah_level, str):
        return None
    ah_match: Final[regex.Match[str] | None] = _AH_LEVEL_RE.fullmatch(ah_level)
    if ah_match is None:
        return None
    return int(ah_match.group("level"))


@validate_call
def effective_children_view_type(node: RoamNode) -> ChildrenViewType:
    """Return *node*'s children view type, falling back to the default when unset.

    Args:
        node: The node to inspect.

    Returns:
        :attr:`~RoamNode.children_view_type` if set, otherwise
        :data:`~guffin.roam.primitives.DEFAULT_CHILDREN_VIEW_TYPE`.
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
        first URL entry in the ``image-size`` map, each recorded dimension rounded
        to whole pixels (Roam records fractional values for a drag-resized image).

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
    size_map: Final[dict[str, dict[str, float | None]]] = IMAGE_SIZE_PROP_ADAPTER.validate_python(raw)
    first_entry: Final[dict[str, float | None] | None] = next(iter(size_map.values()), None)
    if first_entry is None:
        return ImageSize()
    width: Final[float | None] = first_entry.get("width")
    height: Final[float | None] = first_entry.get("height")
    return ImageSize(
        width=round(width) if width is not None else None,
        height=round(height) if height is not None else None,
    )


def _parsed_better_bullet_type(props: Mapping[str, object] | None, uid: Uid) -> BetterBulletType | None:
    """Return the Better Bullets kind a block property map records, or ``None`` if it records none.

    Args:
        props: A block's property map; may be ``None``.
        uid: The owning node's uid, naming the node in the failure message.

    Returns:
        The :class:`~guffin.roam.better_bullet.BetterBulletType` the map's ``type`` entry
        identifies, or ``None`` when *props* is ``None`` or carries no ``type`` entry.

    Raises:
        ValueError: If the ``type`` entry holds anything but a recognized
            :class:`~guffin.roam.better_bullet.BetterBulletType` identifier.
    """
    raw: Final[object | None] = (props or {}).get("type")
    if raw is None:
        return None
    if not isinstance(raw, str) or raw not in BetterBulletType:
        raise ValueError(f"node uid={uid!r} has an unrecognized Better Bullets 'type' prop {raw!r}")
    return BetterBulletType(raw)


@validate_call
def better_bullet_type(node: RoamNode) -> BetterBulletType | None:
    """Return the Better Bullets kind recorded on *node*, or ``None`` if it carries none.

    The Better Bullets Roam extension persists an applied bullet kind on the block as the
    kind's identifier in the ``type`` entry of the block's property map
    (``node.props["type"]``).  An absent property map or an absent ``type`` entry resolves to
    ``None``.  An unrecognized value never occurs on a constructed node:
    :class:`RoamNode` enforces the same judgment at construction
    (:meth:`RoamNode._validate_better_bullet_type`).

    Args:
        node: The node to inspect.

    Returns:
        The :class:`~guffin.roam.better_bullet.BetterBulletType` the block's ``type``
        property identifies, or ``None``.
    """
    return _parsed_better_bullet_type(node.props, node.uid)


def _parsed_better_bullet_provenance(props: Mapping[str, object] | None, uid: Uid) -> BetterBulletProvenance | None:
    """Return the provenance kind a block property map records, or ``None`` if it records none.

    Args:
        props: A block's property map; may be ``None``.
        uid: The owning node's uid, naming the node in the failure message.

    Returns:
        The :class:`~guffin.roam.better_bullet.BetterBulletProvenance` the map's
        ``provenance`` entry identifies, or ``None`` when *props* is ``None`` or carries no
        ``provenance`` entry.

    Raises:
        ValueError: If the ``provenance`` entry holds anything but a recognized
            :class:`~guffin.roam.better_bullet.BetterBulletProvenance` identifier.
    """
    raw: Final[object | None] = (props or {}).get("provenance")
    if raw is None:
        return None
    if not isinstance(raw, str) or raw not in BetterBulletProvenance:
        raise ValueError(f"node uid={uid!r} has an unrecognized Better Bullets 'provenance' prop {raw!r}")
    return BetterBulletProvenance(raw)


@validate_call
def better_bullet_provenance(node: RoamNode) -> BetterBulletProvenance | None:
    """Return the Better Bullets provenance recorded on *node*, or ``None`` if it carries none.

    The Better Bullets Roam extension persists an applied provenance badge on the block as
    the kind's identifier in the ``provenance`` entry of the block's property map
    (``node.props["provenance"]``).  An absent property map or an absent ``provenance``
    entry resolves to ``None``.  An unrecognized value never occurs on a constructed node:
    :class:`RoamNode` enforces the same judgment at construction
    (:meth:`RoamNode._validate_better_bullet_provenance`).

    Args:
        node: The node to inspect.

    Returns:
        The :class:`~guffin.roam.better_bullet.BetterBulletProvenance` the block's
        ``provenance`` property identifies, or ``None``.
    """
    return _parsed_better_bullet_provenance(node.props, node.uid)


type NodesByUid = dict[Uid, RoamNode]
"""``dict`` mapping each :attr:`~RoamNode.uid` to its :class:`RoamNode`."""


@validate_call
def node_type(node: RoamNode) -> NodeType:
    """Return the :class:`NodeType` of *node*.

    Discriminates first on :attr:`~RoamNode.title`: returns :attr:`NodeType.PAGE` when
    ``title`` is a non-``None`` string.  For title-less nodes (blocks), returns
    :attr:`NodeType.IMAGE_BLOCK` when ``string`` is a standalone Markdown image link — the
    link as the string's entire content (as matched by :data:`~guffin.roam.markdown.IMAGE_LINK_RE`),
    :attr:`NodeType.HEADING_BLOCK` when :func:`effective_heading_level` is non-``None``,
    :attr:`NodeType.CALLOUT_BLOCK` when ``string`` matches the full callout marker pattern
    (as matched by :data:`~guffin.roam.blockquote.CALLOUT_RE`),
    :attr:`NodeType.QUOTE_BLOCK` when :func:`~guffin.roam.blockquote.is_quote_block`
    returns ``True`` for ``string`` — i.e. a Roam ``[[>]]``-prefixed blockquote or a standard
    Markdown ``>``-prefixed blockquote,
    :attr:`NodeType.CODE_BLOCK` when the trimmed ``string`` is a fenced code block
    (as determined by :func:`~guffin.common.markdown.is_fenced_code_block`),
    :attr:`NodeType.NATIVE_TABLE` when the trimmed ``string`` is one of
    :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKERS`,
    :attr:`NodeType.TODO_BLOCK` when the ``string``'s first content is a Roam TODO marker
    (as recognized by :func:`~guffin.roam.todo.todo_state`, seeing through leading formatting
    markup),
    :attr:`NodeType.EMBED_BLOCK` when the trimmed ``string`` is wholly a Roam block embed
    (as matched by :data:`~guffin.roam.markdown.BLOCK_EMBED_RE`),
    :attr:`NodeType.EMBED_PAGE` when the trimmed ``string`` is wholly a Roam page embed
    (as matched by :data:`~guffin.roam.markdown.PAGE_EMBED_RE`),
    :attr:`NodeType.PDF_BLOCK` when the trimmed ``string`` is wholly a Roam PDF component
    (as matched in full by :data:`~guffin.roam.markdown.PDF_EMBED_RE`),
    :attr:`NodeType.ASSET_BLOCK` when the trimmed ``string`` is wholly a bare Firebase Storage
    URL (as matched in full by :data:`~guffin.roam.markdown.FIREBASE_STORAGE_URL_RE`),
    :attr:`NodeType.ATTRIBUTE_BLOCK` when the trimmed ``string`` is wholly a Roam attribute
    assignment (as matched in full by :data:`~guffin.roam.markdown.ATTRIBUTE_ASSIGNMENT_RE`),
    and :attr:`NodeType.TEXT_BLOCK` otherwise.

    Args:
        node: The node whose entity type to determine.

    Returns:
        :attr:`NodeType.PAGE` if ``title`` is set;
        :attr:`NodeType.IMAGE_BLOCK` if ``string`` is a standalone Markdown image link;
        :attr:`NodeType.HEADING_BLOCK` if ``heading`` or ``props['ah-level']`` is set;
        :attr:`NodeType.CALLOUT_BLOCK` if ``string`` matches ``[[>]] [[!<TYPE>]]``;
        :attr:`NodeType.QUOTE_BLOCK` if :func:`~guffin.roam.blockquote.is_quote_block` is ``True``;
        :attr:`NodeType.CODE_BLOCK` if the trimmed ``string`` is a CommonMark fenced code block;
        :attr:`NodeType.NATIVE_TABLE` if the trimmed ``string`` is one of
        :data:`~guffin.roam.markdown.ROAM_NATIVE_TABLE_MARKERS`;
        :attr:`NodeType.TODO_BLOCK` if the ``string``'s first content is a Roam TODO marker;
        :attr:`NodeType.EMBED_BLOCK` if the trimmed ``string`` is wholly a Roam block embed;
        :attr:`NodeType.EMBED_PAGE` if the trimmed ``string`` is wholly a Roam page embed;
        :attr:`NodeType.PDF_BLOCK` if the trimmed ``string`` is wholly a Roam PDF component;
        :attr:`NodeType.ASSET_BLOCK` if the trimmed ``string`` is wholly a bare Firebase Storage URL;
        :attr:`NodeType.ATTRIBUTE_BLOCK` if the trimmed ``string`` is wholly a Roam attribute assignment;
        :attr:`NodeType.TEXT_BLOCK` otherwise.
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
    if is_quote_block(string):
        return NodeType.QUOTE_BLOCK
    if is_fenced_code_block(string.strip()):
        return NodeType.CODE_BLOCK
    if string.strip() in ROAM_NATIVE_TABLE_MARKERS:
        return NodeType.NATIVE_TABLE
    if todo_state(string) is not None:
        return NodeType.TODO_BLOCK
    if BLOCK_EMBED_RE.fullmatch(string.strip()):
        return NodeType.EMBED_BLOCK
    if PAGE_EMBED_RE.fullmatch(string.strip()):
        return NodeType.EMBED_PAGE
    if PDF_EMBED_RE.fullmatch(string.strip()):
        return NodeType.PDF_BLOCK
    if FIREBASE_STORAGE_URL_RE.fullmatch(string.strip()):
        return NodeType.ASSET_BLOCK
    if ATTRIBUTE_ASSIGNMENT_RE.fullmatch(string.strip()):
        return NodeType.ATTRIBUTE_BLOCK
    return NodeType.TEXT_BLOCK
