"""Where Booktures keeps its data, and the settings file.

Everything lives under one folder (``~/.booktures`` by default, or
``$BOOKTURES_HOME``)::

    ~/.booktures/
      booktures.db      library database (SQLite)
      settings.json     chosen providers and their options (API keys stay here)
      books/<id>/       uploaded file + generated images for each book
      plugins/          drop-in provider plugins (*.py)
"""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

SECRET_MASK = "••••••"

DEFAULT_SETTINGS: dict = {
    "text": {"provider": "offline", "configs": {}},
    "image": {"provider": "sketchbook", "configs": {}},
    "pipeline": {
        "width": 768,
        "height": 512,
        "similarity_threshold": 0.72,  # reuse the previous image when scenes are this similar
        "safety": "standard",  # standard | off
        "fallback_to_offline": True,  # if the story model errors, use the offline analyzer for that page
        "max_pages": 0,  # 0 = whole book
        "excerpt_chars": 14000,  # how much of the opening the story model reads for the character bible
    },
}


def data_dir(override: str | Path | None = None) -> Path:
    path = Path(override or os.environ.get("BOOKTURES_HOME") or Path.home() / ".booktures").expanduser()
    path.mkdir(parents=True, exist_ok=True)
    (path / "books").mkdir(exist_ok=True)
    (path / "plugins").mkdir(exist_ok=True)
    return path


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class SettingsStore:
    """JSON settings with secret masking for the API."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._read()
        env_text = os.environ.get("BOOKTURES_TEXT_PROVIDER")
        env_image = os.environ.get("BOOKTURES_IMAGE_PROVIDER")
        if env_text:
            self._data["text"]["provider"] = env_text
        if env_image:
            self._data["image"]["provider"] = env_image

    def _read(self) -> dict:
        if self.path.exists():
            try:
                return _deep_merge(DEFAULT_SETTINGS, json.loads(self.path.read_text()))
            except (OSError, json.JSONDecodeError):
                pass
        return copy.deepcopy(DEFAULT_SETTINGS)

    def _write(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        try:
            os.chmod(tmp, 0o600)  # the file can hold API keys
        except OSError:
            pass
        tmp.replace(self.path)

    def get(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def provider_config(self, kind: str, provider_id: str | None = None) -> tuple[str, dict]:
        data = self.get()[kind]
        pid = provider_id or data["provider"]
        return pid, dict(data["configs"].get(pid, {}))

    def update(self, patch: dict, secret_keys: dict[tuple[str, str], set[str]]) -> dict:
        """Merge a settings patch. Masked secret values keep the stored secret."""
        with self._lock:
            current = copy.deepcopy(self._data)
            for kind in ("text", "image"):
                section = patch.get(kind) or {}
                if "provider" in section:
                    current[kind]["provider"] = section["provider"]
                for pid, cfg in (section.get("configs") or {}).items():
                    stored = current[kind]["configs"].setdefault(pid, {})
                    for key, value in (cfg or {}).items():
                        if key in secret_keys.get((kind, pid), set()) and isinstance(value, str) and value.startswith(SECRET_MASK):
                            continue
                        stored[key] = value
            if isinstance(patch.get("pipeline"), dict):
                current["pipeline"].update(patch["pipeline"])
            self._data = current
            self._write()
            return copy.deepcopy(self._data)

    @staticmethod
    def mask(data: dict, secret_keys: dict[tuple[str, str], set[str]]) -> dict:
        out = copy.deepcopy(data)
        for kind in ("text", "image"):
            for pid, cfg in out[kind]["configs"].items():
                for key in secret_keys.get((kind, pid), set()):
                    value = cfg.get(key)
                    if value:
                        cfg[key] = SECRET_MASK + str(value)[-4:]
        return out
