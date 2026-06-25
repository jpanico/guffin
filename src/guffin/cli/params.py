"""Typer parameter declarations shared across the Guffin CLI commands.

Each alias bundles a shared argument/option's type with its Typer ``Argument``/``Option`` metadata
(flags, environment variable, help) so that a single declaration is reused by every command that
takes the parameter; a per-command default, when needed, is still supplied at the call site.

Public symbols:

- :data:`TargetArgument` — the page-title-or-node-UID positional argument.
- :data:`PortOption` — ``--port`` / ``-p`` Roam Local API port option.
- :data:`GraphOption` — ``--graph`` / ``-g`` Roam graph-name option.
- :data:`TokenOption` — ``--token`` / ``-t`` Roam Local API bearer-token option.

Each alias is a plain ``Name = Annotated[...]`` assignment rather than a PEP 695 ``type`` alias:
Typer resolves the embedded ``Argument``/``Option`` metadata off the annotation object and cannot see
through a ``TypeAliasType`` (it raises ``RuntimeError: Type not yet supported``).
"""

from typing import Annotated

import typer

from guffin.roam.primitives import ANCHORED_UID_PATTERN

TargetArgument = Annotated[
    str,
    typer.Argument(
        help=(
            "Roam page title or node UID. "
            f"Treated as a node UID if it matches {ANCHORED_UID_PATTERN}; "
            "otherwise treated as a page title."
        ),
    ),
]

PortOption = Annotated[
    int,
    typer.Option(
        "--port",
        "-p",
        envvar="GUFFIN_ROAM_LOCAL_API_PORT",
        help="Port for Roam Local API",
    ),
]

GraphOption = Annotated[
    str,
    typer.Option(
        "--graph",
        "-g",
        envvar="GUFFIN_ROAM_GRAPH_NAME",
        help="Name of the Roam graph",
    ),
]

TokenOption = Annotated[
    str,
    typer.Option(
        "--token",
        "-t",
        envvar="GUFFIN_ROAM_API_TOKEN",
        help="Bearer token for Roam Local API authentication",
    ),
]
