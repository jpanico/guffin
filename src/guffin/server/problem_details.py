"""RFC 9457 problem-details responses (``application/problem+json``).

Public symbols:

- :data:`PROBLEM_MEDIA_TYPE` — the problem-details IANA media type.
- :func:`problem_response` — a problem-details JSON response for a failure.
"""

from collections.abc import Mapping
from typing import Final

from fastapi.responses import JSONResponse
from pydantic import validate_call

from guffin.common.json_value import JsonValue

PROBLEM_MEDIA_TYPE: Final[str] = "application/problem+json"
"""The RFC 9457 problem-details IANA media type."""


@validate_call
def problem_response(
    status_code: int,
    title: str,
    detail: str,
    extensions: Mapping[str, JsonValue] | None = None,
) -> JSONResponse:
    """Return an RFC 9457 problem-details response describing a failure.

    Args:
        status_code: The HTTP status code, mirrored into the body's ``status`` member.
        title: A short, human-readable summary of the problem type.
        detail: The complete, human-readable explanation of this occurrence.
        extensions: Optional additional members merged into the body (e.g. an exit code).

    Returns:
        A :class:`~fastapi.responses.JSONResponse` with the problem media type.
    """
    body: Final[dict[str, JsonValue]] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    body.update(extensions or {})
    return JSONResponse(content=body, status_code=status_code, media_type=PROBLEM_MEDIA_TYPE)
