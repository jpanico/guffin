"""Diagnosis of a code block against its source reference — the pure judgment, with no retrieval.

Given a code block and the source-of-truth evidence (the referenced content at the ref's
current tip, and — when relevant — at the recorded snapshot commit), the verdict is a pure
function: *verified* (the block matches the tip), *drift* (the block matches the recorded
snapshot but the ref has moved on), or *local modification* (the block matches neither).
How the evidence is obtained is not this module's concern.

Public symbols:

- **Enumerations**: :class:`CodeSourceDiagnosis` — what a verification finding means
  (fetch failure / drift / local modification).
- **Models**: :class:`CodeSourceFinding` — one code block's verification failure.
- **Functions**: :func:`code_matches_source` — whether a block's code matches a source text
  (the normalization policy: trailing newlines ignored); :func:`diagnosed_finding` — the
  three-way judgment of a sourced code block over supplied evidence.

Sits near the top of the ``model/`` conceptual stack: it may depend on the structural
primitives (:mod:`~guffin.model.vertex`) and the :mod:`~guffin.model.code_source` value
model, and none of them may depend on it.
"""

import enum
import logging
from typing import Final

from pydantic import BaseModel, ConfigDict, validate_call

from guffin.common.github_file_ref import BlobGitHubUrl, CommitSha
from guffin.model.code_source import CodeSource
from guffin.model.primitives import Uid
from guffin.model.vertex import CodeBlockVertex

logger = logging.getLogger(__name__)


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
        url: The source reference's GitHub blob URL
            (:data:`~guffin.common.github_file_ref.BlobGitHubUrl`), verbatim.
        diagnosis: What the failure means (:class:`CodeSourceDiagnosis`).
        detail: A human-readable elaboration of the diagnosis.
    """

    model_config = ConfigDict(frozen=True)

    uid: Uid
    url: BlobGitHubUrl
    diagnosis: CodeSourceDiagnosis
    detail: str


@validate_call
def code_matches_source(code: str, source_text: str) -> bool:
    """Return whether a block's *code* matches *source_text*, trailing newlines ignored.

    The single comparison policy for code content: a fenced block and a fetched line slice
    legitimately differ in trailing newlines, so those are normalized away; every other
    byte counts.

    Args:
        code: The code block's content.
        source_text: The source text to compare against.

    Returns:
        ``True`` when the two are identical after trailing-newline normalization.
    """
    return code.rstrip("\n") == source_text.rstrip("\n")


@validate_call
def diagnosed_finding(
    vertex: CodeBlockVertex,
    tip_sha: CommitSha,
    tip_content: str,
    snapshot_content: str | None,
) -> CodeSourceFinding | None:
    """Judge a sourced code block against the supplied source-of-truth evidence.

    The pure three-way verdict: a block matching *tip_content* is verified (``None``); a
    mismatched block whose ref has not moved (*tip_sha* equals the recorded snapshot
    commit) was modified locally; otherwise the recorded snapshot disambiguates — a block
    matching *snapshot_content* has drifted (the source moved on), one matching neither
    was modified locally.

    Args:
        vertex: The code-block vertex to judge; must carry a
            :attr:`~guffin.model.vertex.CodeBlockVertex.code_source`.
        tip_sha: The commit the reference's ref currently names.
        tip_content: The referenced source content at *tip_sha*, already line-sliced.
        snapshot_content: The referenced source content at the recorded snapshot commit,
            already line-sliced; required exactly when the judgment needs it (*tip_content*
            mismatches and *tip_sha* is not the recorded commit), ``None`` otherwise.

    Returns:
        ``None`` when the block matches *tip_content*; the :class:`CodeSourceFinding`
        describing the failure otherwise.

    Raises:
        ValueError: If *vertex* carries no source reference, or *snapshot_content* is
            ``None`` when the judgment requires it.
    """
    if vertex.code_source is None:
        raise ValueError(f"code block uid={vertex.uid!r} carries no code-source reference to judge against")
    source: Final[CodeSource] = vertex.code_source
    if code_matches_source(vertex.code, tip_content):
        return None
    if tip_sha == source.commit_sha:
        return CodeSourceFinding(
            uid=vertex.uid,
            url=source.url,
            diagnosis=CodeSourceDiagnosis.LOCAL_MODIFICATION,
            detail="the code block differs from the source at the recorded commit (the ref has not moved)",
        )
    if snapshot_content is None:
        raise ValueError(
            f"code block uid={vertex.uid!r}: snapshot content is required to disambiguate a mismatch "
            f"when the ref has moved (tip {tip_sha[:7]}, snapshot {source.commit_sha[:7]})"
        )
    if code_matches_source(vertex.code, snapshot_content):
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
