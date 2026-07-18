"""Tests for the guffin.model.code_source module."""

import datetime

import pytest
from pydantic import ValidationError

from guffin.common.line_range import LineRange
from guffin.model.code_source import CodeSource

_URL: str = "https://raw.githubusercontent.com/psf/requests/refs/heads/main/src/requests/api.py#L14-L60"
_SHA: str = "0d9ca427f7d7dbe92694284d4a6249178255036e"
_DATE: str = "2026-07-17"


class TestCodeSource:
    """CodeSource holds a validated (url, commit sha, fetched date) provenance triple."""

    def test_constructs_from_legal_triple(self) -> None:
        """A parseable URL, full SHA, and ISO date string construct a frozen value."""
        source = CodeSource(url=_URL, commit_sha=_SHA, fetched_date=_DATE)
        assert source.url == _URL
        assert source.commit_sha == _SHA
        assert source.fetched_date == datetime.date(2026, 7, 17)

    def test_rejects_unparseable_url(self) -> None:
        """A URL that is not a raw GitHub URL is rejected at construction."""
        with pytest.raises(ValidationError, match="raw.githubusercontent.com"):
            CodeSource(url="https://example.com/file.py", commit_sha=_SHA, fetched_date=_DATE)

    def test_rejects_abbreviated_sha(self) -> None:
        """An abbreviated commit SHA is rejected at construction."""
        with pytest.raises(ValidationError, match="40-hex"):
            CodeSource(url=_URL, commit_sha="0d9ca42", fetched_date=_DATE)

    def test_rejects_reduced_precision_date(self) -> None:
        """A reduced-precision fetch date is rejected at construction."""
        with pytest.raises(ValidationError, match="valid date"):
            CodeSource(url=_URL, commit_sha=_SHA, fetched_date="2026-07")

    def test_serializes_with_kebab_case_aliases(self) -> None:
        """The sha and date fields serialize under their kebab-case aliases."""
        source = CodeSource(url=_URL, commit_sha=_SHA, fetched_date=_DATE)
        dumped = source.model_dump(by_alias=True)
        assert dumped["commit-sha"] == _SHA
        assert dumped["fetched-date"] == datetime.date(2026, 7, 17)

    def test_file_ref_decomposes_the_url(self) -> None:
        """file_ref() yields the parsed reference, line range included."""
        source = CodeSource(url=_URL, commit_sha=_SHA, fetched_date=_DATE)
        file_ref = source.file_ref()
        assert file_ref.owner == "psf"
        assert file_ref.repo == "requests"
        assert file_ref.ref_name == "main"
        assert file_ref.path == "src/requests/api.py"
        assert file_ref.line_range == LineRange(start=14, end=60)
