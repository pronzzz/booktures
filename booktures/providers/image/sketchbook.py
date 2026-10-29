"""Sketchbook: a procedural painter that needs no model and no network.

It reads the prompt for time of day, weather, landscape and people, then paints
a layered gouache-style scene with Pillow. The same prompt and seed always give
the same picture. It is the default illustrator so a fresh install can turn a
book into a picture book immediately; switch to a real image model for real art.
"""

from __future__ import annotations

import io
import random
import re
import zlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from booktures.plugins import Field, ImageProvider, ImageRequest, register

RGB = tuple[int, int, int]

PALETTES: dict[str, dict[str, RGB]] = {
    "day": dict(sky_top=(118, 168, 214), sky_bot=(222, 233, 236), far=(150, 172, 190), mid=(104, 138, 112),
                near=(58, 82, 64), water=(84, 132, 168), light=(255, 246, 214), ink=(34, 40, 38)),
    "dusk": dict(sky_top=(58, 62, 120), sky_bot=(246, 166, 112), far=(136, 98, 128), mid=(92, 66, 96),
                 near=(46, 34, 54), water=(96, 84, 128), light=(255, 196, 120), ink=(28, 20, 32)),
    "dawn": dict(sky_top=(132, 160, 204), sky_bot=(250, 210, 182), far=(170, 160, 186), mid=(118, 128, 140),
                 near=(68, 74, 88), water=(140, 160, 190), light=(255, 228, 190), ink=(40, 42, 54)),
    "night": dict(sky_top=(10, 16, 40), sky_bot=(42, 58, 102), far=(34, 44, 76), mid=(24, 32, 56),
                  near=(12, 16, 30), water=(26, 40, 74), light=(236, 232, 200), ink=(6, 8, 16)),
    "storm": dict(sky_top=(62, 70, 80), sky_bot=(150, 156, 160), far=(104, 112, 118), mid=(74, 84, 86),
                  near=(42, 48, 50), water=(70, 86, 96), light=(220, 224, 226), ink=(24, 28, 30)),
    "sunlit": dict(sky_top=(96, 150, 210), sky_bot=(244, 224, 176), far=(196, 172, 142), mid=(176, 140, 96),
                   near=(120, 88, 58), water=(70, 130, 170), light=(255, 240, 200), ink=(60, 40, 28)),
}

WORDS = {
    "night": "night midnight moon moonlight moonlit stars starlight dark darkness evening-dark nocturnal".split(),
    "dusk": "dusk sunset evening twilight golden-hour".split(),
    "dawn": "dawn sunrise morning daybreak".split(),
    "storm": "storm rain rainy thunder grey gray overcast fog foggy mist misty gloomy".split(),
    "sunlit": "hot desert sun sunny heat dry summer white hills valley".split(),
    "water": "sea ocean waves wave harbor harbour lake river shore beach coast bay tide boat ship sail".split(),
    "mountain": "mountain mountains peaks cliffs cliff alps ridge".split(),
    "hills": "hills hill valley meadow field fields plains".split(),
    "forest": "forest woods trees tree pines garden orchard jungle grove".split(),
    "city": "city street streets town buildings alley skyline houses rooftops market village".split(),
    "tower": "lighthouse tower spire steeple castle".split(),
    "interior": "room kitchen library parlor parlour bedroom hall office study attic cabin bar cafe diner "
                "table desk shelf bookshelf fireplace".split(),
    "rain": "rain raining rainy downpour drizzle".split(),
    "snow": "snow snowy snowing winter frost".split(),
    "fire": "fire candle candlelight lamp lantern torch hearth fireplace glow".split(),
    "station": "station rails railway train platform tracks".split(),
}


def _has(words: set[str], key: str) -> bool:
    return any(w in words for w in WORDS[key])


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _ridge(rng: random.Random, width: int, base: float, amp: float, rough: float = 0.55) -> list[float]:
    """Midpoint-displacement skyline: a list of y values across the width."""
    n = 65
    pts = [base + rng.uniform(-amp, amp) * 0.4, base + rng.uniform(-amp, amp) * 0.4]
    scale = amp
    while len(pts) < n:
        nxt = []
        for i in range(len(pts) - 1):
            nxt.append(pts[i])
            nxt.append((pts[i] + pts[i + 1]) / 2 + rng.uniform(-scale, scale))
        nxt.append(pts[-1])
        pts = nxt
        scale *= rough
    step = width / (len(pts) - 1)
    return [pts[int(x / step)] for x in range(width + 1)]


def _fill_ridge(draw: ImageDraw.ImageDraw, ys: list[float], h: int, color) -> None:
    pts = [(x, y) for x, y in enumerate(ys)] + [(len(ys) - 1, h), (0, h)]
    draw.polygon(pts, fill=color)


def _glow(img: Image.Image, cx: int, cy: int, r: int, color: RGB, strength: float = 0.7) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(6, 0, -1):
        rr = int(r * (1 + i * 0.9))
        a = int(255 * strength * (0.07 + 0.02 * (6 - i)))
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (a,))
    layer = layer.filter(ImageFilter.GaussianBlur(r * 0.8))
    img.alpha_composite(layer)


def _figure(d: ImageDraw.ImageDraw, x: int, ground: int, height: int, color, rng: random.Random) -> None:
    """A simple standing silhouette: head, neck, tapered coat or tunic, legs."""
    head_r = height * 0.075
    neck_y = ground - height * 0.82
    sway = rng.uniform(-0.03, 0.03) * height
    cx = x + sway
    d.ellipse([cx - head_r, neck_y - head_r * 2.05, cx + head_r, neck_y - head_r * 0.05], fill=color)
    d.rectangle([cx - head_r * 0.35, neck_y - head_r * 0.4, cx + head_r * 0.35, neck_y + head_r * 0.3], fill=color)
    shoulder = height * rng.uniform(0.11, 0.14)
    coat = rng.random() < 0.55
    hem_y = ground - height * (0.16 if coat else 0.4)
    hem = height * (0.16 if coat else 0.1)
    d.polygon([(cx - shoulder * 0.55, neck_y), (cx + shoulder * 0.55, neck_y),
               (cx + shoulder, neck_y + height * 0.06), (x + hem, hem_y),
               (x - hem, hem_y), (cx - shoulder, neck_y + height * 0.06)], fill=color)
    # arms
    d.line([(cx - shoulder * 0.95, neck_y + height * 0.07), (x - shoulder * 1.15, ground - height * 0.42)], fill=color, width=max(2, int(height * 0.045)))
    d.line([(cx + shoulder * 0.95, neck_y + height * 0.07), (x + shoulder * 1.15, ground - height * 0.42)], fill=color, width=max(2, int(height * 0.045)))
    leg = height * 0.04
    d.polygon([(x - leg * 2.4, hem_y - 2), (x - leg * 0.3, hem_y - 2), (x - leg * 0.6, ground), (x - leg * 2.4, ground)], fill=color)
    d.polygon([(x + leg * 0.3, hem_y - 2), (x + leg * 2.4, hem_y - 2), (x + leg * 2.4, ground), (x + leg * 0.6, ground)], fill=color)


def _paper(size: tuple[int, int], rng: random.Random) -> Image.Image:
    # Seeded noise (Image.effect_noise uses a global RNG, which would break determinism).
    def noise(w: int, h: int, spread: int) -> Image.Image:
        raw = Image.frombytes("L", (w, h), rng.randbytes(w * h))
        return raw.point(lambda v: 128 + (v - 128) * spread // 128)

    fine = noise(*size, 40).filter(ImageFilter.GaussianBlur(1.1))
    fibres = noise(size[0] // 8 + 1, size[1] // 8 + 1, 90).resize(size, Image.BICUBIC)
    return ImageChops.add(fine, fibres, scale=2.0)


def paint(prompt: str, width: int, height: int, seed: int) -> Image.Image:
    text = prompt.lower()
    words = set(re.findall(r"[a-z\-]+", text))
    rng = random.Random((zlib.crc32(prompt.encode()) ^ (seed * 2654435761)) & 0xFFFFFFFF)
    w, h = width, height

    tod = next((k for k in ("night", "dusk", "dawn", "storm", "sunlit") if _has(words, k)), "day")
    pal = dict(PALETTES[tod])
    if "neon" in words or "cyberpunk" in words:
        pal.update(light=(255, 92, 196), water=(60, 30, 110), sky_bot=(120, 40, 140))

    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    interior = _has(words, "interior") and not (_has(words, "water") or _has(words, "forest"))
    horizon = int(h * rng.uniform(0.52, 0.64))

    def sky(box):
        x0, y0, x1, y1 = box
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0)
            d.line([(x0, y), (x1, y)], fill=_mix(pal["sky_top"], pal["sky_bot"], t ** 0.8))

    if interior:
        wall = _mix(pal["mid"], (120, 96, 70), 0.55)
        for y in range(h):
            d.line([(0, y), (w, y)], fill=_mix(_mix(wall, (0, 0, 0), 0.35), wall, min(1, y / h * 1.6)))
        # window
        wx0, wy0 = int(w * rng.uniform(0.12, 0.5)), int(h * 0.14)
        wx1, wy1 = wx0 + int(w * 0.3), int(h * 0.56)
        sky((wx0, wy0, wx1, wy1))
        if tod == "night":
            for _ in range(30):
                sx, sy = rng.randint(wx0, wx1), rng.randint(wy0, wy1)
                d.point((sx, sy), fill=(230, 230, 210))
        frame = _mix(wall, (30, 20, 12), 0.6)
        d.rectangle([wx0, wy0, wx1, wy1], outline=frame, width=max(3, w // 120))
        d.line([((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1)], fill=frame, width=max(2, w // 200))
        d.line([(wx0, (wy0 + wy1) // 2), (wx1, (wy0 + wy1) // 2)], fill=frame, width=max(2, w // 200))
        # shelves
        if "library" in words or "book" in words or "shelf" in words or rng.random() < 0.5:
            sx0 = wx1 + int(w * 0.08) if wx1 < w * 0.6 else int(w * 0.04)
            for row in range(4):
                y = int(h * (0.16 + row * 0.12))
                x = sx0
                while x < sx0 + int(w * 0.28):
                    bw = rng.randint(max(3, w // 160), max(6, w // 70))
                    bh = int(h * rng.uniform(0.07, 0.1))
                    d.rectangle([x, y + int(h * 0.1) - bh, x + bw, y + int(h * 0.1)],
                                fill=_mix(rng.choice([(120, 50, 40), (60, 80, 70), (150, 120, 70), (70, 60, 90)]), wall, 0.3))
                    x += bw + 1
                d.line([(sx0 - 4, y + int(h * 0.1)), (sx0 + int(w * 0.3), y + int(h * 0.1))], fill=frame, width=3)
        floor = int(h * 0.74)
        d.rectangle([0, floor, w, h], fill=_mix(wall, (40, 26, 16), 0.5))
        # table
        tx = int(w * rng.uniform(0.35, 0.6))
        d.rectangle([tx - w * 0.18, floor - h * 0.1, tx + w * 0.18, floor - h * 0.08], fill=frame)
        d.rectangle([tx - w * 0.16, floor - h * 0.08, tx - w * 0.15, floor + h * 0.06], fill=frame)
        d.rectangle([tx + w * 0.15, floor - h * 0.08, tx + w * 0.16, floor + h * 0.06], fill=frame)
        if _has(words, "fire") or tod in ("night", "dusk"):
            lx, ly = int(tx + w * 0.1), int(floor - h * 0.14)
            d.rectangle([lx - 3, ly, lx + 3, floor - h * 0.1], fill=(40, 30, 20))
            _glow(img, lx, ly, max(8, w // 40), (255, 190, 110), 1.0)
        ground = floor + int(h * 0.12)
    else:
        sky((0, 0, w, horizon + 4))
        if tod == "night":
            for _ in range(int(w * h / 2600)):
                x, y = rng.randint(0, w), rng.randint(0, int(horizon * 0.9))
                c = rng.randint(170, 255)
                d.point((x, y), fill=(c, c, int(c * 0.9)))
        # sun or moon
        if tod != "storm":
            cx, cy = int(w * rng.uniform(0.2, 0.8)), int(horizon * rng.uniform(0.25, 0.7 if tod in ("dusk", "dawn") else 0.45))
            r = int(min(w, h) * (0.05 if tod == "night" else 0.07))
            _glow(img, cx, cy, r, pal["light"], 0.9)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=pal["light"])
            if tod == "night":
                off = int(r * 0.45)
                d.ellipse([cx - r + off, cy - r - off // 3, cx + r + off, cy + r - off // 3], fill=_mix(pal["sky_top"], pal["sky_bot"], cy / horizon))
        # clouds
        clouds = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(clouds)
        for _ in range(rng.randint(3, 7 if tod == "storm" else 5)):
            cx, cy = rng.randint(-w // 8, w), rng.randint(int(h * 0.05), int(horizon * 0.7))
            for _ in range(rng.randint(3, 6)):
                rw, rh = rng.randint(w // 14, w // 6), rng.randint(h // 40, h // 16)
                ox = rng.randint(-w // 10, w // 10)
                cd.ellipse([cx + ox - rw, cy - rh, cx + ox + rw, cy + rh],
                           fill=_mix(pal["sky_bot"], (255, 255, 255), 0.4) + (70 if tod != "storm" else 140,))
        img.alpha_composite(clouds.filter(ImageFilter.GaussianBlur(w // 90 + 2)))

        mountainous = _has(words, "mountain")
        far_amp = h * (0.16 if mountainous else 0.06)
        _fill_ridge(d, _ridge(rng, w, horizon - h * (0.1 if mountainous else 0.03), far_amp, 0.6),
                    h, _mix(pal["far"], pal["sky_bot"], 0.35))
        if _has(words, "city") or _has(words, "station"):
            x = rng.randint(-20, 10)
            base = horizon + int(h * 0.02)
            village = not ({"city", "skyline", "buildings"} & words)
            while x < w:
                if village:
                    bw, bh = rng.randint(w // 16, w // 9), rng.randint(int(h * 0.05), int(h * 0.1))
                else:
                    bw, bh = rng.randint(w // 28, w // 11), rng.randint(int(h * 0.06), int(h * 0.26))
                col = _mix(pal["mid"], pal["far"], rng.uniform(0, 0.4))
                d.rectangle([x, base - bh, x + bw, base + 4], fill=col)
                if village:
                    roof = _mix(rng.choice([(150, 70, 52), (90, 70, 60), (70, 90, 110)]), pal["far"], 0.45)
                    d.polygon([(x - 4, base - bh), (x + bw + 4, base - bh), (x + bw // 2, base - bh - int(bw * 0.45))], fill=roof)
                    if rng.random() < 0.6:
                        dx = x + rng.randint(4, max(5, bw - 12))
                        d.rectangle([dx, base - bh // 2, dx + max(4, bw // 7), base], fill=_mix(rng.choice([(60, 90, 140), (40, 60, 90)]), col, 0.3))
                elif rng.random() < 0.35:
                    d.polygon([(x - 2, base - bh), (x + bw + 2, base - bh), (x + bw // 2, base - bh - bw // 2)], fill=col)
                if tod in ("night", "dusk", "storm"):
                    for wy in range(base - bh + 6, base - 4, max(6, h // 50)):
                        for wx in range(x + 3, x + bw - 3, max(6, w // 90)):
                            if rng.random() < 0.3:
                                d.rectangle([wx, wy, wx + 2, wy + 3], fill=pal["light"] if "neon" not in words else rng.choice([(255, 90, 200), (90, 230, 255)]))
                x += bw + rng.randint(0, w // 50)

        if _has(words, "water"):
            for y in range(horizon, h):
                t = (y - horizon) / max(1, h - horizon)
                d.line([(0, y), (w, y)], fill=_mix(_mix(pal["water"], pal["sky_bot"], 0.35), pal["water"], t ** 0.6))
            for _ in range(int(h * 0.6)):
                y = rng.randint(horizon + 2, h)
                x = rng.randint(0, w)
                ln = rng.randint(w // 60, w // 14)
                d.line([(x, y), (x + ln, y)], fill=_mix(pal["water"], pal["light"], rng.uniform(0.1, 0.45)), width=1)
            # a headland so there is something to stand on
            side = rng.choice([0, 1])
            land = _ridge(rng, w, horizon + h * 0.1, h * 0.06, 0.5)
            land = [y if (x < w * 0.42 if side == 0 else x > w * 0.58) else h + 10 for x, y in enumerate(land)]
            _fill_ridge(d, land, h, pal["near"])
            ground_ys = land
            if _has(words, "tower"):
                tx = int(w * (0.2 if side == 0 else 0.8))
                top = int(min(land[tx], h) - h * 0.42)
                bottom = int(min(land[tx], h))
                tw = w * 0.028
                d.polygon([(tx - tw, bottom), (tx + tw, bottom), (tx + tw * 0.65, top), (tx - tw * 0.65, top)], fill=(232, 226, 214))
                for band in range(1, 4):
                    by = bottom - (bottom - top) * band / 4
                    d.rectangle([tx - tw * 0.9, by - h * 0.02, tx + tw * 0.9, by], fill=(160, 54, 48))
                d.rectangle([tx - tw * 0.8, top - h * 0.05, tx + tw * 0.8, top], fill=pal["ink"])
                lamp = (tx, int(top - h * 0.03))
                if tod in ("night", "dusk", "storm"):
                    beam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                    bd = ImageDraw.Draw(beam)
                    direction = 1 if side == 0 else -1
                    bd.polygon([lamp, (lamp[0] + direction * w, lamp[1] - h * 0.12), (lamp[0] + direction * w, lamp[1] + h * 0.06)],
                               fill=pal["light"] + (60,))
                    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(6)))
                _glow(img, *lamp, max(6, w // 70), pal["light"], 1.0)
        else:
            mid = _ridge(rng, w, horizon + h * 0.05, h * (0.05 if _has(words, "hills") else 0.03), 0.55)
            _fill_ridge(d, mid, h, pal["mid"])
            near = _ridge(rng, w, horizon + h * 0.2, h * 0.04, 0.5)
            _fill_ridge(d, near, h, pal["near"])
            ground_ys = near
            if _has(words, "station"):
                ry = int(sum(near) / len(near)) + int(h * 0.08)
                for off in (0, int(h * 0.05)):
                    d.line([(0, ry + off), (w, ry + off * 0.6)], fill=(70, 62, 58), width=max(2, h // 160))
            if _has(words, "tower") and not _has(words, "city"):
                tx = int(w * rng.uniform(0.6, 0.85))
                gy = int(mid[tx])
                d.rectangle([tx - w * 0.03, gy - h * 0.3, tx + w * 0.03, gy], fill=_mix(pal["mid"], pal["ink"], 0.5))
                d.polygon([(tx - w * 0.045, gy - h * 0.3), (tx + w * 0.045, gy - h * 0.3), (tx, gy - h * 0.42)], fill=_mix(pal["mid"], pal["ink"], 0.6))

        if _has(words, "forest"):
            for layer, t in ((0, 0.25), (1, 0.6)):
                base_ys = ground_ys
                for _ in range(int(w / (34 if layer else 22))):
                    x = rng.randint(0, w)
                    gy = min(base_ys[min(x, w)], h) + (0 if layer else -h * 0.04)
                    th = h * rng.uniform(0.12, 0.26) * (1.2 if layer else 0.8)
                    tw = th * rng.uniform(0.28, 0.38)
                    col = _mix(pal["near"], pal["mid"], t * rng.uniform(0.3, 1.0))
                    if rng.random() < 0.6:
                        d.polygon([(x, gy - th), (x - tw, gy), (x + tw, gy)], fill=col)
                    else:
                        d.ellipse([x - tw, gy - th, x + tw, gy - th * 0.25], fill=col)
                        d.rectangle([x - tw * 0.08, gy - th * 0.3, x + tw * 0.08, gy], fill=pal["ink"])
        ground = int(min(ground_ys[w // 2], h - 4))

    # People: one silhouette per named character (up to three).
    named = len(re.findall(r"\b[A-Z][a-z]+: ", prompt))
    people = min(3, named or (1 if re.search(r"\b(man|woman|girl|boy|he|she|figure|stranger|they)\b", text) else 0))
    if people:
        fig_h = int(h * rng.uniform(0.26, 0.34) * (1.25 if interior else 1))
        start = int(w * rng.uniform(0.3, 0.55))
        for i in range(people):
            x = start + int(i * fig_h * rng.uniform(0.35, 0.55)) * (1 if i % 2 == 0 else -1)
            gy = ground if interior else int(min((ground_ys[min(max(x, 0), w)] if not interior else ground), h - 2)) + int(h * 0.02)
            _figure(d, x, gy, int(fig_h * rng.uniform(0.88, 1.0)), _mix(pal["ink"], pal["near"], 0.15), rng)

    if _has(words, "rain"):
        rain = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rain)
        for _ in range(int(w * h / 900)):
            x, y = rng.randint(-20, w), rng.randint(-20, h)
            rd.line([(x, y), (x + 4, y + h // 30)], fill=(220, 226, 236, 70), width=1)
        img.alpha_composite(rain)
    if _has(words, "snow"):
        for _ in range(int(w * h / 700)):
            x, y = rng.randint(0, w), rng.randint(0, h)
            r = rng.choice([1, 1, 2])
            d.ellipse([x - r, y - r, x + r, y + r], fill=(245, 245, 250))
    if "fog" in words or "mist" in words or "misty" in words or "foggy" in words:
        fog = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fog)
        for _ in range(8):
            y = rng.randint(int(h * 0.4), h)
            fd.ellipse([rng.randint(-w // 2, w // 2), y - h // 12, rng.randint(w // 2, w * 3 // 2), y + h // 12], fill=(230, 232, 236, 50))
        img.alpha_composite(fog.filter(ImageFilter.GaussianBlur(h // 20)))

    out = img.convert("RGB")
    # Painterly finish: soften, posterize slightly, lay on paper grain and a vignette.
    out = out.filter(ImageFilter.ModeFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
    out = ImageOps.posterize(out, 6).filter(ImageFilter.SMOOTH)
    grain = _paper((w, h), rng).convert("RGB")
    out = ImageChops.blend(out, ImageChops.multiply(out, ImageOps.autocontrast(grain, cutoff=2)), 0.1)
    vignette = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vignette).ellipse([-w * 0.25, -h * 0.3, w * 1.25, h * 1.3], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    out = Image.composite(out, ImageChops.multiply(out, Image.new("RGB", (w, h), (120, 110, 100))), vignette)

    if any(k in words for k in ("sepia", "engraving", "woodcut", "noir", "monochrome")) or "black and white" in text:
        gray = ImageOps.grayscale(out)
        tint = (255, 236, 200) if "noir" not in words else (240, 240, 240)
        out = ImageOps.colorize(ImageOps.autocontrast(gray), black=(26, 20, 16), white=tint)
    return out


@register
class Sketchbook(ImageProvider):
    id = "sketchbook"
    name = "Sketchbook (offline)"
    description = (
        "Procedural gouache-style painter built into Booktures. Instant, deterministic, no model "
        "download. Reads the prompt for time of day, weather, landscape and characters."
    )
    local = True
    fields = [
        Field("scale", "Render scale", type="number", default=1.0, help="Multiply the output size (0.5–2)."),
    ]

    def check(self) -> str:
        return "Ready. Runs fully offline."

    def generate(self, request: ImageRequest) -> bytes:
        s = max(0.25, min(2.0, float(self.config.get("scale") or 1.0)))
        img = paint(request.prompt, int(request.width * s), int(request.height * s), request.seed)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
