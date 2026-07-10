"""Colorized logging configuration for guffin CLI tools.

Public symbols:

- :func:`configure_logging` — install the colorized handler and call
  :func:`logging.basicConfig`.
"""

import logging
import os
from typing import Final, TextIO

import regex

_LEVEL_COLORS: dict[str, str] = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_LOCATION_COLOR: str = "\033[35m"  # magenta — distinct from all level colors
_COLOR_RESET: str = "\033[0m"

_MESSAGE_HIGHLIGHTS: list[tuple[regex.Pattern[str], str]] = [
    (regex.compile(r"\s*id=\d+,"), "\033[1;97m"),  # bold bright white
]

_SUPPRESSED_RECORDS: Final[list[tuple[str, regex.Pattern[str]]]] = [
    # pypdf warns once per malformed cross-reference entry while it recovers by scanning; the
    # condition is a quirk of a third-party PDF file the user cannot act on, and pypdf reads on.
    ("pypdf", regex.compile(r"^Ignoring wrong pointing object ")),
]
"""Log records to suppress: ``(logger prefix, message pattern)`` pairs, matched per record."""


class _RecordSuppressionFilter(logging.Filter):
    """Drops the log records matched by :data:`_SUPPRESSED_RECORDS`; passes everything else."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return ``False`` when *record* matches a suppressed (logger prefix, message) pair."""
        for logger_prefix, message_pattern in _SUPPRESSED_RECORDS:
            name_matches: bool = record.name == logger_prefix or record.name.startswith(f"{logger_prefix}.")
            if name_matches and message_pattern.search(record.getMessage()) is not None:
                return False
        return True


def _highlight_message(message: str) -> str:
    """Return *message* with all :data:`_MESSAGE_HIGHLIGHTS` patterns ANSI-colorized."""
    for pattern, color in _MESSAGE_HIGHLIGHTS:
        message = pattern.sub(lambda m, c=color: f"{c}{m.group()}{_COLOR_RESET}", message)
    return message


class _ColorLevelFormatter(logging.Formatter):
    """Formatter that ANSI-colorizes the levelname, call-site location, and message highlights."""

    def format(self, record: logging.LogRecord) -> str:
        """Format *record*, colorizing levelname, module::funcName location, and message highlights."""
        color = _LEVEL_COLORS.get(record.levelname, "")
        original_levelname = record.levelname
        original_msg = record.msg
        original_args = record.args
        # The Formatter contract only reads values off the record, so the colorized fields must be
        # written onto it; the finally guarantees the shared record is restored even when the
        # super().format() call raises, so the mutation never escapes to other handlers.
        try:
            record.levelname = f"{color}[{record.levelname}]{_COLOR_RESET}"
            setattr(
                record,
                "location",
                f"{_LOCATION_COLOR}({record.module}::{record.funcName}:{record.lineno}){_COLOR_RESET}",
            )
            record.msg = _highlight_message(record.getMessage())
            record.args = None
            return super().format(record)
        finally:
            record.levelname = original_levelname
            record.msg = original_msg
            record.args = original_args
            if hasattr(record, "location"):
                delattr(record, "location")


def configure_logging() -> None:
    """Install the colorized handler and configure the root logger.

    Reads the desired log level from the ``LOG_LEVEL`` environment variable
    (default: ``"INFO"``).  Safe to call multiple times — subsequent calls
    are no-ops because :func:`logging.basicConfig` only applies when no
    handlers are already installed on the root logger.
    """
    handler: Final[logging.StreamHandler[TextIO]] = logging.StreamHandler()
    handler.setFormatter(
        _ColorLevelFormatter(
            fmt="%(asctime)s %(levelname)s %(location)s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    # The filter sits on the handler (not a logger), so it applies to every record that would
    # reach the output, whichever library logger emitted it.
    handler.addFilter(_RecordSuppressionFilter())
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        handlers=[handler],
    )
