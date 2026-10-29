"""Provider registry and plugin discovery.

Providers come from three places, loaded in this order:

1. Built-ins shipped in ``booktures.providers``.
2. Installed packages that declare a ``booktures.plugins`` entry point.
3. Drop-in ``*.py`` files in the plugin folders (``~/.booktures/plugins`` by
   default, plus any folder passed with ``--plugins`` or ``BOOKTURES_PLUGINS``).

A later provider with the same id replaces an earlier one, so a plugin can
override a built-in.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import traceback
from importlib.metadata import entry_points
from pathlib import Path

from booktures.plugins import ImageProvider, Provider, TextProvider

log = logging.getLogger("booktures.plugins")

BUILTIN_MODULES = [
    "booktures.providers.text.offline",
    "booktures.providers.text.openai_compat",
    "booktures.providers.text.ollama",
    "booktures.providers.text.anthropic",
    "booktures.providers.text.gemini",
    "booktures.providers.image.sketchbook",
    "booktures.providers.image.diffusers_local",
    "booktures.providers.image.pollinations",
    "booktures.providers.image.openai_images",
    "booktures.providers.image.stability",
    "booktures.providers.image.automatic1111",
    "booktures.providers.image.comfyui",
]


class Registry:
    def __init__(self) -> None:
        self.text: dict[str, type[TextProvider]] = {}
        self.image: dict[str, type[ImageProvider]] = {}
        self.origins: dict[tuple[str, str], str] = {}
        self.errors: list[dict] = []
        self._origin = "built-in"
        self._loaded_files: set[str] = set()

    def add(self, cls: type[Provider]) -> None:
        if not getattr(cls, "id", ""):
            raise ValueError(f"{cls.__name__} has no 'id'")
        if issubclass(cls, TextProvider):
            table, kind = self.text, "text"
        elif issubclass(cls, ImageProvider):
            table, kind = self.image, "image"
        else:
            raise TypeError(f"{cls.__name__} must subclass TextProvider or ImageProvider")
        if not cls.name:
            cls.name = cls.id
        table[cls.id] = cls
        self.origins[(kind, cls.id)] = self._origin

    def get(self, kind: str, provider_id: str) -> type[Provider]:
        table = self.text if kind == "text" else self.image
        if provider_id not in table:
            raise KeyError(f"No {kind} provider named '{provider_id}'")
        return table[provider_id]

    def create(self, kind: str, provider_id: str, config: dict | None = None) -> Provider:
        return self.get(kind, provider_id)(config or {})

    # -- discovery -----------------------------------------------------
    def load_builtins(self) -> None:
        self._origin = "built-in"
        for module in BUILTIN_MODULES:
            self._import(module, module)

    def load_entry_points(self) -> None:
        for ep in entry_points(group="booktures.plugins"):
            self._origin = f"package: {ep.value}"
            try:
                obj = ep.load()
                if isinstance(obj, type) and issubclass(obj, Provider):
                    self.add(obj)
            except Exception as exc:  # noqa: BLE001 - a broken plugin must not stop the app
                self._error(ep.value, exc)

    def load_directory(self, folder: Path) -> None:
        folder = Path(folder).expanduser()
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_") or str(path.resolve()) in self._loaded_files:
                continue
            self._loaded_files.add(str(path.resolve()))
            self._origin = f"file: {path}"
            name = f"booktures_user_plugin_{path.stem}"
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
            except Exception as exc:  # noqa: BLE001
                sys.modules.pop(name, None)
                self._error(str(path), exc)

    def _import(self, module: str, source: str) -> None:
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001
            self._error(source, exc)

    def _error(self, source: str, exc: Exception) -> None:
        log.warning("Plugin %s failed to load: %s", source, exc)
        self.errors.append(
            {
                "source": source,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=4),
            }
        )

    def catalog(self) -> dict:
        def rows(kind: str, table: dict) -> list[dict]:
            out = []
            for pid, cls in table.items():
                info = cls.describe()
                info["origin"] = self.origins.get((kind, pid), "built-in")
                out.append(info)
            return out

        return {
            "text": rows("text", self.text),
            "image": rows("image", self.image),
            "errors": self.errors,
        }


registry = Registry()


def load_all(plugin_dirs: list[Path]) -> Registry:
    """Load built-ins, entry points and drop-in folders (safe to call twice)."""
    if not registry.text:
        registry.load_builtins()
        registry.load_entry_points()
    for folder in plugin_dirs:
        registry.load_directory(folder)
    return registry
