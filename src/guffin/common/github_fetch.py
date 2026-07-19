"""GitHub content fetching — ref resolution and commit-pinned file retrieval — with no domain coupling.

Public symbols:

- :data:`GITHUB_TOKEN_ENV_VAR` — the environment variable naming an optional GitHub token
  that raises the API rate limit for ref resolution.
- :func:`resolve_commit_sha` — resolve a reference's ref to its current tip commit SHA
  (a SHA ref resolves to itself without any network call).
- :func:`fetch_source_at_commit` — fetch the referenced file's content at a specific commit,
  via the immutable SHA-pinned raw URL.
"""

import os
from typing import Final

import requests
from pydantic import validate_call

from guffin.common.github_file_ref import CommitSha, GitHubFileRef, raw_github_url, verified_commit_sha

GITHUB_TOKEN_ENV_VAR: Final[str] = "GUFFIN_GITHUB_TOKEN"
"""Environment variable naming an optional GitHub token for ref resolution.

When set, the token is sent as a bearer credential on ``api.github.com`` requests, raising
the rate limit from 60 requests/hour (per IP, unauthenticated) to 5,000/hour (per token).
It is deliberately never sent to ``raw.githubusercontent.com`` — content fetches need no
credential for public repositories, and the fewer places a credential travels the better.
"""

_GITHUB_API_ROOT: Final[str] = "https://api.github.com"
_REQUEST_TIMEOUT_SECONDS: Final[float] = 30.0


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
