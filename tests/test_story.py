"""Offline story model, prompt parsing and prompt composition."""

import pytest

from booktures.pipeline import prompts, safety
from booktures.pipeline.styles import resolve_style
from booktures.pipeline.text_utils import similarity
from booktures.plugins import SceneContext
from booktures.providers.text.offline import OfflineStoryModel, detect_genre
from tests.conftest import SAMPLE_MD

TEXT = SAMPLE_MD.read_text()


def test_offline_character_bible_finds_people_not_places():
    bible = OfflineStoryModel().analyze_book(TEXT)["character_bible"]
    assert set(bible) == {"Mara", "Tobias", "Elias"}
    assert "copper hair" in bible["Mara"]
    assert "white beard" in bible["Tobias"]
    assert "black cloak" in bible["Elias"]
    assert "cloak" not in bible["Tobias"]  # no bleed between characters


def test_offline_genre_and_style():
    genre, style = detect_genre(TEXT)
    assert genre == "sea adventure"
    assert "illustration" in style


def test_offline_scene_ignores_dialogue_and_lists_characters():
    page = '"We must hurry," said Tobias. Mara ran down the cliff path to the beach where a boat lay on the sand.'
    ctx = SceneContext("start", {"Mara": "girl", "Tobias": "old man"}, "watercolor")
    scene = OfflineStoryModel().describe_scene(page, ctx)
    assert "hurry" not in scene["visual_description"]
    assert "Mara" in scene["characters"]


@pytest.mark.parametrize(
    "reply",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Sure! Here you go: {"a": 1} Hope that helps.',
        '<think>{"draft": true} hmm</think>{"a": 1}',
        '{"a": 1, "s": "brace } inside"}',
    ],
)
def test_parse_json_loose(reply):
    assert prompts.parse_json_loose(reply)["a"] == 1


def test_parse_json_loose_rejects_prose():
    with pytest.raises(ValueError):
        prompts.parse_json_loose("no json here")


def test_normalize_scene_matches_names_case_insensitively():
    ctx = SceneContext("", {"Mara": "copper hair"}, "ink")
    out = prompts.normalize_scene(
        {"scene_summary": "s", "visual_description": "mara climbs the stairs", "characters": ["MARA", "Nobody"]}, ctx
    )
    assert out["characters"] == ["Mara"]


def test_normalize_analysis_accepts_list_style_bible():
    out = prompts.normalize_analysis(
        {"global_art_style": ["oil", "warm"], "characters": [{"name": "Ada", "description": "silver hair"}]}
    )
    assert out["character_bible"] == {"Ada": "silver hair"}
    assert out["global_art_style"] == "oil, warm"


def test_compose_prompt_injects_traits_and_style_first():
    p = prompts.compose_prompt("a girl on stairs", ["Mara"], {"Mara": "copper hair, yellow oilskin"}, "watercolor")
    assert p.startswith("watercolor")
    assert "Mara: copper hair, yellow oilskin" in p


def test_style_resolution_order():
    assert resolve_style("ink", "my custom look", "llm style") == "my custom look"
    assert "ink" in resolve_style("ink", "", "llm style")
    assert resolve_style("auto", "", "llm style") == "llm style"


def test_similarity():
    assert similarity("Mara stands in the lamp room", "Mara stands in the lamp room at night") > 0.8
    assert similarity("a market full of fish stalls", "a storm over the lighthouse") < 0.2
    assert similarity("", "x") == 0.0


def test_keyword_safety_screen():
    assert safety.is_safe("a girl on a beach", "standard")
    assert not safety.is_safe("a gory battlefield", "standard")
    assert safety.is_safe("a gory battlefield", "off")
