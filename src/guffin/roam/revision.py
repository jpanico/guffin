"""Capture a content :class:`~guffin.common.revision.Revision` from a raw Roam fetch.

Derives the revision facts from the raw Datalog wire response: a content-addressed hash over the
canonicalized node set, and the latest edit-bookkeeping timestamp among the fetched nodes.

The canonical form makes the hash a function of the *content alone*: transient session/UI keys
are stripped (:func:`~guffin.roam.local_api.without_transient_keys` — the same judgment that
defines content identity for recorded fixtures), result rows are sorted by the pulled entity's
``uid``, stub lists (``children``/``refs``/``parents``) are sorted by ``id``, and dict keys are
sorted in the JSON serialization — so neither Datalog result ordering nor pull iteration order
can move the digest.  Children's *semantic* order is untouched: it lives in each node's ``order``
prop, which is hashed.

Public symbols:

- **Functions**: :func:`snapshot` — SHA-256 hex digest of a raw fetch result's canonical
  form, the snapshot's identity; :func:`gather_revision` — capture a full
  :class:`~guffin.common.revision.Revision` from a raw fetch result.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Final

from pydantic import validate_call

from guffin.common.revision import Revision
from guffin.roam.local_api import without_transient_keys

_STUB_LIST_KEYS: Final[tuple[str, ...]] = ("children", "refs", "parents")
"""Pull-block keys holding ``IdObject`` stub lists, whose wire order is not semantically meaningful."""

_TIME_KEYS: Final[tuple[str, ...]] = ("time", "edit-time")
"""Pull-block keys carrying Roam's create/edit bookkeeping timestamps (epoch milliseconds).

Both creation and edit are content events, so the revision's ``last_edited_at`` is the maximum
over both keys — which also sidesteps the wire's ambiguous namespace-stripped key naming.
"""


def _stub_sort_key(stub: object) -> int:
    """Return the ``id`` of an ``IdObject`` stub dict, or ``0`` for anything else."""
    if isinstance(stub, dict):
        identifier: object = stub.get("id")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(identifier, int):
            return identifier
    return 0


def _row_sort_key(row: list[dict[str, object]]) -> str:
    """Return the pulled entity's ``uid`` for a result row, or ``""`` when absent."""
    if not row:
        return ""
    uid: Final[object] = row[0].get("uid", "")
    return uid if isinstance(uid, str) else ""


def _canonical_json(raw_result: list[list[dict[str, object]]]) -> str:
    """Return the canonical JSON serialization of *raw_result* (see the module docstring)."""
    rows: Final[list[list[dict[str, object]]]] = []
    for row in without_transient_keys(raw_result):
        canonical_row: list[dict[str, object]] = []
        for block in row:
            canonical_block: dict[str, object] = dict(block)
            for key in _STUB_LIST_KEYS:
                stubs = canonical_block.get(key)
                if isinstance(stubs, list):
                    canonical_block[key] = sorted(
                        stubs,  # pyright: ignore[reportUnknownArgumentType]
                        key=_stub_sort_key,
                    )
            canonical_row.append(canonical_block)
        rows.append(canonical_row)
    rows.sort(key=_row_sort_key)
    return json.dumps(rows, sort_keys=True, ensure_ascii=False)


@validate_call
def snapshot(raw_result: list[list[dict[str, object]]]) -> str:
    """Return the SHA-256 hex digest of *raw_result*'s canonical form — the snapshot's identity.

    Content-addressed: any substantive change to any fetched node changes the digest, while
    transient session/UI state and wire-ordering variation do not.

    Args:
        raw_result: The raw Datalog query result, as stored in
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.raw_result`.

    Returns:
        The 64-character SHA-256 hex digest.
    """
    return hashlib.sha256(_canonical_json(raw_result).encode()).hexdigest()


def _last_edited_at(raw_result: list[list[dict[str, object]]]) -> datetime | None:
    """Return the latest create/edit bookkeeping timestamp among *raw_result*'s blocks, or ``None``."""
    latest_ms: int | None = None
    for row in raw_result:
        for block in row:
            for key in _TIME_KEYS:
                value = block.get(key)
                if isinstance(value, int) and (latest_ms is None or value > latest_ms):
                    latest_ms = value
    if latest_ms is None:
        return None
    return datetime.fromtimestamp(latest_ms / 1000, tz=UTC)


@validate_call
def gather_revision(raw_result: list[list[dict[str, object]]], revision: str | None = None) -> Revision:
    """Capture a :class:`~guffin.common.revision.Revision` from a raw fetch result.

    Computes the content-addressed :func:`snapshot` and the latest edit-bookkeeping timestamp
    from *raw_result*, stamps the capture moment, and carries the caller-supplied *revision*
    (an author-declared revision name resolved by the caller's own vocabulary).

    Args:
        raw_result: The raw Datalog query result, as stored in
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.raw_result`.
        revision: An author-declared revision name, or ``None`` when the content declares none.

    Returns:
        The captured :class:`~guffin.common.revision.Revision`.
    """
    return Revision(
        snapshot=snapshot(raw_result),
        last_edited_at=_last_edited_at(raw_result),
        revision=revision,
        fetched_at=datetime.now(tz=UTC),
    )
