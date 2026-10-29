"""Any server that speaks the OpenAI Chat Completions API.

That covers OpenAI itself plus OpenRouter, Groq, Together, DeepSeek, Mistral,
and local servers such as LM Studio, llama.cpp, vLLM, LocalAI and Jan.
"""

from __future__ import annotations

from booktures.pipeline.prompts import parse_json_loose
from booktures.plugins import Field, ProviderError, TextProvider, register
from booktures.providers._http import join, request

PRESETS = {
    "OpenAI": "https://api.openai.com/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Groq": "https://api.groq.com/openai/v1",
    "Together": "https://api.together.xyz/v1",
    "DeepSeek": "https://api.deepseek.com/v1",
    "Mistral": "https://api.mistral.ai/v1",
    "LM Studio (local)": "http://localhost:1234/v1",
    "llama.cpp server (local)": "http://localhost:8080/v1",
    "vLLM (local)": "http://localhost:8000/v1",
    "Ollama /v1 (local)": "http://localhost:11434/v1",
}


@register
class OpenAICompatible(TextProvider):
    id = "openai-compatible"
    name = "OpenAI-compatible"
    description = (
        "OpenAI, OpenRouter, Groq, Together, DeepSeek, Mistral, or a local LM Studio / "
        "llama.cpp / vLLM server. Anything with a /chat/completions endpoint."
    )
    homepage = "https://platform.openai.com/docs/api-reference/chat"
    fields = [
        Field("preset", "Service", type="select", default="OpenAI", options=list(PRESETS) + ["Custom"],
              help="Picking a service fills in the base URL.",
              sets={name: {"base_url": url} for name, url in PRESETS.items()}),
        Field("base_url", "Base URL", type="url", default=PRESETS["OpenAI"],
              placeholder="https://api.openai.com/v1"),
        Field("api_key", "API key", type="secret", env="OPENAI_API_KEY",
              help="Leave empty for local servers that need no key. Falls back to $OPENAI_API_KEY."),
        Field("model", "Model", default="gpt-5-mini", placeholder="gpt-5-mini, llama-3.3-70b-versatile, …"),
        Field("json_mode", "Ask for JSON mode", type="boolean", default=True,
              help="Turn off for servers that reject response_format."),
        Field("timeout", "Timeout (seconds)", type="number", default=120),
    ]

    def _headers(self) -> dict:
        key = self.config.get("api_key")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        if "openrouter.ai" in self.config["base_url"]:
            headers["HTTP-Referer"] = "https://github.com/pronzzz/booktures"
            headers["X-Title"] = "Booktures"
        return headers

    def complete_json(self, system: str, user: str) -> dict:
        body = {
            "model": self.require("model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.config.get("json_mode"):
            body["response_format"] = {"type": "json_object"}
        resp = request(
            self.name, "POST", join(self.require("base_url"), "chat/completions"),
            json=body, headers=self._headers(), timeout=float(self.config.get("timeout") or 120),
        )
        try:
            content = resp.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(f"{self.name}: unexpected response shape") from exc
        try:
            return parse_json_loose(content)
        except ValueError as exc:
            raise ProviderError(f"{self.name}: model reply was not JSON: {content[:160]!r}") from exc

    def moderate(self, text: str) -> bool | None:
        if "api.openai.com" not in self.config.get("base_url", "") or not self.config.get("api_key"):
            return None
        resp = request(
            self.name, "POST", join(self.config["base_url"], "moderations"),
            json={"model": "omni-moderation-latest", "input": text}, headers=self._headers(), timeout=30,
        )
        return not resp.json()["results"][0]["flagged"]

    def check(self) -> str:
        resp = request(self.name, "GET", join(self.require("base_url"), "models"),
                       headers=self._headers(), timeout=20)
        try:
            ids = [m.get("id") for m in resp.json().get("data", [])]
        except ValueError:
            ids = []
        model = self.config.get("model")
        if ids and model not in ids:
            sample = ", ".join(sorted(i for i in ids if i)[:6])
            return f"Connected, but '{model}' is not in the model list. Available: {sample}…"
        return f"Connected. Using {model}."
