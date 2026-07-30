"""The artifact an export invocation leaves in its output directory, packaged for transfer.

An export writes exactly one primary artifact into its output directory — a single document
file, or a ``.mdbundle`` directory — possibly alongside ancillary debug files.  This module
resolves that one artifact (:func:`resolved_artifact_path`), packages it into a single
transferable file (:func:`packaged_artifact` — a directory artifact is zipped, layout
preserved), and computes the integrity header its transfer carries
(:func:`content_digest_header`, an RFC 9530 ``Content-Digest`` value).

Public symbols:

- :data:`ARTIFACT_MEDIA_TYPES` — each artifact suffix's IANA media type.
- :class:`ArtifactResolutionError` — no single artifact could be resolved.
- :class:`ExportArtifact` — a packaged artifact ready for transfer.
- :func:`resolved_artifact_path` — the single artifact entry in an output directory.
- :func:`packaged_artifact` — an artifact packaged into one transferable file.
- :func:`content_digest_header` — a file's RFC 9530 ``Content-Digest`` header value.
"""

import base64
import hashlib
import zipfile
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict, validate_call

ARTIFACT_MEDIA_TYPES: Final[Mapping[str, str]] = MappingProxyType(
    {
        ".pdf": "application/pdf",
        ".epub": "application/epub+zip",
        ".md": "text/markdown",
        ".mdbundle": "application/zip",
    }
)
"""Each recognized artifact suffix's IANA media type (a ``.mdbundle`` directory transfers zipped)."""


class ArtifactResolutionError(Exception):
    """No single artifact could be resolved from an export's output directory."""


class ExportArtifact(BaseModel):
    """A packaged export artifact ready for transfer.

    Attributes:
        path: The transferable file on disk (the artifact itself, or its zip archive).
        file_name: The client-facing download name.
        media_type: The transfer's IANA media type.
    """

    model_config = ConfigDict(frozen=True)

    path: Path
    file_name: str
    media_type: str


@validate_call
def resolved_artifact_path(output_dir: Path) -> Path:
    """Return the single artifact entry in *output_dir*.

    An entry is an artifact when its suffix is recognized (:data:`ARTIFACT_MEDIA_TYPES`);
    everything else — ancillary debug files such as a dumped Pandoc AST — is ignored.

    Args:
        output_dir: The directory an export invocation wrote into.

    Returns:
        The one artifact entry (a file, or a ``.mdbundle`` directory).

    Raises:
        ArtifactResolutionError: When the directory holds no artifact, or more than one.
    """
    candidates: Final[list[Path]] = sorted(
        entry for entry in output_dir.iterdir() if entry.suffix in ARTIFACT_MEDIA_TYPES
    )
    if len(candidates) != 1:
        names: Final[str] = ", ".join(entry.name for entry in candidates) or "none"
        raise ArtifactResolutionError(f"expected exactly one artifact in {output_dir}, found: {names}")
    return candidates[0]


def _zipped_directory(directory: Path) -> Path:
    """Write a zip archive of *directory* beside it and return the archive's path.

    Entries are rooted at the directory's own name, so unzipping reproduces the directory
    exactly as it was written.
    """
    archive_path: Final[Path] = directory.with_name(directory.name + ".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in sorted(directory.rglob("*")):
            if member.is_file():
                archive.write(member, arcname=member.relative_to(directory.parent))
    return archive_path


@validate_call
def packaged_artifact(artifact_path: Path) -> ExportArtifact:
    """Return *artifact_path* packaged into a single transferable file.

    A file artifact transfers as itself under its suffix's media type; a directory artifact
    (a ``.mdbundle``) is zipped beside itself, layout preserved, and transfers as the archive.

    Args:
        artifact_path: The artifact entry resolved from an export's output directory.

    Returns:
        The :class:`ExportArtifact` naming the transferable file, download name, and media type.
    """
    if artifact_path.is_dir():
        archive_path: Final[Path] = _zipped_directory(artifact_path)
        return ExportArtifact(
            path=archive_path, file_name=archive_path.name, media_type=ARTIFACT_MEDIA_TYPES[artifact_path.suffix]
        )
    return ExportArtifact(
        path=artifact_path, file_name=artifact_path.name, media_type=ARTIFACT_MEDIA_TYPES[artifact_path.suffix]
    )


@validate_call
def content_digest_header(file_path: Path) -> str:
    """Return *file_path*'s RFC 9530 ``Content-Digest`` header value (a ``sha-256`` digest).

    Args:
        file_path: The file to digest; read in chunks, so size does not affect memory.

    Returns:
        The header value, e.g. ``sha-256=:RK/0qy18MlBSVnWgjwz6lZEWjP/lF5HF9bvEF8FabDg=:``.
    """
    with file_path.open("rb") as source:
        digest_value: Final[bytes] = hashlib.file_digest(source, "sha256").digest()
    encoded: Final[str] = base64.b64encode(digest_value).decode("ascii")
    return f"sha-256=:{encoded}:"
