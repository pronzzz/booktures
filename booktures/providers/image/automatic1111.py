"""AUTOMATIC1111 Stable Diffusion WebUI, Forge, SD.Next — anything with /sdapi/v1/txt2img.

Start the WebUI with the ``--api`` flag.
"""

from __future__ import annotations

import base64

from booktures.plugins import Field, ImageProvider, ImageRequest, ProviderError, register
from booktures.providers._http import join, request


@register
class Automatic1111(ImageProvider):
    id = "automatic1111"
    name = "SD WebUI (A1111 / Forge)"
    description = "Your local AUTOMATIC1111, Forge or SD.Next server and whatever checkpoints and LoRAs it has."
    homepage = "https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API"
    local = True
    fields = [
        Field("base_url", "Server URL", type="url", default="http://127.0.0.1:7860",
              help="Launch the WebUI with --api."),
        Field("checkpoint", "Checkpoint (optional)", placeholder="sd_xl_base_1.0.safetensors",
              help="Leave empty to use the one loaded in the WebUI."),
        Field("steps", "Steps", type="number", default=25),
        Field("cfg_scale", "CFG scale", type="number", default=6.5),
        Field("sampler", "Sampler", default="DPM++ 2M"),
        Field("extra_prompt", "Extra prompt (LoRAs, quality tags)", placeholder="<lora:storybook:0.7>, masterpiece"),
        Field("timeout", "Timeout (seconds)", type="number", default=300),
    ]

    def generate(self, req: ImageRequest) -> bytes:
        prompt = req.prompt
        if self.config.get("extra_prompt"):
            prompt = f"{prompt}, {self.config['extra_prompt']}"
        body = {
            "prompt": prompt,
            "negative_prompt": req.negative_prompt,
            "seed": int(req.seed) % 4294967294,
            "steps": int(self.config.get("steps") or 25),
            "cfg_scale": float(self.config.get("cfg_scale") or 6.5),
            "sampler_name": self.config.get("sampler") or "DPM++ 2M",
            "width": req.width // 8 * 8,
            "height": req.height // 8 * 8,
        }
        if self.config.get("checkpoint"):
            body["override_settings"] = {"sd_model_checkpoint": self.config["checkpoint"]}
        resp = request(self.name, "POST", join(self.require("base_url"), "sdapi/v1/txt2img"), json=body,
                       timeout=float(self.config.get("timeout") or 300))
        images = resp.json().get("images") or []
        if not images:
            raise ProviderError("SD WebUI returned no images.")
        data = images[0].split(",", 1)[-1]
        return base64.b64decode(data)

    def check(self) -> str:
        resp = request(self.name, "GET", join(self.require("base_url"), "sdapi/v1/sd-models"), timeout=15)
        models = [m.get("model_name") for m in resp.json()]
        return f"Connected. {len(models)} checkpoint(s) available."
