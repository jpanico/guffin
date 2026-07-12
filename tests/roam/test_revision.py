"""Unit tests for guffin.roam.revision."""

from datetime import UTC, datetime

from guffin.roam.revision import content_hash, gather_revision

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


class TestContentHash:
    """content_hash() is content-addressed: ordering and transient state cannot move it."""

    def test_deterministic(self) -> None:
        """The same input hashes identically."""
        assert content_hash(_RAW) == content_hash(_RAW)

    def test_row_order_is_canonicalized(self) -> None:
        """Reversing the result rows leaves the digest unchanged."""
        assert content_hash(list(reversed(_RAW))) == content_hash(_RAW)

    def test_stub_list_order_is_canonicalized(self) -> None:
        """Reordering a children stub list leaves the digest unchanged."""
        reordered = [
            [{**_RAW[0][0], "children": [{"id": 2}, {"id": 3}]}],
            _RAW[1],
        ]
        assert content_hash(reordered) == content_hash(_RAW)

    def test_transient_state_is_ignored(self) -> None:
        """Flipping a transient key (block open state) leaves the digest unchanged."""
        toggled = [_RAW[0], [{**_RAW[1][0], "open": False}]]
        assert content_hash(toggled) == content_hash(_RAW)

    def test_content_change_moves_the_digest(self) -> None:
        """Changing a block string changes the digest."""
        edited = [_RAW[0], [{**_RAW[1][0], "string": "goodbye"}]]
        assert content_hash(edited) != content_hash(_RAW)


class TestGatherRevision:
    """gather_revision() captures the hash, edit bookkeeping, label, and snapshot moment."""

    def test_last_edited_at_is_the_max_over_time_keys(self) -> None:
        """The latest of the create/edit bookkeeping timestamps wins (epoch ms → UTC datetime)."""
        revision = gather_revision(_RAW)
        assert revision.last_edited_at == datetime.fromtimestamp(1780944773800 / 1000, tz=UTC)

    def test_label_is_carried(self) -> None:
        """A caller-supplied label lands on the revision."""
        assert gather_revision(_RAW, label="draft-3").label == "draft-3"

    def test_fetched_at_is_stamped(self) -> None:
        """The capture moment is recorded."""
        revision = gather_revision(_RAW)
        assert revision.fetched_at is not None

    def test_no_time_keys_yields_none(self) -> None:
        """A result with no bookkeeping timestamps yields last_edited_at=None."""
        raw: list[list[dict[str, object]]] = [[{"uid": "page00001", "id": 1, "title": "Doc"}]]
        assert gather_revision(raw).last_edited_at is None
