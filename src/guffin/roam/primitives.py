"""Foundational Roam Research primitives: type aliases, stub models, and pattern constants.

Public symbols are organized into the following groups:

- **Primitive type aliases**: :data:`Uid`, :data:`Id`, :data:`Order`, :data:`PageTitle`.
- **Composite type aliases**: :data:`UidPair`, :data:`RawChildren`, :data:`RawRefs`.
- **Stub models**: :class:`IdObject`, :class:`LinkObject`.
- **Enums**: :class:`ChildrenViewType` — Roam block ``:children/view-type`` values.
- **Constants**: :data:`DEFAULT_CHILDREN_VIEW_TYPE` — fallback :class:`ChildrenViewType` for a
  block whose ``:children/view-type`` is unset; :data:`IMAGE_SIZE_PROP_ADAPTER` — Pydantic
  :class:`~pydantic.TypeAdapter` validating the ``image-size`` block prop.
- **Pattern constants**: :data:`SYNTHETIC_UID_PATTERN` (Roam-generated 9-char UID) and
  :data:`DAILY_NOTE_UID_PATTERN` (``MM-DD-YYYY`` daily-note-page UID) compose
  :data:`UID_PATTERN` / :data:`UID_RE` — the unanchored regex matching *any* node UID;
  :data:`ANCHORED_UID_PATTERN` / :data:`ANCHORED_UID_RE` — the whole-string anchored form.
- **Functions**: :func:`parse_daily_note_uid` — parse a daily-note UID (``MM-DD-YYYY``) into a
  :class:`datetime.date`, or ``None`` for a synthetic UID; :func:`daily_note_title` — the canonical
  verbose Roam title (e.g. ``January 1st, 2026``) for a :class:`datetime.date`.
"""

import datetime
import enum
from typing import Annotated, Final, Literal

import regex
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, validate_call

from guffin.common.date import ENGLISH_MONTHS, ordinal_suffix

SYNTHETIC_UID_PATTERN: Final[str] = r"[A-Za-z0-9_-]{9}"
"""Regex for a Roam-generated node UID: nine alphanumeric/dash/underscore characters (the common case).

Left unanchored so it can be embedded within a larger pattern — e.g. a ``((<uid>))`` block reference,
which only ever contains synthetic UIDs (daily-note pages are referenced by title, not by UID).
"""

DAILY_NOTE_UID_PATTERN: Final[str] = r"[0-9]{2}-[0-9]{2}-[0-9]{4}"
"""Regex for a Daily Note Page UID: ``MM-DD-YYYY`` (e.g. ``08-24-2026``).

Roam auto-creates one page per calendar day whose UID is the date in this form, unlike the synthetic
UIDs of every other node.
"""

_DAILY_NOTE_UID_RE: Final[regex.Pattern[str]] = regex.compile(DAILY_NOTE_UID_PATTERN)
"""Compiled :data:`DAILY_NOTE_UID_PATTERN`, precompiled for the hot validation path.

:func:`parse_daily_note_uid` runs it against every node's UID during validation, where a per-call
string-pattern lookup is ~19x slower.
"""

UID_PATTERN: Final[str] = rf"(?:{DAILY_NOTE_UID_PATTERN}|{SYNTHETIC_UID_PATTERN})"
"""Unanchored regex for *any* Roam node UID — a :data:`DAILY_NOTE_UID_PATTERN` or :data:`SYNTHETIC_UID_PATTERN`.

The date alternative is listed first so that, matched unanchored, a full ``MM-DD-YYYY`` UID is not
truncated to its first nine characters by the synthetic branch.  To test whether a string is *wholly*
a UID, use :data:`ANCHORED_UID_PATTERN` / :data:`ANCHORED_UID_RE`.
"""

UID_RE: Final[regex.Pattern[str]] = regex.compile(UID_PATTERN)
"""Compiled (unanchored) :data:`UID_PATTERN`; use to find a UID embedded in a larger string."""

ANCHORED_UID_PATTERN: Final[str] = rf"^{UID_PATTERN}$"
""":data:`UID_PATTERN` anchored at both ends, matching a string that is exactly a UID."""

ANCHORED_UID_RE: Final[regex.Pattern[str]] = regex.compile(ANCHORED_UID_PATTERN)
"""Compiled :data:`ANCHORED_UID_PATTERN` for matching a string that is exactly a Roam node UID."""

type Uid = Annotated[str, Field(pattern=ANCHORED_UID_PATTERN)]
"""Stable block/page identifier (:block/uid).

Either a synthetic nine-character UID (:data:`SYNTHETIC_UID_PATTERN`) or a ``MM-DD-YYYY`` Daily Note
Page UID (:data:`DAILY_NOTE_UID_PATTERN`).
"""

type Id = int
"""Datomic internal numeric entity id (:db/id).

Ephemeral — not stable across exports.
"""

type Order = Annotated[int, Field(ge=0)]
"""Zero-based position of a child block among its siblings (:block/order)."""

type PageTitle = Annotated[str, Field(min_length=1)]
"""Page title string (:node/title).

Only present on page entities.
"""

type UidPair = tuple[Literal["uid"], Uid]
"""A two-element tuple ``('uid', <uid-value>)`` used as a Datomic :entity/attrs source or value."""


class ChildrenViewType(enum.StrEnum):
    """How a block's children are rendered in the Roam UI (:children/view-type).

    - **BULLET**: children shown as a bulleted list (the Roam default).
    - **DOCUMENT**: children shown as a flowing document without bullets.
    - **NUMBERED**: children shown as a numbered list.
    """

    BULLET = "bullet"
    DOCUMENT = "document"
    NUMBERED = "numbered"


DEFAULT_CHILDREN_VIEW_TYPE: Final[ChildrenViewType] = ChildrenViewType.BULLET
"""Fallback :class:`ChildrenViewType` for a block whose ``:children/view-type`` is unset."""

IMAGE_SIZE_PROP_ADAPTER: Final[TypeAdapter[dict[str, dict[str, int | None]]]] = TypeAdapter(
    dict[str, dict[str, int | None]]
)
"""Pydantic :class:`~pydantic.TypeAdapter` for validating the ``image-size`` block prop.

The ``image-size`` prop maps an image URL string to a ``{"width": int|None, "height": int|None}``
dict; validating through the adapter extracts dimensions without Unknown-type propagation.
"""


class IdObject(BaseModel):
    """A thin wrapper carrying only a Datomic entity id.

    This is the stub shape returned by ``pull [*]`` for nested refs
    (e.g. ``:block/children``, ``:block/refs``, ``:block/page``).

    Attributes:
        id: The Datomic internal numeric entity id (:db/id).
    """

    model_config = ConfigDict(frozen=True)

    id: Id = Field(..., description="Datomic internal numeric entity id (:db/id)")


class LinkObject(BaseModel):
    """A :entity/attrs link entry, representing a typed attribute assertion.

    Each entry in a ``:entity/attrs`` value is a ``LinkObject`` carrying a
    source UidPair (the attribute identity) and a value that is either a
    UidPair (a reference to another page/block) or a plain string (a literal
    value, e.g. ``' n'``, ``' y'``, ``' 0'``, or free text).

    Attributes:
        source: ``('uid', <attr-uid>)`` — the attribute being asserted.
        value: The asserted value — a ``('uid', <uid>)`` reference pair or a
            literal string.
    """

    model_config = ConfigDict(frozen=True)

    source: UidPair = Field(..., description="Attribute identity as a UidPair")
    value: UidPair | str = Field(..., description="Asserted value: a UidPair reference or a literal string")


type RawChildren = list[IdObject]
"""Child block stubs as returned directly by ``pull [*]``.

Each element is an :class:`IdObject` carrying only a ``:db/id``; full block data
is resolved during the normalization pass.
"""

type RawRefs = list[IdObject]
"""Page/block reference stubs as returned directly by ``pull [*]``.

Same shape as :data:`RawChildren` — :class:`IdObject` stubs awaiting normalization.
"""


@validate_call
def parse_daily_note_uid(uid: Uid) -> datetime.date | None:
    """Parse a daily-note *uid* (``MM-DD-YYYY``) into its calendar date, or ``None`` if synthetic.

    A daily-note UID is ``MM-DD-YYYY`` (:data:`DAILY_NOTE_UID_PATTERN`); a synthetic UID is not a date.

    Args:
        uid: The page UID to parse.

    Returns:
        The :class:`datetime.date` a daily-note UID encodes, or ``None`` for a synthetic UID.

    Raises:
        ValueError: If *uid* matches the daily-note pattern but encodes an impossible calendar date
            (e.g. ``13-45-2026``) — ``strptime`` rejects it.
    """
    if _DAILY_NOTE_UID_RE.fullmatch(uid) is None:
        return None
    return datetime.datetime.strptime(uid, "%m-%d-%Y").date()


@validate_call
def daily_note_title(note_date: datetime.date) -> str:
    """Return the canonical Roam daily-note page title for *note_date*, e.g. ``January 1st, 2026``.

    The title is the verbose date Roam fixes a daily-note page's title to: the English month name,
    the day-of-month with its ordinal suffix, and the year.  Built from the fixed
    :data:`~guffin.common.date.ENGLISH_MONTHS` and :func:`~guffin.common.date.ordinal_suffix` (not
    ``strftime``, whose ``%B`` is locale-dependent and which has no ordinal-suffix directive).

    Args:
        note_date: The calendar date to format.

    Returns:
        The verbose title, e.g. ``January 1st, 2026``.
    """
    return f"{ENGLISH_MONTHS[note_date.month - 1]} {note_date.day}{ordinal_suffix(note_date.day)}, {note_date.year}"
