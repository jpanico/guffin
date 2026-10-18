"""Rendering of floats: numbering a built document's figures, tables, and listings, and labelling them.

A float (:mod:`~guffin.model.floats`) renders as a captioned Pandoc element carrying the float's
identifier (:func:`~guffin.render.pandoc_rendering.float_identifier`): a :class:`~panflute.Figure`
for a figure or a listing, a :class:`~panflute.Table` with its own caption for a table.  Its number
is not part of that build: it comes from the model's reading-order numbering
(:func:`~guffin.model.floats.float_numbers`), decided by the work's
:class:`~guffin.render.project.FloatNumberingStyle` and chapter level, and is written into the
caption afterwards as a label (*Figure 2.3.*), the same text in every format.  The same numbering
feeds the references the running text makes to the floats.

Public symbols:

- **Models**: :class:`PreparedFloats` — what a document's floats resolve to: the floats by
  wrapper and their numbers.
- **Functions**: :func:`float_chapter_level` — the heading level a policy numbers floats by, if
  any; :func:`label_floats` — write each numbered float's label into its caption;
  :func:`prepare_floats` — number a document's floats and label them, returning what the link
  resolver needs.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so its symbols are typed as Unknown by pyright; the
# document edits below are plain panflute attribute writes.

from collections.abc import Mapping
from typing import Final, NamedTuple

import panflute as pf  # type: ignore[import-untyped]
from pydantic import ConfigDict, validate_call

from guffin.model.floats import Float, FloatNumber, float_numbers, floats_in
from guffin.model.primitives import Uid
from guffin.model.vertex_tree import VertexTree
from guffin.render.pandoc_rendering import FLOAT_ID_PREFIX
from guffin.render.project import FloatNumberingStyle, StructuralPolicy


class PreparedFloats(NamedTuple):
    """A document's floats and their numbers.

    Attributes:
        floats: Every float in the tree, keyed by wrapper UID.
        numbers: Each displayed float's number, keyed by wrapper UID.
    """

    floats: Mapping[Uid, Float]
    numbers: Mapping[Uid, FloatNumber]


@validate_call
def float_chapter_level(policy: StructuralPolicy) -> int | None:
    """Return the heading level *policy* numbers floats by, or ``None`` to number straight through.

    A policy numbering by chapter numbers by its division's chapter heading level; one whose
    division has no chapters (a top-level division of sections) numbers straight through, as a
    sequential policy does.

    Args:
        policy: The work's structural policy.

    Returns:
        The chapter heading level, or ``None``.
    """
    if policy.float_numbering is not FloatNumberingStyle.BY_CHAPTER:
        return None
    return policy.top_level_division.chapter_heading_level


def _label_inlines(number: FloatNumber) -> list[pf.Inline]:
    """Return the label that leads a numbered float's caption: its kind's label and its number, in bold."""
    return [pf.Strong(pf.Str(f"{number.kind.label} {number.text}.")), pf.Space()]


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def label_floats(doc: pf.Doc, numbers: Mapping[Uid, FloatNumber]) -> None:
    """Write each numbered float's label into its caption in *doc*, in place.

    Every :class:`~panflute.Figure` or :class:`~panflute.Table` whose identifier is a float
    identifier, and whose wrapper is among *numbers*, has its caption's first block led by the
    label (*Figure 2.3.*, in bold, then a space).  A float with no number — one never displayed
    by the reading-order walk, which validation reports — keeps its bare caption.

    Args:
        doc: The document to label.
        numbers: Each displayed float's number, keyed by wrapper UID.
    """

    def _label(elem: pf.Element, _doc: pf.Doc) -> None:
        if not isinstance(elem, (pf.Figure, pf.Table)) or not elem.identifier.startswith(FLOAT_ID_PREFIX):
            return
        number: FloatNumber | None = numbers.get(elem.identifier[len(FLOAT_ID_PREFIX) :])
        if number is None:
            return
        caption_blocks: Final[list[pf.Block]] = list(elem.caption.content)
        if caption_blocks and isinstance(caption_blocks[0], (pf.Plain, pf.Para)):
            caption_blocks[0].content = pf.ListContainer(*_label_inlines(number), *caption_blocks[0].content)

    doc.walk(_label)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def prepare_floats(doc: pf.Doc, vertex_tree: VertexTree, policy: StructuralPolicy) -> PreparedFloats:
    """Number *vertex_tree*'s floats per *policy* and label them in *doc*.

    Args:
        doc: The document built from *vertex_tree*, labelled in place.
        vertex_tree: The tree whose floats to number.
        policy: The work's structural policy, giving the numbering style and the chapter level.

    Returns:
        The floats and their numbers, for the link resolver.
    """
    numbering = float_numbers(vertex_tree, float_chapter_level(policy))
    label_floats(doc, numbering.numbers)
    return PreparedFloats(floats=floats_in(vertex_tree), numbers=numbering.numbers)
