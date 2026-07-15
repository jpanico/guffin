"""Tests for :mod:`guffin.render.pandoc_server` — server-accelerated Markdown→Pandoc-JSON parsing."""

import json
from typing import Final

import pypandoc  # type: ignore[import-untyped]
import pytest

from guffin.render.pandoc_server import markdown_to_json

SAMPLES: Final[list[str]] = [
    "hello **world** with a [link](http://x.com) and `code`",
    "```python\nprint('x')\n```",
    "text with — em dash, “curly” quotes, and $x^2$ math",
    "> a block quote\n\nplain paragraph after it",
]
"""Representative Markdown constructs the render pipeline parses (emphasis, code, math, quotes)."""


@pytest.mark.pandoc
class TestMarkdownToJson:
    """``markdown_to_json`` serves the same Pandoc AST as the CLI when enabled, and ``None`` otherwise.

    The AST equality (after JSON decoding, which absorbs the server's trailing-newline wire
    difference) is the safety contract: the server acceleration must never change output.  The CLI
    conversion via :func:`pypandoc.convert_text` is the independent oracle.
    """

    @pytest.mark.parametrize("text", SAMPLES)
    def test_server_result_matches_cli(self, text: str) -> None:
        """With the server enabled for the suite (see ``conftest``), it serves the CLI's exact AST."""
        served: Final[str | None] = markdown_to_json(text)
        assert served is not None
        assert json.loads(served) == json.loads(
            pypandoc.convert_text(text, "json", format="markdown")  # type: ignore[no-untyped-call]
        )


class TestDisabled:
    """When not opted in, ``markdown_to_json`` declines with ``None`` and never touches the server."""

    def test_returns_none_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Turning the flag off makes the server decline (return ``None``) so the caller falls back."""
        monkeypatch.setenv("GUFFIN_PANDOC_SERVER", "0")
        assert markdown_to_json(SAMPLES[0]) is None
