#!/usr/bin/env python3
"""CLI launcher for the Guffin HTTP server.

Starts a uvicorn server on the ASGI application in :mod:`guffin.server.app`, which exposes the
Guffin commands as HTTP command endpoints (``POST /v1/export``, ``POST /v1/dump``,
``GET /v1/health``).  The server must run on the machine where the Roam Desktop app runs — the
Roam Local API answers only there — and binds ``127.0.0.1`` by default; exposing it beyond the
host is an explicit ``--host`` decision.

Logging is colorized by level via :mod:`guffin.cli.logging_config` and configurable via the
``LOG_LEVEL`` environment variable (default: ``INFO``).

Public symbols:

- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`main` — the CLI entry point; registered as the ``guffin-server`` console script.

Example::

    guffin-server
    guffin-server --host 0.0.0.0 --port 9000
"""

import logging
from typing import Annotated, Final

import typer
import uvicorn

from guffin.cli.logging_config import configure_logging
from guffin.cli.params import VersionOption
from guffin.server.app import app as asgi_app

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer()

DEFAULT_HOST: Final[str] = "127.0.0.1"
"""The default bind address: the local host only, never the network."""

DEFAULT_PORT: Final[int] = 8077
"""The default TCP port the server listens on."""


@app.command()
def main(
    host: Annotated[
        str,
        typer.Option(
            "--host",
            envvar="GUFFIN_SERVER_HOST",
            help=(
                "Address to bind. The default serves the local host only; binding a network "
                "address (e.g. 0.0.0.0) exposes the server — and the Roam bearer tokens riding "
                "in request bodies — to that network, so front it with TLS or a trusted path."
            ),
        ),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            envvar="GUFFIN_SERVER_PORT",
            help="TCP port to listen on.",
        ),
    ] = DEFAULT_PORT,
    version: VersionOption = False,
) -> None:
    """Serve the Guffin commands over HTTP (export/dump command endpoints plus health).

    Runs until interrupted.  The process must be colocated with the Roam Desktop app: every
    request's Roam fetch goes through the Roam Local API, which listens only on the local host
    of the machine running Roam Desktop.
    """
    logger.info("serving guffin on http://%s:%d (endpoints: /v1/export, /v1/dump, /v1/health)", host, port)
    uvicorn.run(asgi_app, host=host, port=port)


if __name__ == "__main__":
    app()
