"""Art style presets. "auto" lets the story model choose a style for the book."""

STYLE_PRESETS: list[dict] = [
    {"id": "auto", "name": "Auto", "prompt": "", "blurb": "Let the story model pick a look that fits the book"},
    {
        "id": "watercolor",
        "name": "Watercolor",
        "prompt": "delicate watercolor storybook illustration, soft washes, textured paper, muted palette",
        "blurb": "Soft washes on textured paper",
    },
    {
        "id": "ink",
        "name": "Ink & wash",
        "prompt": "ink and wash book illustration, fine cross-hatching, sepia tones, vintage engraving",
        "blurb": "Victorian book plates",
    },
    {
        "id": "oil",
        "name": "Oil painting",
        "prompt": "classical oil painting, rich chiaroscuro, visible brushstrokes, warm varnish",
        "blurb": "Old-master light and shadow",
    },
    {
        "id": "gouache",
        "name": "Gouache",
        "prompt": "gouache painting, flat shapes, warm golden light, whimsical storybook, hand painted",
        "blurb": "Warm, flat and whimsical",
    },
    {
        "id": "anime",
        "name": "Anime",
        "prompt": "anime key visual, cel shading, vibrant colors, detailed painted background",
        "blurb": "Cel-shaded key visuals",
    },
    {
        "id": "noir",
        "name": "Noir comic",
        "prompt": "film noir graphic novel panel, high contrast black and white ink, dramatic shadows",
        "blurb": "Hard shadows, black and white",
    },
    {
        "id": "cinematic",
        "name": "Cinematic",
        "prompt": "cinematic film still, 35mm photograph, dramatic lighting, shallow depth of field",
        "blurb": "Film stills with real lenses",
    },
    {
        "id": "woodcut",
        "name": "Woodcut",
        "prompt": "woodcut print, bold carved linework, two-tone, folk art texture",
        "blurb": "Carved lines, two tones",
    },
    {
        "id": "pixel",
        "name": "Pixel art",
        "prompt": "detailed 16-bit pixel art scene, limited palette, dithering, retro game",
        "blurb": "Retro 16-bit scenes",
    },
]

PRESETS_BY_ID = {p["id"]: p for p in STYLE_PRESETS}


def resolve_style(preset: str, custom: str, suggested: str) -> str:
    """Custom text wins, then a fixed preset, then whatever the story model suggested."""
    if custom and custom.strip():
        return custom.strip()
    p = PRESETS_BY_ID.get(preset or "auto")
    if p and p["prompt"]:
        return p["prompt"]
    return suggested or "detailed book illustration, painterly, soft natural light"
