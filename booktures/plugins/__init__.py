"""Public plugin API for Booktures.

A plugin is any Python class that subclasses :class:`TextProvider` (a "story
model" that reads the book and writes scene prompts) or :class:`ImageProvider`
(an "illustrator" that turns a prompt into a picture), decorated with
:func:`register`.

Minimal example — drop this into ``~/.booktures/plugins/my_llm.py``::

    from booktures.plugins import TextProvider, Field, register

    @register
    class MyLLM(TextProvider):
        id = "my-llm"
        name = "My LLM"
        fields = [Field("api_key", "API key", type="secret")]

        def complete_json(self, system: str, user: str) -> dict:
            ...  # call your model, return the parsed JSON object

See docs/PLUGINS.md for the full guide.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

__all__ = [
    "Field",
    "ImageProvider",
    "ImageRequest",
    "Provider",
    "ProviderError",
    "SceneContext",
    "TextProvider",
    "register",
]


class ProviderError(RuntimeError):
    """Raised by a provider when a call fails in a way the user should see."""


@dataclass
class Field:
    """One configurable option, rendered as a form control in Settings."""

    key: str
    label: str
    type: str = "string"  # string | secret | url | number | boolean | select | textarea
    default: Any = None
    help: str = ""
    placeholder: str = ""
    options: list[str] | None = None
    env: str | None = None  # environment variable used when the value is empty
    required: bool = False
    #: For selects: choosing an option fills in other fields, e.g. {"Groq": {"base_url": "..."}}.
    sets: dict[str, dict[str, Any]] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SceneContext:
    """What a story model knows when it describes one page."""

    previous_summary: str
    character_bible: dict[str, str]
    global_style: str
    setting: str = ""
    page_number: int = 1
    total_pages: int = 1


@dataclass
class ImageRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 768
    height: int = 512
    seed: int = 0
    style: str = ""
    # Free-form hints such as {"characters": [...], "mood": "..."}; providers may ignore them.
    hints: dict = field(default_factory=dict)


class Provider:
    """Base class shared by text and image providers."""

    kind: ClassVar[str] = ""
    id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    homepage: ClassVar[str] = ""
    fields: ClassVar[list[Field]] = []
    #: True when the provider never sends book content off this machine.
    local: ClassVar[bool] = False
    #: Python modules that must be importable for the provider to work.
    requires: ClassVar[list[str]] = []
    #: Shell command that installs the requirements, shown in the UI.
    install_hint: ClassVar[str] = ""

    def __init__(self, config: dict | None = None):
        self.config = self.resolve_config(config or {})

    # -- configuration -------------------------------------------------
    @classmethod
    def resolve_config(cls, config: dict) -> dict:
        resolved: dict[str, Any] = {}
        for f in cls.fields:
            value = config.get(f.key)
            if value in (None, "") and f.env:
                value = os.environ.get(f.env, "")
            if value in (None, ""):
                value = f.default
            if f.type == "number" and value not in (None, ""):
                try:
                    value = float(value)
                    if value.is_integer():
                        value = int(value)
                except (TypeError, ValueError):
                    value = f.default
            if f.type == "boolean":
                value = value in (True, "true", "1", 1, "yes", "on")
            resolved[f.key] = value
        # Keep unknown keys so plugins can read extra settings.
        for key, value in config.items():
            resolved.setdefault(key, value)
        return resolved

    def require(self, key: str) -> Any:
        value = self.config.get(key)
        if value in (None, ""):
            label = next((f.label for f in self.fields if f.key == key), key)
            raise ProviderError(f"{self.name}: '{label}' is not set. Add it in Settings.")
        return value

    @classmethod
    def available(cls) -> tuple[bool, str]:
        missing = [m for m in cls.requires if importlib.util.find_spec(m) is None]
        if missing:
            hint = f" Install with: {cls.install_hint}" if cls.install_hint else ""
            return False, f"Missing Python packages: {', '.join(missing)}.{hint}"
        return True, ""

    def check(self) -> str:
        """Validate the configuration. Return a short success message or raise ProviderError."""
        ok, why = self.available()
        if not ok:
            raise ProviderError(why)
        return "Ready"

    @classmethod
    def describe(cls) -> dict:
        ok, why = cls.available()
        return {
            "id": cls.id,
            "kind": cls.kind,
            "name": cls.name,
            "description": cls.description,
            "homepage": cls.homepage,
            "local": cls.local,
            "available": ok,
            "unavailable_reason": why,
            "install_hint": cls.install_hint,
            "fields": [f.to_dict() for f in cls.fields],
        }


class TextProvider(Provider):
    """A story model. Implement :meth:`complete_json`; the rest has defaults."""

    kind = "text"

    def complete_json(self, system: str, user: str) -> dict:
        raise NotImplementedError

    def analyze_book(self, excerpt: str) -> dict:
        """Read the opening of a book; return title, genre, setting, style and character bible."""
        from booktures.pipeline import prompts

        raw = self.complete_json(prompts.ANALYZE_SYSTEM, prompts.analyze_user(excerpt))
        return prompts.normalize_analysis(raw)

    def describe_scene(self, page_text: str, ctx: SceneContext) -> dict:
        """Turn one page into a visual scene description."""
        from booktures.pipeline import prompts

        raw = self.complete_json(prompts.scene_system(ctx), prompts.scene_user(page_text))
        return prompts.normalize_scene(raw, ctx)

    def moderate(self, text: str) -> bool | None:
        """Return False if the text is unsafe, True if safe, None if unsupported."""
        return None


class ImageProvider(Provider):
    """An illustrator. Implement :meth:`generate` and return PNG/JPEG/WebP bytes."""

    kind = "image"

    def generate(self, request: ImageRequest) -> bytes:
        raise NotImplementedError


def register(cls):
    """Class decorator that adds a provider to the global registry."""
    from booktures.plugins.registry import registry

    registry.add(cls)
    return cls
