from booktures.plugins import Field, ImageProvider, TextProvider
from booktures.plugins.registry import Registry, load_all

GOOD_PLUGIN = '''
from booktures.plugins import TextProvider, Field, register

@register
class EchoLLM(TextProvider):
    id = "echo-test"
    name = "Echo"
    fields = [Field("prefix", "Prefix", default="echo")]

    def complete_json(self, system, user):
        return {"scene_summary": self.config["prefix"], "visual_description": "a quiet harbor at dawn",
                "characters": [], "global_art_style": "test style", "character_bible": {"Ada": "silver hair"}}
'''


def test_builtins_registered():
    reg = load_all([])
    assert {"offline", "openai-compatible", "ollama", "anthropic", "gemini"} <= set(reg.text)
    assert {"sketchbook", "diffusers", "pollinations", "openai-images", "stability", "automatic1111", "comfyui"} <= set(reg.image)
    cat = reg.catalog()
    assert all("fields" in p for p in cat["text"] + cat["image"])


def test_dropin_plugin_loads_and_works(tmp_path):
    (tmp_path / "echo.py").write_text(GOOD_PLUGIN)
    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')")
    (tmp_path / "_private.py").write_text("raise RuntimeError('should be skipped')")
    reg = load_all([tmp_path])
    assert "echo-test" in reg.text
    assert reg.origins[("text", "echo-test")].startswith("file:")
    assert any("broken.py" in e["source"] and "boom" in e["error"] for e in reg.errors)
    assert not any("_private" in e["source"] for e in reg.errors)

    llm = reg.create("text", "echo-test", {"prefix": "hi"})
    analysis = llm.analyze_book("Ada sailed.")
    assert analysis["character_bible"] == {"Ada": "silver hair"}
    from booktures.plugins import SceneContext

    scene = llm.describe_scene("text", SceneContext("", {}, "s"))
    assert scene["scene_summary"] == "hi"


def test_field_resolution(monkeypatch):
    class P(ImageProvider):
        id = "p"
        fields = [
            Field("key", "Key", type="secret", env="P_TEST_KEY"),
            Field("steps", "Steps", type="number", default=4),
            Field("flag", "Flag", type="boolean", default=False),
        ]

    monkeypatch.setenv("P_TEST_KEY", "from-env")
    p = P({"steps": "12", "flag": "true", "extra": 1})
    assert p.config == {"key": "from-env", "steps": 12, "flag": True, "extra": 1}


def test_unavailable_provider_reports_install_hint():
    class Needs(TextProvider):
        id = "needs"
        requires = ["definitely_not_a_module_xyz"]
        install_hint = "pip install xyz"

    ok, why = Needs.available()
    assert not ok and "pip install xyz" in why


def test_registry_rejects_non_providers():
    reg = Registry()
    try:
        reg.add(object)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("expected an error")
