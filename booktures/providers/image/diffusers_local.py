"""Local diffusion models through Hugging Face ``diffusers``.

The default is SD-Turbo, a ~1 B-parameter distilled Stable Diffusion that
paints a 512 px image in 1–4 steps. That is about a second on an Apple M-series
GPU or a mid-range NVIDIA card, and still usable on CPU. Any text-to-image repo
that ``AutoPipelineForText2Image`` understands works (SDXL-Turbo, SD 1.5, SDXL,
LCM models, FLUX.1-schnell on big GPUs).

Install with ``pip install "booktures[local]"``. Weights download from the
Hugging Face Hub on first use and are cached in ``~/.cache/huggingface``.
"""

from __future__ import annotations

import io
import threading

from booktures.plugins import Field, ImageProvider, ImageRequest, ProviderError, register

_PIPES: dict[tuple, object] = {}
_LOCK = threading.Lock()

PRESETS = {
    "stabilityai/sd-turbo": {"steps": 4, "guidance": 0.0, "size": 512},
    "stabilityai/sdxl-turbo": {"steps": 4, "guidance": 0.0, "size": 512},
    "SimianLuo/LCM_Dreamshaper_v7": {"steps": 6, "guidance": 1.5, "size": 512},
    "stable-diffusion-v1-5/stable-diffusion-v1-5": {"steps": 25, "guidance": 7.0, "size": 512},
}


def pick_device(pref: str = "auto") -> str:
    import torch

    if pref and pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_pipeline(model: str, device: str):
    """Load (once) and cache a text-to-image pipeline."""
    key = (model, device)
    with _LOCK:
        if key in _PIPES:
            return _PIPES[key]
        import torch
        from diffusers import AutoPipelineForText2Image
        from diffusers.utils import logging as diffusers_logging

        diffusers_logging.set_verbosity_error()
        diffusers_logging.disable_progress_bar()
        try:
            from transformers.utils import logging as transformers_logging

            transformers_logging.set_verbosity_error()
            transformers_logging.disable_progress_bar()
        except ImportError:
            pass

        # fp16 halves memory on CUDA. On MPS/CPU we load the fp16 files but run in fp32,
        # which avoids black images from the fp16 VAE.
        dtype = torch.float16 if device == "cuda" else torch.float32
        kwargs = {"torch_dtype": dtype}
        try:
            pipe = AutoPipelineForText2Image.from_pretrained(model, variant="fp16", **kwargs)
        except (OSError, ValueError):
            pipe = AutoPipelineForText2Image.from_pretrained(model, **kwargs)
        if hasattr(pipe, "safety_checker"):
            pipe.safety_checker = None  # prompts are already screened by the pipeline
        pipe = pipe.to(device)
        if device != "cuda":
            pipe.enable_attention_slicing()
        pipe.set_progress_bar_config(disable=True)
        _PIPES[key] = pipe
        return pipe


@register
class LocalDiffusion(ImageProvider):
    id = "diffusers"
    name = "Local diffusion (mini model)"
    description = (
        "Runs a small image model on your own GPU or CPU. Defaults to SD-Turbo: about a "
        "second per image on Apple silicon, no API key, nothing leaves your computer."
    )
    homepage = "https://huggingface.co/stabilityai/sd-turbo"
    local = True
    requires = ["torch", "diffusers", "transformers"]
    install_hint = 'pip install "booktures[local]"'
    fields = [
        Field("model", "Model repo", default="stabilityai/sd-turbo", options=list(PRESETS),
              help="Any Hugging Face text-to-image repo. Downloads on first use (SD-Turbo is ~2.5 GB)."),
        Field("steps", "Steps", type="number", default=0, help="0 = model default (4 for SD-Turbo)."),
        Field("guidance", "Guidance scale", type="number", default=-1, help="-1 = model default (0 for turbo models)."),
        Field("base_size", "Base size (px)", type="number", default=0,
              help="Long edge used for generation; 0 = model default (512). Larger is slower."),
        Field("device", "Device", type="select", default="auto", options=["auto", "cuda", "mps", "cpu"]),
    ]

    def _params(self) -> dict:
        model = self.require("model")
        preset = PRESETS.get(model, {"steps": 25, "guidance": 7.0, "size": 768})
        steps = int(self.config.get("steps") or 0) or preset["steps"]
        guidance = float(self.config.get("guidance", -1))
        if guidance < 0:
            guidance = preset["guidance"]
        size = int(self.config.get("base_size") or 0) or preset["size"]
        return {"model": model, "steps": steps, "guidance": guidance, "size": size}

    def check(self) -> str:
        super().check()
        p = self._params()
        device = pick_device(self.config.get("device", "auto"))
        from huggingface_hub import try_to_load_from_cache

        cached = try_to_load_from_cache(p["model"], "model_index.json")
        state = "weights cached" if isinstance(cached, str) else "weights will download on first image"
        return f"Ready on {device.upper()}: {p['model']} ({state})."

    def generate(self, request: ImageRequest) -> bytes:
        ok, why = self.available()
        if not ok:
            raise ProviderError(why)
        import torch

        p = self._params()
        device = pick_device(self.config.get("device", "auto"))
        try:
            pipe = load_pipeline(p["model"], device)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Could not load {p['model']}: {exc}") from exc

        # Keep the requested aspect ratio, scaled to the model's native size, multiple of 8.
        scale = p["size"] / max(request.width, request.height)
        width = max(256, int(request.width * scale) // 8 * 8)
        height = max(256, int(request.height * scale) // 8 * 8)
        generator = torch.Generator(device="cpu").manual_seed(int(request.seed) % (2**32))
        kwargs = dict(
            prompt=request.prompt,
            num_inference_steps=p["steps"],
            guidance_scale=p["guidance"],
            width=width,
            height=height,
            generator=generator,
        )
        if p["guidance"] > 1 and request.negative_prompt:
            kwargs["negative_prompt"] = request.negative_prompt
        with _LOCK:  # one image at a time per process keeps GPU memory predictable
            try:
                image = pipe(**kwargs).images[0]
            except Exception as exc:  # noqa: BLE001
                raise ProviderError(f"Generation failed: {exc}") from exc
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
