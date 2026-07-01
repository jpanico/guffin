"""The classification assigned to each normalized graph vertex.

Public symbols:

- **Enumerations**: :class:`VertexType` — the string enum classifying a vertex by the shape of its
  source :class:`~guffin.roam.node.RoamNode`.
"""

from enum import StrEnum


class VertexType(StrEnum):
    """Classification assigned to each vertex during transcription.

    Every :class:`~guffin.roam.node.RoamNode` is classified into exactly one
    ``VertexType`` based on the shape of its raw fields.  The values are
    string-valued so they serialize cleanly to/from JSON without extra conversion.

    Values:
        PAGE: Normalized form of a Roam *Page* node — ``:node/title`` is
            present; ``:block/string`` is absent.
        TEXT: Normalized form of a Roam *Block* node that has no
            ``heading`` property — i.e. normal body text.
        HEADING: Normalized form of a Roam *Block* node that carries a
            ``heading`` property (value 1, 2, or 3).
        IMAGE: Normalized form of a Roam *Block* node whose
            ``:block/string`` embeds a Cloud Firestore URL pointing to a
            Roam-managed image upload.
        CALLOUT: Normalized form of a Roam *Block* node whose
            ``:block/string`` starts with ``[[>]] [[!<TYPE>]]`` — a Roam callout marker.
        CODE_BLOCK: Normalized form of a Roam *Block* node whose
            ``:block/string`` is a CommonMark fenced code block.
        BLOCK_QUOTE: Normalized form of a Roam *Block* node whose
            ``:block/string`` is a standard Markdown block quote (``> text``) or a
            Roam-specific block quote (``[[>]] text``).
        TABLE: Normalized form of a Roam native table node — a block whose
            ``:block/string`` equals ``{{table}}``, with its child blocks forming the
            rows and each child's children forming the cells.
        BLOCK_EMBED: Normalized form of a Roam *Block* node whose
            ``:block/string`` is wholly a block embed (``{{embed: ((<uid>))}}``),
            transcluding the referenced block.
    """

    PAGE = "guffin/page"
    TEXT = "guffin/text"
    HEADING = "guffin/heading"
    IMAGE = "guffin/image"
    CALLOUT = "guffin/callout"
    CODE_BLOCK = "guffin/code-block"
    BLOCK_QUOTE = "guffin/block-quote"
    TABLE = "guffin/table"
    BLOCK_EMBED = "guffin/block-embed"
