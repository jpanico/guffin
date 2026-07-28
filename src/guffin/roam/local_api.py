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
- :data:`TRANSIENT_RAW_KEYS` — Local API wire keys carrying transient session/UI state
  (block open/collapse, page sidebar, edit/create timestamps and users, nonces, word count),
  irrelevant to a node's structural content.
- :func:`without_transient_keys` — drop every :data:`TRANSIENT_RAW_KEYS` entry from each pull-block
  of a raw Datalog result.
"""

import logging
from typing import ClassVar, Final, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, SecretStr, validate_call

from guffin.common.json_value import JsonValue

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

    The token is held as a :class:`~pydantic.SecretStr`, so it is masked wherever the endpoint is
    rendered — ``repr``, ``str``, and ``model_dump``/``model_dump_json`` alike.  Every Local API
    call logs its endpoint at DEBUG, and an endpoint is a parameter of much of the fetch layer, so
    a plain string would reach the logs from many sites; masking it at the field is the one place
    that covers them all.  Read the value deliberately, via
    :meth:`~pydantic.SecretStr.get_secret_value`.

    Attributes:
        url: The endpoint URL identifying the host, port, and graph.
        bearer_token: Bearer token for authenticating with the Local API (non-empty), masked
            in every rendering of the model.
    """

    model_config = ConfigDict(frozen=True)

    url: ApiEndpointURL
    bearer_token: SecretStr = Field(min_length=1)

    @classmethod
    def from_parts(cls, local_api_port: int, graph_name: str, bearer_token: str) -> ApiEndpoint:
        """Construct an ApiEndpoint from its constituent primitive values.

        Convenience factory for the common case where the port, graph name, and
        bearer token are available as separate values (e.g. from CLI args or
        environment variables) rather than as a pre-built :class:`ApiEndpointURL`.

        Args:
            local_api_port: Port on which the Roam Local API is listening.
            graph_name: Name of the target Roam graph (non-empty).
            bearer_token: Bearer token for authenticating with the Local API (non-empty); a
                plain string here, wrapped into the model's masked field on construction.

        Returns:
            A frozen :class:`ApiEndpoint` instance.
        """
        return cls(
            url=ApiEndpointURL(local_api_port=local_api_port, graph_name=graph_name),
            bearer_token=SecretStr(bearer_token),
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
    # The one deliberate read of the secret: it has to reach the Authorization header.
    request_headers: Final[Request.Headers] = Request.Headers.with_bearer_token(
        api_endpoint.bearer_token.get_secret_value()
    )
    request_url: Final[str] = str(api_endpoint.url)
    json_body: Final[dict[str, JsonValue]] = request_payload.model_dump(mode="json")
    header_fields: Final[dict[str, str]] = request_headers.model_dump(by_alias=True)

    response: Final[requests.Response] = requests.post(
        request_url,
        json=json_body,
        headers=header_fields,
        stream=False,
    )
    logger.debug("response: %s", response)

    if response.status_code != 200:
        error_msg: Final[str] = (
            f"Failed to make request. Status Code: {response.status_code}, Response: {response.text}"
        )
        logger.error(error_msg)
        raise requests.exceptions.HTTPError(error_msg)
    return Response.Payload.model_validate_json(response.text)


TRANSIENT_RAW_KEYS: Final[frozenset[str]] = frozenset(
    {
        "open",  # :block/open — expand/collapse UI state
        "sidebar",  # :page/sidebar — right-sidebar UI state
        "dirty?",  # :page/dirty? — pending-unsynced-changes sync flag
        "time",  # :create/time — creation timestamp
        "user",  # :create/user — creating-user ref
        "edit-time",  # :edit/time — last-edit timestamp
        "edit-user",  # :edit/user — last-editing-user ref
        "edit-nonce",  # :page/edit-nonce — edit nonce
        "seen-by",  # :edit/seen-by — seen-by user refs
        "word-count",  # :page/word-count — page word count
        "prevent-clean",  # :restrictions/prevent-clean — restriction flag
        # :block/view-type — a per-block display default the Alpha API writes onto any block it
        # updates; pulled under its own alias so it cannot collide with the authored children
        # layout, and transient here because an extension touching a block would otherwise move
        # the content snapshot without the content having changed.
        "block-view-type",
    }
)
"""Local API wire keys carrying transient session/UI state, not a node's structural content.

These attributes change with ordinary Roam activity (expanding a block, opening the sidebar, editing,
viewing) without altering the exported document, so they are noise for any content-oriented consumer.
The wire key is the namespace-stripped attribute name the Local API returns (e.g. ``:block/open`` →
``open``); the comment on each entry records its source Datomic attribute.
"""


@validate_call
def without_transient_keys(raw_result: list[list[dict[str, object]]]) -> list[list[dict[str, object]]]:
    """Return *raw_result* with every :data:`TRANSIENT_RAW_KEYS` entry dropped from each pull-block.

    A raw Datalog result is rows of pulled entities, each a flat pull-block ``dict`` whose transient
    attributes (block open state, page sidebar, edit/create metadata, …) are top-level keys — nested
    values are only ``{id}`` reference stubs and property maps, which carry no transient keys.  So
    dropping the transient keys from each block dict fully removes them.  Side-effect-free: builds and
    returns a new structure rather than mutating *raw_result*.

    Args:
        raw_result: The raw Datalog query result, as stored in
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.raw_result`.

    Returns:
        A copy of *raw_result* with every transient key removed from each pull-block.
    """
    return [
        [{key: value for key, value in block.items() if key not in TRANSIENT_RAW_KEYS} for block in row]
        for row in raw_result
    ]
