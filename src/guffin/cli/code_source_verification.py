"""Verification of code blocks' GitHub source references against the source of truth.

The effectful half of code-source verification: gathers the source-of-truth evidence for
every sourced, render-visible code block (retrieval via :mod:`~guffin.common.github_fetch`,
line narrowing via :mod:`~guffin.common.line_range`) and hands it to the pure judgment in
:mod:`~guffin.model.code_source_diagnosis`, accumulating every failure into the returned
findings — the caller decides what a non-empty result means (advisory warnings, a hard
abort, …).

Public symbols:

- **Functions**: :func:`verify_code_source` — gather evidence for one code block and judge
  it against its source reference; :func:`verify_code_sources` — verify every sourced,
  render-visible code block in a :class:`~guffin.model.vertex_tree.VertexTree`, returning
  every accumulated :class:`~guffin.model.code_source_diagnosis.CodeSourceFinding`.
"""

import logging
from typing import Final

import requests
from pydantic import validate_call

from guffin.common.github_fetch import fetch_source_at_commit, resolve_commit_sha
from guffin.common.github_url import CommitSha, GitHubFileRef
from guffin.common.line_range import sliced_line_range
from guffin.model.code_source import CodeSource
from guffin.model.code_source_diagnosis import (
    CodeSourceDiagnosis,
    CodeSourceFinding,
    code_matches_source,
    diagnosed_finding,
)
from guffin.model.vertex import CodeBlockVertex
from guffin.model.vertex_tree import VertexTree, transcluded_vertices

logger = logging.getLogger(__name__)


def _fetched_slice(file_ref: GitHubFileRef, commit_sha: CommitSha) -> str:
    """Return the referenced content at *commit_sha*, narrowed to the reference's line range.

    Args:
        file_ref: The reference naming the file and optional line range.
        commit_sha: The commit to fetch the file at.

    Returns:
        The line-sliced content.

    Raises:
        requests.RequestException: If the fetch fails.
        ValueError: If the reference's line range exceeds the fetched file.
    """
    return sliced_line_range(fetch_source_at_commit(file_ref, commit_sha), file_ref.line_range)


@validate_call
def verify_code_source(vertex: CodeBlockVertex) -> CodeSourceFinding | None:
    """Gather source-of-truth evidence for *vertex* and judge its code against it.

    Resolves the reference's ref to its current tip, fetches and line-slices the content
    there, and — only when the judgment requires disambiguation (a mismatch while the ref
    has moved) — fetches the content at the recorded snapshot commit too.  The verdict
    itself is :func:`~guffin.model.code_source_diagnosis.diagnosed_finding`; any retrieval
    failure (network or HTTP error, unresolvable ref, out-of-range line slice) becomes a
    :attr:`~guffin.model.code_source_diagnosis.CodeSourceDiagnosis.FETCH_FAILURE` finding.
    A vertex carrying no source reference verifies trivially.

    Args:
        vertex: The code-block vertex to verify.

    Returns:
        ``None`` when the code matches the source at the ref's current tip (or the vertex is
        unsourced); the :class:`~guffin.model.code_source_diagnosis.CodeSourceFinding`
        describing the failure otherwise.
    """
    if vertex.code_source is None:
        return None
    source: Final[CodeSource] = vertex.code_source
    file_ref: Final[GitHubFileRef] = source.file_ref()
    try:
        tip_sha: Final[CommitSha] = resolve_commit_sha(file_ref)
        tip_content: Final[str] = _fetched_slice(file_ref, tip_sha)
    except (requests.RequestException, ValueError) as exc:
        return CodeSourceFinding(
            uid=vertex.uid, url=source.url, diagnosis=CodeSourceDiagnosis.FETCH_FAILURE, detail=str(exc)
        )
    # The snapshot fetch is evidence-gathering for the judgment's disambiguation branch;
    # it is needed exactly when the tip mismatches and the ref has moved off the snapshot.
    needs_snapshot: Final[bool] = not code_matches_source(vertex.code, tip_content) and tip_sha != source.commit_sha
    snapshot_content: str | None = None
    if needs_snapshot:
        try:
            snapshot_content = _fetched_slice(file_ref, source.commit_sha)
        except (requests.RequestException, ValueError) as exc:
            return CodeSourceFinding(
                uid=vertex.uid, url=source.url, diagnosis=CodeSourceDiagnosis.FETCH_FAILURE, detail=str(exc)
            )
    return diagnosed_finding(vertex, tip_sha, tip_content, snapshot_content)


@validate_call
def verify_code_sources(tree: VertexTree) -> tuple[CodeSourceFinding, ...]:
    """Verify every sourced, render-visible code block in *tree* against its source reference.

    Walks the render-visible vertices (:func:`~guffin.model.vertex_tree.transcluded_vertices`
    — tree vertices plus embed-transcluded content) and verifies each
    :class:`~guffin.model.vertex.CodeBlockVertex` carrying a source reference.  Every block
    is checked, so the result carries all findings at once; the caller decides what a
    non-empty result means.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to verify.

    Returns:
        One :class:`~guffin.model.code_source_diagnosis.CodeSourceFinding` per failing
        block, in document order; empty when every sourced block verifies.
    """
    findings: Final[list[CodeSourceFinding]] = []
    for vertex in transcluded_vertices(tree):
        if not isinstance(vertex, CodeBlockVertex) or vertex.code_source is None:
            continue
        finding: CodeSourceFinding | None = verify_code_source(vertex)
        if finding is not None:
            findings.append(finding)
    return tuple(findings)
