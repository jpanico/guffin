"""Unit tests for guffin.server.export_artifact."""

import base64
import hashlib
import pathlib
import zipfile

import pytest

from guffin.server.export_artifact import (
    ArtifactResolutionError,
    content_digest_header,
    packaged_artifact,
    resolved_artifact_path,
)


class TestResolvedArtifactPath:
    """Tests for resolved_artifact_path."""

    def test_single_file_resolves(self, tmp_path: pathlib.Path) -> None:
        """A lone document file with debug files beside it resolves to the document."""
        artifact = tmp_path / "Foo.default.md"
        artifact.write_text("# Foo\n")
        (tmp_path / "Foo.pandoc.json").write_text("{}")
        (tmp_path / "Foo.body.typ").write_text("")
        assert resolved_artifact_path(tmp_path) == artifact

    def test_mdbundle_directory_resolves(self, tmp_path: pathlib.Path) -> None:
        """A .mdbundle directory is an artifact entry like any document file."""
        bundle = tmp_path / "Foo.default.mdbundle"
        bundle.mkdir()
        assert resolved_artifact_path(tmp_path) == bundle

    def test_empty_output_raises(self, tmp_path: pathlib.Path) -> None:
        """An output directory holding no artifact is a resolution error."""
        (tmp_path / "Foo.pandoc.json").write_text("{}")
        with pytest.raises(ArtifactResolutionError, match="none"):
            resolved_artifact_path(tmp_path)

    def test_multiple_artifacts_raise(self, tmp_path: pathlib.Path) -> None:
        """More than one artifact entry is a resolution error naming them all."""
        (tmp_path / "Foo.default.md").write_text("")
        (tmp_path / "Foo.default.pdf").write_bytes(b"")
        with pytest.raises(ArtifactResolutionError, match="Foo.default.md"):
            resolved_artifact_path(tmp_path)


class TestPackagedArtifact:
    """Tests for packaged_artifact."""

    @pytest.mark.parametrize(
        ("file_name", "media_type"),
        [
            ("Foo.default.pdf", "application/pdf"),
            ("Foo.book.epub", "application/epub+zip"),
            ("Foo.default.md", "text/markdown"),
        ],
    )
    def test_file_artifact_transfers_as_itself(self, tmp_path: pathlib.Path, file_name: str, media_type: str) -> None:
        """A file artifact transfers verbatim under its suffix's media type."""
        artifact_path = tmp_path / file_name
        artifact_path.write_bytes(b"content")
        artifact = packaged_artifact(artifact_path)
        assert artifact.path == artifact_path
        assert artifact.file_name == file_name
        assert artifact.media_type == media_type

    def test_mdbundle_zips_with_its_layout_preserved(self, tmp_path: pathlib.Path) -> None:
        """A .mdbundle directory transfers as a zip whose entries are rooted at the bundle name."""
        bundle = tmp_path / "Foo.default.mdbundle"
        (bundle / "assets").mkdir(parents=True)
        (bundle / "Foo.default.md").write_text("# Foo\n")
        (bundle / "assets" / "img.png").write_bytes(b"png-bytes")
        artifact = packaged_artifact(bundle)
        assert artifact.media_type == "application/zip"
        assert artifact.file_name == "Foo.default.mdbundle.zip"
        with zipfile.ZipFile(artifact.path) as archive:
            assert sorted(archive.namelist()) == [
                "Foo.default.mdbundle/Foo.default.md",
                "Foo.default.mdbundle/assets/img.png",
            ]


class TestContentDigestHeader:
    """Tests for content_digest_header."""

    def test_header_value_is_the_rfc_9530_sha_256_form(self, tmp_path: pathlib.Path) -> None:
        """The header value wraps the base64 SHA-256 digest in the structured-field byte form."""
        artifact_path = tmp_path / "doc.md"
        artifact_path.write_bytes(b"guffin")
        expected = base64.b64encode(hashlib.sha256(b"guffin").digest()).decode("ascii")
        assert content_digest_header(artifact_path) == f"sha-256=:{expected}:"
