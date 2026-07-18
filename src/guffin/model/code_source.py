"""The provenance of a code block's content: the GitHub source reference it was snapshotted from.

Public symbols:

- :class:`CodeSource` — where a code block's content was fetched from: the raw GitHub URL,
  the commit SHA the content was actually fetched at, and the fetch date.

A pure value model near the bottom of the ``model/`` conceptual stack: depends only on
``common/``, so any ``model/`` module may depend on it.
"""

import datetime

from pydantic import BaseModel, ConfigDict, Field

from guffin.common.github_url import CommitSha, GitHubFileRef, RawGitHubUrl, parse_raw_github_url


class CodeSource(BaseModel):
    """Where a code block's content was fetched from.

    The three facts a source snapshot needs: the reference the content tracks (``url``, whose
    ref may be a moving branch), the immutable version actually captured (``commit_sha``), and
    when the capture happened (``fetched_date``).

    Attributes:
        url: The ``raw.githubusercontent.com`` URL the content was fetched from
            (:data:`~guffin.common.github_url.RawGitHubUrl` — verbatim text, always parseable
            via :func:`~guffin.common.github_url.parse_raw_github_url`), optionally narrowed
            by a ``#L<n>[-L<m>]`` line-range fragment.
        commit_sha: The full 40-hex commit SHA the content was actually fetched at — immutable
            even when the URL's ref is a branch that has since moved (serialized as
            ``commit-sha``).
        fetched_date: The calendar day the content was fetched (serialized as
            ``fetched-date``); accepts the ISO ``YYYY-MM-DD`` string at validation.
    """

    model_config = ConfigDict(frozen=True, validate_by_name=True)

    url: RawGitHubUrl
    commit_sha: CommitSha = Field(..., serialization_alias="commit-sha")
    fetched_date: datetime.date = Field(..., serialization_alias="fetched-date")

    def file_ref(self) -> GitHubFileRef:
        """Return the decomposed reference the ``url`` denotes.

        Returns:
            The :class:`~guffin.common.github_url.GitHubFileRef` parsed from ``url``; always
            succeeds, since ``url`` is validated at construction.
        """
        return parse_raw_github_url(self.url)
