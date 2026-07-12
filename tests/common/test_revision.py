"""Unit tests for guffin.common.revision."""

from datetime import UTC, datetime

from guffin.common.revision import Revision

_HASH = "d8666f090982aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class TestRevision:
    """Revision models the content-snapshot facts identifying one export's input."""

    def test_minimal_construction(self) -> None:
        """Only the snapshot hash is required; the optional facts default to None."""
        revision = Revision(snapshot=_HASH)
        assert revision.snapshot == _HASH
        assert revision.last_edited_at is None
        assert revision.revision is None
        assert revision.fetched_at is None


class TestRevisionSummary:
    """summary() renders the revision as one compact line."""

    def test_snapshot_only(self) -> None:
        """Without an authored name, an em-dash placeholder leads the parenthesized snapshot."""
        assert Revision(snapshot=_HASH).summary() == "revision: — (snapshot: d8666f090982)"

    def test_all_facts(self) -> None:
        """The revision name leads; the snapshot and timestamps follow in one parenthesized group."""
        revision = Revision(
            snapshot=_HASH,
            revision="draft-3",
            last_edited_at=datetime(2026, 7, 11, 18, 22, tzinfo=UTC),
            fetched_at=datetime(2026, 7, 12, 9, 30, tzinfo=UTC),
        )
        assert (
            revision.summary()
            == "revision: draft-3 (snapshot: d8666f090982, edited: 2026-07-11T18:22Z, fetched: 2026-07-12T09:30Z)"
        )
