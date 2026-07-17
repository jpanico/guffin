"""Roam's programming-language vocabulary for fenced code blocks, and its canonical mapping.

The Roam UI offers a fixed dropdown of code-block languages; :class:`CodeLanguage`
mirrors that closed set, each member's value being the identifier Roam embeds in the
fence's info string.  :func:`canonical_id_for` maps each member into the canonical
vocabulary of :mod:`~guffin.common.programming_language` (most values resolve by
name/alias lookup; the few divergent spellings carry explicit overrides).

Public symbols:

- :class:`CodeLanguage` — ``StrEnum`` of programming languages identified by a fenced code
  block's info string.
- :func:`canonical_id_for` — the canonical language id a :class:`CodeLanguage` member maps to.
"""

import enum
from collections.abc import Mapping
from typing import Final

from pydantic import validate_call

from guffin.common.programming_language import CodeLanguageId, canonical_language_id


class CodeLanguage(enum.StrEnum):
    """Programming language identified by a fenced code block's info string.

    Each member's value is the language identifier string as it appears in the
    info string of a fenced code block (e.g. the ``javascript`` in
    ```` ```javascript ````).
    """

    C = "c"
    CLOJURE = "clojure"
    COMMON_LISP = "commonlisp"
    CSS = "css"
    C_PLUS_PLUS = "c++"
    C_SHARP = "c#"
    DART = "dart"
    ELIXIR = "elixir"
    GO = "go"
    HASKELL = "haskell"
    HTML = "html"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    JSON = "json"
    JSON_LD = "json-ld"
    JSX = "jsx"
    JULIA = "julia"
    KOTLIN = "kotlin"
    LATEX = "latex"
    LUA = "lua"
    MARKDOWN = "markdown"
    OBJECTIVE_C = "objective-c"
    PHP = "php"
    PLAIN_TEXT = "plain text"
    PYTHON = "python"
    R = "r"
    RUBY = "ruby"
    RUST = "rust"
    SCALA = "scala"
    SHELL = "shell"
    SOLIDITY = "solidity"
    SPARQL = "sparql"
    SQL = "sql"
    SWIFT = "swift"
    TOML = "toml"
    TSX = "tsx"
    TURTLE = "turtle"
    TYPESCRIPT = "typescript"
    VB = "vb"
    VBSCRIPT = "vbscript"
    XML = "xml"
    YAML = "yaml"


# The CodeLanguage values whose spelling has no name/alias in the canonical vocabulary;
# each maps to its canonical language id explicitly.  Every other member resolves through
# canonical_language_id() on its value.
_CANONICAL_ID_OVERRIDES: Final[Mapping[CodeLanguage, str]] = {
    CodeLanguage.COMMON_LISP: "common lisp",
    CodeLanguage.JSON_LD: "jsonld",
    CodeLanguage.JSX: "javascript",
    CodeLanguage.VB: "visual basic .net",
}


@validate_call
def canonical_id_for(language: CodeLanguage) -> CodeLanguageId:
    """Return the canonical language id *language* maps to.

    Resolves the member's value through
    :func:`~guffin.common.programming_language.canonical_language_id`, with the few
    divergently-spelled members carried by explicit overrides (``commonlisp`` →
    ``common lisp``, ``json-ld`` → ``jsonld``, ``jsx`` → ``javascript``, ``vb`` →
    ``visual basic .net``).  Every member resolves: the mapping is total.

    Args:
        language: The Roam code-block language to map.

    Returns:
        The canonical language id.

    Raises:
        ValueError: If the vocabulary resolves no id for *language* — impossible while
            the override table covers every divergent member, and enforced by test.
    """
    override: Final[str | None] = _CANONICAL_ID_OVERRIDES.get(language)
    if override is not None:
        return override
    resolved: Final[str | None] = canonical_language_id(language.value)
    if resolved is None:
        raise ValueError(f"CodeLanguage {language!r} resolves to no canonical language id")
    return resolved
