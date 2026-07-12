"""Unit tests for guffin.common.revision."""

from datetime import UTC, datetime

from guffin.common.revision import Revision

_HASH = "d8666f090982aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class TestRevision:
    """Revision models the content-snapshot facts identifying one export's input."""

    def test_minimal_construction(self) -> None:
        """Only the content hash is required; the optional facts default to None."""
        revision = Revision(content_hash=_HASH)
        assert revision.content_hash == _HASH
        assert revision.last_edited_at is None
        assert revision.label is None
        assert revision.fetched_at is None


class TestRevisionSummary:
    """summary() renders the revision as one compact line."""

    def test_hash_only(self) -> None:
        """A minimal revision renders the shortened hash alone."""
        assert Revision(content_hash=_HASH).summary() == "rev d8666f090982"

    def test_all_facts(self) -> None:
        """Label and timestamps follow the hash, dot-separated."""
        revision = Revision(
            content_hash=_HASH,
            label="draft-3",
            last_edited_at=datetime(2026, 7, 11, 18, 22, tzinfo=UTC),
            fetched_at=datetime(2026, 7, 12, 9, 30, tzinfo=UTC),
        )
        assert (
            revision.summary()
            == "rev d8666f090982 · label draft-3 · edited 2026-07-11T18:22Z · fetched 2026-07-12T09:30Z"
        )
