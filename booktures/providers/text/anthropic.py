"""Anthropic Claude via the official ``anthropic`` Python SDK."""

from __future__ import annotations

from booktures.pipeline.prompts import parse_json_loose
from booktures.plugins import Field, ProviderError, TextProvider, register

# Models that accept the server-side refusal fallback (`fallbacks: "default"`).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


@register
class Claude(TextProvider):
    id = "anthropic"
    name = "Anthropic Claude"
    description = "Claude models through the Anthropic API. Strong at reading long books and keeping characters consistent."
    homepage = "https://platform.claude.com"
    requires = ["anthropic"]
    install_hint = 'pip install "booktures[anthropic]"'
    fields = [
        Field("api_key", "API key", type="secret", env="ANTHROPIC_API_KEY",
              help="Falls back to $ANTHROPIC_API_KEY or your `ant auth login` profile."),
        Field("model", "Model", default="claude-opus-5-5",
              placeholder="claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5"),
        Field("effort", "Effort", type="select", default="low",
              options=["low", "medium", "high", "default"],
              help="Writing scene briefs is light work, so 'low' keeps it fast and cheap. 'default' sends no effort setting."),
        Field("base_url", "Base URL", type="url", default="", placeholder="https://api.anthropic.com",
              help="Only change this for a proxy or gateway."),
    ]

    def _client(self):
        import anthropic

        kwargs = {"max_retries": 2, "timeout": 300.0}
        if self.config.get("api_key"):
            kwargs["api_key"] = self.config["api_key"]
        if self.config.get("base_url"):
            kwargs["base_url"] = self.config["base_url"]
        return anthropic.Anthropic(**kwargs)

    def complete_json(self, system: str, user: str) -> dict:
        import anthropic

        model = self.require("model")
        params: dict = {
            "model": model,
            "max_tokens": 16000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.config.get("effort") and self.config["effort"] != "default":
            params["output_config"] = {"effort": self.config["effort"]}
        try:
            client = self._client()
            if model in FALLBACK_MODELS:
                # Re-run declined requests on a fallback model inside the same call.
                response = client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                response = client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise ProviderError("Anthropic: invalid API key.") from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError(f"Anthropic: model '{model}' not found.") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("Anthropic: rate limited. Try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic: HTTP {exc.status_code}. {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Anthropic: could not reach the API.") from exc

        if response.stop_reason == "refusal":
            raise ProviderError("Anthropic: the model declined this page.")
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return parse_json_loose(text)
        except ValueError as exc:
            raise ProviderError(f"Anthropic: reply was not JSON: {text[:160]!r}") from exc

    def check(self) -> str:
        super().check()
        import anthropic

        try:
            info = self._client().models.retrieve(self.require("model"))
        except anthropic.AuthenticationError as exc:
            raise ProviderError("Anthropic: invalid API key.") from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError(f"Anthropic: model '{self.config['model']}' not found.") from exc
        except anthropic.APIError as exc:
            raise ProviderError(f"Anthropic: {exc}") from exc
        return f"Connected. Using {getattr(info, 'display_name', None) or info.id}."
