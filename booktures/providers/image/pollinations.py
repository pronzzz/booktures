"""Pollinations.ai — free hosted image generation (FLUX and others), no key required."""

from __future__ import annotations

from urllib.parse import quote

from booktures.plugins import Field, ImageProvider, ImageRequest, ProviderError, register
from booktures.providers._http import request

BASE = "https://image.pollinations.ai/prompt/"


@register
class Pollinations(ImageProvider):
    id = "pollinations"
    name = "Pollinations (free cloud)"
    description = "Free hosted FLUX images with no sign-up. Prompts are sent to pollinations.ai."
    homepage = "https://pollinations.ai"
    fields = [
        Field("model", "Model", default="flux", placeholder="flux, turbo"),
        Field("token", "API token (optional)", type="secret", env="POLLINATIONS_TOKEN",
              help="A free token raises rate limits. Works without one."),
        Field("enhance", "Let Pollinations enhance prompts", type="boolean", default=False),
        Field("timeout", "Timeout (seconds)", type="number", default=180),
    ]

    def _url(self, req: ImageRequest) -> tuple[str, dict]:
        params = {
            "width": req.width,
            "height": req.height,
            "seed": req.seed,
            "model": self.config.get("model") or "flux",
            "nologo": "true",
            "private": "true",
            "enhance": "true" if self.config.get("enhance") else "false",
        }
        if req.negative_prompt:
            params["negative_prompt"] = req.negative_prompt
        return BASE + quote(req.prompt[:1500], safe=""), params

    def generate(self, req: ImageRequest) -> bytes:
        url, params = self._url(req)
        headers = {}
        if self.config.get("token"):
            headers["Authorization"] = f"Bearer {self.config['token']}"
        resp = request(self.name, "GET", url, params=params, headers=headers,
                       timeout=float(self.config.get("timeout") or 180))
        if not resp.headers.get("content-type", "").startswith("image/"):
            raise ProviderError(f"Pollinations returned {resp.headers.get('content-type')} instead of an image.")
        return resp.content

    def check(self) -> str:
        resp = request(self.name, "GET", "https://image.pollinations.ai/models", timeout=20)
        try:
            models = resp.json()
            names = [m if isinstance(m, str) else m.get("name", "") for m in models]
        except ValueError:
            names = []
        return f"Reachable. Models: {', '.join(n for n in names[:6] if n) or 'flux'}."
