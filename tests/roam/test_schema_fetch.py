"""Tests for the roam_schema_fetch module."""

import json
import logging
import os
from typing import Final
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from guffin.roam.local_api import ApiEndpoint
from guffin.roam.schema_fetch import FetchRoamSchema
from guffin.roam.schema import RoamAttribute, RoamNamespace, RoamSchema

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_200_response() -> MagicMock:
    """Return a mock requests.Response with status 200 and a minimal schema body."""
    mock: Final[MagicMock] = MagicMock()
    mock.status_code = 200
    mock.text = json.dumps(
        {
            "success": True,
            "result": [
                ["block", "uid"],
                ["block", "string"],
                ["node", "title"],
            ],
        }
    )
    return mock


class TestFetchRoamSchemaInstantiation:
    """Tests that FetchRoamSchema cannot be instantiated."""

    def test_instantiation_raises_type_error(self) -> None:
        """Test that instantiating FetchRoamSchema raises TypeError."""
        with pytest.raises(TypeError, match="stateless utility class"):
            FetchRoamSchema()


class TestFetchRoamSchemaRequest:
    """Tests for FetchRoamSchema.Request constants."""

    def test_datalog_schema_query_is_non_empty(self) -> None:
        """Test that DATALOG_SCHEMA_QUERY is a non-empty string."""
        assert isinstance(FetchRoamSchema.Request.DATALOG_SCHEMA_QUERY, str)
        assert len(FetchRoamSchema.Request.DATALOG_SCHEMA_QUERY) > 0

    def test_datalog_schema_query_contains_find_clause(self) -> None:
        """Test that DATALOG_SCHEMA_QUERY contains a :find clause."""
        assert ":find" in FetchRoamSchema.Request.DATALOG_SCHEMA_QUERY

    def test_payload_action_is_data_q(self) -> None:
        """Test that PAYLOAD.action is 'data.q'."""
        assert FetchRoamSchema.Request.PAYLOAD.action == "data.q"

    def test_payload_args_contains_schema_query(self) -> None:
        """Test that PAYLOAD.args contains the schema query string."""
        assert FetchRoamSchema.Request.DATALOG_SCHEMA_QUERY in FetchRoamSchema.Request.PAYLOAD.args

    def test_payload_is_json_serializable(self) -> None:
        """Test that PAYLOAD round-trips through JSON correctly."""
        json_str: str = FetchRoamSchema.Request.PAYLOAD.model_dump_json()
        parsed: dict[str, object] = json.loads(json_str)

        assert parsed == {"action": "data.q", "args": [FetchRoamSchema.Request.DATALOG_SCHEMA_QUERY]}


class TestFetchRoamSchemaResponsePayload:
    """Tests for FetchRoamSchema.Response.Payload validation."""

    def test_valid_construction(self) -> None:
        """Test that a valid Payload can be constructed."""
        payload: FetchRoamSchema.Response.Payload = FetchRoamSchema.Response.Payload(
            success=True,
            result=[("block", "uid"), ("node", "title")],
        )

        assert payload.success is True
        assert len(payload.result) == 2

    def test_null_raises_validation_error(self) -> None:
        """Test that model_validate(None) raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamSchema.Response.Payload.model_validate(None)

    def test_valid_schema_result_parses_correctly(self) -> None:
        """Test that a list of [namespace, attr_name] pairs parses into raw string tuples."""
        raw: dict[str, object] = {
            "success": True,
            "result": [["block", "uid"], ["block", "string"], ["node", "title"]],
        }

        payload: FetchRoamSchema.Response.Payload = FetchRoamSchema.Response.Payload.model_validate(raw)

        assert payload.success is True
        assert len(payload.result) == 3
        assert payload.result[0] == ("block", "uid")
        assert payload.result[2] == ("node", "title")

    def test_missing_success_key_raises_error(self) -> None:
        """Test that a missing 'success' key raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamSchema.Response.Payload.model_validate({"result": [["block", "uid"]]})

    def test_missing_result_key_raises_error(self) -> None:
        """Test that a missing 'result' key raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamSchema.Response.Payload.model_validate({"success": True})

    def test_immutability(self) -> None:
        """Test that Payload instances are immutable (frozen)."""
        payload: FetchRoamSchema.Response.Payload = FetchRoamSchema.Response.Payload(
            success=True,
            result=[("block", "uid")],
        )
        with pytest.raises(Exception):
            payload.success = False  # type: ignore[misc]


class TestFetchRoamSchemaFetch:
    """Tests for FetchRoamSchema.fetch."""

    def test_null_api_endpoint_raises_validation_error(self) -> None:
        """Test that None api_endpoint raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamSchema.fetch(api_endpoint=None)  # type: ignore[arg-type]

    def test_http_error_response_raises_http_error(self, api_endpoint: ApiEndpoint) -> None:
        """Test that a non-200 response raises HTTPError."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                FetchRoamSchema.fetch(api_endpoint)

    def test_successful_fetch_returns_schema(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that a 200 response is parsed and returned as a list of RoamAttribute members."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response):
            result: RoamSchema = FetchRoamSchema.fetch(api_endpoint)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] is RoamAttribute.BLOCK_UID
        assert result[0].namespace is RoamNamespace.BLOCK
        assert result[0].attr_name == "uid"
        assert result[2] is RoamAttribute.NODE_TITLE
        assert result[2].namespace is RoamNamespace.NODE
        assert result[2].attr_name == "title"

    def test_posts_to_correct_endpoint_url(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that the POST is made to the correct endpoint URL."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            FetchRoamSchema.fetch(api_endpoint)

        assert mock_post.call_args.args[0] == str(api_endpoint.url)

    def test_posts_data_q_action(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that the POST body contains the data.q action."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            FetchRoamSchema.fetch(api_endpoint)

        posted_json: dict[str, object] = mock_post.call_args.kwargs["json"]
        assert posted_json["action"] == "data.q"

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_schema_matches_enum(self, live_api_endpoint: ApiEndpoint) -> None:
        """Live test: fetched schema must exactly match the RoamAttribute enum.

        Fails with a diff when either direction of drift is detected:

        - live graph has attributes not yet represented in :class:`RoamAttribute`
          (fetch raises ``ValueError`` — enum needs new members added), or
        - :class:`RoamAttribute` has stale members absent from the live graph
          (enum needs old members removed).
        """
        try:
            fetched: RoamSchema = FetchRoamSchema.fetch(live_api_endpoint)
        except ValueError as exc:
            pytest.fail(f"Live schema contains attribute(s) not in RoamAttribute enum: {exc}")

        fetched_set: set[RoamAttribute] = set(fetched)
        expected_set: set[RoamAttribute] = set(RoamAttribute)

        in_enum_not_fetched: set[RoamAttribute] = expected_set - fetched_set
        in_fetched_not_enum: set[RoamAttribute] = fetched_set - expected_set

        diffs: list[str] = []
        if in_enum_not_fetched:
            lines = sorted(f"  {a.namespace}/{a.attr_name}" for a in in_enum_not_fetched)
            diffs.append("In RoamAttribute enum but NOT in live schema:\n" + "\n".join(lines))
        if in_fetched_not_enum:
            lines = sorted(f"  {a.namespace}/{a.attr_name}" for a in in_fetched_not_enum)
            diffs.append("In live schema but NOT in RoamAttribute enum:\n" + "\n".join(lines))

        assert not diffs, "\n".join(diffs)

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_fetch(self, live_api_endpoint: ApiEndpoint) -> None:
        """Live test: fetch the real Datomic schema from a running Roam graph."""
        schema: RoamSchema = FetchRoamSchema.fetch(live_api_endpoint)

        assert isinstance(schema, list)
        assert len(schema) > 0
        assert all(isinstance(a, RoamAttribute) for a in schema)
        logger.debug(f"Fetched {len(schema)} schema entries")
        for attr in schema[:5]:
            logger.debug(f"  {attr.namespace}: {attr.attr_name}")
