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
        record.levelname = f"{color}[{record.levelname}]{_COLOR_RESET}"
        setattr(
            record, "location", f"{_LOCATION_COLOR}({record.module}::{record.funcName}:{record.lineno}){_COLOR_RESET}"
        )
        record.msg = _highlight_message(record.getMessage())
        record.args = None
        result = super().format(record)
        record.levelname = original_levelname
        record.msg = original_msg
        record.args = original_args
        delattr(record, "location")
        return result


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
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        handlers=[handler],
    )
