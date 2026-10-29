"""Ollama — run Llama, Qwen, Gemma, Mistral and friends on your own machine."""

from __future__ import annotations

from booktures.pipeline.prompts import parse_json_loose
from booktures.plugins import Field, ProviderError, TextProvider, register
from booktures.providers._http import join, request


@register
class Ollama(TextProvider):
    id = "ollama"
    name = "Ollama"
    description = "Local models served by Ollama (llama3.2, qwen3, gemma3, mistral…). Book text never leaves your machine."
    homepage = "https://ollama.com"
    local = True
    fields = [
        Field("base_url", "Server URL", type="url", default="http://localhost:11434", env="OLLAMA_HOST"),
        Field("model", "Model", default="llama3.2", placeholder="llama3.2, qwen3:8b, gemma3:4b",
              help="Pull it first: ollama pull llama3.2"),
        Field("temperature", "Temperature", type="number", default=0.4),
        Field("num_ctx", "Context window", type="number", default=8192),
        Field("timeout", "Timeout (seconds)", type="number", default=300),
    ]

    def _base(self) -> str:
        base = self.require("base_url")
        return base if base.startswith("http") else f"http://{base}"

    def complete_json(self, system: str, user: str) -> dict:
        body = {
            "model": self.require("model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": float(self.config.get("temperature") or 0.4),
                "num_ctx": int(self.config.get("num_ctx") or 8192),
            },
        }
        resp = request(self.name, "POST", join(self._base(), "api/chat"), json=body,
                       timeout=float(self.config.get("timeout") or 300))
        content = (resp.json().get("message") or {}).get("content", "")
        try:
            return parse_json_loose(content)
        except ValueError as exc:
            raise ProviderError(f"Ollama: model reply was not JSON: {content[:160]!r}") from exc

    def check(self) -> str:
        resp = request(self.name, "GET", join(self._base(), "api/tags"), timeout=10)
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        want = self.config.get("model", "")
        if not any(m == want or m.split(":")[0] == want for m in models):
            listed = ", ".join(models[:8]) or "none"
            raise ProviderError(f"Ollama is running but '{want}' is not pulled. Run: ollama pull {want}. Installed: {listed}")
        return f"Connected. {len(models)} model(s) installed; using {want}."
