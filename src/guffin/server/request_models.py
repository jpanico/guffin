"""The server's concrete request models, derived from the CLI command signatures at import time.

Each command's request vocabulary is not written here — it is read off the command function's own
Typer signature via :mod:`guffin.server.request_derivation`, so the CLI declaration stays the
single source of truth for parameter names, types, flag spellings, and help text.  Two deliberate
per-command adjustments shape the derivation:

- the export vocabulary excludes ``output_dir`` — a remote client names no server path; the
  serving layer supplies a per-request output directory of its own;
- the dump vocabulary gains three console fields with no CLI counterpart (``console_format``,
  ``console_width``, ``ansi``) — how the captured rendering is represented, how wide it wraps,
  and whether a text representation keeps ANSI style escapes.  They are consumed by the serving
  layer and never translate to argv.

Public symbols:

- :data:`EXPORT_EXCLUDED_PARAMETERS` — export command parameters left out of the vocabulary.
- :data:`DEFAULT_CONSOLE_WIDTH` — the dump rendering width when a request names none.
- :data:`EXPORT_REQUEST_FIELDS` — the export command's derived request fields.
- :data:`DUMP_REQUEST_FIELDS` — the dump command's derived request fields.
- :data:`EXPORT_REQUEST_MODEL` — the export request model.
- :data:`DUMP_REQUEST_MODEL` — the dump request model.
"""

from typing import Final

from pydantic import BaseModel, Field

from guffin.cli import dump_roam_tree, export_roam_tree
from guffin.server.console_export import ConsoleFormat
from guffin.server.request_derivation import RequestField, derived_request_model, request_fields_for

EXPORT_EXCLUDED_PARAMETERS: Final[frozenset[str]] = frozenset({"output_dir"})
"""Export command parameters deliberately absent from the request vocabulary.

``output_dir`` names a server path a remote client has no business choosing; the serving layer
allocates a per-request output directory instead.
"""

DEFAULT_CONSOLE_WIDTH: Final[int] = 120
"""The character width a dump rendering wraps at when the request names none."""

EXPORT_REQUEST_FIELDS: Final[tuple[RequestField, ...]] = request_fields_for(
    export_roam_tree.main, excluded=EXPORT_EXCLUDED_PARAMETERS
)
"""The export command's derived request fields, in signature order."""

DUMP_REQUEST_FIELDS: Final[tuple[RequestField, ...]] = request_fields_for(dump_roam_tree.main)
"""The dump command's derived request fields, in signature order."""

EXPORT_REQUEST_MODEL: Final[type[BaseModel]] = derived_request_model("ExportRequest", EXPORT_REQUEST_FIELDS)
"""The export request model: one optional field per :data:`EXPORT_REQUEST_FIELDS` entry (target required)."""

DUMP_REQUEST_MODEL: Final[type[BaseModel]] = derived_request_model(
    "DumpRequest",
    DUMP_REQUEST_FIELDS,
    extra_definitions={
        "console_format": (
            ConsoleFormat,
            Field(
                default=ConsoleFormat.TEXT,
                description=(
                    "Representation of the captured console rendering: 'text' (default), "
                    "'html' (standalone HTML document), or 'svg' (terminal image)."
                ),
            ),
        ),
        "console_width": (
            int,
            Field(
                default=DEFAULT_CONSOLE_WIDTH,
                description="Character width the console rendering wraps at.",
            ),
        ),
        "ansi": (
            bool,
            Field(
                default=False,
                description=(
                    "Whether a 'text' representation keeps ANSI style escapes; the richer "
                    "representations always capture colored and ignore this."
                ),
            ),
        ),
    },
)
"""The dump request model: the derived fields plus the console representation extras."""
