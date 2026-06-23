"""Tests for the roam_local_api module."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from guffin.roam.local_api import ApiEndpoint, ApiEndpointURL, Request, Response, invoke_action

logger = logging.getLogger(__name__)


class TestApiEndpointURL:
    """Tests for the ApiEndpointURL Pydantic model."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_valid_initialization(self) -> None:
        """Test creating ApiEndpointURL with valid port and graph name."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        assert url.local_api_port == 3333
        assert url.graph_name == "SCFH"

    def test_port_coercion_from_string(self) -> None:
        """Test that local_api_port coerces a numeric string to int."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port="8080", graph_name="my-graph")  # type: ignore[arg-type]
        assert url.local_api_port == 8080
        assert isinstance(url.local_api_port, int)

    def test_missing_port_raises_validation_error(self) -> None:
        """Test that omitting local_api_port raises ValidationError."""
        with pytest.raises(ValidationError):
            ApiEndpointURL(graph_name="SCFH")  # type: ignore[call-arg]

    def test_missing_graph_name_raises_validation_error(self) -> None:
        """Test that omitting graph_name raises ValidationError."""
        with pytest.raises(ValidationError):
            ApiEndpointURL(local_api_port=3333)  # type: ignore[call-arg]

    def test_empty_graph_name_raises_validation_error(self) -> None:
        """Test that an empty string for graph_name raises ValidationError."""
        with pytest.raises(ValidationError):
            ApiEndpointURL(local_api_port=3333, graph_name="")

    def test_non_coercible_port_raises_validation_error(self) -> None:
        """Test that a non-numeric port string raises ValidationError."""
        with pytest.raises(ValidationError):
            ApiEndpointURL(local_api_port="not-a-port", graph_name="SCFH")  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # __str__
    # ------------------------------------------------------------------

    def test_str_basic(self) -> None:
        """Test that __str__ returns the correctly formatted URL."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        assert str(endpoint) == "http://127.0.0.1:3333/api/SCFH"

    def test_str_different_port(self) -> None:
        """Test that __str__ embeds an alternative port correctly."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=8080, graph_name="SCFH")
        assert str(endpoint) == "http://127.0.0.1:8080/api/SCFH"

    def test_str_different_graph_name(self) -> None:
        """Test that __str__ embeds an alternative graph name correctly."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="my-other-graph")
        assert str(endpoint) == "http://127.0.0.1:3333/api/my-other-graph"

    def test_str_uses_http_scheme(self) -> None:
        """Test that the URL always uses the http scheme."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        assert str(endpoint).startswith("http://")

    def test_str_uses_loopback_host(self) -> None:
        """Test that the URL always targets 127.0.0.1."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        assert "127.0.0.1" in str(endpoint)

    def test_str_contains_api_path_stem(self) -> None:
        """Test that the URL always contains the /api/ path stem."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        assert "/api/" in str(endpoint)

    # ------------------------------------------------------------------
    # Immutability
    # ------------------------------------------------------------------

    def test_immutable_port(self) -> None:
        """Test that local_api_port cannot be reassigned on a frozen instance."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        with pytest.raises(Exception):
            endpoint.local_api_port = 9999  # type: ignore[misc]

    def test_immutable_graph_name(self) -> None:
        """Test that graph_name cannot be reassigned on a frozen instance."""
        endpoint: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        with pytest.raises(Exception):
            endpoint.graph_name = "other-graph"  # type: ignore[misc]


class TestApiEndpoint:
    """Tests for the ApiEndpoint Pydantic model."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_valid_initialization(self) -> None:
        """Test creating ApiEndpoint with a valid URL and bearer token."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        endpoint: ApiEndpoint = ApiEndpoint(url=url, bearer_token="my-secret-token")
        assert endpoint.url == url
        assert endpoint.bearer_token == "my-secret-token"

    def test_missing_url_raises_validation_error(self) -> None:
        """Test that omitting url raises ValidationError."""
        with pytest.raises(ValidationError):
            ApiEndpoint(bearer_token="my-secret-token")  # type: ignore[call-arg]

    def test_missing_bearer_token_raises_validation_error(self) -> None:
        """Test that omitting bearer_token raises ValidationError."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        with pytest.raises(ValidationError):
            ApiEndpoint(url=url)  # type: ignore[call-arg]

    def test_empty_bearer_token_raises_validation_error(self) -> None:
        """Test that an empty string for bearer_token raises ValidationError."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        with pytest.raises(ValidationError):
            ApiEndpoint(url=url, bearer_token="")

    def test_null_url_raises_validation_error(self) -> None:
        """Test that passing None for url raises ValidationError."""
        with pytest.raises(ValidationError):
            ApiEndpoint(url=None, bearer_token="my-secret-token")  # type: ignore[arg-type]

    def test_null_bearer_token_raises_validation_error(self) -> None:
        """Test that passing None for bearer_token raises ValidationError."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        with pytest.raises(ValidationError):
            ApiEndpoint(url=url, bearer_token=None)  # type: ignore[arg-type]

    def test_url_coercion_from_dict(self) -> None:
        """Test that url can be coerced from a plain dict by Pydantic."""
        endpoint: ApiEndpoint = ApiEndpoint(
            url={"local_api_port": 3333, "graph_name": "SCFH"},  # type: ignore[arg-type]
            bearer_token="my-secret-token",
        )
        assert endpoint.url.local_api_port == 3333
        assert endpoint.url.graph_name == "SCFH"

    # ------------------------------------------------------------------
    # from_parts factory
    # ------------------------------------------------------------------

    def test_from_parts_valid(self) -> None:
        """Test that from_parts constructs a correct ApiEndpoint from primitives."""
        endpoint: ApiEndpoint = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="SCFH", bearer_token="my-secret-token"
        )
        assert endpoint.url.local_api_port == 3333
        assert endpoint.url.graph_name == "SCFH"
        assert endpoint.bearer_token == "my-secret-token"

    def test_from_parts_url_string(self) -> None:
        """Test that from_parts produces the same URL string as direct construction."""
        direct: ApiEndpoint = ApiEndpoint(
            url=ApiEndpointURL(local_api_port=3333, graph_name="SCFH"),
            bearer_token="my-secret-token",
        )
        from_parts: ApiEndpoint = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="SCFH", bearer_token="my-secret-token"
        )
        assert str(from_parts.url) == str(direct.url)

    def test_from_parts_empty_graph_name_raises_validation_error(self) -> None:
        """Test that from_parts raises ValidationError when graph_name is empty."""
        with pytest.raises(ValidationError):
            ApiEndpoint.from_parts(local_api_port=3333, graph_name="", bearer_token="my-secret-token")

    def test_from_parts_empty_bearer_token_raises_validation_error(self) -> None:
        """Test that from_parts raises ValidationError when bearer_token is empty."""
        with pytest.raises(ValidationError):
            ApiEndpoint.from_parts(local_api_port=3333, graph_name="SCFH", bearer_token="")

    def test_from_parts_result_is_frozen(self) -> None:
        """Test that the instance returned by from_parts is immutable."""
        endpoint: ApiEndpoint = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="SCFH", bearer_token="my-secret-token"
        )
        with pytest.raises(Exception):
            endpoint.bearer_token = "new-token"  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Immutability
    # ------------------------------------------------------------------

    def test_immutable_url(self) -> None:
        """Test that url cannot be reassigned on a frozen instance."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        endpoint: ApiEndpoint = ApiEndpoint(url=url, bearer_token="my-secret-token")
        new_url: ApiEndpointURL = ApiEndpointURL(local_api_port=8080, graph_name="other-graph")
        with pytest.raises(Exception):
            endpoint.url = new_url  # type: ignore[misc]

    def test_immutable_bearer_token(self) -> None:
        """Test that bearer_token cannot be reassigned on a frozen instance."""
        url: ApiEndpointURL = ApiEndpointURL(local_api_port=3333, graph_name="SCFH")
        endpoint: ApiEndpoint = ApiEndpoint(url=url, bearer_token="my-secret-token")
        with pytest.raises(Exception):
            endpoint.bearer_token = "new-token"  # type: ignore[misc]


class TestRequestHeaders:
    """Tests for the Request.Headers Pydantic model."""

    # ------------------------------------------------------------------
    # with_bearer_token factory
    # ------------------------------------------------------------------

    def test_with_bearer_token_sets_authorization(self) -> None:
        """Test that with_bearer_token formats the Authorization field as 'Bearer <token>'."""
        headers: Request.Headers = Request.Headers.with_bearer_token("my-secret-token")
        assert headers.authorization == "Bearer my-secret-token"

    def test_with_bearer_token_sets_content_type(self) -> None:
        """Test that with_bearer_token sets content_type to 'application/json' by default."""
        headers: Request.Headers = Request.Headers.with_bearer_token("my-secret-token")
        assert headers.content_type == "application/json"

    def test_model_dump_by_alias_produces_wire_format_keys(self) -> None:
        """Test that model_dump(by_alias=True) yields HTTP wire-format header names."""
        headers: Request.Headers = Request.Headers.with_bearer_token("my-secret-token")
        dumped: dict[str, str] = headers.model_dump(by_alias=True)
        assert set(dumped.keys()) == {"Content-Type", "Authorization"}
        assert dumped["Content-Type"] == "application/json"
        assert dumped["Authorization"] == "Bearer my-secret-token"


class TestRequestPayload:
    """Tests for the Request.Payload Pydantic model."""

    def test_valid_construction(self) -> None:
        """Test that a valid Request.Payload instance can be constructed."""
        payload: Request.Payload = Request.Payload(
            action="file.get",
            args=[{"url": "https://example.com/file.jpg", "format": "base64"}],
        )
        assert payload.action == "file.get"
        assert len(payload.args) == 1

    def test_is_base_model_at_runtime(self) -> None:
        """Test that Request.Payload is a BaseModel instance at runtime."""
        payload: Request.Payload = Request.Payload(action="q", args=[])
        assert isinstance(payload, Request.Payload)

    def test_empty_args_list(self) -> None:
        """Test that args can be an empty list."""
        payload: Request.Payload = Request.Payload(action="q", args=[])
        assert payload.args == []


class TestResponsePayload:
    """Tests for the Response.Payload Pydantic model."""

    def test_valid_construction(self) -> None:
        """Test that a valid Response.Payload instance can be constructed."""
        payload: Response.Payload = Response.Payload(success=True, result={"filename": "test.jpg"})
        assert payload.success is True
        assert payload.result == {"filename": "test.jpg"}

    def test_is_base_model_at_runtime(self) -> None:
        """Test that Response.Payload is a BaseModel instance at runtime."""
        payload: Response.Payload = Response.Payload(success=True, result={})
        assert isinstance(payload, Response.Payload)

    def test_empty_result(self) -> None:
        """Test that result can be an empty dict."""
        payload: Response.Payload = Response.Payload(success=True, result={})
        assert payload.result == {}


class TestMakeRequest:
    """Tests for the invoke_action module-level function."""

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def api_endpoint(self) -> ApiEndpoint:
        """Return a standard ApiEndpoint for use in tests."""
        return ApiEndpoint.from_parts(local_api_port=3333, graph_name="SCFH", bearer_token="test-token")

    @pytest.fixture
    def file_get_payload(self) -> Request.Payload:
        """Return a minimal file.get Request.Payload for use in tests."""
        return Request.Payload(
            action="file.get",
            args=[{"url": "https://firebasestorage.googleapis.com/test.jpg", "format": "base64"}],
        )

    @pytest.fixture
    def mock_200_response(self) -> MagicMock:
        """Return a mock requests.Response with status 200 and a minimal success body."""
        mock: MagicMock = MagicMock()
        mock.status_code = 200
        mock.text = json.dumps({"success": True, "result": {"filename": "test.jpg"}})
        return mock

    # ------------------------------------------------------------------
    # Success path
    # ------------------------------------------------------------------

    def test_200_returns_parsed_response_payload(
        self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload, mock_200_response: MagicMock
    ) -> None:
        """Test that a 200 response is parsed and returned as Response.Payload."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response):
            result: Response.Payload = invoke_action(file_get_payload, api_endpoint)

        assert result.success is True
        assert result.result == {"filename": "test.jpg"}

    def test_posts_to_endpoint_url(
        self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload, mock_200_response: MagicMock
    ) -> None:
        """Test that the POST is made to the correct endpoint URL."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            invoke_action(file_get_payload, api_endpoint)

        assert mock_post.call_args.args[0] == str(api_endpoint.url)

    def test_sends_authorization_header(
        self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload, mock_200_response: MagicMock
    ) -> None:
        """Test that the Authorization header contains the bearer token."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            invoke_action(file_get_payload, api_endpoint)

        headers: dict[str, str] = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {api_endpoint.bearer_token}"

    def test_sends_content_type_header(
        self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload, mock_200_response: MagicMock
    ) -> None:
        """Test that the Content-Type header is application/json."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            invoke_action(file_get_payload, api_endpoint)

        headers: dict[str, str] = mock_post.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/json"

    def test_sends_payload_as_json_body(
        self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload, mock_200_response: MagicMock
    ) -> None:
        """Test that the serialized payload dict is passed as the json kwarg."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            invoke_action(file_get_payload, api_endpoint)

        assert mock_post.call_args.kwargs["json"] == file_get_payload.model_dump()

    # ------------------------------------------------------------------
    # Error path
    # ------------------------------------------------------------------

    def test_403_raises_http_error(self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload) -> None:
        """Test that a 403 response raises requests.exceptions.HTTPError."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                invoke_action(file_get_payload, api_endpoint)

    def test_500_raises_http_error(self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload) -> None:
        """Test that a 500 response raises requests.exceptions.HTTPError."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                invoke_action(file_get_payload, api_endpoint)

    def test_error_message_contains_status_code(
        self, api_endpoint: ApiEndpoint, file_get_payload: Request.Payload
    ) -> None:
        """Test that the HTTPError message includes the status code."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError, match="401"):
                invoke_action(file_get_payload, api_endpoint)
