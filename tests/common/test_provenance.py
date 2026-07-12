"""Tests for :mod:`guffin.common.provenance`."""

from datetime import UTC, datetime
from typing import Final

import regex

from guffin.common.provenance import UNKNOWN_COMMIT, Provenance, gather_provenance

_FULL_SHA_RE: Final[regex.Pattern[str]] = regex.compile(r"^[0-9a-f]{40}$")


class TestProvenanceSummary:
    """:meth:`Provenance.summary` renders the commit and timestamps as one identifier line."""

    def test_full_summary_with_dirty_and_timestamps(self) -> None:
        """A dirty commit renders a 7-char hash, the -dirty marker, and both ISO times."""
        provenance: Final[Provenance] = Provenance(
            commit="abc123def456789",
            dirty=True,
            committed_at=datetime(2026, 6, 29, 14, 2, 11, tzinfo=UTC),
            exported_at=datetime(2026, 6, 29, 22, 40, 3, tzinfo=UTC),
        )
        summary: Final[str] = provenance.summary()
        assert summary == "guffin, commit: abc123d-dirty, committed: 2026-06-29T14:02Z, exported: 2026-06-29T22:40Z"

    def test_clean_commit_omits_dirty_marker(self) -> None:
        """A clean commit carries no -dirty suffix."""
        provenance: Final[Provenance] = Provenance(commit="abc123", dirty=False)
        assert provenance.summary() == "guffin, commit: abc123"

    def test_missing_timestamps_are_omitted(self) -> None:
        """Absent commit/export timestamps drop their segments rather than rendering None."""
        provenance: Final[Provenance] = Provenance(commit=UNKNOWN_COMMIT)
        assert provenance.summary() == "guffin, commit: unknown"

    def test_extra_fields_render_after_guffin_in_order(self) -> None:
        """Extra key→value facts render as 'key value' segments right after 'guffin', in order."""
        provenance: Final[Provenance] = Provenance(
            commit="abc123",
            exported_at=datetime(2026, 6, 29, 22, 40, 3, tzinfo=UTC),
            extra={"type": "book", "edition": "2"},
        )
        assert provenance.summary() == "guffin, type: book, edition: 2, commit: abc123, exported: 2026-06-29T22:40Z"


class TestGatherProvenance:
    """:func:`gather_provenance` captures the current source commit and export time."""

    def test_captures_commit_and_export_time(self) -> None:
        """Run from the project checkout, it records a full SHA (or 'unknown') and an export time."""
        provenance: Final[Provenance] = gather_provenance()
        assert provenance.exported_at is not None
        assert provenance.commit == UNKNOWN_COMMIT or _FULL_SHA_RE.match(provenance.commit) is not None
        # When a real commit was found, its timestamp is recorded too.
        if provenance.commit != UNKNOWN_COMMIT:
            assert provenance.committed_at is not None
