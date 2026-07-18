"""Tests for the guffin.model.code_source_diagnosis module."""

import pytest

from guffin.model.code_source import CodeSource
from guffin.model.code_source_diagnosis import (
    CodeSourceDiagnosis,
    code_matches_source,
    diagnosed_finding,
)
from guffin.model.vertex import CodeBlockVertex

_TIP_SHA: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_SNAPSHOT_SHA: str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_URL: str = "https://raw.githubusercontent.com/psf/requests/main/setup.py#L2-L3"


def _sourced_vertex(code: str, sha: str = _SNAPSHOT_SHA) -> CodeBlockVertex:
    """A python code block carrying *code* and a code-source snapshot at *sha*."""
    return CodeBlockVertex(
        uid="code00001",
        code=code,
        language="python",
        code_source=CodeSource(url=_URL, commit_sha=sha, fetched_date="2026-07-17"),
    )


class TestCodeMatchesSource:
    """code_matches_source() is the comparison policy: trailing newlines ignored, all else counts."""

    def test_identical_texts_match(self) -> None:
        """Byte-identical texts match."""
        assert code_matches_source("line one\nline two", "line one\nline two")

    def test_trailing_newlines_are_normalized(self) -> None:
        """Trailing-newline differences on either side are ignored."""
        assert code_matches_source("line one\n", "line one")
        assert code_matches_source("line one", "line one\n\n")

    def test_interior_difference_counts(self) -> None:
        """Any non-trailing difference — including interior blank lines — is a mismatch."""
        assert not code_matches_source("line one\n\nline two", "line one\nline two")

    def test_leading_whitespace_counts(self) -> None:
        """Leading whitespace is significant (indentation is code)."""
        assert not code_matches_source("  indented", "indented")


class TestDiagnosedFinding:
    """diagnosed_finding() is the pure three-way judgment over supplied evidence."""

    def test_tip_match_is_verified(self) -> None:
        """A block matching the tip content judges as verified (None), snapshot evidence unused."""
        vertex = _sourced_vertex("the code\n")
        assert diagnosed_finding(vertex, _TIP_SHA, "the code", None) is None

    def test_mismatch_with_unmoved_ref_is_local_modification(self) -> None:
        """A mismatch while the tip IS the recorded commit needs no snapshot evidence."""
        vertex = _sourced_vertex("edited locally", sha=_TIP_SHA)
        finding = diagnosed_finding(vertex, _TIP_SHA, "the code", None)
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.LOCAL_MODIFICATION
        assert "has not moved" in finding.detail

    def test_snapshot_match_is_drift(self) -> None:
        """A block matching the snapshot but not the moved tip has drifted."""
        vertex = _sourced_vertex("the code")
        finding = diagnosed_finding(vertex, _TIP_SHA, "rewritten upstream", "the code")
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.DRIFT
        assert _TIP_SHA[:7] in finding.detail
        assert _SNAPSHOT_SHA[:7] in finding.detail

    def test_matching_neither_is_local_modification(self) -> None:
        """A block matching neither tip nor snapshot was modified locally."""
        vertex = _sourced_vertex("edited locally")
        finding = diagnosed_finding(vertex, _TIP_SHA, "the code", "also not this")
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.LOCAL_MODIFICATION
        assert "neither" in finding.detail

    def test_unsourced_vertex_is_rejected(self) -> None:
        """A vertex without a source reference cannot be judged."""
        vertex = CodeBlockVertex(uid="code00001", code="print(1)", language="python")
        with pytest.raises(ValueError, match="no code-source reference"):
            diagnosed_finding(vertex, _TIP_SHA, "the code", None)

    def test_missing_required_snapshot_evidence_is_rejected(self) -> None:
        """Omitting the snapshot content when the judgment needs it is a contract violation."""
        vertex = _sourced_vertex("edited locally")
        with pytest.raises(ValueError, match="snapshot content is required"):
            diagnosed_finding(vertex, _TIP_SHA, "the code", None)
