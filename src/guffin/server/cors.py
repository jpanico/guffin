"""Cross-origin admission: the CORS grants that let a browser page's JavaScript use the server.

The endpoints serve any HTTP client, but a *browser* page's JavaScript is additionally subject
to the browser's CORS enforcement: without the grant headers this module supplies, the browser
withholds responses from the page (simple requests) or never sends the request at all
(preflighted ones).  Admission is origin-scoped and strictly additive — an application wrapped
with the grants answers non-browser clients exactly as before, and a CORS grant governs only
what a browser lets a page read; it authenticates nothing.

The grants also cover Chromium's Private Network Access check: a preflight asking
``Access-Control-Request-Private-Network`` (sent when a public page addresses a
private-network server, e.g. loopback) is answered with
``Access-Control-Allow-Private-Network: true`` — harmless where the check is not enforced,
required where it is.

Public symbols:

- :data:`ALLOWED_METHODS` — the HTTP methods a cross-origin page may use.
- :data:`ALLOWED_REQUEST_HEADERS` — the non-safelisted request headers a preflight may claim.
- :data:`EXPOSED_RESPONSE_HEADERS` — the response headers a cross-origin page may read.
- :func:`cors_wrapped_app` — an ASGI application wrapped with origin-scoped CORS grants.
"""

from collections.abc import Sequence
from typing import Final

from pydantic import ConfigDict, validate_call
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

ALLOWED_METHODS: Final[tuple[str, ...]] = ("GET", "POST", "OPTIONS")
"""The HTTP methods a cross-origin page may use — exactly the methods the endpoints answer."""

ALLOWED_REQUEST_HEADERS: Final[tuple[str, ...]] = ("Content-Type",)
"""The non-safelisted request headers a preflight may claim (a JSON body's ``Content-Type``)."""

EXPOSED_RESPONSE_HEADERS: Final[tuple[str, ...]] = ("Content-Disposition", "Content-Digest")
"""The response headers a cross-origin page may read beyond the CORS-safelisted set.

Without the exposure a page can read a response's body but not the download filename it
should save under (``Content-Disposition``) nor the integrity digest it could verify
(``Content-Digest``).
"""


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def cors_wrapped_app(application: ASGIApp, allowed_origins: Sequence[str]) -> CORSMiddleware:
    """Return *application* wrapped with CORS grants admitting *allowed_origins*.

    The wrap is non-mutating: *application* itself is untouched, and running it unwrapped
    emits no CORS headers at all.  The grants are fixed to the server's surface — methods
    :data:`ALLOWED_METHODS`, request headers :data:`ALLOWED_REQUEST_HEADERS`, exposed response
    headers :data:`EXPOSED_RESPONSE_HEADERS`, and the Private Network Access preflight
    answer — with the origin list the only variable.

    Args:
        application: The ASGI application to wrap.
        allowed_origins: The web origins (``scheme://host[:port]``) admitted by the grants.

    Returns:
        The wrapped ASGI application.
    """
    return CORSMiddleware(
        application,
        allow_origins=list(allowed_origins),
        allow_methods=list(ALLOWED_METHODS),
        allow_headers=list(ALLOWED_REQUEST_HEADERS),
        allow_private_network=True,
        expose_headers=list(EXPOSED_RESPONSE_HEADERS),
    )
