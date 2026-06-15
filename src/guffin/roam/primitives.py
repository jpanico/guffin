"""Foundational Roam Research primitives: type aliases, stub models, and pattern constants.

Public symbols are organized into four groups:

- **Primitive type aliases**: :data:`Uid`, :data:`Id`, :data:`Order`, :data:`HeadingLevel`,
  :data:`PageTitle`, :data:`Url`.
- **Composite type aliases**: :data:`UidPair`, :data:`RawChildren`, :data:`RawRefs`.
- **Stub models**: :class:`IdObject`, :class:`LinkObject`.
- **Pattern constants**: :data:`UID_PATTERN` — raw regex string for a Roam node UID;
  :data:`UID_RE` — compiled form.
"""

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

UID_PATTERN: Final[str] = r"^[A-Za-z0-9_-]{9}$"
"""Raw regex pattern string for a Roam node UID: exactly 9 alphanumeric/dash/underscore characters."""

UID_RE: Final[re.Pattern[str]] = re.compile(UID_PATTERN)
"""Compiled regex for matching a Roam node UID."""

type Uid = Annotated[str, Field(pattern=UID_PATTERN)]
"""Nine-character alphanumeric stable block/page identifier (:block/uid)."""

type Id = int
"""Datomic internal numeric entity id (:db/id).

Ephemeral — not stable across exports.
"""

type Order = Annotated[int, Field(ge=0)]
"""Zero-based position of a child block among its siblings (:block/order)."""

type HeadingLevel = Annotated[int, Field(ge=1, le=6)]
"""Markdown heading level 1–6 (:block/heading).

Absent (None) on non-heading blocks.
"""

type PageTitle = Annotated[str, Field(min_length=1)]
"""Page title string (:node/title).

Only present on page entities.
"""

type Url = HttpUrl
"""A validated HTTP/HTTPS URL (e.g. a Cloud Firestore storage URL for a Roam-managed file)."""


type UidPair = tuple[Literal["uid"], Uid]
"""A two-element tuple ``('uid', <uid-value>)`` used as a Datomic :entity/attrs source or value."""


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
