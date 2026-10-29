"""Built-in providers against a local mock HTTP server."""

import base64
import json

import pytest

from booktures.pipeline import prompts
from booktures.plugins import ImageRequest, ProviderError, SceneContext
from booktures.plugins.registry import load_all
from tests.conftest import PNG

REG = load_all([])
CTX = SceneContext("start", {"Mara": "copper hair"}, "watercolor", "coast")
SCENE = {"scene_summary": "Mara climbs", "visual_description": "Mara climbs the lighthouse stairs", "characters": ["Mara"]}


def test_openai_compatible_chat(mock_server):
    mock_server.json("POST", "/v1/chat/completions", {"choices": [{"message": {"content": json.dumps(SCENE)}}]})
    llm = REG.create("text", "openai-compatible", {"base_url": mock_server.url + "/v1", "api_key": "k", "model": "m"})
    scene = llm.describe_scene("page", CTX)
    assert scene["characters"] == ["Mara"]
    req = mock_server.requests[-1]
    body = json.loads(req["body"])
    assert req["headers"]["authorization"] == "Bearer k"
    assert body["model"] == "m" and body["response_format"] == {"type": "json_object"}
    assert "Character bible" in body["messages"][0]["content"]


def test_openai_compatible_error_is_readable(mock_server):
    mock_server.json("POST", "/v1/chat/completions", {"error": {"message": "Incorrect API key"}}, status=401)
    llm = REG.create("text", "openai-compatible", {"base_url": mock_server.url + "/v1", "model": "m"})
    with pytest.raises(ProviderError, match="401.*Incorrect API key.*Check the API key"):
        llm.complete_json("s", "u")


def test_connection_refused_is_readable():
    llm = REG.create("text", "ollama", {"base_url": "http://127.0.0.1:9", "model": "x"})
    with pytest.raises(ProviderError, match="could not connect"):
        llm.complete_json("s", "u")


def test_ollama_chat_and_check(mock_server):
    mock_server.json("POST", "/api/chat", {"message": {"content": json.dumps(SCENE)}})
    mock_server.json("GET", "/api/tags", {"models": [{"name": "llama3.2:latest"}]})
    llm = REG.create("text", "ollama", {"base_url": mock_server.url, "model": "llama3.2"})
    assert llm.describe_scene("page", CTX)["visual_description"].startswith("Mara")
    assert mock_server.last_json()["format"] == "json"
    assert "llama3.2" in llm.check()
    with pytest.raises(ProviderError, match="ollama pull qwen3"):
        REG.create("text", "ollama", {"base_url": mock_server.url, "model": "qwen3"}).check()


def test_gemini_request_shape(mock_server, monkeypatch):
    from booktures.providers.text import gemini

    monkeypatch.setattr(gemini, "API", mock_server.url + "/v1beta")
    mock_server.json(
        "POST", "/v1beta/models/gemini-flash-latest:generateContent",
        {"candidates": [{"content": {"parts": [{"text": json.dumps(SCENE)}]}}]},
    )
    llm = REG.create("text", "gemini", {"api_key": "g"})
    assert llm.describe_scene("p", CTX)["characters"] == ["Mara"]
    req = mock_server.requests[-1]
    assert req["headers"]["x-goog-api-key"] == "g"
    assert json.loads(req["body"])["generationConfig"]["responseMimeType"] == "application/json"


def test_anthropic_uses_sdk_with_effort_and_fallbacks(mock_server):
    pytest.importorskip("anthropic")
    message = {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": json.dumps(SCENE)}],
        "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }
    mock_server.json("POST", "/v1/messages", message)
    llm = REG.create("text", "anthropic", {"api_key": "sk-ant-test", "base_url": mock_server.url})
    assert llm.describe_scene("page", CTX)["characters"] == ["Mara"]
    req = mock_server.requests[-1]
    body = json.loads(req["body"])
    auth = req["headers"].get("x-api-key") or req["headers"].get("authorization", "").removeprefix("Bearer ")
    assert auth == "sk-ant-test"
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "low"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in req["headers"].get("anthropic-beta", "")


def test_anthropic_refusal_raises(mock_server):
    pytest.importorskip("anthropic")
    mock_server.json("POST", "/v1/messages", {
        "id": "m", "type": "message", "role": "assistant", "model": "claude-haiku-5-5", "content": [],
        "stop_reason": "refusal", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 0},
    })
    llm = REG.create("text", "anthropic", {"api_key": "k", "base_url": mock_server.url, "model": "claude-haiku-5-5"})
    with pytest.raises(ProviderError, match="declined"):
        llm.complete_json("s", "u")
    # Haiku is not in the fallback list, so no fallback parameter is sent.
    assert "fallbacks" not in mock_server.last_json()


def test_automatic1111(mock_server):
    mock_server.json("POST", "/sdapi/v1/txt2img", {"images": [base64.b64encode(PNG).decode()]})
    img = REG.create("image", "automatic1111", {"base_url": mock_server.url, "checkpoint": "dream.safetensors"})
    assert img.generate(ImageRequest("a lighthouse", "blurry", 770, 515, 3)) == PNG
    body = mock_server.last_json()
    assert body["width"] == 768 and body["height"] == 512
    assert body["override_settings"]["sd_model_checkpoint"] == "dream.safetensors"


def test_comfyui_default_graph(mock_server):
    mock_server.json("POST", "/prompt", {"prompt_id": "abc"})
    mock_server.json("GET", "/history/abc", {"abc": {"outputs": {"9": {"images": [{"filename": "o.png", "subfolder": "", "type": "output"}]}}}})
    mock_server.raw("GET", "/view", PNG)
    img = REG.create("image", "comfyui", {"base_url": mock_server.url, "checkpoint": "sd15.safetensors"})
    assert img.generate(ImageRequest("a cat", "ugly", 512, 512, 99)) == PNG
    graph = json.loads(mock_server.requests[0]["body"])["prompt"]
    assert graph["6"]["inputs"]["text"] == "a cat"
    assert graph["3"]["inputs"]["seed"] == 99  # placeholders keep their type


def test_comfyui_custom_workflow_placeholders():
    from booktures.providers.image.comfyui import fill

    out = fill({"a": "{{prompt}} at night", "b": "{{seed}}", "c": ["{{width}}"]}, {"prompt": "x", "seed": 5, "width": 64})
    assert out == {"a": "x at night", "b": 5, "c": [64]}


def test_openai_images(mock_server):
    mock_server.json("POST", "/v1/images/generations", {"data": [{"b64_json": base64.b64encode(PNG).decode()}]})
    img = REG.create("image", "openai-images", {"base_url": mock_server.url + "/v1", "api_key": "k"})
    assert img.generate(ImageRequest("p", width=768, height=512)) == PNG
    assert mock_server.last_json()["size"] == "1536x1024"


def test_pollinations(mock_server, monkeypatch):
    from booktures.providers.image import pollinations

    monkeypatch.setattr(pollinations, "BASE", mock_server.url + "/prompt/")
    mock_server.routes[("GET", "/prompt/a%20red%20door")] = lambda b, p: (200, "image/jpeg", b"\xff\xd8jpeg")
    img = REG.create("image", "pollinations", {})
    assert img.generate(ImageRequest("a red door", seed=7)) == b"\xff\xd8jpeg"
    assert "seed=7" in mock_server.requests[-1]["path"]


def test_sketchbook_is_deterministic():
    img = REG.create("image", "sketchbook", {"scale": 0.25})
    req = ImageRequest("a lighthouse in a storm at night. Mara: girl", width=400, height=300, seed=1)
    a, b = img.generate(req), img.generate(req)
    assert a == b and a.startswith(b"\x89PNG")


def test_stability_multipart(mock_server, monkeypatch):
    from booktures.providers.image import stability

    monkeypatch.setattr(stability, "API", mock_server.url)
    mock_server.raw("POST", "/v2beta/stable-image/generate/core", PNG)
    img = REG.create("image", "stability", {"api_key": "s"})
    assert img.generate(ImageRequest("p", width=768, height=512)) == PNG
    body = mock_server.requests[-1]["body"]
    assert b'name="aspect_ratio"' in body and b"3:2" in body


def test_negative_prompt_constant_is_sane():
    assert "watermark" in prompts.NEGATIVE_PROMPT
