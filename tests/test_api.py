"""End-to-end through the HTTP API with the offline providers."""

import time

import pytest
from fastapi.testclient import TestClient

from booktures.app import create_app
from tests.conftest import SAMPLE_PDF


@pytest.fixture
def client(home):
    app = create_app(home)
    with TestClient(app) as c:
        yield c


def wait_for(client, book_id, done=lambda b: b["status"] in ("done", "failed", "cancelled"), timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        book = client.get(f"/api/books/{book_id}").json()
        if done(book):
            return book
        time.sleep(0.2)
    raise AssertionError(f"timed out; last status {book['status']}")


def upload(client, path=SAMPLE_PDF, **form):
    with open(path, "rb") as f:
        r = client.post("/api/books", files={"file": (path.name, f, "application/pdf")}, data=form)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_and_catalog(client):
    assert client.get("/api/health").json()["version"] == "2.0.0"
    cat = client.get("/api/providers").json()
    assert cat["active"] == {"text": "offline", "image": "sketchbook"}
    assert any(p["id"] == "diffusers" for p in cat["image"])
    assert len(client.get("/api/styles").json()) >= 8


def test_full_book_flow(client):
    book = upload(client, style_preset="watercolor", max_pages="4")
    assert book["page_count"] == 4
    book = wait_for(client, book["id"])
    assert book["status"] == "done", book
    assert set(book["character_bible"]) >= {"Mara", "Tobias"}
    assert "watercolor" in book["global_style"]
    for page in book["pages"]:
        assert page["image_status"] in ("done", "reused")
        assert page["image_prompt"].startswith("delicate watercolor")
        img = client.get(page["image_url"])
        assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    assert book["cover_url"]

    # Export is a standalone HTML file with embedded images.
    html = client.get(f"/api/books/{book['id']}/export").text
    assert "data:image/png;base64," in html and "The Lantern Keeper" in html

    # Edit the bible, then repaint one page with a custom prompt.
    r = client.patch(f"/api/books/{book['id']}", json={"character_bible": {"Mara": "tall woman, red scarf", " ": "x"}})
    assert r.json()["character_bible"] == {"Mara": "tall woman, red scarf"}
    client.post(f"/api/books/{book['id']}/pages/2/regenerate", json={"prompt_override": "a red kite over the sea"})
    page2 = wait_for(client, book["id"], done=lambda b: b["pages"][1]["image_status"] == "done")["pages"][1]
    assert page2["image_prompt"] == "a red kite over the sea"
    assert page2["image_url"] != book["pages"][1]["image_url"]

    # Library listing and delete.
    assert [b["id"] for b in client.get("/api/books").json()] == [book["id"]]
    assert client.delete(f"/api/books/{book['id']}").json()["ok"]
    assert client.get(f"/api/books/{book['id']}").status_code == 404


def test_repaint_and_reanalyze(client):
    book = wait_for(client, upload(client, max_pages="2")["id"])
    client.post(f"/api/books/{book['id']}/run", json={"mode": "reanalyze"})
    again = wait_for(client, book["id"], done=lambda b: b["status"] == "done" and b["global_style"])
    assert again["pages"][0]["image_url"] != book["pages"][0]["image_url"]
    assert client.post(f"/api/books/{book['id']}/run", json={"mode": "nope"}).status_code == 400


def test_failing_illustrator_stops_after_three_pages(client, home):
    client.put("/api/settings", json={"image": {"provider": "automatic1111", "configs": {"automatic1111": {"base_url": "http://127.0.0.1:9"}}}})
    book = wait_for(client, upload(client)["id"])
    assert book["status"] == "failed"
    assert "three pages in a row" in book["error"]
    assert sum(p["image_status"] == "failed" for p in book["pages"]) == 3


def test_settings_mask_secrets(client):
    r = client.put("/api/settings", json={"text": {"provider": "openai-compatible", "configs": {"openai-compatible": {"api_key": "sk-secret-1234", "model": "m"}}}})
    masked = r.json()["text"]["configs"]["openai-compatible"]["api_key"]
    assert "secret" not in masked and masked.endswith("1234")
    # Sending the mask back keeps the stored key.
    client.put("/api/settings", json={"text": {"configs": {"openai-compatible": {"api_key": masked, "model": "m2"}}}})
    eng = client.app.state.engine
    assert eng.settings.get()["text"]["configs"]["openai-compatible"] == {"api_key": "sk-secret-1234", "model": "m2"}
    assert client.put("/api/settings", json={"image": {"provider": "nope"}}).status_code == 400


def test_provider_check_and_test_endpoints(client):
    assert client.post("/api/providers/text/offline/check", json={"config": {}}).json()["ok"]
    r = client.post("/api/providers/image/sketchbook/test", json={"config": {}}).json()
    assert r["ok"] and r["image"].startswith("data:image/png;base64,")
    r = client.post("/api/providers/text/offline/test", json={"config": {}}).json()
    assert r["ok"] and "Mara" in r["scene"]["characters"]
    bad = client.post("/api/providers/text/ollama/check", json={"config": {"base_url": "http://127.0.0.1:9"}}).json()
    assert not bad["ok"] and "could not connect" in bad["message"]


def test_rejects_unsupported_upload(client, tmp_path):
    f = tmp_path / "x.docx"
    f.write_bytes(b"nope")
    with open(f, "rb") as fh:
        r = client.post("/api/books", files={"file": ("x.docx", fh)})
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]


def test_media_path_traversal_blocked(client):
    assert client.get("/media/../../etc/passwd").status_code == 404
    assert client.get("/media/abcdef123456/..%2F..%2Fsettings.json").status_code == 404
