"""OpenAI Images API (gpt-image-1, dall-e-3) or any server that copies it (LocalAI, etc.)."""

from __future__ import annotations

import base64

from booktures.plugins import Field, ImageProvider, ImageRequest, ProviderError, register
from booktures.providers._http import join, request


@register
class OpenAIImages(ImageProvider):
    id = "openai-images"
    name = "OpenAI Images"
    description = "gpt-image-1 or DALL·E 3 through the OpenAI Images API, or a compatible server."
    homepage = "https://platform.openai.com/docs/guides/image-generation"
    fields = [
        Field("base_url", "Base URL", type="url", default="https://api.openai.com/v1"),
        Field("api_key", "API key", type="secret", env="OPENAI_API_KEY"),
        Field("model", "Model", default="gpt-image-1", placeholder="gpt-image-1, dall-e-3"),
        Field("quality", "Quality", type="select", default="low",
              options=["low", "medium", "high", "auto", "standard", "hd"],
              help="gpt-image-1 uses low/medium/high; DALL·E 3 uses standard/hd."),
        Field("timeout", "Timeout (seconds)", type="number", default=240),
    ]

    def _size(self, req: ImageRequest) -> str:
        model = self.config.get("model", "")
        ratio = req.width / max(1, req.height)
        if model.startswith("dall-e-3"):
            return "1792x1024" if ratio > 1.2 else "1024x1792" if ratio < 0.8 else "1024x1024"
        return "1536x1024" if ratio > 1.2 else "1024x1536" if ratio < 0.8 else "1024x1024"

    def generate(self, req: ImageRequest) -> bytes:
        model = self.require("model")
        body = {"model": model, "prompt": req.prompt[:3800], "n": 1, "size": self._size(req)}
        if self.config.get("quality"):
            body["quality"] = self.config["quality"]
        if model.startswith("dall-e"):
            body["response_format"] = "b64_json"
        headers = {"Authorization": f"Bearer {self.require('api_key')}"}
        resp = request(self.name, "POST", join(self.require("base_url"), "images/generations"),
                       json=body, headers=headers, timeout=float(self.config.get("timeout") or 240))
        try:
            item = resp.json()["data"][0]
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError("OpenAI Images: unexpected response") from exc
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            return request(self.name, "GET", item["url"], timeout=60).content
        raise ProviderError("OpenAI Images: no image in response")

    def check(self) -> str:
        headers = {"Authorization": f"Bearer {self.require('api_key')}"}
        request(self.name, "GET", join(self.require("base_url"), "models"), headers=headers, timeout=20)
        return f"Connected. Using {self.config.get('model')}."
