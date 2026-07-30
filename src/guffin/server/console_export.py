"""The representation a captured console rendering is returned in.

A Rich console rendering is captured as text — with or without ANSI style escapes — and can be
re-rendered into richer self-contained representations: a standalone HTML document or an SVG
image of the terminal, via Rich's own export machinery.  This module names the representation
vocabulary (:class:`ConsoleFormat`), the environment a capture must run under to feed each
representation (:func:`console_environment`), and the conversion from a capture to its final
representation (:func:`exported_console`).

Public symbols:

- :class:`ConsoleFormat` — the representation a captured console rendering is returned in.
- :data:`CONSOLE_MEDIA_TYPE` — each representation's IANA media type.
- :func:`console_environment` — the environment overlay a capture runs under for a representation.
- :func:`exported_console` — a captured rendering converted to its final representation.
"""

import enum
import io
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from pydantic import validate_call
from rich.console import Console
from rich.text import Text


class ConsoleFormat(enum.StrEnum):
    """The representation a captured console rendering is returned in.

    Attributes:
        TEXT: The captured text itself (ANSI style escapes included only when the capture ran
            colored).
        HTML: A standalone HTML document re-rendering the capture, styles inlined.
        SVG: An SVG image of the terminal re-rendering the capture.
    """

    TEXT = "text"
    HTML = "html"
    SVG = "svg"


CONSOLE_MEDIA_TYPE: Final[Mapping[ConsoleFormat, str]] = MappingProxyType(
    {
        ConsoleFormat.TEXT: "text/plain",
        ConsoleFormat.HTML: "text/html",
        ConsoleFormat.SVG: "image/svg+xml",
    }
)
"""Each :class:`ConsoleFormat`'s IANA media type; total over the enum."""

_SVG_TITLE: Final[str] = "dump-roam-tree"
"""The terminal-window title rendered into an SVG export."""


@validate_call
def console_environment(console_format: ConsoleFormat, console_width: int, ansi: bool) -> dict[str, str | None]:
    """Return the environment overlay a console capture must run under.

    The overlay pins the rendering width (``COLUMNS``, honored by Rich when the output stream is
    not a terminal) and the color decision: :attr:`ConsoleFormat.HTML` and
    :attr:`ConsoleFormat.SVG` always capture colored (their styling is reconstructed from the
    ANSI escapes), while :attr:`ConsoleFormat.TEXT` captures colored only when *ansi* asks for
    it.  A ``None`` value means the variable must be absent, so an inherited setting cannot
    contradict the decision.

    Args:
        console_format: The representation the capture will feed.
        console_width: The character width the rendering wraps at.
        ansi: Whether a :attr:`ConsoleFormat.TEXT` capture keeps ANSI style escapes.

    Returns:
        The ``{variable: value-or-None}`` overlay to apply for the capture's duration.
    """
    environment: Final[dict[str, str | None]] = {"COLUMNS": str(console_width)}
    colored: Final[bool] = console_format is not ConsoleFormat.TEXT or ansi
    if colored:
        environment.update({"FORCE_COLOR": "1", "COLORTERM": "truecolor", "TERM": "xterm-256color", "NO_COLOR": None})
    else:
        environment.update({"NO_COLOR": "1", "FORCE_COLOR": None})
    return environment


@validate_call
def exported_console(captured: str, console_format: ConsoleFormat, console_width: int) -> str:
    """Return *captured* converted to *console_format*'s representation.

    :attr:`ConsoleFormat.TEXT` passes the capture through verbatim.  The richer representations
    re-render it: the capture's ANSI escapes are decoded back into styled text
    (:meth:`rich.text.Text.from_ansi`), printed through a recording console at *console_width*,
    and exported as a standalone HTML document or an SVG image.

    Args:
        captured: The captured console text (with ANSI escapes for the richer representations).
        console_format: The representation to convert to.
        console_width: The character width the re-rendering wraps at; must match the capture's.

    Returns:
        The representation's full text (plain text, an HTML document, or an SVG document).
    """
    if console_format is ConsoleFormat.TEXT:
        return captured
    recording_console: Final[Console] = Console(record=True, width=console_width, file=io.StringIO())
    recording_console.print(Text.from_ansi(captured))
    if console_format is ConsoleFormat.HTML:
        return recording_console.export_html()
    return recording_console.export_svg(title=_SVG_TITLE)
