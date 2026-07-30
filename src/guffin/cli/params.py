"""Typer parameter declarations shared across the Guffin CLI commands.

Each alias bundles a shared argument/option's type with its Typer ``Argument``/``Option`` metadata
(flags, environment variable, help) so that a single declaration is reused by every command that
takes the parameter; a per-command default, when needed, is still supplied at the call site.

Public symbols:

- :data:`TargetArgument` — the page-title-or-node-UID positional argument.
- :data:`PortOption` — ``--port`` / ``-p`` Roam Local API port option.
- :data:`GraphOption` — ``--graph`` / ``-g`` Roam graph-name option.
- :data:`TokenOption` — ``--token`` / ``-t`` Roam Local API bearer-token option.
- :data:`CacheDirOption` — ``--cache-dir`` / ``-c`` asset-cache directory option.
- :data:`VersionOption` — ``--version`` print-version-and-exit option.

Each alias is a plain ``Name = Annotated[...]`` assignment rather than a PEP 695 ``type`` alias:
Typer resolves the embedded ``Argument``/``Option`` metadata off the annotation object and cannot see
through a ``TypeAliasType`` (it raises ``RuntimeError: Type not yet supported``).
"""

import importlib.metadata
from pathlib import Path
from typing import Annotated

import typer

from guffin.roam.primitives import ANCHORED_UID_PATTERN


def _print_version_and_exit(value: bool) -> None:
    """Typer eager callback for ``--version``: print the guffin package version and exit.

    Eager, so the flag answers before any required parameter is demanded; a ``False`` value (the
    flag absent) does nothing.
    """
    if not value:
        return
    print(f"guffin {importlib.metadata.version('guffin')}")
    raise typer.Exit()


TargetArgument = Annotated[
    str,
    typer.Argument(
        help=(
            "Roam page title (optionally wrapped in [[ ]]), node UID, or block reference (( uid )). "
            f"Treated as a node UID when wrapped in (( )) or matching {ANCHORED_UID_PATTERN}; "
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

CacheDirOption = Annotated[
    Path | None,
    typer.Option(
        "--cache-dir",
        "-c",
        envvar="GUFFIN_CACHE_DIR",
        help=(
            "Directory for caching downloaded Cloud Firestore assets across runs. "
            "Unset, every run re-downloads every asset it displays or inspects."
        ),
    ),
]

VersionOption = Annotated[
    bool,
    typer.Option(
        "--version",
        callback=_print_version_and_exit,
        is_eager=True,
        help="Print the guffin package version and exit.",
    ),
]
