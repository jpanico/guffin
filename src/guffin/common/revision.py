"""Content revision for an exported document: which version of the source content produced it.

The content-side counterpart of :mod:`~guffin.common.provenance`: where a
:class:`~guffin.common.provenance.Provenance` identifies the *software* that produced a document,
a :class:`Revision` identifies the *content snapshot* it was produced from — a content-addressed
hash of the fetched source (the revision's identity), the latest edit-bookkeeping timestamp among
the fetched nodes (an advisory upper bound on when the content last changed), an optional
authored revision label, and the moment the snapshot was taken.

Public symbols:

- **Models**: :class:`Revision` — the content-snapshot facts identifying one export's input.
"""

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.common.date import utc_timestamp

_SHORT_HASH_LENGTH: Final[int] = 12
"""Leading content-hash characters shown by :meth:`Revision.summary`."""


class Revision(BaseModel):
    """The content-snapshot facts that identify a single export's input.

    Together these answer, for any document the exporter produces, exactly which content it was
    produced from: a content-addressed hash of the canonicalized source (the revision's sole
    identity — two exports with equal hashes were built from identical content), the latest
    edit-bookkeeping timestamp among the fetched nodes, an optional author-declared revision
    label, and the moment the snapshot was taken.

    Attributes:
        content_hash: SHA-256 hex digest of the canonicalized source content — the revision's
            identity.
        last_edited_at: The latest edit-bookkeeping timestamp among the fetched nodes — an
            *upper bound* on when the content last changed (the bookkeeping's exact trigger
            conditions belong to the source system, not to this record); ``None`` when unknown.
        label: An author-declared revision label carried by the content itself (e.g. a draft
            name or version string), or ``None`` when the content declares none.
        fetched_at: The moment the content snapshot was taken, or ``None`` when not recorded.
    """

    model_config = ConfigDict(frozen=True)

    content_hash: str = Field(..., description="SHA-256 hex digest of the canonicalized source content.")
    last_edited_at: datetime | None = Field(
        default=None, description="Latest edit-bookkeeping timestamp among the fetched nodes (upper bound)."
    )
    label: str | None = Field(default=None, description="Author-declared revision label, when the content has one.")
    fetched_at: datetime | None = Field(default=None, description="The moment the content snapshot was taken.")

    @validate_call
    def summary(self) -> str:
        """Return a single-line identifier encoding the content hash, label, and timestamps.

        The content hash is shortened to its first :data:`_SHORT_HASH_LENGTH` characters; the
        label (when present) and the edit/fetch timestamps (minute-precision UTC with an explicit
        ``Z`` — see :func:`~guffin.common.date.utc_timestamp`) follow.  Example::

            rev d8666f090982 · label draft-3 · edited 2026-07-11T18:22Z · fetched 2026-07-12T09:30Z

        Returns:
            The revision as one compact, human- and machine-readable line.
        """
        parts: Final[list[str]] = [f"rev {self.content_hash[:_SHORT_HASH_LENGTH]}"]
        if self.label is not None:
            parts.append(f"label {self.label}")
        if self.last_edited_at is not None:
            parts.append(f"edited {utc_timestamp(self.last_edited_at)}")
        if self.fetched_at is not None:
            parts.append(f"fetched {utc_timestamp(self.fetched_at)}")
        return " · ".join(parts)
