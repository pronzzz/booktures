"""Google Gemini through the Generative Language REST API."""

from __future__ import annotations

from booktures.pipeline.prompts import parse_json_loose
from booktures.plugins import Field, ProviderError, TextProvider, register
from booktures.providers._http import request

API = "https://generativelanguage.googleapis.com/v1beta"


@register
class Gemini(TextProvider):
    id = "gemini"
    name = "Google Gemini"
    description = "Gemini models via Google AI Studio keys. Large context windows and a generous free tier."
    homepage = "https://aistudio.google.com/apikey"
    fields = [
        Field("api_key", "API key", type="secret", env="GEMINI_API_KEY"),
        Field("model", "Model", default="gemini-flash-latest", placeholder="gemini-flash-latest, gemini-2.5-pro"),
        Field("timeout", "Timeout (seconds)", type="number", default=120),
    ]

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.require("api_key"), "Content-Type": "application/json"}

    def complete_json(self, system: str, user: str) -> dict:
        model = self.require("model").removeprefix("models/")
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        resp = request(self.name, "POST", f"{API}/models/{model}:generateContent", json=body,
                       headers=self._headers(), timeout=float(self.config.get("timeout") or 120))
        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as exc:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise ProviderError(f"Gemini returned no text{f' (blocked: {reason})' if reason else ''}.") from exc
        try:
            return parse_json_loose(text)
        except ValueError as exc:
            raise ProviderError(f"Gemini: reply was not JSON: {text[:160]!r}") from exc

    def check(self) -> str:
        model = self.require("model").removeprefix("models/")
        resp = request(self.name, "GET", f"{API}/models/{model}", headers=self._headers(), timeout=20)
        return f"Connected. Using {resp.json().get('displayName', model)}."
