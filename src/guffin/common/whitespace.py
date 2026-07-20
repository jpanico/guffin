"""Whitespace normalization helpers with no domain coupling.

Public symbols:

- :data:`NON_ASCII_SPACE_PATTERN` / :data:`NON_ASCII_SPACE_RE` — a single Unicode
  space-separator character other than the ASCII space (``U+0020``).
- :func:`normalize_spaces` — replace every non-ASCII Unicode space separator in a
  string with an ordinary ASCII space.
"""

from typing import Final

import regex
from pydantic import validate_call

NON_ASCII_SPACE_PATTERN: Final[str] = r"[\p{Zs}--[\x20]]"
"""A single Unicode ``Space_Separator`` (``Zs``) character other than the ASCII space.

Matches every horizontal space Unicode classifies as ``Zs`` — the no-break space
(``U+00A0``), the narrow no-break space (``U+202F``), the fixed-width typographic spaces
(``U+2000``–``U+200A``, ``U+205F``), the ideographic space (``U+3000``), and the Ogham space
mark (``U+1680``) — *except* the ordinary ASCII space (``U+0020``), which is subtracted out.
Deliberately excludes the tab, newline, and other non-``Zs`` whitespace (categories ``Cc`` /
``Cf``), so structural whitespace and zero-width format characters (e.g. the emoji
zero-width joiner) are left untouched.  Uses :data:`regex.V1` set-difference syntax.
"""

NON_ASCII_SPACE_RE: Final[regex.Pattern[str]] = regex.compile(NON_ASCII_SPACE_PATTERN, regex.V1)
"""Compiled :data:`NON_ASCII_SPACE_PATTERN`."""


@validate_call
def normalize_spaces(text: str) -> str:
    """Replace every non-ASCII Unicode space separator in *text* with an ASCII space.

    Each character matched by :data:`NON_ASCII_SPACE_RE` — a Unicode ``Space_Separator``
    (``Zs``) other than the ordinary ASCII space — is replaced one-for-one with ``U+0020``.
    The substitution is length-preserving: it never collapses runs of spaces, and it touches
    only horizontal space separators, so tabs, newlines, and zero-width format characters pass
    through unchanged.

    A no-break space (``U+00A0``) and its kin are common paste artifacts (copied from rich
    text, HTML, or terminal-rendered output); because they forbid line breaks or carry a fixed
    width, they surface downstream as unwrappable, overflowing lines.  Folding them to the
    ordinary space restores normal wrapping in every output format.

    Args:
        text: The string to normalize.

    Returns:
        *text* with every non-ASCII Unicode space separator replaced by an ASCII space;
        the input unchanged when it contains none.
    """
    return NON_ASCII_SPACE_RE.sub(" ", text)
