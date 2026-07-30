"""Endpoint tests for guffin.server.app (offline: the Roam Local API fetch is mocked)."""

import base64
import hashlib
from typing import Final
from unittest.mock import patch

import pytest
from conftest import FIXTURES_MD_DIR, article1_node_tree
from fastapi.testclient import TestClient

from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec
from guffin.server.app import app
from guffin.server.problem_details import PROBLEM_MEDIA_TYPE

_FETCH_SEAM: Final[str] = "guffin.cli.common.FetchRoamNodes.fetch_roam_nodes"
"""The wire-level seam every offline endpoint test mocks: the Roam Local API node fetch."""

_CONNECTION: Final[dict[str, object]] = {"local_api_port": 3333, "graph_name": "SCFH", "api_bearer_token": "tok"}
"""The Roam-connection request fields shared by every invocation test."""


def _article1_fetch_result() -> NodeFetchResult:
    """Return a fetch result recreating the ``[[Test Article]] 1`` fetch from its fixture."""
    fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
        anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
    )
    node_tree = article1_node_tree()
    all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
    return NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])


class TestHealthEndpoint:
    """Tests for GET /v1/health."""

    def test_health_reports_ok_with_version_and_provenance(self) -> None:
        """The health endpoint answers liveness, the package version, and provenance."""
        client = TestClient(app)
        response = client.get("/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"]
        assert "provenance" in body


class TestRequestValidation:
    """Tests for the 400 request-validation contract, shared by both command endpoints."""

    def test_non_json_body_answers_400_problem(self) -> None:
        """A body that is not JSON answers 400 with a problem-details body."""
        client = TestClient(app)
        response = client.post("/v1/export", content="not json", headers={"Content-Type": "application/json"})
        assert response.status_code == 400
        assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
        assert response.json()["title"] == "malformed request body"

    def test_unknown_field_answers_400_problem(self) -> None:
        """An unknown request field answers 400, naming the offender in the detail."""
        client = TestClient(app)
        response = client.post("/v1/export", json={"target": "X", "bogus": 1})
        assert response.status_code == 400
        assert "bogus" in response.json()["detail"]

    def test_missing_target_answers_400_problem(self) -> None:
        """A request without a target answers 400."""
        client = TestClient(app)
        response = client.post("/v1/dump", json={})
        assert response.status_code == 400
        assert "target" in response.json()["detail"]


@pytest.mark.pandoc
class TestExportEndpoint:
    """Tests for POST /v1/export."""

    def test_export_success_returns_the_document(self) -> None:
        """A no-bundle markdown export answers the GFM document with integrity headers."""
        client = TestClient(app)
        with patch(_FETCH_SEAM, return_value=_article1_fetch_result()):
            response = client.post(
                "/v1/export",
                json={"target": "[[Test Article]] 1", "should_bundle": False, **_CONNECTION},
            )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/markdown")
        expected: Final[str] = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert response.text == expected
        assert "Test_Article_1.default.md" in response.headers["content-disposition"]
        expected_digest: Final[str] = base64.b64encode(hashlib.sha256(response.content).digest()).decode("ascii")
        assert response.headers["content-digest"] == f"sha-256=:{expected_digest}:"

    def test_export_failure_answers_422_with_the_complete_error(self) -> None:
        """A failed invocation answers 422, the detail carrying the captured error text."""
        client = TestClient(app)
        with patch(_FETCH_SEAM, side_effect=RuntimeError("kaboom")):
            response = client.post("/v1/export", json={"target": "MISSING", **_CONNECTION})
        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
        body = response.json()
        assert body["exit_code"] == 1
        assert body["target"] == "MISSING"
        assert "kaboom" in body["detail"]


class TestDumpEndpoint:
    """Tests for POST /v1/dump."""

    def test_dump_text_returns_the_console_rendering(self) -> None:
        """A node-tree dump answers the captured console text."""
        client = TestClient(app)
        with patch(_FETCH_SEAM, return_value=_article1_fetch_result()):
            response = client.post(
                "/v1/dump",
                json={
                    "target": "[[Test Article]] 1",
                    "show_render_bundle": False,
                    "show_node_tree": True,
                    **_CONNECTION,
                },
            )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/plain")
        assert "Node Tree" in response.text
        assert "node(s) in anchor tree" in response.text

    def test_dump_html_returns_a_standalone_document(self) -> None:
        """An html-representation dump answers a full HTML document of the rendering."""
        client = TestClient(app)
        with patch(_FETCH_SEAM, return_value=_article1_fetch_result()):
            response = client.post(
                "/v1/dump",
                json={
                    "target": "[[Test Article]] 1",
                    "show_render_bundle": False,
                    "show_node_tree": True,
                    "console_format": "html",
                    **_CONNECTION,
                },
            )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/html")
        assert "<html" in response.text
        assert "Node Tree" in response.text

    def test_dump_failure_answers_422_with_the_complete_error(self) -> None:
        """A failed dump invocation answers 422 with the captured error text."""
        client = TestClient(app)
        with patch(_FETCH_SEAM, side_effect=RuntimeError("dump kaboom")):
            response = client.post("/v1/dump", json={"target": "MISSING", **_CONNECTION})
        assert response.status_code == 422
        assert "dump kaboom" in response.json()["detail"]
