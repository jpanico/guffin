"""The single-token spelling a code listing's language is labelled with in output.

A canonical language id is a lowercased Linguist name, which may contain spaces
(``common lisp``, ``emacs lisp``).  Rendered output carries the language label in
positions where whitespace is structural: a fenced code block's info string (Typst reads
only the first word as the language tag and turns the remainder into a spurious first
line of the listing; a CommonMark info string ends its language token at the first
space) and an HTML ``class`` attribute (a space splits one class into two).  A
space-bearing id must therefore be respelled before it reaches an output document.

The token resolves in three steps:

1. An id whose highlighter-recognized spelling diverges from its Linguist name carries
   an explicit override — e.g. ``common lisp`` → ``lisp``, the token Typst's built-in
   syntect set, Pandoc's skylighting, and Linguist itself all recognize.  Every override
   value is itself a Linguist alias of its key's language, so the token stays resolvable
   in the canonical vocabulary.
2. Any other space-bearing id folds its whitespace runs to single hyphens — safe in
   every output position, with best-effort highlighter recognition.
3. A whitespace-free id passes through verbatim.

Public symbols:

- :func:`code_language_token` — the whitespace-free token for a canonical language id.
"""

from collections.abc import Mapping
from typing import Final

import regex
from pydantic import validate_call

from guffin.common.programming_language import CodeLanguageId

# Canonical ids whose Linguist name diverges from the token output highlighters
# recognize; each maps to a whitespace-free Linguist alias of the same language.
_CODE_LANGUAGE_TOKEN_OVERRIDES: Final[Mapping[str, str]] = {
    "common lisp": "lisp",
    "emacs lisp": "elisp",
    "visual basic .net": "vbnet",
}

_WHITESPACE_RUN_RE: Final[regex.Pattern[str]] = regex.compile(r"\s+")


@validate_call
def code_language_token(language_id: CodeLanguageId) -> str:
    """Return the whitespace-free token for *language_id*.

    An id carrying an explicit override resolves to its highlighter-recognized alias
    (``common lisp`` → ``lisp``); any other space-bearing id folds its whitespace runs
    to single hyphens (``standard ml`` → ``standard-ml``); a whitespace-free id is
    returned verbatim.

    Args:
        language_id: The canonical language id to respell.

    Returns:
        The token, guaranteed to contain no whitespace.
    """
    override: Final[str | None] = _CODE_LANGUAGE_TOKEN_OVERRIDES.get(language_id)
    if override is not None:
        return override
    return _WHITESPACE_RUN_RE.sub("-", language_id)
