"""Tests for the guffin.cli.code_source_verification module."""

import pytest
import requests

import guffin.cli.code_source_verification as csv_module
from guffin.cli.code_source_verification import verify_code_source, verify_code_sources
from guffin.common.github_file_ref import GitHubFileRef
from guffin.model.code_source import CodeSource
from guffin.model.code_source_diagnosis import CodeSourceDiagnosis
from guffin.model.vertex import CodeBlockVertex, PageVertex
from guffin.model.vertex_tree import VertexTree

_TIP_SHA: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_SNAPSHOT_SHA: str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
_URL: str = "https://github.com/psf/requests/blob/main/setup.py#L2-L3"
_FILE_TEXT: str = "line one\nline two\nline three\nline four\n"


def _sourced_vertex(code: str, uid: str = "code00001", sha: str = _SNAPSHOT_SHA) -> CodeBlockVertex:
    """A python code block carrying *code* and a code-source snapshot at *sha*."""
    return CodeBlockVertex(
        uid=uid,
        code=code,
        language="python",
        code_source=CodeSource(url=_URL, commit_sha=sha, fetched_date="2026-07-17"),
    )


def _patch_github(
    monkeypatch: pytest.MonkeyPatch,
    tip_sha: str,
    contents_by_sha: dict[str, str],
) -> list[str]:
    """Fake the two network functions; return the list of SHAs fetch was called with."""
    fetched: list[str] = []

    def _fake_resolve(file_ref: GitHubFileRef) -> str:
        return tip_sha

    def _fake_fetch(file_ref: GitHubFileRef, commit_sha: str) -> str:
        fetched.append(commit_sha)
        return contents_by_sha[commit_sha]

    monkeypatch.setattr(csv_module, "resolve_commit_sha", _fake_resolve)
    monkeypatch.setattr(csv_module, "fetch_source_at_commit", _fake_fetch)
    return fetched


class TestVerifyCodeSource:
    """verify_code_source() diagnoses match, drift, local modification, and fetch failure."""

    def test_matching_tip_verifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Code matching the tip slice (trailing newline ignored) verifies as None."""
        _patch_github(monkeypatch, _TIP_SHA, {_TIP_SHA: _FILE_TEXT})
        vertex = _sourced_vertex("line two\nline three\n")
        assert verify_code_source(vertex) is None

    def test_unsourced_vertex_verifies_trivially(self) -> None:
        """A code block with no source reference verifies with no network access."""
        vertex = CodeBlockVertex(uid="code00001", code="print(1)", language="python")
        assert verify_code_source(vertex) is None

    def test_drift_diagnosed_when_snapshot_still_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Code matching the recorded snapshot but not the moved tip is drift."""
        moved_text = _FILE_TEXT.replace("line two", "line 2.0")
        _patch_github(monkeypatch, _TIP_SHA, {_TIP_SHA: moved_text, _SNAPSHOT_SHA: _FILE_TEXT})
        finding = verify_code_source(_sourced_vertex("line two\nline three"))
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.DRIFT
        assert _TIP_SHA[:7] in finding.detail
        assert _SNAPSHOT_SHA[:7] in finding.detail

    def test_local_modification_when_ref_unmoved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A mismatch while the tip IS the recorded commit is a local modification (one fetch only)."""
        fetched = _patch_github(monkeypatch, _SNAPSHOT_SHA, {_SNAPSHOT_SHA: _FILE_TEXT})
        finding = verify_code_source(_sourced_vertex("edited locally"))
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.LOCAL_MODIFICATION
        assert fetched == [_SNAPSHOT_SHA]

    def test_local_modification_when_matching_neither(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Code matching neither tip nor snapshot is a local modification."""
        _patch_github(monkeypatch, _TIP_SHA, {_TIP_SHA: _FILE_TEXT, _SNAPSHOT_SHA: _FILE_TEXT})
        finding = verify_code_source(_sourced_vertex("edited locally"))
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.LOCAL_MODIFICATION
        assert "neither" in finding.detail

    def test_fetch_failure_diagnosed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A network error during resolution is a fetch failure carrying the error text."""

        def _raising(file_ref: GitHubFileRef) -> str:
            raise requests.ConnectionError("no route to host")

        monkeypatch.setattr(csv_module, "resolve_commit_sha", _raising)
        finding = verify_code_source(_sourced_vertex("line two"))
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.FETCH_FAILURE
        assert "no route to host" in finding.detail

    def test_out_of_range_line_slice_is_fetch_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A line range exceeding the fetched file is a fetch failure, not a crash."""
        _patch_github(monkeypatch, _TIP_SHA, {_TIP_SHA: "only one line"})
        finding = verify_code_source(_sourced_vertex("line two"))
        assert finding is not None
        assert finding.diagnosis is CodeSourceDiagnosis.FETCH_FAILURE
        assert "exceeds" in finding.detail


class TestVerifyCodeSources:
    """verify_code_sources() returns every finding accumulated across the render-visible tree."""

    def test_tree_without_sourced_blocks_passes_offline(self) -> None:
        """A tree with no sourced code blocks verifies to no findings without any network access."""
        page = PageVertex(uid="page00001", title="P", children=["code00001"])
        code = CodeBlockVertex(uid="code00001", code="print(1)", language="python")
        assert verify_code_sources(VertexTree(tree_vertices=[page, code])) == ()

    def test_all_findings_accumulate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two failing blocks both appear in the returned findings, in document order."""
        _patch_github(monkeypatch, _SNAPSHOT_SHA, {_SNAPSHOT_SHA: _FILE_TEXT})
        page = PageVertex(uid="page00001", title="P", children=["code00001", "code00002"])
        bad_one = _sourced_vertex("edited one", uid="code00001")
        bad_two = _sourced_vertex("edited two", uid="code00002")
        tree = VertexTree(tree_vertices=[page, bad_one, bad_two])
        findings = verify_code_sources(tree)
        assert [finding.uid for finding in findings] == ["code00001", "code00002"]

    def test_passing_tree_returns_no_findings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A tree whose sourced blocks all match verifies to an empty result."""
        _patch_github(monkeypatch, _TIP_SHA, {_TIP_SHA: _FILE_TEXT})
        page = PageVertex(uid="page00001", title="P", children=["code00001"])
        good = _sourced_vertex("line two\nline three")
        assert verify_code_sources(VertexTree(tree_vertices=[page, good])) == ()
