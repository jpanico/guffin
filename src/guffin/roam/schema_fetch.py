"""Roam Research Datomic schema fetching via the Local API.

Public symbols:

- :class:`FetchRoamSchema` — stateless utility class that fetches the Datomic
  schema for a Roam graph via the Local API's ``data.q`` action.

The schema model types (:data:`~guffin.roam.schema.RoamSchema`,
:class:`~guffin.roam.schema.SchemaNamespace`,
:class:`~guffin.roam.schema.SchemaAttribute`) are defined in
:mod:`guffin.roam.schema`.
"""

import logging
import textwrap
from typing import Final, final

from pydantic import BaseModel, ConfigDict, validate_call

from guffin.roam.local_api import (
    ApiEndpoint,
    invoke_action,
)
from guffin.roam.local_api import (
    Request as LocalApiRequest,
)
from guffin.roam.local_api import (
    Response as LocalApiResponse,
)
from guffin.roam.schema import RoamSchema, SchemaAttribute, SchemaNamespace

logger = logging.getLogger(__name__)


@final
class FetchRoamSchema:
    """Stateless utility class for fetching the Roam Datomic schema from the Roam Research Local API.

    Executes a ``data.q`` action via the Local API, which proxies
    ``roamAlphaAPI.data.q`` through the Roam Desktop app's local HTTP server.
    The schema is returned as a :data:`~guffin.roam.schema.RoamSchema`.

    Delegates HTTP transport to :func:`~guffin.roam.local_api.invoke_action`,
    which handles header construction and error raising.
    """

    def __init__(self) -> None:
        """Prevent instantiation of this stateless utility class."""
        raise TypeError("FetchRoamSchema is a stateless utility class and cannot be instantiated")

    class Request:
        """Namespace for the ``data.q`` schema request."""

        DATALOG_SCHEMA_QUERY: Final[str] = textwrap.dedent("""\
            [:find ?namespace ?attr
            :where
            [_ ?attr]
            [(namespace ?attr) ?namespace]]""")

        PAYLOAD: Final[LocalApiRequest.Payload] = LocalApiRequest.Payload(
            action="data.q",
            args=[DATALOG_SCHEMA_QUERY],
        )

    class Response:
        """Namespace for ``data.q`` schema response types."""

        class Payload(BaseModel):
            """Parsed ``data.q`` schema response payload (raw wire format).

            ``result`` holds the raw ``(namespace, attr_name)`` string pairs
            exactly as returned by the Local API.  :meth:`FetchRoamSchema.fetch`
            converts them to :data:`RoamSchema` (``list[SchemaAttribute]``).
            """

            model_config = ConfigDict(frozen=True)

            success: bool
            result: list[tuple[str, str]]

    @staticmethod
    @validate_call
    def fetch(api_endpoint: ApiEndpoint) -> RoamSchema:
        """Fetch the Roam Datomic schema via the Local API.

        Executes the ``data.q`` schema query and returns all attributes present in
        the graph's Datomic schema as :class:`~guffin.roam.schema.SchemaAttribute` members.

        Args:
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.

        Returns:
            A :data:`~guffin.roam.schema.RoamSchema` — a list of
            :class:`~guffin.roam.schema.SchemaAttribute` members, one per row in the
            schema query result.

        Raises:
            ValueError: If a ``(namespace, attr_name)`` pair returned by the live graph
                has no matching :class:`~guffin.roam.schema.SchemaAttribute` member
                (schema drift detected).
            ValidationError: If ``api_endpoint`` is ``None`` or invalid.
            requests.exceptions.ConnectionError: If the Local API is unreachable.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        logger.debug("api_endpoint: %s", api_endpoint)

        local_api_response_payload: LocalApiResponse.Payload = invoke_action(
            FetchRoamSchema.Request.PAYLOAD, api_endpoint
        )
        logger.debug("local_api_response_payload: %s", local_api_response_payload)

        schema_response_payload: FetchRoamSchema.Response.Payload = FetchRoamSchema.Response.Payload.model_validate(
            local_api_response_payload.model_dump(mode="json")
        )
        logger.debug("schema_response_payload: %s", schema_response_payload)

        raw_result: list[tuple[str, str]] = schema_response_payload.result
        return [SchemaAttribute((SchemaNamespace(ns), attr_name)) for ns, attr_name in raw_result]
