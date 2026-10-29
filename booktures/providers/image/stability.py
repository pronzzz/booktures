"""Stability AI hosted API (Stable Image Core / Ultra / SD3.5)."""

from __future__ import annotations

from booktures.plugins import Field, ImageProvider, ImageRequest, register
from booktures.providers._http import request

API = "https://api.stability.ai"
RATIOS = {"16:9": 16 / 9, "3:2": 1.5, "5:4": 1.25, "1:1": 1.0, "4:5": 0.8, "2:3": 2 / 3, "9:16": 9 / 16}


@register
class StabilityAI(ImageProvider):
    id = "stability"
    name = "Stability AI"
    description = "Stable Image Core, Ultra or SD 3.5 through the Stability AI platform."
    homepage = "https://platform.stability.ai"
    fields = [
        Field("api_key", "API key", type="secret", env="STABILITY_API_KEY"),
        Field("service", "Service", type="select", default="core", options=["core", "ultra", "sd3"],
              help="core is cheapest; ultra is highest quality; sd3 uses the model below."),
        Field("model", "SD3 model", default="sd3.5-medium", help="Only used when Service is sd3."),
        Field("timeout", "Timeout (seconds)", type="number", default=180),
    ]

    def generate(self, req: ImageRequest) -> bytes:
        ratio = req.width / max(1, req.height)
        aspect = min(RATIOS, key=lambda k: abs(RATIOS[k] - ratio))
        service = self.config.get("service") or "core"
        data = {
            "prompt": req.prompt[:9000],
            "aspect_ratio": aspect,
            "seed": str(int(req.seed) % 4294967294),
            "output_format": "png",
        }
        if req.negative_prompt:
            data["negative_prompt"] = req.negative_prompt
        if service == "sd3":
            data["model"] = self.config.get("model") or "sd3.5-medium"
        resp = request(
            self.name, "POST", f"{API}/v2beta/stable-image/generate/{service}",
            headers={"Authorization": f"Bearer {self.require('api_key')}", "Accept": "image/*"},
            files={"none": ("", b"")}, data=data, timeout=float(self.config.get("timeout") or 180),
        )
        return resp.content

    def check(self) -> str:
        resp = request(self.name, "GET", f"{API}/v1/user/balance",
                       headers={"Authorization": f"Bearer {self.require('api_key')}"}, timeout=20)
        credits = resp.json().get("credits")
        return f"Connected. Balance: {credits:.1f} credits." if isinstance(credits, (int, float)) else "Connected."
