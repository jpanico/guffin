"""Build provenance for an exported document: which software produced it, and when.

Captures the facts needed to trace any produced document back to the exact software that generated
it — the installed package version, the git commit of the source tree (with a marker when that tree
had uncommitted changes), the commit's own timestamp, and the moment the export ran — as a single
:class:`Provenance` value whose :meth:`Provenance.summary` renders them as one compact identifier
line.

Public symbols:

- **Constants**: :data:`UNKNOWN_COMMIT` — placeholder commit id used when the source commit
  cannot be determined; :data:`UNKNOWN_VERSION` — placeholder package version used when the
  installed version cannot be determined.
- **Models**: :class:`Provenance` — the version, source-commit, and timestamp facts identifying
  one export.
- **Functions**: :func:`gather_provenance` — capture the current package version, git commit,
  dirty state, and time.
"""

import importlib.metadata
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.common.date import utc_timestamp

logger = logging.getLogger(__name__)

UNKNOWN_COMMIT: Final[str] = "unknown"
"""Placeholder :attr:`Provenance.commit` value used when the source git commit cannot be determined."""

UNKNOWN_VERSION: Final[str] = "unknown"
"""Placeholder :attr:`Provenance.version` value used when the installed version cannot be determined."""

_DISTRIBUTION_NAME: Final[str] = "guffin"
"""The distribution whose identity — name and version — leads a provenance summary."""

_SHORT_COMMIT_LENGTH: Final[int] = 7
"""Leading commit-hash characters shown by :meth:`Provenance.summary` (git's / GitHub's short-SHA length)."""


class Provenance(BaseModel):
    """The version, source-commit, and timestamp facts that identify a single export.

    Together these answer, for any document the exporter produces, exactly which software produced
    it and when: the installed package version, the git commit (with a ``dirty`` marker when the
    working tree had uncommitted changes to tracked files), the commit's own timestamp, and the
    moment the export ran.  Callers may attach further free-form facts via :attr:`extra` (e.g. the
    project type) without this module needing to know about them.

    Attributes:
        version: The installed package version that produced the export, or
            :data:`UNKNOWN_VERSION` when it could not be determined (e.g. not installed).
        commit: The full git commit hash of the source tree, or :data:`UNKNOWN_COMMIT` when it
            could not be determined (e.g. not running from a git checkout).
        dirty: Whether the source working tree had uncommitted changes to tracked files; when
            ``True`` the commit hash alone does not capture the exact source.
        committed_at: The commit's own timestamp, or ``None`` when unknown.
        exported_at: The moment the export ran, or ``None`` when not recorded.
        extra: Arbitrary caller-supplied ``key → value`` facts, rendered by :meth:`summary` right
            after the leading ``guffin <version>`` segment, in insertion order, as ``key: value``
            segments; lets front ends record context (such as the project type) without this layer
            depending on theirs.
    """

    model_config = ConfigDict(frozen=True)

    version: str = Field(..., description="The installed package version that produced the export, or 'unknown'.")
    commit: str = Field(..., description="Full git commit hash of the source tree, or 'unknown'.")
    dirty: bool = Field(default=False, description="Whether the working tree had uncommitted tracked changes.")
    committed_at: datetime | None = Field(default=None, description="The commit's own timestamp.")
    exported_at: datetime | None = Field(default=None, description="The moment the export ran.")
    extra: dict[str, str] = Field(
        default_factory=dict, description="Arbitrary caller-supplied key→value facts appended to the summary."
    )

    @validate_call
    def summary(self) -> str:
        """Return a single-line identifier encoding the version, commit, and timestamps.

        The leading segment names the software and its version (``guffin <version>``); every other
        field renders as a ``key: value`` segment, comma-separated: each :attr:`extra` pair follows
        the leading segment, in insertion order; then the commit hash — shortened to its first
        :data:`_SHORT_COMMIT_LENGTH` characters, with a ``-dirty`` suffix when :attr:`dirty` is
        set — and the commit and export timestamps (minute-precision UTC with an explicit ``Z`` —
        see :func:`~guffin.common.date.utc_timestamp`; timestamps captured with other offsets,
        such as git's local-time commit stamps, are normalized) when present.  Example::

            guffin 0.2.0, type: book, commit: 1ce1966-dirty, committed: 2026-06-29T14:02Z, exported: 2026-06-29T22:40Z

        Returns:
            The provenance as one compact, human- and machine-readable line.
        """
        short_commit: Final[str] = self.commit[:_SHORT_COMMIT_LENGTH]
        commit: Final[str] = f"{short_commit}-dirty" if self.dirty else short_commit
        parts: Final[list[str]] = [
            f"{_DISTRIBUTION_NAME} {self.version}",
            *(f"{key}: {value}" for key, value in self.extra.items()),
            f"commit: {commit}",
        ]
        if self.committed_at is not None:
            parts.append(f"committed: {utc_timestamp(self.committed_at)}")
        if self.exported_at is not None:
            parts.append(f"exported: {utc_timestamp(self.exported_at)}")
        return ", ".join(parts)


def _git(repo_dir: Path, *args: str) -> str:
    """Run ``git -C <repo_dir> <args…>`` and return its stripped stdout (raises on failure)."""
    result: Final[subprocess.CompletedProcess[str]] = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_dirty(repo_dir: Path) -> bool:
    """Whether tracked files differ from ``HEAD`` (staged or unstaged), mirroring ``git --dirty``.

    Untracked files do not count, matching the dirty semantics of ``git describe --dirty``.
    """
    result: Final[subprocess.CompletedProcess[bytes]] = subprocess.run(
        ["git", "-C", str(repo_dir), "diff", "--quiet", "HEAD"],
        capture_output=True,
    )
    return result.returncode != 0


def _package_version() -> str:
    """Return the installed distribution's version, or :data:`UNKNOWN_VERSION` when not installed."""
    try:
        return importlib.metadata.version(_DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError as exc:
        logger.warning("could not determine the installed package version: %s", exc)
        return UNKNOWN_VERSION


@validate_call
def gather_provenance(extra: dict[str, str] | None = None) -> Provenance:
    """Capture the package version, source git commit, dirty state, and export time as a :class:`Provenance`.

    The version is read from the installed distribution's metadata (:data:`UNKNOWN_VERSION` when
    not installed).  ``git`` runs against the directory containing this module — the installed
    package's own source tree, which for an editable install is the project's git checkout.  When
    git is unavailable or that directory is not a git work tree, the returned :class:`Provenance`
    carries commit :data:`UNKNOWN_COMMIT` so an export can still proceed.  ``exported_at`` is set
    to the current UTC time in every case.

    Args:
        extra: Optional arbitrary ``key → value`` facts to record on the result's
            :attr:`Provenance.extra` (e.g. the project type); ``None`` records none.

    Returns:
        The captured :class:`Provenance`.
    """
    repo_dir: Final[Path] = Path(__file__).resolve().parent
    version: Final[str] = _package_version()
    exported_at: Final[datetime] = datetime.now(UTC)
    extra_fields: Final[dict[str, str]] = dict(extra) if extra else {}
    try:
        commit: Final[str] = _git(repo_dir, "rev-parse", "HEAD")
        dirty: Final[bool] = _git_dirty(repo_dir)
        committed_at: Final[datetime] = datetime.fromisoformat(_git(repo_dir, "show", "-s", "--format=%cI", "HEAD"))
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logger.warning("could not determine source git provenance: %s", exc)
        return Provenance(version=version, commit=UNKNOWN_COMMIT, exported_at=exported_at, extra=extra_fields)
    return Provenance(
        version=version,
        commit=commit,
        dirty=dirty,
        committed_at=committed_at,
        exported_at=exported_at,
        extra=extra_fields,
    )
