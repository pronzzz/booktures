"""Prompts sent to story models, and the code that cleans up their answers.

Every story model gets the same two jobs:

* ``analyze`` — read the opening of the book once and return the art style,
  setting and a *character bible* (name -> fixed physical description).
* ``scene`` — for each page, return a short visual description of what an
  illustrator should paint, plus which characters are on screen.

The final image prompt is assembled by :func:`compose_prompt` in code, not by
the model, so character traits and the art style are always injected even when
a small model forgets them.
"""

from __future__ import annotations

import json
import re

from booktures.plugins import SceneContext

ANALYZE_SYSTEM = """You are the art director for an illustrated edition of a book.
Read the opening excerpt and plan a consistent look for every illustration.

Reply with one JSON object and nothing else:
{
  "title": "book title if stated, else empty string",
  "author": "author if stated, else empty string",
  "genre": "one or two words, e.g. 'gothic horror' or 'space opera'",
  "setting": "where and when the story happens, under 20 words",
  "global_art_style": "comma-separated image style tags: medium, palette, lighting, mood (under 25 words)",
  "character_bible": {
    "Character Name": "fixed physical description an illustrator can reuse on every page: age, build, hair, clothing, distinctive marks (under 25 words)"
  }
}

Rules:
- Only include characters who are people (or creatures) that appear on the page, at most 8.
- Describe looks only. No personality, no plot.
- If the text gives no description, invent a plausible one that fits the setting and keep it simple."""


def analyze_user(excerpt: str) -> str:
    return f"Opening excerpt:\n\n{excerpt}"


def scene_system(ctx: SceneContext) -> str:
    bible = json.dumps(ctx.character_bible, ensure_ascii=False) if ctx.character_bible else "{}"
    return f"""You write illustration briefs for page {ctx.page_number} of {ctx.total_pages} of a book.

Art style (do not repeat it in your answer): {ctx.global_style}
Setting: {ctx.setting or "unknown"}
Character bible: {bible}
What the previous illustration showed: {ctx.previous_summary}

Reply with one JSON object and nothing else:
{{
  "scene_summary": "one sentence saying what happens on this page, for continuity",
  "visual_description": "what the picture shows: place, light, objects, who is there and what they are doing (under 45 words, no dialogue, no style words)",
  "characters": ["names from the character bible who are visible in the picture"],
  "new_characters": {{"Name": "physical description, only for important people not yet in the bible"}},
  "mood": "one or two words"
}}

Rules:
- Paint a single moment. Ignore dialogue and inner thoughts; show only what a camera could see.
- If nothing visible happens, show the setting or an object the page mentions.
- Use character names exactly as they appear in the bible."""


def scene_user(page_text: str) -> str:
    return f"Page text:\n\n{page_text[:6000]}"


# -- answer parsing --------------------------------------------------------


def parse_json_loose(text: str) -> dict:
    """Parse the first JSON object in a model reply (tolerates code fences and chatter)."""
    if isinstance(text, dict):
        return text
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    # Reasoning models sometimes wrap their thinking in <think> tags.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start : i + 1])
                        if isinstance(value, dict):
                            return value
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("The model did not return a JSON object")


def _clean(value, limit: int = 400) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value)
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def _clean_bible(value) -> dict[str, str]:
    bible: dict[str, str] = {}
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):  # [{"name": ..., "description": ...}]
        items = [
            (v.get("name"), v.get("description") or v.get("appearance"))
            for v in value
            if isinstance(v, dict)
        ]
    else:
        return bible
    for name, desc in items:
        if isinstance(desc, dict):
            desc = ", ".join(str(v) for v in desc.values())
        name, desc = _clean(name, 60), _clean(desc, 240)
        if name and desc:
            bible[name] = desc
    return dict(list(bible.items())[:12])


def normalize_analysis(raw: dict) -> dict:
    return {
        "title": _clean(raw.get("title"), 200),
        "author": _clean(raw.get("author"), 200),
        "genre": _clean(raw.get("genre"), 60),
        "setting": _clean(raw.get("setting"), 240),
        "global_art_style": _clean(raw.get("global_art_style") or raw.get("style"), 300),
        "character_bible": _clean_bible(raw.get("character_bible") or raw.get("characters")),
    }


def normalize_scene(raw: dict, ctx: SceneContext) -> dict:
    visual = _clean(
        raw.get("visual_description") or raw.get("image_prompt") or raw.get("description"), 600
    )
    summary = _clean(raw.get("scene_summary") or raw.get("summary") or visual, 400)
    chars = raw.get("characters") or []
    if isinstance(chars, str):
        chars = [c.strip() for c in chars.split(",")]
    known = {k.lower(): k for k in ctx.character_bible}
    present = []
    for c in chars:
        key = known.get(str(c).strip().lower())
        if key and key not in present:
            present.append(key)
    # Also catch bible names the model mentioned in the description but did not list.
    for lower, name in known.items():
        if name not in present and re.search(rf"\b{re.escape(lower)}\b", visual.lower()):
            present.append(name)
    return {
        "scene_summary": summary,
        "visual_description": visual or summary,
        "characters": present,
        "new_characters": _clean_bible(raw.get("new_characters")),
        "mood": _clean(raw.get("mood"), 40),
    }


NEGATIVE_PROMPT = (
    "text, letters, words, watermark, signature, logo, blurry, lowres, jpeg artifacts, "
    "deformed, disfigured, extra limbs, extra fingers, bad anatomy, duplicate, cropped"
)


def compose_prompt(
    visual: str, characters: list[str], bible: dict[str, str], style: str, mood: str = ""
) -> str:
    """Build the final image prompt: style first (so it survives truncation), then scene, then traits."""
    parts = []
    if style:
        parts.append(style.rstrip(" ,."))
    if visual:
        parts.append(visual.rstrip(" ,."))
    for name in characters[:3]:
        desc = bible.get(name)
        if desc:
            parts.append(f"{name}: {desc.rstrip(' ,.')}")
    if mood:
        parts.append(f"{mood} mood")
    return ". ".join(parts)
