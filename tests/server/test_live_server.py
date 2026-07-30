"""Live end-to-end test: the real HTTP server against the live Roam graph.

Boots a real uvicorn server on the ASGI app and exercises the full transport path — request
over the wire, in-process invocation, live Roam Local API fetch, streamed document response —
that the offline endpoint tests exercise only through the ASGI test client.
"""

import base64
import hashlib
import os
import threading
import time

import httpx
import pytest
import uvicorn
from conftest import FIXTURES_MD_DIR

from guffin.server.app import app

_STARTUP_TIMEOUT_SECONDS: float = 15.0
"""How long the test waits for the in-thread server to finish starting."""


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
class TestServerLive:
    """Tests running the real server over real HTTP against the live graph."""

    def test_live_export_over_http_matches_fixture(self) -> None:
        """A no-bundle markdown export over real HTTP reproduces the recorded fixture, digest intact.

        The request omits every Roam-connection field, so the server's own environment
        (``GUFFIN_ROAM_LOCAL_API_PORT``/``GUFFIN_ROAM_GRAPH_NAME``/``GUFFIN_ROAM_API_TOKEN``)
        must resolve them — the env-fallback behavior the request contract promises.
        """
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
            while not server.started:
                assert time.monotonic() < deadline, "uvicorn did not start in time"
                time.sleep(0.05)
            port: int = server.servers[0].sockets[0].getsockname()[1]
            response = httpx.post(
                f"http://127.0.0.1:{port}/v1/export",
                json={"target": "[[Test Article]] 1", "should_bundle": False},
                timeout=300.0,
            )
            assert response.status_code == 200, response.text
            assert response.headers["content-type"].startswith("text/markdown")
            expected: str = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
            assert response.text == expected
            digest: str = base64.b64encode(hashlib.sha256(response.content).digest()).decode("ascii")
            assert response.headers["content-digest"] == f"sha-256=:{digest}:"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
