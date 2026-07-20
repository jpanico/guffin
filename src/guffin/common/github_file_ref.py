"""GitHub file addressing — :class:`GitHubFileRef` with its string types and URL encodings — with no domain coupling.

Public symbols:

- :data:`COMMIT_SHA_PATTERN` — regex pattern for a full 40-hex git commit SHA;
  :data:`COMMIT_SHA_RE` — compiled :data:`COMMIT_SHA_PATTERN`.
- :data:`LINE_FRAGMENT_PATTERN` — regex pattern for a GitHub line-range URL fragment
  (``L12`` or ``L10-L40``); :data:`LINE_FRAGMENT_RE` — compiled :data:`LINE_FRAGMENT_PATTERN`.
- :data:`GITHUB_HOST` — the main GitHub web hostname, serving the blob viewer;
  :data:`RAW_GITHUB_HOST` — the hostname that serves raw GitHub file content.
- :data:`CommitSha` — a validated full 40-hex git commit SHA string; Pydantic enforces it
  wherever the annotation appears.
- :data:`BlobGitHubUrl` — a validated ``github.com`` blob URL string (one that parses via
  :func:`parse_blob_github_url`); Pydantic enforces it wherever the annotation appears,
  the text kept verbatim.
- :class:`GitHubFileRef` — the structured address of a file in a GitHub repository (owner,
  repo, ref, path, optional :class:`~guffin.common.line_range.LineRange`).
- :func:`verified_commit_sha` — return a string after verifying it is a full 40-hex commit SHA.
- :func:`verified_blob_github_url` — return a string after verifying it parses as a GitHub
  blob URL.
- :func:`parse_blob_github_url` — decompose a ``github.com`` blob URL into a
  :class:`GitHubFileRef`.
- :func:`raw_github_url` — the raw-content URL for a :class:`GitHubFileRef`, optionally
  re-pinned at a commit SHA.
- :func:`blob_github_url` — the human-facing ``github.com`` blob URL for a
  :class:`GitHubFileRef`, optionally re-pinned at a commit SHA, line-range fragment included.
"""

from typing import Annotated, Final
from urllib.parse import urlsplit

import regex
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, validate_call

from guffin.common.line_range import LineRange

COMMIT_SHA_PATTERN: Final[str] = r"[0-9a-f]{40}"
"""Regex pattern for a full 40-hex git commit SHA, lowercase.

Unanchored; ``fullmatch`` against it to test whether a string is *wholly* such a SHA.
Abbreviated SHAs deliberately do not match: a full SHA names a commit immutably and
unambiguously, which is what a recorded reference needs.
"""

COMMIT_SHA_RE: Final[regex.Pattern[str]] = regex.compile(COMMIT_SHA_PATTERN)
"""Compiled :data:`COMMIT_SHA_PATTERN`."""

LINE_FRAGMENT_PATTERN: Final[str] = r"L(?P<start>\d+)(?:-L(?P<end>\d+))?"
"""Regex pattern for a GitHub line-range URL fragment: ``L12`` (one line) or ``L10-L40`` (a range).

Unanchored; ``fullmatch`` against it to test whether a URL fragment is *wholly* such a range.
Captures named groups ``start`` and (for the two-ended form) ``end``.
"""

LINE_FRAGMENT_RE: Final[regex.Pattern[str]] = regex.compile(LINE_FRAGMENT_PATTERN)
"""Compiled :data:`LINE_FRAGMENT_PATTERN`."""

RAW_GITHUB_HOST: Final[str] = "raw.githubusercontent.com"
"""The hostname that serves raw GitHub file content."""

GITHUB_HOST: Final[str] = "github.com"
"""The main GitHub web hostname — the one serving the human-facing blob viewer."""

_BLOB_SEGMENT: Final[str] = "blob"
_REF_QUALIFIER_SEGMENT: Final[str] = "refs"
_REF_KIND_SEGMENTS: Final[frozenset[str]] = frozenset({"heads", "tags"})
_REF_QUALIFIER_PREFIXES: Final[tuple[str, ...]] = tuple(f"refs/{kind}/" for kind in sorted(_REF_KIND_SEGMENTS))


def _checked_commit_sha(sha_text: str) -> str:
    """Return *sha_text* after checking it is a full 40-hex git commit SHA.

    Args:
        sha_text: The candidate SHA string.

    Returns:
        *sha_text*, unchanged.

    Raises:
        ValueError: If *sha_text* is not wholly 40 lowercase hex digits.
    """
    if COMMIT_SHA_RE.fullmatch(sha_text) is None:
        raise ValueError(f"commit sha {sha_text!r} is not a full 40-hex git commit SHA")
    return sha_text


type CommitSha = Annotated[str, AfterValidator(_checked_commit_sha)]
"""A validated full 40-hex git commit SHA string, lowercase.

The annotation carries the check, so Pydantic enforces it wherever the type appears (model
fields, ``@validate_call`` parameters).  To validate imperatively, use
:func:`verified_commit_sha`.
"""


@validate_call
def verified_commit_sha(sha_text: str) -> CommitSha:
    """Return *sha_text* after verifying it is a full 40-hex git commit SHA.

    The imperative form of :data:`CommitSha`: applies the same check the annotation carries.

    Args:
        sha_text: The candidate SHA string.

    Returns:
        *sha_text*, unchanged, established as a :data:`CommitSha`.

    Raises:
        ValueError: If *sha_text* is not wholly 40 lowercase hex digits.
    """
    return _checked_commit_sha(sha_text)


class GitHubFileRef(BaseModel):
    """The structured address of a file in a GitHub repository.

    The decomposed form of a ``github.com`` blob URL (see :func:`parse_blob_github_url`):
    which file, in which repository, at which ref, optionally narrowed to a line range.

    Attributes:
        owner: The repository owner (user or organization).
        repo: The repository name.
        ref: The git ref naming the content version — a branch, a tag, a commit SHA, or the
            fully-qualified ``refs/heads/<branch>`` / ``refs/tags/<tag>`` form.
        path: The repository-relative file path, no leading slash.
        line_range: The line range the reference is narrowed to, or ``None`` for the whole
            file (serialized as ``line-range``).
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    owner: str = Field(..., min_length=1)
    repo: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)
    line_range: LineRange | None = Field(default=None, serialization_alias="line-range")

    @property
    def ref_name(self) -> str:
        """The human-meaningful ref name: ``ref`` with any ``refs/heads/`` or ``refs/tags/`` prefix stripped."""
        for prefix in _REF_QUALIFIER_PREFIXES:
            if self.ref.startswith(prefix):
                return self.ref.removeprefix(prefix)
        return self.ref

    @property
    def is_sha_ref(self) -> bool:
        """Whether ``ref`` is itself a full 40-hex commit SHA — an immutable reference needing no resolution."""
        return COMMIT_SHA_RE.fullmatch(self.ref) is not None


def _parsed_line_range(fragment: str) -> LineRange | None:
    """Return the :class:`LineRange` a URL *fragment* denotes, or ``None`` for an empty fragment.

    Args:
        fragment: The URL fragment, without its leading ``#`` (as :func:`urllib.parse.urlsplit`
            yields it); empty when the URL carries none.

    Returns:
        The parsed range — ``L12`` yields the single-line range 12-12 — or ``None`` when
        *fragment* is empty.

    Raises:
        ValueError: If *fragment* is non-empty but not a line-range fragment.
    """
    if not fragment:
        return None
    fragment_match: Final[regex.Match[str] | None] = LINE_FRAGMENT_RE.fullmatch(fragment)
    if fragment_match is None:
        raise ValueError(f"URL fragment {fragment!r} is not a line range (L<n> or L<n>-L<m>)")
    start: Final[int] = int(fragment_match.group("start"))
    end_text: Final[str | None] = fragment_match.group("end")
    return LineRange(start=start, end=int(end_text) if end_text is not None else start)


@validate_call
def parse_blob_github_url(url: str) -> GitHubFileRef:
    """Decompose a ``github.com`` blob URL into a :class:`GitHubFileRef`.

    The URL path must be ``/<owner>/<repo>/blob/<ref>/<file-path>``, where ``<ref>`` is a
    single segment (a branch, tag, or commit SHA) or the three-segment qualified form
    ``refs/heads/<branch>`` / ``refs/tags/<tag>``.  A branch or tag name containing ``/`` is
    ambiguous in the single-segment form and is not supported.  An optional ``#L<n>`` or
    ``#L<n>-L<m>`` fragment narrows the reference to a line range.

    Args:
        url: The candidate GitHub blob URL.

    Returns:
        The decomposed reference.

    Raises:
        ValueError: If *url* is not https, is not hosted on ``github.com``, carries a query
            string, lacks the ``blob`` path segment, has too few or empty path segments, or
            carries a fragment that is not a line range.
    """
    split_url: Final = urlsplit(url)
    if split_url.scheme != "https":
        raise ValueError(f"GitHub blob URL {url!r} must use the https scheme")
    if split_url.hostname != GITHUB_HOST:
        raise ValueError(f"GitHub blob URL {url!r} is not hosted on {GITHUB_HOST}")
    if split_url.query:
        raise ValueError(f"GitHub blob URL {url!r} must not carry a query string")
    segments: Final[list[str]] = split_url.path.strip("/").split("/")
    if len(segments) < 5 or any(not segment for segment in segments):
        raise ValueError(f"GitHub blob URL {url!r} needs a /<owner>/<repo>/blob/<ref>/<file-path> path")
    if segments[2] != _BLOB_SEGMENT:
        raise ValueError(f"GitHub blob URL {url!r} needs {_BLOB_SEGMENT!r} as its third path segment")
    qualified: Final[bool] = segments[3] == _REF_QUALIFIER_SEGMENT and segments[4] in _REF_KIND_SEGMENTS
    ref_length: Final[int] = 3 if qualified else 1
    if len(segments) < 4 + ref_length:
        raise ValueError(f"GitHub blob URL {url!r} has a qualified ref but no file path")
    return GitHubFileRef(
        owner=segments[0],
        repo=segments[1],
        ref="/".join(segments[3 : 3 + ref_length]),
        path="/".join(segments[3 + ref_length :]),
        line_range=_parsed_line_range(split_url.fragment),
    )


def _checked_blob_github_url(url_text: str) -> str:
    """Return *url_text* after checking it parses as a GitHub blob URL.

    Args:
        url_text: The candidate URL string.

    Returns:
        *url_text*, unchanged — the verbatim text, with the parse result discarded (derive
        it on demand via :func:`parse_blob_github_url`).

    Raises:
        ValueError: If *url_text* is not a parseable GitHub blob URL (see
            :func:`parse_blob_github_url`).
    """
    parse_blob_github_url(url_text)
    return url_text


type BlobGitHubUrl = Annotated[str, AfterValidator(_checked_blob_github_url)]
"""A validated ``github.com`` blob URL string, kept verbatim.

The annotation carries the full grammar check — the string parses via
:func:`parse_blob_github_url` — so Pydantic enforces it wherever the type appears, while the
text itself stays exactly as authored (the decomposed form is derived on demand, not
stored).  To validate imperatively, use :func:`verified_blob_github_url`.
"""


@validate_call
def verified_blob_github_url(url_text: str) -> BlobGitHubUrl:
    """Return *url_text* after verifying it parses as a GitHub blob URL.

    The imperative form of :data:`BlobGitHubUrl`: applies the same check the annotation
    carries.

    Args:
        url_text: The candidate URL string.

    Returns:
        *url_text*, unchanged, established as a :data:`BlobGitHubUrl`.

    Raises:
        ValueError: If *url_text* is not a parseable GitHub blob URL (see
            :func:`parse_blob_github_url`).
    """
    return _checked_blob_github_url(url_text)


@validate_call
def raw_github_url(file_ref: GitHubFileRef, commit_sha: CommitSha | None = None) -> str:
    """Return the ``raw.githubusercontent.com`` content URL for *file_ref*.

    The URL carries no line-range fragment: raw content is always the whole file, with any
    narrowing applied by the consumer.

    Args:
        file_ref: The reference to build the URL for.
        commit_sha: When given, pins the URL at this commit instead of ``file_ref.ref`` —
            an immutable URL naming exactly one version of the file.

    Returns:
        The raw-content URL.
    """
    ref: Final[str] = commit_sha if commit_sha is not None else file_ref.ref
    return f"https://{RAW_GITHUB_HOST}/{file_ref.owner}/{file_ref.repo}/{ref}/{file_ref.path}"


@validate_call
def blob_github_url(file_ref: GitHubFileRef, commit_sha: CommitSha | None = None) -> str:
    """Return the human-facing ``github.com`` blob URL for *file_ref*.

    The blob page renders the file with GitHub's viewer; a line range carries over as the
    fragment GitHub's viewer highlights (``#L12`` for a single line, ``#L10-L40`` for a range).

    Args:
        file_ref: The reference to build the URL for.
        commit_sha: When given, pins the URL at this commit instead of ``file_ref.ref`` —
            a link that shows the referenced version even after the ref moves on.

    Returns:
        The blob URL, line-range fragment included when *file_ref* carries one.
    """
    ref: Final[str] = commit_sha if commit_sha is not None else file_ref.ref
    base: Final[str] = f"https://{GITHUB_HOST}/{file_ref.owner}/{file_ref.repo}/{_BLOB_SEGMENT}/{ref}/{file_ref.path}"
    if file_ref.line_range is None:
        return base
    if file_ref.line_range.start == file_ref.line_range.end:
        return f"{base}#L{file_ref.line_range.start}"
    return f"{base}#L{file_ref.line_range.start}-L{file_ref.line_range.end}"
