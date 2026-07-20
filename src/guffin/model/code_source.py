"""The provenance of a code block's content: the GitHub source reference it was snapshotted from.

Public symbols:

- :class:`CodeSource` — where a code block's content was fetched from: the GitHub blob URL,
  the commit SHA the content was actually fetched at, and the fetch date.

A pure value model near the bottom of the ``model/`` conceptual stack: depends only on
``common/``, so any ``model/`` module may depend on it.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from guffin.common.github_file_ref import BlobGitHubUrl, CommitSha, GitHubFileRef, parse_blob_github_url


class CodeSource(BaseModel):
    """Where a code block's content was fetched from.

    The three facts a source snapshot needs: the reference the content tracks (``url``, whose
    ref may be a moving branch), the immutable version actually captured (``commit_sha``), and
    when the capture happened (``fetched_date``).

    Attributes:
        url: The ``github.com`` blob URL naming the source file at its ref
            (:data:`~guffin.common.github_file_ref.BlobGitHubUrl` — verbatim text, always
            parseable via :func:`~guffin.common.github_file_ref.parse_blob_github_url`),
            optionally narrowed by a ``#L<n>[-L<m>]`` line-range fragment.  The blob form is
            the human-usable click target; the raw content URL a fetch needs is derived from
            the parsed reference, never stored.
        commit_sha: The full 40-hex commit SHA the content was actually fetched at — immutable
            even when the URL's ref is a branch that has since moved (serialized as
            ``commit-sha``).
        fetched_date: The calendar day the content was fetched (serialized as
            ``fetched-date``); accepts the ISO ``YYYY-MM-DD`` string at validation.
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    url: BlobGitHubUrl
    commit_sha: CommitSha = Field(..., serialization_alias="commit-sha")
    fetched_date: datetime.date = Field(..., serialization_alias="fetched-date")

    def file_ref(self) -> GitHubFileRef:
        """Return the decomposed reference the ``url`` denotes.

        Returns:
            The :class:`~guffin.common.github_file_ref.GitHubFileRef` parsed from ``url``; always
            succeeds, since ``url`` is validated at construction.
        """
        return parse_blob_github_url(self.url)
