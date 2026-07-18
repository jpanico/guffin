"""Verification of code blocks' GitHub source references against the source of truth.

Fetches the referenced content for every code block carrying a
:class:`~guffin.model.code_source.CodeSource` and compares it against the block's own code,
diagnosing any difference: *drift* (the source has moved on since the snapshot), *local
modification* (the block no longer matches even the recorded snapshot), or *fetch failure*
(the reference could not be retrieved at all).

Public symbols:

- :data:`GITHUB_TOKEN_ENV_VAR` — the environment variable naming an optional GitHub token
  that raises the API rate limit for ref resolution.
- **Enumerations**: :class:`CodeSourceDiagnosis` — what a verification finding means
  (fetch failure / drift / local modification).
- **Models**: :class:`CodeSourceFinding` — one code block's verification failure.
- **Exceptions**: :class:`CodeSourceVerificationError` — raised when any code block fails
  verification, carrying every finding.
- **Functions**: :func:`resolve_commit_sha` — resolve a reference's ref to its current tip
  commit SHA (a SHA ref resolves to itself without any network call);
  :func:`fetch_source_at_commit` — fetch the referenced file's content at a specific commit;
  :func:`verify_code_source` — verify one code block against its source reference;
  :func:`verify_code_sources` — verify every sourced, render-visible code block in a
  :class:`~guffin.model.vertex_tree.VertexTree`, accumulating all findings before raising.
"""

import enum
import logging
import os
from typing import Final

import requests
from pydantic import BaseModel, ConfigDict, validate_call

from guffin.common.github_url import (
    CommitSha,
    GitHubFileRef,
    RawGitHubUrl,
    raw_github_url,
    verified_commit_sha,
)
from guffin.common.line_range import sliced_line_range
from guffin.model.code_source import CodeSource
from guffin.model.primitives import Uid
from guffin.model.vertex import CodeBlockVertex
from guffin.model.vertex_tree import VertexTree, transcluded_vertices

logger = logging.getLogger(__name__)

GITHUB_TOKEN_ENV_VAR: Final[str] = "GUFFIN_GITHUB_TOKEN"
"""Environment variable naming an optional GitHub token for ref resolution.

When set, the token is sent as a bearer credential on ``api.github.com`` requests, raising
the rate limit from 60 requests/hour (per IP, unauthenticated) to 5,000/hour (per token).
It is deliberately never sent to ``raw.githubusercontent.com`` — content fetches need no
credential for public repositories, and the fewer places a credential travels the better.
"""

_GITHUB_API_ROOT: Final[str] = "https://api.github.com"
_REQUEST_TIMEOUT_SECONDS: Final[float] = 30.0


class CodeSourceDiagnosis(enum.StrEnum):
    """What a code block's verification failure means.

    Attributes:
        FETCH_FAILURE: The reference could not be retrieved — a network or HTTP error, an
            unresolvable ref, or a line range exceeding the fetched file.
        DRIFT: The code block matches the content at its recorded snapshot commit, but the
            reference's ref has since moved to different content.
        LOCAL_MODIFICATION: The code block matches neither the current source nor the
            recorded snapshot — the block itself was edited after the snapshot.
    """

    FETCH_FAILURE = "fetch-failure"
    DRIFT = "drift"
    LOCAL_MODIFICATION = "local-modification"


class CodeSourceFinding(BaseModel):
    """One code block's source-verification failure.

    Attributes:
        uid: The failing code-block vertex's uid.
        url: The source reference's raw GitHub URL
            (:data:`~guffin.common.github_url.RawGitHubUrl`), verbatim.
        diagnosis: What the failure means (:class:`CodeSourceDiagnosis`).
        detail: A human-readable elaboration of the diagnosis.
    """

    model_config = ConfigDict(frozen=True)

    uid: Uid
    url: RawGitHubUrl
    diagnosis: CodeSourceDiagnosis
    detail: str


class CodeSourceVerificationError(Exception):
    """Raised when one or more code blocks fail source verification.

    Attributes:
        findings: Every :class:`CodeSourceFinding` accumulated across the verified tree.
    """

    def __init__(self, findings: tuple[CodeSourceFinding, ...]) -> None:
        """Initialize with the accumulated *findings*."""
        super().__init__(f"{len(findings)} code block(s) failed source verification")
        self.findings: Final[tuple[CodeSourceFinding, ...]] = findings


def _auth_headers() -> dict[str, str]:
    """Return the bearer-credential headers for an ``api.github.com`` request.

    Returns:
        ``{"Authorization": "Bearer <token>"}`` when :data:`GITHUB_TOKEN_ENV_VAR` is set to a
        non-empty value; empty otherwise.
    """
    token: Final[str | None] = os.environ.get(GITHUB_TOKEN_ENV_VAR)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


@validate_call
def resolve_commit_sha(file_ref: GitHubFileRef) -> CommitSha:
    """Return the current tip commit SHA that *file_ref*'s ref names.

    A ref that is already a full commit SHA resolves to itself without any network call —
    it is immutable.  Any other ref (branch, tag, abbreviated SHA) is resolved via the
    GitHub API's commits endpoint, which returns the bare tip SHA under the
    ``application/vnd.github.sha`` media type.

    Args:
        file_ref: The reference whose ref to resolve.

    Returns:
        The full 40-hex commit SHA the ref currently names.

    Raises:
        requests.RequestException: If the API request fails (network error or HTTP error
            status).
        ValueError: If the API response is not a full commit SHA.
    """
    if file_ref.is_sha_ref:
        return file_ref.ref
    url: Final[str] = f"{_GITHUB_API_ROOT}/repos/{file_ref.owner}/{file_ref.repo}/commits/{file_ref.ref_name}"
    headers: Final[dict[str, str]] = {"Accept": "application/vnd.github.sha", **_auth_headers()}
    response: Final[requests.Response] = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return verified_commit_sha(response.text.strip())


@validate_call
def fetch_source_at_commit(file_ref: GitHubFileRef, commit_sha: CommitSha) -> str:
    """Return the referenced file's full content at *commit_sha*.

    Fetches the SHA-pinned raw URL — immutable, so the response is exactly the file as it
    existed at that commit, immune to the raw host's branch-URL caching.  No credential is
    sent (see :data:`GITHUB_TOKEN_ENV_VAR`).

    Args:
        file_ref: The reference naming the file to fetch.
        commit_sha: The commit to fetch the file at.

    Returns:
        The file's text content, whole — any line range on *file_ref* is not applied.

    Raises:
        requests.RequestException: If the fetch fails (network error or HTTP error status).
    """
    url: Final[str] = raw_github_url(file_ref, commit_sha=commit_sha)
    response: Final[requests.Response] = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _normalized(code: str) -> str:
    """Return *code* with trailing newlines stripped, the comparison form for code content."""
    return code.rstrip("\n")


@validate_call
def verify_code_source(vertex: CodeBlockVertex) -> CodeSourceFinding | None:
    """Verify *vertex*'s code against its source reference, returning a finding on failure.

    Fetches the referenced content at the ref's current tip and compares (trailing newlines
    ignored).  On a mismatch, the recorded snapshot commit disambiguates the diagnosis: a
    block matching the snapshot but not the tip has *drifted* (the source moved on), while a
    block matching neither was *locally modified*.  A vertex carrying no source reference
    verifies trivially.

    Args:
        vertex: The code-block vertex to verify.

    Returns:
        ``None`` when the code matches the source at the ref's current tip (or the vertex is
        unsourced); the :class:`CodeSourceFinding` describing the failure otherwise.
    """
    if vertex.code_source is None:
        return None
    source: Final[CodeSource] = vertex.code_source
    file_ref: Final[GitHubFileRef] = source.file_ref()
    try:
        tip_sha: Final[CommitSha] = resolve_commit_sha(file_ref)
        tip_slice: Final[str] = sliced_line_range(fetch_source_at_commit(file_ref, tip_sha), file_ref.line_range)
    except (requests.RequestException, ValueError) as exc:
        return CodeSourceFinding(
            uid=vertex.uid, url=source.url, diagnosis=CodeSourceDiagnosis.FETCH_FAILURE, detail=str(exc)
        )
    if _normalized(vertex.code) == _normalized(tip_slice):
        return None
    if tip_sha == source.commit_sha:
        return CodeSourceFinding(
            uid=vertex.uid,
            url=source.url,
            diagnosis=CodeSourceDiagnosis.LOCAL_MODIFICATION,
            detail="the code block differs from the source at the recorded commit (the ref has not moved)",
        )
    try:
        recorded_slice: Final[str] = sliced_line_range(
            fetch_source_at_commit(file_ref, source.commit_sha), file_ref.line_range
        )
    except (requests.RequestException, ValueError) as exc:
        return CodeSourceFinding(
            uid=vertex.uid, url=source.url, diagnosis=CodeSourceDiagnosis.FETCH_FAILURE, detail=str(exc)
        )
    if _normalized(vertex.code) == _normalized(recorded_slice):
        return CodeSourceFinding(
            uid=vertex.uid,
            url=source.url,
            diagnosis=CodeSourceDiagnosis.DRIFT,
            detail=(
                f"the source has moved on since the snapshot: the ref's tip is {tip_sha[:7]}, "
                f"the snapshot was {source.commit_sha[:7]}"
            ),
        )
    return CodeSourceFinding(
        uid=vertex.uid,
        url=source.url,
        diagnosis=CodeSourceDiagnosis.LOCAL_MODIFICATION,
        detail="the code block matches neither the recorded snapshot nor the current source",
    )


@validate_call
def verify_code_sources(tree: VertexTree) -> None:
    """Verify every sourced, render-visible code block in *tree* against its source reference.

    Walks the render-visible vertices (:func:`~guffin.model.vertex_tree.transcluded_vertices`
    — tree vertices plus embed-transcluded content) and verifies each
    :class:`~guffin.model.vertex.CodeBlockVertex` carrying a source reference.  Every block
    is checked before any failure is raised, so the error carries all findings at once.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to verify.

    Raises:
        CodeSourceVerificationError: If any sourced code block fails verification; carries
            one :class:`CodeSourceFinding` per failing block.
    """
    findings: Final[list[CodeSourceFinding]] = []
    for vertex in transcluded_vertices(tree):
        if not isinstance(vertex, CodeBlockVertex) or vertex.code_source is None:
            continue
        finding: CodeSourceFinding | None = verify_code_source(vertex)
        if finding is not None:
            findings.append(finding)
    if findings:
        raise CodeSourceVerificationError(tuple(findings))
