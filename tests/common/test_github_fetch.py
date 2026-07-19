"""Tests for the guffin.common.github_fetch module."""

import os

import pytest

from guffin.common.github_fetch import fetch_source_at_commit, resolve_commit_sha
from guffin.common.github_file_ref import GitHubFileRef

_SHA: str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class TestResolveCommitSha:
    """resolve_commit_sha() short-circuits SHA refs without any network access."""

    def test_sha_ref_resolves_to_itself(self) -> None:
        """A full-SHA ref is immutable and resolves offline to itself."""
        file_ref = GitHubFileRef(owner="psf", repo="requests", ref=_SHA, path="setup.py")
        assert resolve_commit_sha(file_ref) == _SHA


class TestLiveGitHubFetch:
    """Live tests against real GitHub endpoints (network required)."""

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires network access to github.com")
    def test_resolve_and_fetch_pinned_public_file(self) -> None:
        """A tag-pinned public file resolves to a full SHA and fetches content containing a known line."""
        file_ref = GitHubFileRef(owner="psf", repo="requests", ref="refs/tags/v2.32.3", path="setup.py")
        sha = resolve_commit_sha(file_ref)
        assert len(sha) == 40
        content = fetch_source_at_commit(file_ref, sha)
        assert "setuptools" in content
