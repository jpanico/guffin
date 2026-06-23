"""Tests for the roam_node_fetch module."""

import json
import logging
import os
from typing import Final
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml
from pydantic import ValidationError
from guffin.roam.local_api import ApiEndpoint, Response as LocalApiResponse
from guffin.roam.primitives import IdObject
from guffin.roam.node import RoamNode
from guffin.roam.node_fetch import FetchRoamNodes, RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec

from conftest import FIXTURES_YAML_DIR, article1_node_tree

logger = logging.getLogger(__name__)

# Fields excluded from live-test comparisons because they change with normal
# Roam activity and are not indicative of structural correctness.
_TRANSIENT_NODE_FIELDS: set[str] = {"time", "user", "open", "sidebar", "lookup", "seen_by"}


def _stable_node_dict(node: RoamNode) -> dict[str, object]:
    """Return a serialised *node* with all transient fields stripped."""
    return node.model_dump(exclude=_TRANSIENT_NODE_FIELDS)


@pytest.fixture
def mock_200_response() -> MagicMock:
    """Return a mock requests.Response with status 200 and a minimal page body."""
    mock: Final[MagicMock] = MagicMock()
    mock.status_code = 200
    mock.text = json.dumps(
        {
            "success": True,
            "result": [
                [
                    {
                        "title": "My Page",
                        "uid": "abc123xyz",
                        "id": 1,
                        "time": 1700000000000,
                        "user": {"id": 3},
                        "children": [],
                    }
                ]
            ],
        }
    )
    return mock


class TestFetchRoamNodesInstantiation:
    """Tests that FetchRoamNodes cannot be instantiated."""

    def test_instantiation_raises_type_error(self) -> None:
        """Test that instantiating FetchRoamNodes raises TypeError."""
        with pytest.raises(TypeError, match="stateless utility class"):
            FetchRoamNodes()


class TestFetchRoamNodesRequest:
    """Tests for FetchRoamNodes.Request constants and payload factory."""

    def test_datalog_page_query_is_non_empty(self) -> None:
        """Test that BY_PAGE_TITLE_QUERY is a non-empty string."""
        assert isinstance(FetchRoamNodes.Request.BY_PAGE_TITLE_QUERY, str)
        assert len(FetchRoamNodes.Request.BY_PAGE_TITLE_QUERY) > 0

    def test_datalog_page_query_contains_find_clause(self) -> None:
        """Test that BY_PAGE_TITLE_QUERY contains a :find clause."""
        assert ":find" in FetchRoamNodes.Request.BY_PAGE_TITLE_QUERY

    def test_datalog_page_query_contains_node_title(self) -> None:
        """Test that BY_PAGE_TITLE_QUERY filters by :node/title."""
        assert ":node/title" in FetchRoamNodes.Request.BY_PAGE_TITLE_QUERY

    def test_payload_action_is_data_q(self) -> None:
        """Test that payload_by_page_title() produces action 'data.q'."""
        assert FetchRoamNodes.Request.payload_by_page_title("Any Page").action == "data.q"

    def test_payload_args_contains_query_with_refs(self) -> None:
        """Test that payload_by_page_title() uses BY_PAGE_TITLE_WITH_REFS_QUERY by default."""
        args: list[object] = FetchRoamNodes.Request.payload_by_page_title("Any Page", True).args
        assert FetchRoamNodes.Request.BY_PAGE_TITLE_WITH_REFS_QUERY in args
        assert FetchRoamNodes.Request.DESCENDANT_AND_PAGE_REF_RULES in args

    def test_payload_args_contains_query_without_refs(self) -> None:
        """Test that payload_by_page_title(include_refs=False) uses BY_PAGE_TITLE_QUERY."""
        args: list[object] = FetchRoamNodes.Request.payload_by_page_title("Any Page", include_refs=False).args
        assert FetchRoamNodes.Request.BY_PAGE_TITLE_QUERY in args
        assert FetchRoamNodes.Request.DESCENDANT_RULE in args

    def test_payload_args_contains_page_title(self) -> None:
        """Test that payload_by_page_title() includes the page title in args."""
        assert "My Page" in FetchRoamNodes.Request.payload_by_page_title("My Page").args

    def test_payload_uid_args_contains_query_with_refs(self) -> None:
        """Test that payload_by_node_uid(include_refs=True) uses BY_NODE_UID_WITH_REFS_QUERY."""
        args: list[object] = FetchRoamNodes.Request.payload_by_node_uid("wdMgyBiP9", include_refs=True).args
        assert FetchRoamNodes.Request.BY_NODE_UID_WITH_REFS_QUERY in args
        assert FetchRoamNodes.Request.DESCENDANT_AND_PAGE_REF_RULES in args

    def test_payload_uid_args_contains_query_without_refs(self) -> None:
        """Test that payload_by_node_uid(include_refs=False) uses BY_NODE_UID_QUERY."""
        args: list[object] = FetchRoamNodes.Request.payload_by_node_uid("wdMgyBiP9", include_refs=False).args
        assert FetchRoamNodes.Request.BY_NODE_UID_QUERY in args
        assert FetchRoamNodes.Request.DESCENDANT_RULE in args

    def test_payload_uid_args_contains_node_uid(self) -> None:
        """Test that payload_by_node_uid() includes the node UID in args."""
        assert "wdMgyBiP9" in FetchRoamNodes.Request.payload_by_node_uid("wdMgyBiP9").args


class TestFetchRoamNodesResponsePayload:
    """Tests for FetchRoamNodes.Response.Payload validation."""

    def test_valid_construction(self) -> None:
        """Test that a valid Payload can be constructed."""
        payload: FetchRoamNodes.Response.Payload = FetchRoamNodes.Response.Payload(
            success=True,
            result=[
                [RoamNode(uid="abc123xyz", id=1, time=1700000000000, user=IdObject(id=3), title="My Page", children=[])]
            ],
        )

        assert payload.success is True
        assert len(payload.result) == 1
        assert payload.result[0][0].uid == "abc123xyz"

    def test_null_raises_validation_error(self) -> None:
        """Test that model_validate(None) raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.Response.Payload.model_validate(None)

    def test_valid_result_parses_correctly(self) -> None:
        """Test that a nested result dict is parsed into a list[list[RoamNode]]."""
        raw: dict[str, object] = {
            "success": True,
            "result": [
                [
                    {
                        "title": "My Page",
                        "uid": "abc123xyz",
                        "id": 1,
                        "time": 1700000000000,
                        "user": {"id": 3},
                        "children": [],
                    }
                ]
            ],
        }

        payload: FetchRoamNodes.Response.Payload = FetchRoamNodes.Response.Payload.model_validate(raw)

        assert payload.success is True
        assert len(payload.result) == 1
        node: RoamNode = payload.result[0][0]
        assert node.uid == "abc123xyz"
        assert node.title == "My Page"
        assert node.time == 1700000000000

    def test_empty_result_is_valid(self) -> None:
        """Test that an empty result list (page not found) is valid."""
        payload: FetchRoamNodes.Response.Payload = FetchRoamNodes.Response.Payload.model_validate(
            {"success": True, "result": []}
        )

        assert payload.result == []

    def test_missing_success_key_raises_error(self) -> None:
        """Test that a missing 'success' key raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.Response.Payload.model_validate({"result": [[{"uid": "abc123xyz", "title": "My Page"}]]})

    def test_missing_result_key_raises_error(self) -> None:
        """Test that a missing 'result' key raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.Response.Payload.model_validate({"success": True})

    def test_missing_uid_in_result_node_raises_error(self) -> None:
        """Test that a result node dict missing 'uid' raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.Response.Payload.model_validate({"success": True, "result": [[{"title": "My Page"}]]})

    def test_immutability(self) -> None:
        """Test that Payload instances are immutable (frozen)."""
        payload: FetchRoamNodes.Response.Payload = FetchRoamNodes.Response.Payload(
            success=True,
            result=[],
        )
        with pytest.raises(Exception):
            payload.success = False  # type: ignore[misc]


class TestFetchRoamNodesFetchByPageTitle:
    """Tests for FetchRoamNodes.fetch_by_page_title."""

    def test_null_api_endpoint_raises_validation_error(self) -> None:
        """Test that None api_endpoint raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                api_endpoint=None,  # type: ignore[arg-type]
            )

    def test_null_fetch_spec_raises_validation_error(self, api_endpoint: ApiEndpoint) -> None:
        """Test that None fetch_spec raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.fetch_by_page_title(fetch_spec=None, api_endpoint=api_endpoint)  # type: ignore[arg-type]

    def test_http_error_response_raises_http_error(self, api_endpoint: ApiEndpoint) -> None:
        """Test that a non-200 HTTP response raises requests.exceptions.HTTPError."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(requests.exceptions.HTTPError):
                FetchRoamNodes.fetch_by_page_title(
                    fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                    api_endpoint=api_endpoint,
                )

    def test_successful_fetch_returns_roam_nodes(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that a successful HTTP 200 response returns a NodeFetchResult with the fetched nodes."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response):
            result: NodeFetchResult = FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        assert len(result.network) == 1
        assert result.network[0].title == "My Page"
        assert result.network[0].uid == "abc123xyz"

    def test_page_not_found_raises_not_found_error(self, api_endpoint: ApiEndpoint) -> None:
        """Test that an empty result (page not found) raises RoamNodeNotFoundError carrying the fetch_spec."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"success": True, "result": []})

        spec: Final[NodeFetchSpec] = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="Nonexistent"), include_refs=False)
        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(RoamNodeNotFoundError) as exc_info:
                FetchRoamNodes.fetch_by_page_title(fetch_spec=spec, api_endpoint=api_endpoint)
        assert exc_info.value.fetch_spec == spec

    def test_posts_to_correct_endpoint_url(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that the POST is made to the correct endpoint URL."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        assert mock_post.call_args.args[0] == str(api_endpoint.url)

    def test_posts_data_q_action(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that the POST body contains the data.q action."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        posted_json: dict[str, object] = mock_post.call_args.kwargs["json"]
        assert posted_json["action"] == "data.q"

    def test_posts_page_title_in_args(self, api_endpoint: ApiEndpoint, mock_200_response: MagicMock) -> None:
        """Test that the POST body includes the page title in args."""
        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        posted_json: dict[str, object] = mock_post.call_args.kwargs["json"]
        assert "My Page" in posted_json["args"]  # type: ignore[operator]

    def test_bearer_token_in_request_headers(self, mock_200_response: MagicMock) -> None:
        """Test that the bearer token is correctly placed in the Authorization header."""
        token_endpoint: ApiEndpoint = ApiEndpoint.from_parts(
            local_api_port=3333,
            graph_name="test-graph",
            bearer_token="my-secret-token",
        )

        with patch("guffin.roam.local_api.requests.post", return_value=mock_200_response) as mock_post:
            FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="My Page"), include_refs=False),
                api_endpoint=token_endpoint,
            )

        headers: dict[str, object] = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-secret-token"

    def test_node_attributes_preserved(self, api_endpoint: ApiEndpoint) -> None:
        """Test that extra RoamNode fields (time, children) survive the HTTP round-trip."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(
            {
                "success": True,
                "result": [
                    [
                        {
                            "title": "Rich Page",
                            "uid": "rich1234x",
                            "id": 2,
                            "time": 1700000000000,
                            "user": {"id": 3},
                            "children": [{"id": 42}],
                        }
                    ],
                    [
                        {
                            "string": "A child block",
                            "uid": "richblk01",
                            "id": 42,
                            "time": 1700000000001,
                            "user": {"id": 3},
                            "order": 0,
                            "page": {"id": 2},
                            "parents": [{"id": 2}],
                        }
                    ],
                ],
            }
        )

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            result: NodeFetchResult = FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="Rich Page"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        assert len(result.network) == 2
        assert result.nodes_by_uid is not None
        assert result.nodes_by_uid["rich1234x"].time == 1700000000000
        assert result.nodes_by_uid["rich1234x"].children == [IdObject(id=42)]

    def test_block_props_preserved(self, api_endpoint: ApiEndpoint) -> None:
        """Test that block properties (:block/props) survive the HTTP round-trip.

        Blocks with Augmented Headings set (e.g. ah-level: h4) return a ``props``
        key in the pull-block JSON.  Verifies that the field is parsed into
        ``RoamNode.props`` and that nodes without ``props`` in the JSON get ``None``.
        """
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(
            {
                "success": True,
                "result": [
                    [
                        {
                            "title": "Heading Page",
                            "uid": "headng001",
                            "id": 1,
                            "time": 1700000000000,
                            "user": {"id": 3},
                            "children": [{"id": 2}, {"id": 3}],
                        }
                    ],
                    [
                        {
                            "string": "An H4 heading block",
                            "uid": "h4block01",
                            "id": 2,
                            "time": 1700000000001,
                            "user": {"id": 3},
                            "order": 0,
                            "page": {"id": 1},
                            "open": True,
                            "parents": [{"id": 1}],
                            "props": {"ah-level": "h4"},
                        }
                    ],
                    [
                        {
                            "string": "A plain block",
                            "uid": "plain0001",
                            "id": 3,
                            "time": 1700000000002,
                            "user": {"id": 3},
                            "order": 1,
                            "page": {"id": 1},
                            "open": True,
                            "parents": [{"id": 1}],
                        }
                    ],
                ],
            }
        )

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            result: NodeFetchResult = FetchRoamNodes.fetch_by_page_title(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="Heading Page"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        assert len(result.network) == 3
        assert result.nodes_by_uid is not None
        by_uid = result.nodes_by_uid

        # Page node: no props
        assert by_uid["headng001"].props is None

        # H4 augmented-heading block: props present with ah-level key
        h4_node: RoamNode = by_uid["h4block01"]
        assert h4_node.props is not None
        assert h4_node.props["ah-level"] == "h4"

        # Plain block: no props
        assert by_uid["plain0001"].props is None

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_fetch_testarticle1(self, live_api_endpoint: ApiEndpoint) -> None:
        """Live test: fetch all descendant blocks of a page and compare with fixture.

        Transient fields (``time``, ``user``, ``open``, ``sidebar``, ``lookup``,
        ``seen_by``) are excluded from the comparison because they change with
        normal Roam activity and are not meaningful for structural correctness.
        """
        page_title = "[[Test Article]] 1"

        result: NodeFetchResult = FetchRoamNodes.fetch_by_page_title(
            fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=page_title), include_refs=False),
            api_endpoint=live_api_endpoint,
        )
        logger.debug("result: %s", result)

        fixture_nodes = article1_node_tree().tree_network

        assert [_stable_node_dict(n) for n in sorted(result.network, key=lambda n: n.uid)] == [
            _stable_node_dict(n) for n in sorted(fixture_nodes, key=lambda n: n.uid)
        ]


class TestFetchRoamNodesFetchByNodeUid:
    """Tests for FetchRoamNodes.fetch_by_node_uid."""

    def test_null_api_endpoint_raises_validation_error(self) -> None:
        """Test that None api_endpoint raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.fetch_by_node_uid(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="wdMgyBiP9"), include_refs=False),
                api_endpoint=None,  # type: ignore[arg-type]
            )

    def test_null_fetch_spec_raises_validation_error(self, api_endpoint: ApiEndpoint) -> None:
        """Test that None fetch_spec raises ValidationError."""
        with pytest.raises(ValidationError):
            FetchRoamNodes.fetch_by_node_uid(fetch_spec=None, api_endpoint=api_endpoint)  # type: ignore[arg-type]

    def test_node_not_found_raises_not_found_error(self, api_endpoint: ApiEndpoint) -> None:
        """Test that an empty result (node not found) raises RoamNodeNotFoundError carrying the fetch_spec."""
        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({"success": True, "result": []})

        spec: Final[NodeFetchSpec] = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="wdMgyBiP9"), include_refs=False)
        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            with pytest.raises(RoamNodeNotFoundError) as exc_info:
                FetchRoamNodes.fetch_by_node_uid(fetch_spec=spec, api_endpoint=api_endpoint)
        assert exc_info.value.fetch_spec == spec

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_fetch_by_node_uid(self, live_api_endpoint: ApiEndpoint) -> None:
        """Live test: fetch the wdMgyBiP9 subtree and compare with the fixture hierarchy.

        The ``wdMgyBiP9`` node (Section 2) has seven descendants in the
        ``test_article_1_nodes.yaml`` fixture: Section 2.1 (``drtANJYTg``),
        illustration 2.1 (``OaTXPl93p``), its caption (``tWkumkdUE``), its image
        (``zZG-BfWvs``), Section 2.1.1 (``yFUau9Cpg``), Section 2.1.1.1
        (``bxkcECGwN``), and Section 2.2 (``5f1ahOFdp``).  Transient fields are
        excluded from the comparison.
        """
        node_uid = "wdMgyBiP9"
        section2_uids: set[str] = {
            "wdMgyBiP9",
            "drtANJYTg",
            "5f1ahOFdp",
            "yFUau9Cpg",
            "bxkcECGwN",
            "OaTXPl93p",
            "tWkumkdUE",
            "zZG-BfWvs",
        }

        all_fixture_nodes = article1_node_tree().tree_network
        expected_nodes: list[RoamNode] = [n for n in all_fixture_nodes if n.uid in section2_uids]

        result: NodeFetchResult = FetchRoamNodes.fetch_by_node_uid(
            fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=node_uid), include_refs=False),
            api_endpoint=live_api_endpoint,
        )
        logger.debug("result: %s", result)

        assert {n.uid for n in result.network} == section2_uids
        assert [_stable_node_dict(n) for n in sorted(result.network, key=lambda n: n.uid)] == [
            _stable_node_dict(n) for n in sorted(expected_nodes, key=lambda n: n.uid)
        ]

    def test_fetch_by_node_uid_returns_node_and_descendants(self, api_endpoint: ApiEndpoint) -> None:
        """Test that fetch_by_node_uid returns the root node and all its descendants.

        Uses the test_article_1_nodes.yaml fixture, fetching for node_uid ``'wdMgyBiP9'``
        (Section 2).  Expects the root node plus its seven descendant blocks: Section 2.1
        (``drtANJYTg``), illustration 2.1 (``OaTXPl93p``), its caption (``tWkumkdUE``),
        its image (``zZG-BfWvs``), Section 2.1.1 (``yFUau9Cpg``),
        Section 2.1.1.1 (``bxkcECGwN``), and Section 2.2 (``5f1ahOFdp``).
        """
        # UIDs in the Section 2 subtree: root + all descendants
        section2_uids: set[str] = {
            "wdMgyBiP9",
            "drtANJYTg",
            "5f1ahOFdp",
            "yFUau9Cpg",
            "bxkcECGwN",
            "OaTXPl93p",
            "tWkumkdUE",
            "zZG-BfWvs",
        }

        all_fixture_nodes = article1_node_tree().tree_network
        expected_nodes: list[RoamNode] = [n for n in all_fixture_nodes if n.uid in section2_uids]

        mock_response: MagicMock = MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(
            {
                "success": True,
                "result": [[n.model_dump(mode="json")] for n in expected_nodes],
            }
        )

        with patch("guffin.roam.local_api.requests.post", return_value=mock_response):
            result: NodeFetchResult = FetchRoamNodes.fetch_by_node_uid(
                fetch_spec=NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="wdMgyBiP9"), include_refs=False),
                api_endpoint=api_endpoint,
            )

        assert len(result.network) == len(section2_uids)
        assert [_stable_node_dict(n) for n in sorted(result.network, key=lambda n: n.uid)] == [
            _stable_node_dict(n) for n in sorted(expected_nodes, key=lambda n: n.uid)
        ]


class TestFetchTestarticle2WithRefs:
    """Unit tests for FetchRoamNodes._fetch with ``[[Test Article]] 2`` and ``include_refs=True``.

    Replays the ``test_article_2_raw_result.yaml`` fixture through :meth:`FetchRoamNodes._fetch`
    by patching :func:`~guffin.roam.local_api.invoke_action` so that no live Roam Desktop
    connection is required, then asserts the produced :class:`~guffin.roam.node_fetch_result.NodeFetchResult`
    matches the ``test_article_2_anchor_tree.yaml`` and ``test_article_2_nodes_by_uid.yaml`` fixtures.
    """

    _PAGE_TITLE: Final[str] = "[[Test Article]] 2"

    @pytest.fixture
    def fetch_result(self, api_endpoint: ApiEndpoint) -> NodeFetchResult:
        """Invoke ``_fetch`` with a mocked ``invoke_action`` replaying the raw-result fixture.

        Loads ``test_article_2_raw_result.yaml``, wraps it in a
        :class:`~guffin.roam.local_api.Response.Payload`, patches
        :func:`~guffin.roam.local_api.invoke_action` to return that payload, then calls
        :meth:`FetchRoamNodes._fetch` and returns the resulting
        :class:`~guffin.roam.node_fetch_result.NodeFetchResult`.
        """
        raw_result: list[list[dict[str, object]]] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_2_raw_result.yaml").read_text()
        )
        mock_payload: LocalApiResponse.Payload = LocalApiResponse.Payload(success=True, result=raw_result)
        fetch_spec: NodeFetchSpec = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier=self._PAGE_TITLE),
            include_refs=True,
            include_node_tree=True,
        )
        request_payload = FetchRoamNodes.Request.payload_by_page_title(self._PAGE_TITLE, include_refs=True)
        with patch("guffin.roam.node_fetch.invoke_action", return_value=mock_payload):
            return FetchRoamNodes._fetch(request_payload, api_endpoint, fetch_spec)  # type: ignore[misc]

    def test_anchor_tree_matches_fixture(self, fetch_result: NodeFetchResult) -> None:
        """Anchor tree produced by ``_fetch`` must match ``test_article_2_anchor_tree.yaml``."""
        expected: dict[str, object] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_2_anchor_tree.yaml").read_text()
        )
        assert fetch_result.anchor_tree is not None
        assert fetch_result.anchor_tree.model_dump(mode="json") == expected

    def test_nodes_by_uid_matches_fixture(self, fetch_result: NodeFetchResult) -> None:
        """``nodes_by_uid`` produced by ``_fetch`` must match ``test_article_2_nodes_by_uid.yaml``."""
        expected: dict[str, object] = yaml.safe_load(
            (FIXTURES_YAML_DIR / "test_article_2_nodes_by_uid.yaml").read_text()
        )
        assert fetch_result.nodes_by_uid is not None
        actual: dict[str, object] = {
            uid: node.model_dump(mode="json") for uid, node in fetch_result.nodes_by_uid.items()
        }
        assert actual == expected
