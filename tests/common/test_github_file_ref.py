"""Tests for the guffin.common.github_file_ref module."""

import pytest
from pydantic import TypeAdapter, ValidationError

from guffin.common.github_file_ref import (
    CommitSha,
    GitHubFileRef,
    RawGitHubUrl,
    blob_github_url,
    parse_raw_github_url,
    raw_github_url,
    verified_commit_sha,
    verified_raw_github_url,
)
from guffin.common.line_range import LineRange

_SHA: str = "0d9ca427f7d7dbe92694284d4a6249178255036e"


class TestVerifiedCommitSha:
    """verified_commit_sha() verifies a full 40-hex lowercase commit SHA."""

    def test_full_sha_passes_through(self) -> None:
        """A full 40-hex SHA is returned unchanged."""
        assert verified_commit_sha(_SHA) == _SHA

    @pytest.mark.parametrize("sha_text", ["0d9ca42", _SHA.upper(), _SHA + "0", "g" * 40, ""])
    def test_rejects_non_full_sha(self, sha_text: str) -> None:
        """Abbreviated, uppercase, overlong, non-hex, and empty candidates are rejected."""
        with pytest.raises(ValueError, match="40-hex"):
            verified_commit_sha(sha_text)


class TestCommitShaType:
    """The CommitSha annotation itself enforces the check at Pydantic boundaries."""

    _ADAPTER = TypeAdapter[CommitSha](CommitSha)

    def test_full_sha_validates(self) -> None:
        """A full 40-hex SHA passes through the annotation unchanged."""
        assert self._ADAPTER.validate_python(_SHA) == _SHA

    def test_abbreviated_sha_is_rejected(self) -> None:
        """An abbreviated SHA fails validation at the type boundary."""
        with pytest.raises(ValidationError, match="40-hex"):
            self._ADAPTER.validate_python("0d9ca42")


class TestRawGitHubUrlType:
    """RawGitHubUrl and its imperative form certify the full URL grammar, keeping the text verbatim."""

    _ADAPTER = TypeAdapter[RawGitHubUrl](RawGitHubUrl)
    _URL = "https://raw.githubusercontent.com/psf/requests/main/setup.py#L1-L5"

    def test_verified_url_passes_through(self) -> None:
        """A parseable raw URL is returned unchanged."""
        assert verified_raw_github_url(self._URL) == self._URL

    def test_verified_rejects_wrong_host(self) -> None:
        """The imperative form applies the full parse, not a shape check."""
        with pytest.raises(ValueError, match="raw.githubusercontent.com"):
            verified_raw_github_url("https://github.com/psf/requests/blob/main/setup.py")

    def test_annotation_enforces_at_type_boundary(self) -> None:
        """The annotation carries the grammar check wherever the type appears."""
        assert self._ADAPTER.validate_python(self._URL) == self._URL
        with pytest.raises(ValidationError, match="query string"):
            self._ADAPTER.validate_python("https://raw.githubusercontent.com/psf/requests/main/setup.py?x=1")


class TestParseRawGithubUrl:
    """parse_raw_github_url() decomposes every supported raw-URL form and rejects everything else."""

    def test_bare_branch_ref(self) -> None:
        """A single-segment branch ref parses into its four parts."""
        file_ref = parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/main/src/requests/api.py")
        assert file_ref.owner == "psf"
        assert file_ref.repo == "requests"
        assert file_ref.ref == "main"
        assert file_ref.ref_name == "main"
        assert file_ref.path == "src/requests/api.py"
        assert file_ref.line_range is None
        assert not file_ref.is_sha_ref

    def test_qualified_branch_ref(self) -> None:
        """The refs/heads/<branch> form parses as a three-segment ref with the branch as ref_name."""
        file_ref = parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/refs/heads/main/setup.py")
        assert file_ref.ref == "refs/heads/main"
        assert file_ref.ref_name == "main"
        assert file_ref.path == "setup.py"

    def test_qualified_tag_ref(self) -> None:
        """The refs/tags/<tag> form parses as a three-segment ref with the tag as ref_name."""
        file_ref = parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/refs/tags/v2.32.3/setup.py")
        assert file_ref.ref == "refs/tags/v2.32.3"
        assert file_ref.ref_name == "v2.32.3"

    def test_sha_ref(self) -> None:
        """A full 40-hex SHA ref is recognized as immutable."""
        file_ref = parse_raw_github_url(f"https://raw.githubusercontent.com/psf/requests/{_SHA}/setup.py")
        assert file_ref.ref == _SHA
        assert file_ref.is_sha_ref

    def test_single_line_fragment(self) -> None:
        """A #L12 fragment narrows the reference to the one-line range 12-12."""
        file_ref = parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/main/setup.py#L12")
        assert file_ref.line_range == LineRange(start=12, end=12)

    def test_line_range_fragment(self) -> None:
        """A #L10-L40 fragment narrows the reference to that inclusive range."""
        file_ref = parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/main/setup.py#L10-L40")
        assert file_ref.line_range == LineRange(start=10, end=40)

    def test_rejects_wrong_host(self) -> None:
        """A github.com (non-raw) URL is rejected."""
        with pytest.raises(ValueError, match="raw.githubusercontent.com"):
            parse_raw_github_url("https://github.com/psf/requests/blob/main/setup.py")

    def test_rejects_http_scheme(self) -> None:
        """A plain-http URL is rejected."""
        with pytest.raises(ValueError, match="https"):
            parse_raw_github_url("http://raw.githubusercontent.com/psf/requests/main/setup.py")

    def test_rejects_query_string(self) -> None:
        """A query string (e.g. a cache-buster) is not part of the canonical reference."""
        with pytest.raises(ValueError, match="query string"):
            parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/main/setup.py?token=x")

    def test_rejects_missing_path(self) -> None:
        """A URL with no file path after the ref is rejected."""
        with pytest.raises(ValueError, match="file-path"):
            parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/main")

    def test_rejects_qualified_ref_without_path(self) -> None:
        """A qualified ref that consumes every remaining segment leaves no file path."""
        with pytest.raises(ValueError, match="no file path"):
            parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/refs/heads/main")

    def test_rejects_empty_segment(self) -> None:
        """A doubled slash yields an empty segment, which is rejected."""
        with pytest.raises(ValueError, match="file-path"):
            parse_raw_github_url("https://raw.githubusercontent.com/psf//main/setup.py")

    def test_rejects_malformed_fragment(self) -> None:
        """A fragment that is not a line range is rejected."""
        with pytest.raises(ValueError, match="not a line range"):
            parse_raw_github_url("https://raw.githubusercontent.com/psf/requests/main/setup.py#readme")


class TestRawGithubUrl:
    """raw_github_url() rebuilds the raw-content URL, optionally re-pinned at a commit."""

    _FILE_REF = GitHubFileRef(owner="psf", repo="requests", ref="main", path="setup.py")

    def test_rebuilds_at_own_ref(self) -> None:
        """Without a SHA the URL carries the reference's own ref."""
        assert raw_github_url(self._FILE_REF) == "https://raw.githubusercontent.com/psf/requests/main/setup.py"

    def test_re_pins_at_commit_sha(self) -> None:
        """With a SHA the URL is pinned at that immutable commit."""
        assert raw_github_url(self._FILE_REF, commit_sha=_SHA) == (
            f"https://raw.githubusercontent.com/psf/requests/{_SHA}/setup.py"
        )

    def test_carries_no_fragment(self) -> None:
        """Raw content is whole-file; a line range never rides on the raw URL."""
        ranged = self._FILE_REF.model_copy(update={"line_range": LineRange(start=10, end=40)})
        assert "#" not in raw_github_url(ranged)

    def test_round_trips_through_parse(self) -> None:
        """parse_raw_github_url(raw_github_url(ref)) reproduces the reference (sans range)."""
        assert parse_raw_github_url(raw_github_url(self._FILE_REF)) == self._FILE_REF


class TestBlobGithubUrl:
    """blob_github_url() builds the human-facing github.com blob URL with the line fragment."""

    _FILE_REF = GitHubFileRef(owner="psf", repo="requests", ref="refs/heads/main", path="src/requests/api.py")

    def test_whole_file_url(self) -> None:
        """Without a range the blob URL carries no fragment."""
        assert blob_github_url(self._FILE_REF) == (
            "https://github.com/psf/requests/blob/refs/heads/main/src/requests/api.py"
        )

    def test_range_fragment(self) -> None:
        """A multi-line range renders as the #L<start>-L<end> fragment."""
        ranged = self._FILE_REF.model_copy(update={"line_range": LineRange(start=10, end=40)})
        assert blob_github_url(ranged).endswith("#L10-L40")

    def test_single_line_fragment(self) -> None:
        """A one-line range renders as the compact #L<n> fragment."""
        ranged = self._FILE_REF.model_copy(update={"line_range": LineRange(start=12, end=12)})
        assert blob_github_url(ranged).endswith("#L12")

    def test_re_pins_at_commit_sha(self) -> None:
        """With a SHA the blob URL shows the referenced version even after the ref moves on."""
        assert blob_github_url(self._FILE_REF, commit_sha=_SHA) == (
            f"https://github.com/psf/requests/blob/{_SHA}/src/requests/api.py"
        )
