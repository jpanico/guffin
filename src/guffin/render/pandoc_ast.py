"""Guffin-independent helpers for the Pandoc AST (the panflute object model).

Convert to and from, and transform, the Pandoc AST — with **no dependency on the Guffin model**:
parse Pandoc Markdown strings into panflute elements, strip links to their display text, and serialize
a panflute :class:`~panflute.Doc` to a Pandoc JSON string.

Public symbols:

- **Type aliases**: :data:`InlineMap` — mapping from a Pandoc Markdown text string to its parsed
  panflute inline elements.
- **Functions**: :func:`strip_links` — unwrap every Link to its display-text content;
  :func:`parse_inline_md` — batch-parse Pandoc Markdown strings into inline element lists;
  :func:`parse_block_md` — parse a Pandoc Markdown string into block elements; :func:`pandoc_to_json`
  — serialize a :class:`~panflute.Doc` to a Pandoc JSON string.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation from that import.

import logging
import uuid
from io import StringIO
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
from pydantic import validate_call

from guffin.render import pandoc_server

logger = logging.getLogger(__name__)


def _markdown_to_pandoc_json(text: str) -> str:
    """Convert a Pandoc Markdown string to the Pandoc JSON AST string.

    Prefers the persistent ``pandoc-server`` acceleration (:func:`pandoc_server.markdown_to_json`,
    active only when opted in via ``GUFFIN_PANDOC_SERVER``); when that path declines — not opted in,
    unavailable, or errored — converts via the Pandoc CLI (:func:`pypandoc.convert_text`), which is
    the default everywhere else.

    Args:
        text: The Pandoc Markdown text to parse.

    Returns:
        The Pandoc JSON AST representation of *text*.
    """
    served: Final[str | None] = pandoc_server.markdown_to_json(text)
    if served is not None:
        return served
    cli_json: Final[str] = pypandoc.convert_text(text, "json", format="markdown")  # type: ignore[no-untyped-call]
    return cli_json


type InlineMap = dict[str, list[pf.Inline]]
"""Mapping from Pandoc Markdown text string to its parsed panflute inline elements."""


def strip_links(inlines: list[pf.Inline]) -> list[pf.Inline]:
    """Return *inlines* with every Link replaced by its display-text content.

    Unwraps each :class:`~panflute.Link` to its inner content inlines, preserving
    the display text while discarding the hyperlink target.  Useful wherever a
    run of inlines must be reduced to plain text — e.g. sanitizing metadata
    fields (such as the document title) where Pandoc's Typst writer would embed a
    ``#link("url")[text]`` call inside a double-quoted Typst string and break the
    parser, or flattening a page title that itself contains a nested reference.

    Args:
        inlines: Panflute inline elements to filter.

    Returns:
        A new list with Link elements unwrapped to their content inlines.
    """
    result: list[pf.Inline] = []
    for inline in inlines:
        if isinstance(inline, pf.Link):
            result.extend(list(inline.content))
        else:
            result.append(inline)
    return result


@validate_call
def parse_inline_md(texts: list[str]) -> InlineMap:
    """Batch-parse Pandoc Markdown inline text strings into panflute inline element lists.

    Each parse requires a Pandoc subprocess, so parsing text fields one at a
    time would spawn one subprocess per block.  Batching every unique string
    into a single call amortizes that cost across the whole document.

    Joins all unique, non-empty strings with a random sentinel ATX heading as
    separator, converts the combined document to Pandoc JSON in a single
    subprocess call, then maps each input string back to the inline elements
    from its corresponding paragraph block.  The separator must be a heading
    rather than a bare paragraph: Pandoc's ``definition_lists`` extension
    captures a preceding paragraph — even across one blank line — as the term
    of a ``~``- or ``:``-led definition, so an entry starting with either
    marker would swallow a paragraph separator and silently misalign every
    entry after it; a heading can never be captured that way.

    Text strings that produce no paragraph block (e.g. bare ``---``, which
    Pandoc parses as a thematic break) are absent from the returned mapping;
    callers should fall back to ``[pf.Str(text)]`` for missing entries.

    Args:
        texts: Text strings to parse.  Duplicates and empty strings are
            silently deduplicated / ignored.

    Returns:
        Mapping from each unique non-empty input string to the list of
        panflute inline elements produced by parsing it as Pandoc Markdown.
    """
    unique: Final[list[str]] = list(dict.fromkeys(t for t in texts if t))
    if not unique:
        return {}

    # Random sentinel used as an ATX-heading separator between entries.  UUID hex makes
    # collision with real content effectively impossible; the heading form keeps an adjacent
    # entry's parse from absorbing the separator (see the docstring).
    sep: Final[str] = f"GUFFIN_SEP_{uuid.uuid4().hex}"
    combined: Final[str] = f"\n\n# {sep}\n\n".join(unique)

    json_str: Final[str] = _markdown_to_pandoc_json(combined)
    doc: Final[pf.Doc] = pf.load(StringIO(json_str))

    result: Final[InlineMap] = {}
    text_idx: int = 0

    for block in doc.content:  # `block: pf.Block`
        if text_idx >= len(unique):
            break
        block_inlines: list[pf.Inline] = list(block.content) if hasattr(block, "content") else []
        # Sentinel heading → advance to the next text entry.
        if (
            isinstance(block, pf.Header)
            and len(block_inlines) == 1
            and isinstance(block_inlines[0], pf.Str)
            and block_inlines[0].text == sep
        ):
            text_idx += 1
            continue
        # First Para or Plain block for the current text → record its inlines.
        if isinstance(block, (pf.Para, pf.Plain)) and unique[text_idx] not in result:
            result[unique[text_idx]] = block_inlines

    return result


@validate_call
def parse_block_md(text: str) -> list[pf.Block]:
    """Parse a single Pandoc Markdown string into a list of panflute block elements.

    Unlike :func:`parse_inline_md`, this performs a full block-level parse, so
    block constructs such as fenced code blocks are preserved as their
    corresponding panflute block elements (e.g. :class:`~panflute.CodeBlock`)
    rather than being flattened into inline content.

    Args:
        text: The Pandoc Markdown text to parse.

    Returns:
        The list of :class:`~panflute.Block` elements produced by parsing
        *text*.
    """
    json_str: Final[str] = _markdown_to_pandoc_json(text)
    doc: Final[pf.Doc] = pf.load(StringIO(json_str))
    return list(doc.content)


def pandoc_to_json(
    doc: pf.Doc,
    dump_pandoc_ast: bool = False,
    ast_dump_dir: Path | None = None,
    ast_dump_stem: str | None = None,
) -> str:
    """Serialize *doc* to a Pandoc JSON string.

    Dumps *doc* via :func:`panflute.dump` and returns the resulting JSON
    string.  When *dump_pandoc_ast* is ``True`` and both *ast_dump_dir* and
    *ast_dump_stem* are provided, the JSON is also written to
    ``<ast_dump_dir>/<ast_dump_stem>.pandoc.json`` before being returned —
    useful for inspecting the intermediate Pandoc AST without modifying the
    main rendering pipeline.

    Args:
        doc: The Panflute document to serialize.
        dump_pandoc_ast: When ``True``, write the JSON to disk alongside the
            primary output.  Requires *ast_dump_dir* and *ast_dump_stem*.
        ast_dump_dir: Directory in which to write the ``.pandoc.json`` file.
            Ignored when *dump_pandoc_ast* is ``False``.
        ast_dump_stem: POSIX-normalized filename stem (no extension) used to
            construct the dump filename.  Ignored when *dump_pandoc_ast* is
            ``False``.

    Returns:
        The Pandoc JSON representation of *doc*.
    """
    buf: Final[StringIO] = StringIO()
    pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
    json_str: Final[str] = buf.getvalue()
    if dump_pandoc_ast and ast_dump_dir is not None and ast_dump_stem is not None:
        ast_dump_path: Final[Path] = ast_dump_dir / f"{ast_dump_stem}.pandoc.json"
        ast_dump_path.write_text(json_str, encoding="utf-8")
        logger.info("Wrote Pandoc AST to %s", ast_dump_path)
    return json_str
