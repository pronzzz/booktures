"""ComfyUI — run a built-in text-to-image graph, or your own exported API workflow.

To use your own workflow, export it from ComfyUI with "Save (API Format)" and
paste the JSON into the Workflow field. Booktures replaces these placeholders
anywhere in the JSON: ``{{prompt}}``, ``{{negative}}``, ``{{seed}}``,
``{{width}}``, ``{{height}}``.
"""

from __future__ import annotations

import json
import time
import uuid

from booktures.plugins import Field, ImageProvider, ImageRequest, ProviderError, register
from booktures.providers._http import join, request


def default_workflow(ckpt: str, steps: int, cfg: float, sampler: str, scheduler: str) -> dict:
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": "{{seed}}", "steps": steps, "cfg": cfg, "sampler_name": sampler, "scheduler": scheduler,
            "denoise": 1, "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{width}}", "height": "{{height}}", "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}", "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative}}", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "booktures", "images": ["8", 0]}},
    }


def fill(node, values: dict):
    """Replace {{placeholders}}; a value that is exactly one placeholder keeps its type."""
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, values) for v in node]
    if isinstance(node, str):
        for key, value in values.items():
            token = "{{" + key + "}}"
            if node == token:
                return value
            node = node.replace(token, str(value))
    return node


@register
class ComfyUI(ImageProvider):
    id = "comfyui"
    name = "ComfyUI"
    description = "Drive a local ComfyUI server with a simple built-in graph or your own API-format workflow."
    homepage = "https://github.com/comfyanonymous/ComfyUI"
    local = True
    fields = [
        Field("base_url", "Server URL", type="url", default="http://127.0.0.1:8188"),
        Field("checkpoint", "Checkpoint", placeholder="sd_xl_base_1.0.safetensors",
              help="Used by the built-in graph. Ignored when you paste a workflow."),
        Field("steps", "Steps", type="number", default=20),
        Field("cfg", "CFG", type="number", default=7),
        Field("sampler", "Sampler", default="euler"),
        Field("scheduler", "Scheduler", default="normal"),
        Field("workflow", "Workflow (API format JSON, optional)", type="textarea",
              placeholder='{"3": {"class_type": "KSampler", ...}}'),
        Field("timeout", "Timeout (seconds)", type="number", default=600),
    ]

    def _graph(self, req: ImageRequest) -> dict:
        if self.config.get("workflow"):
            try:
                graph = json.loads(self.config["workflow"])
            except json.JSONDecodeError as exc:
                raise ProviderError(f"ComfyUI workflow is not valid JSON: {exc}") from exc
        else:
            graph = default_workflow(
                self.require("checkpoint"), int(self.config.get("steps") or 20),
                float(self.config.get("cfg") or 7), self.config.get("sampler") or "euler",
                self.config.get("scheduler") or "normal",
            )
        return fill(graph, {
            "prompt": req.prompt, "negative": req.negative_prompt, "seed": int(req.seed),
            "width": req.width // 8 * 8, "height": req.height // 8 * 8,
        })

    def generate(self, req: ImageRequest) -> bytes:
        base = self.require("base_url")
        resp = request(self.name, "POST", join(base, "prompt"),
                       json={"prompt": self._graph(req), "client_id": uuid.uuid4().hex}, timeout=30)
        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            raise ProviderError(f"ComfyUI rejected the workflow: {resp.text[:200]}")
        deadline = time.time() + float(self.config.get("timeout") or 600)
        while time.time() < deadline:
            history = request(self.name, "GET", join(base, f"history/{prompt_id}"), timeout=30).json()
            entry = history.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ProviderError("ComfyUI reported an error while running the workflow.")
                for output in entry.get("outputs", {}).values():
                    for img in output.get("images", []):
                        return request(self.name, "GET", join(base, "view"), timeout=60, params={
                            "filename": img["filename"], "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output"),
                        }).content
            time.sleep(0.75)
        raise ProviderError("ComfyUI did not finish in time.")

    def check(self) -> str:
        stats = request(self.name, "GET", join(self.require("base_url"), "system_stats"), timeout=15).json()
        devices = ", ".join(d.get("name", "?") for d in stats.get("devices", [])) or "unknown device"
        return f"Connected to ComfyUI on {devices}."
