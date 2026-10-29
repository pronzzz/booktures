"""Example Booktures plugin: paint with any model on Hugging Face Inference Providers.

Install it by copying this file into your plugin folder and restarting Booktures:

    cp plugins/hf_inference.py ~/.booktures/plugins/

or point Booktures at this folder:

    booktures --plugins ./plugins

It then shows up under Models & plugins → Illustrator as "Hugging Face Inference".
Get a token at https://huggingface.co/settings/tokens (a "read" token with
"Make calls to Inference Providers" enabled).
"""

from __future__ import annotations

import httpx

from booktures.plugins import Field, ImageProvider, ImageRequest, ProviderError, register

ROUTER = "https://router.huggingface.co/hf-inference/models/"


@register
class HuggingFaceInference(ImageProvider):
    id = "hf-inference"
    name = "Hugging Face Inference"
    description = "Any text-to-image model served by Hugging Face Inference Providers (FLUX, SDXL, SD 3.5…)."
    homepage = "https://huggingface.co/docs/inference-providers"
    fields = [
        Field("token", "Access token", type="secret", env="HF_TOKEN", required=True),
        Field(
            "model",
            "Model",
            default="black-forest-labs/FLUX.1-schnell",
            help="Any model id with the text-to-image task and an inference provider.",
        ),
        Field("steps", "Steps", type="number", default=4, help="FLUX.1-schnell needs only 4."),
        Field("timeout", "Timeout (seconds)", type="number", default=120),
    ]

    def _post(self, url: str, payload: dict) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.require('token')}", "Accept": "image/png"}
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=float(self.config["timeout"]))
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: {exc}") from exc
        if resp.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {resp.status_code}. {resp.text[:300]}")
        return resp

    def generate(self, request: ImageRequest) -> bytes:
        payload = {
            "inputs": request.prompt,
            "parameters": {
                "width": request.width,
                "height": request.height,
                "seed": request.seed,
                "num_inference_steps": int(self.config["steps"]),
            },
        }
        if request.negative_prompt:
            payload["parameters"]["negative_prompt"] = request.negative_prompt
        resp = self._post(ROUTER + self.config["model"], payload)
        if not resp.headers.get("content-type", "").startswith("image/"):
            raise ProviderError(f"{self.name}: expected an image, got {resp.text[:200]}")
        return resp.content

    def check(self) -> str:
        super().check()
        self.require("token")
        try:
            resp = httpx.get(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {self.config['token']}"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"{self.name}: the token was rejected (HTTP {resp.status_code}).")
        return f"Signed in as {resp.json().get('name', 'unknown')}"
