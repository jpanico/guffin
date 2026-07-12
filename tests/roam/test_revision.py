"""Unit tests for guffin.roam.revision."""

from datetime import UTC, datetime

from guffin.roam.revision import gather_revision, snapshot

# A minimal two-row raw result: a page pulling two children stubs, and a block.
_RAW: list[list[dict[str, object]]] = [
    [
        {
            "uid": "page00001",
            "id": 1,
            "title": "Doc",
            "children": [{"id": 3}, {"id": 2}],
            "time": 1700000000000,
        }
    ],
    [
        {
            "uid": "block0001",
            "id": 2,
            "string": "hello",
            "order": 0,
            "edit-time": 1780944773800,
            "open": True,
        }
    ],
]


class TestSnapshot:
    """snapshot() is content-addressed: ordering and transient state cannot move it."""

    def test_deterministic(self) -> None:
        """The same input hashes identically."""
        assert snapshot(_RAW) == snapshot(_RAW)

    def test_row_order_is_canonicalized(self) -> None:
        """Reversing the result rows leaves the digest unchanged."""
        assert snapshot(list(reversed(_RAW))) == snapshot(_RAW)

    def test_stub_list_order_is_canonicalized(self) -> None:
        """Reordering a children stub list leaves the digest unchanged."""
        reordered = [
            [{**_RAW[0][0], "children": [{"id": 2}, {"id": 3}]}],
            _RAW[1],
        ]
        assert snapshot(reordered) == snapshot(_RAW)

    def test_transient_state_is_ignored(self) -> None:
        """Flipping a transient key (block open state) leaves the digest unchanged."""
        toggled = [_RAW[0], [{**_RAW[1][0], "open": False}]]
        assert snapshot(toggled) == snapshot(_RAW)

    def test_content_change_moves_the_digest(self) -> None:
        """Changing a block string changes the digest."""
        edited = [_RAW[0], [{**_RAW[1][0], "string": "goodbye"}]]
        assert snapshot(edited) != snapshot(_RAW)


class TestGatherRevision:
    """gather_revision() captures the snapshot, edit bookkeeping, revision name, and capture moment."""

    def test_last_edited_at_is_the_max_over_time_keys(self) -> None:
        """The latest of the create/edit bookkeeping timestamps wins (epoch ms → UTC datetime)."""
        revision = gather_revision(_RAW)
        assert revision.last_edited_at == datetime.fromtimestamp(1780944773800 / 1000, tz=UTC)

    def test_revision_name_is_carried(self) -> None:
        """A caller-supplied revision name lands on the revision."""
        assert gather_revision(_RAW, revision="draft-3").revision == "draft-3"

    def test_fetched_at_is_stamped(self) -> None:
        """The capture moment is recorded."""
        revision = gather_revision(_RAW)
        assert revision.fetched_at is not None

    def test_no_time_keys_yields_none(self) -> None:
        """A result with no bookkeeping timestamps yields last_edited_at=None."""
        raw: list[list[dict[str, object]]] = [[{"uid": "page00001", "id": 1, "title": "Doc"}]]
        assert gather_revision(raw).last_edited_at is None
