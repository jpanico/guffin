"""Roam Research Local API endpoint models and HTTP transport.

Public symbols:

- :class:`ApiEndpointURL` — immutable Pydantic model that encapsulates the host,
  port, and graph name needed to construct the full URL for a single Roam graph's
  Local API endpoint.
- :class:`ApiEndpoint` — pairs an :class:`ApiEndpointURL` with its bearer token
  for authenticated API calls.
- :class:`Request` — namespace for request-related types (:class:`Request.Payload`,
  :class:`Request.Headers`) and the :meth:`Request.Headers.with_bearer_token` factory.
- :class:`Response` — namespace for response-related types (:class:`Response.Payload`).
- :func:`invoke_action` — sends an authenticated POST to the Local API and returns
  the parsed :class:`Response.Payload`.
"""

import logging
from typing import ClassVar, Final, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, validate_call

logger = logging.getLogger(__name__)


class ApiEndpointURL(BaseModel):
    """Immutable API endpoint URL for a single Roam Research graph.

    Pydantic ensures that ``local_api_port`` and ``graph_name`` are required and
    non-empty. Once created, instances cannot be modified (frozen).

    Attributes:
        local_api_port: Port on which the Roam Local API is listening.
        graph_name: Name of the target Roam graph (non-empty).
    """

    model_config = ConfigDict(frozen=True)

    local_api_port: int
    graph_name: str = Field(min_length=1)

    SCHEME: ClassVar[Final[str]] = "http"
    HOST: ClassVar[Final[str]] = "127.0.0.1"
    API_PATH_STEM: ClassVar[Final[str]] = "/api/"

    def __str__(self) -> str:
        """Return the full API endpoint URL string."""
        return f"{self.SCHEME}://{self.HOST}:{self.local_api_port}{self.API_PATH_STEM}{self.graph_name}"


class ApiEndpoint(BaseModel):
    """Immutable pairing of a Roam Local API endpoint URL and its bearer token.

    Bundles the two values required for every authenticated Local API call.
    Once created, instances cannot be modified (frozen).

    Attributes:
        url: The endpoint URL identifying the host, port, and graph.
        bearer_token: Bearer token for authenticating with the Local API (non-empty).
    """

    model_config = ConfigDict(frozen=True)

    url: ApiEndpointURL
    bearer_token: str = Field(min_length=1)

    @classmethod
    def from_parts(cls, local_api_port: int, graph_name: str, bearer_token: str) -> ApiEndpoint:
        """Construct an ApiEndpoint from its constituent primitive values.

        Convenience factory for the common case where the port, graph name, and
        bearer token are available as separate values (e.g. from CLI args or
        environment variables) rather than as a pre-built :class:`ApiEndpointURL`.

        Args:
            local_api_port: Port on which the Roam Local API is listening.
            graph_name: Name of the target Roam graph (non-empty).
            bearer_token: Bearer token for authenticating with the Local API (non-empty).

        Returns:
            A frozen :class:`ApiEndpoint` instance.
        """
        return cls(
            url=ApiEndpointURL(local_api_port=local_api_port, graph_name=graph_name),
            bearer_token=bearer_token,
        )


class Request:
    """Namespace for Roam Local API request types and header construction.

    Class Attributes:
        Headers: Pydantic model representing the HTTP headers sent with each request.
        Payload: Pydantic model describing the JSON body sent to the Local API.
    """

    class Headers(BaseModel):
        """HTTP headers for an authenticated Roam Local API request.

        Pydantic model whose field aliases match the wire-format header keys,
        so ``model_dump(by_alias=True)`` yields a ``dict[str, str]`` ready
        to pass directly to :func:`requests.post`. Once created, instances
        cannot be modified (frozen).

        Attributes:
            content_type: MIME type of the request body; always ``"application/json"``.
            authorization: Bearer token in the format ``"Bearer <token>"``.
        """

        model_config = ConfigDict(frozen=True)

        content_type: Literal["application/json"] = Field(default="application/json", alias="Content-Type")
        authorization: str = Field(alias="Authorization")

        @classmethod
        def with_bearer_token(cls, api_bearer_token: str) -> Request.Headers:
            """Construct a Headers instance from a bearer token.

            Args:
                api_bearer_token: Bearer token for authenticating with the Local API.

            Returns:
                A :class:`Request.Headers` instance with ``Content-Type`` set to
                ``"application/json"`` and ``Authorization`` set to
                ``"Bearer <api_bearer_token>"``.
            """
            return cls(Authorization=f"Bearer {api_bearer_token}")

    class Payload(BaseModel):
        """JSON body for a Roam Local API POST request.

        Once created, instances cannot be modified (frozen).

        Attributes:
            action: The Local API action to invoke (e.g. ``"pull-block"``).
            args: Positional arguments passed to the action.
        """

        model_config = ConfigDict(frozen=True)

        action: str
        args: list[object]


class Response:
    """Namespace for Roam Local API response types.

    Class Attributes:
        Payload: Pydantic model describing the parsed JSON body returned by the Local API.
    """

    class Payload(BaseModel):
        """Parsed JSON body of a successful Roam Local API response.

        Once created, instances cannot be modified (frozen).

        Attributes:
            success: Status string from the API (e.g. ``'success'``).
            result: Action-specific result data keyed by string.
        """

        model_config = ConfigDict(frozen=True)

        success: bool
        result: Final[object]


@validate_call
def invoke_action(request_payload: Request.Payload, api_endpoint: ApiEndpoint) -> Response.Payload:
    """Invoke a Roam Local API action and return the parsed response.

    Builds the ``Authorization`` and ``Content-Type`` headers via
    :meth:`Request.Headers.with_bearer_token`, POSTs the payload as JSON to
    ``api_endpoint.url``, and returns the parsed :class:`Response.Payload` on success.

    Args:
        request_payload: The :class:`Request.Payload` describing the action and its arguments.
        api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.

    Returns:
        The parsed :class:`Response.Payload` from the Local API.

    Raises:
        requests.exceptions.ConnectionError: If the Local API is unreachable.
        requests.exceptions.HTTPError: If the Local API returns a non-200 status.
    """
    logger.debug("payload: %s, api_endpoint: %s", request_payload, api_endpoint)
    request_headers: Final[Request.Headers] = Request.Headers.with_bearer_token(api_endpoint.bearer_token)

    response: Final[requests.Response] = requests.post(
        str(api_endpoint.url),
        json=request_payload.model_dump(mode="json"),
        headers=request_headers.model_dump(by_alias=True),
        stream=False,
    )
    logger.debug("response: %s", response)

    if response.status_code == 200:
        return Response.Payload.model_validate_json(response.text)
    else:
        error_msg: str = f"Failed to make request. Status Code: {response.status_code}, Response: {response.text}"
        logger.error(error_msg)
        raise requests.exceptions.HTTPError(error_msg)
