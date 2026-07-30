"""Unit tests for guffin.server.cors."""

from typing import Final

from fastapi.testclient import TestClient

from guffin.server.app import app
from guffin.server.cors import EXPOSED_RESPONSE_HEADERS, cors_wrapped_app

ROAM_ORIGIN: Final[str] = "https://roamresearch.com"
"""The origin the admitted-origin tests grant."""

OTHER_ORIGIN: Final[str] = "https://other.example"
"""An origin outside the single-origin tests' grant."""


def preflight_headers(origin: str, private_network: bool = False) -> dict[str, str]:
    """Return the headers of a browser preflight for a cross-origin JSON POST from *origin*."""
    headers: Final[dict[str, str]] = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    if private_network:
        headers["Access-Control-Request-Private-Network"] = "true"
    return headers


class TestDefaultPosture:
    """The unwrapped application emits no CORS headers at all — the opt-in's off state."""

    def test_simple_request_answers_without_any_grant(self) -> None:
        """A cross-origin GET is answered normally but carries no allow-origin grant."""
        client = TestClient(app)
        response = client.get("/v1/health", headers={"Origin": ROAM_ORIGIN})
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_is_not_answered(self) -> None:
        """A preflight OPTIONS finds no CORS answerer and earns no grant headers."""
        client = TestClient(app)
        response = client.options("/v1/export", headers=preflight_headers(ROAM_ORIGIN))
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-private-network" not in response.headers


class TestPreflight:
    """The preflight dialog for the admitted and the disallowed origin."""

    def test_admitted_origin_preflight_is_granted(self) -> None:
        """A preflight from an admitted origin earns the origin echo and the method grant."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN]))
        response = client.options("/v1/export", headers=preflight_headers(ROAM_ORIGIN))
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ROAM_ORIGIN
        assert "POST" in response.headers["access-control-allow-methods"]

    def test_preflight_without_private_network_ask_earns_no_private_network_grant(self) -> None:
        """The private-network grant appears only when the preflight asks for it."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN]))
        response = client.options("/v1/export", headers=preflight_headers(ROAM_ORIGIN))
        assert response.status_code == 200
        assert "access-control-allow-private-network" not in response.headers

    def test_preflight_asking_private_network_is_granted_it(self) -> None:
        """A successful preflight carrying the PNA ask is answered with the PNA grant."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN]))
        response = client.options("/v1/export", headers=preflight_headers(ROAM_ORIGIN, private_network=True))
        assert response.status_code == 200
        assert response.headers["access-control-allow-private-network"] == "true"

    def test_disallowed_origin_preflight_fails_without_an_origin_grant(self) -> None:
        """A preflight from a disallowed origin answers 400 and earns no origin grant."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN]))
        response = client.options("/v1/export", headers=preflight_headers(OTHER_ORIGIN, private_network=True))
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


class TestSimpleRequests:
    """The response-side grants on ordinary (non-preflighted) requests."""

    def test_admitted_origin_reads_the_response_and_the_exposed_headers(self) -> None:
        """An admitted origin's GET carries the origin echo and exposes the download headers."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN]))
        response = client.get("/v1/health", headers={"Origin": ROAM_ORIGIN})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ROAM_ORIGIN
        exposed: Final[str] = response.headers["access-control-expose-headers"]
        for header_name in EXPOSED_RESPONSE_HEADERS:
            assert header_name in exposed

    def test_disallowed_origin_is_answered_but_earns_no_grant(self) -> None:
        """A disallowed origin's GET still executes server-side; only the grant is withheld."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN]))
        response = client.get("/v1/health", headers={"Origin": OTHER_ORIGIN})
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_every_admitted_origin_is_echoed(self) -> None:
        """Each of several admitted origins earns its own origin echo."""
        client = TestClient(cors_wrapped_app(app, [ROAM_ORIGIN, OTHER_ORIGIN]))
        for origin in (ROAM_ORIGIN, OTHER_ORIGIN):
            response = client.get("/v1/health", headers={"Origin": origin})
            assert response.headers["access-control-allow-origin"] == origin
