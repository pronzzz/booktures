import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_MD = ROOT / "booktures" / "samples" / "the-lantern-keeper.md"
SAMPLE_PDF = ROOT / "samples" / "the-lantern-keeper.pdf"
FIXTURES = Path(__file__).parent / "fixtures"

# 1x1 transparent PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


class MockServer:
    """A tiny HTTP server: register handlers per (method, path) and inspect requests."""

    def __init__(self):
        self.routes: dict[tuple[str, str], callable] = {}
        self.requests: list[dict] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _handle(self, method):
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                path = self.path.split("?")[0]
                server.requests.append(
                    {"method": method, "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body}
                )
                fn = server.routes.get((method, path))
                if not fn:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'{"error": {"message": "no route"}}')
                    return
                status, ctype, payload = fn(body, self.path)
                if not isinstance(payload, (bytes, bytearray)):
                    payload = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def json(self, method, path, payload, status=200):
        self.routes[(method, path)] = lambda body, full: (status, "application/json", payload)

    def raw(self, method, path, payload: bytes, ctype="image/png", status=200):
        self.routes[(method, path)] = lambda body, full: (status, ctype, payload)

    def last_json(self) -> dict:
        return json.loads(self.requests[-1]["body"] or b"{}")


@pytest.fixture
def mock_server():
    srv = MockServer()
    yield srv
    srv.httpd.shutdown()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path / "home"
