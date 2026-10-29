"""Offline story model: rule-based text analysis, no network and no model weights.

It is the default so Booktures works the moment it is installed. It finds
recurring character names, pulls appearance phrases from nearby sentences,
guesses the genre from vocabulary and picks the most visual sentence on each
page. Results are rougher than a real LLM, but continuity still holds because
the pipeline injects the character bible into every prompt.
"""

from __future__ import annotations

import re
from collections import Counter

from booktures.pipeline.text_utils import sentences, strip_dialogue, truncate_words
from booktures.plugins import SceneContext, TextProvider, register

COMMON_CAPS = set(
    """The A An He She It They I We You His Her Hers Their Its Our My Your But And Or Then When What
    Where Why How Who Which While This That These Those There Here In On At As If So For Of To With
    After Before Into From By Not No Yes Oh Ah Well Now Just Once Still Even All Some Every Each One
    Two Three Chapter Part Book Mr Mrs Ms Miss Dr Sir Lady Lord Saint St Monday Tuesday Wednesday
    Thursday Friday Saturday Sunday January February March April May June July August September
    October November December God Heaven Hell Christmas English French German American Spanish
    Italian Russian Chinese Japanese Indian Perhaps Maybe Nothing Something Everything Anyone Someone
    Nobody Everyone Good Thank Thanks Please Hello Goodbye Come Look Let Do Don Did Was Were Is Are
    Had Have Has Will Would Could Should Can May Might Must Yet Though Although Because Since Until
    Unless Whether Over Under Above Below Behind Beyond Across Through Around Again Never Always
    Sometimes Soon Later Today Tomorrow Yesterday Tonight Morning Evening Night Day Above End""".split()
)

SPEECH_VERBS = (
    "said|asked|replied|whispered|shouted|cried|answered|called|murmured|laughed|smiled|nodded|"
    "frowned|sighed|walked|ran|stood|sat|looked|turned|took|held|opened|closed|watched|knew|felt|"
    "thought|wanted|went|came|pulled|pushed|climbed|reached|grabbed|stepped|wore|had|was"
)
TITLES = r"(?:Mr|Mrs|Ms|Miss|Dr|Captain|Professor|Sir|Lady|Lord|Uncle|Aunt|King|Queen|Prince|Princess|Father|Mother|Sister|Brother|Detective|Inspector|Old)\.?"

APPEARANCE = (
    "hair|eyes|beard|moustache|mustache|coat|cloak|dress|gown|scarf|hat|cap|boots|shoes|jacket|"
    "shirt|skirt|robe|apron|uniform|armor|armour|glasses|spectacles|freckles|scar|skin|braid|"
    "braids|curls|ponytail|tattoo|necklace|ring|gloves|shawl|sweater|vest|trousers|jeans|hood|"
    "cane|staff|sword|satchel|earring|lenses|goggles|bowler|briefcase|suit|peacoat|overalls"
)
APPEARANCE_RE = re.compile(
    rf"\b((?:[a-z\-]+\s){{0,3}}(?:{APPEARANCE}))\b", re.I
)
BODY_RE = re.compile(
    r"\b(?:a|an)\s((?:(?:tall|short|old|young|elderly|little|small|thin|slender|broad|stout|"
    r"stooped|wiry|plump|lanky|gaunt|grey-haired|gray-haired|white-haired|red-haired|dark-haired|"
    r"fair-haired|bearded|freckled|pale|weathered|sturdy|frail|graceful|round|gangly|heavyset|lean|"
    r"slim|skinny|burly|stocky|petite|bony|hulking|nervous|portly)(?:,\s*|\s)){1,3}"
    r"(?:man|woman|girl|boy|child|lady|gentleman|figure|stranger|soldier|sailor|knight|witch|wizard))\b",
    re.I,
)
ARTICLE_RE = re.compile(r"^(?:a|an|the|his|her|their|its|my|your|our|some|this|that)\s", re.I)

GENRES: dict[str, tuple[list[str], str]] = {
    "fantasy": (
        "dragon dragons sword magic wizard witch spell castle kingdom elf elves dwarf quest enchanted "
        "sorcerer throne realm prophecy rune knight potion clockwork fairy fairies troll gnome spirits "
        "magical cursed".split(),
        "luminous fantasy illustration, painterly, epic golden light, rich jewel tones",
    ),
    "science fiction": (
        "ship starship planet galaxy robot android laser station orbit neon cyber hologram engine "
        "spacecraft alien colony reactor drone console".split(),
        "retro-futuristic science fiction illustration, glowing neon accents, atmospheric haze",
    ),
    "mystery": (
        "detective murder clue inspector police alibi suspect crime corpse evidence revolver "
        "cigarette rain alley case".split(),
        "moody noir illustration, deep shadows, rain-slicked streets, muted teal and amber",
    ),
    "horror": (
        "blood scream shadow shadows dread ghost corpse grave crypt fear darkness creature "
        "whisper cellar candle haunted".split(),
        "dark gothic illustration, desaturated palette, eerie fog, candlelit shadows",
    ),
    "romance": (
        "kiss love heart wedding dance ball letter blush embrace gown rose garden".split(),
        "soft romantic impressionist painting, warm pastel light, gentle brushwork",
    ),
    "sea adventure": (
        "sea ocean waves ship sail sails harbor harbour lighthouse captain island storm deck "
        "tide shore gulls boat".split(),
        "adventure novel illustration, gouache, sweeping seascapes, golden-hour light",
    ),
}
DEFAULT_STYLE = "literary watercolor illustration, soft natural light, textured paper"

PLACE_WORDS = (
    "city town village street road station house cottage room kitchen library hall forest woods "
    "garden field meadow river lake sea ocean shore beach harbor harbour lighthouse cliff mountain "
    "hill valley castle tower church market square bridge ship deck cabin cave desert island "
    "bar cafe diner office school train platform attic cellar"
).split()

VISUAL_WORDS = set(
    (
        "light dark shadow shadows sun moon stars sky cloud clouds rain snow fog mist wind storm fire "
        "lamp lantern candle window door table chair bed wall floor stairs road path tree trees "
        "flowers grass water waves boat river hill hills mountain mountains field street city tower "
        "glow glowing gold golden silver red blue green white black grey gray amber bright dim "
        "stood walked ran climbed sat looked held carried opened lifted knelt danced fell rode "
        "smoke ash dust stone glass iron wood sand ice beads curtain station rails train bar"
    ).split()
    + PLACE_WORDS
)


def _pronoun_gender(text: str, name: str) -> str:
    he = she = 0
    for m in re.finditer(rf"\b{re.escape(name)}\b", text):
        window = text[m.end() : m.end() + 160].lower()
        he += len(re.findall(r"\b(he|him|his)\b", window))
        she += len(re.findall(r"\b(she|her|hers)\b", window))
    if she > he * 1.3:
        return "woman"
    if he > she * 1.3:
        return "man"
    return ""


PLACE_SUFFIXES = set(
    """Point Street Road Lane Avenue Bay Island Isle Hill Hills Castle House Hall Manor Lake River Sea
    Ocean Bridge Station Park Square Town City Valley Forest Wood Woods Mountain Mountains Cove Harbor
    Harbour Inn Tower Church Abbey Court Gate Gardens Garden Moor Fen Falls Creek Port Haven Downs""".split()
)


def find_characters(text: str, limit: int = 6) -> dict[str, str]:
    total: Counter[str] = Counter()
    mid_counts: Counter[str] = Counter()
    person_signal: Counter[str] = Counter()
    place_signal: Counter[str] = Counter()

    for sent in sentences(text):
        for m in re.finditer(r"\b([A-Z][a-z]{1,15}(?:\s[A-Z][a-z]{1,15})?)\b", sent):
            name = m.group(1)
            words = name.split()
            if words[0] in COMMON_CAPS:
                # "Then Alice" -> keep the second word if present.
                if len(words) < 2 or words[1] in COMMON_CAPS:
                    continue
                name = words[1]
            elif len(words) == 2 and words[1] in COMMON_CAPS:
                name = words[0]
            if name.split()[-1] in PLACE_SUFFIXES:
                continue
            total[name] += 1
            if m.start() > 0:
                mid_counts[name] += 1
            after = sent[m.end() : m.end() + 24]
            before = sent[max(0, m.start() - 14) : m.start()]
            if re.match(rf"\s+(?:{SPEECH_VERBS})\b", after) or re.search(r"[,”\"]\s*$", before):
                person_signal[name] += 1
            if re.search(rf"\b{TITLES}\s*$", before) or re.match(r"\s+and\s+[A-Z]", after):
                person_signal[name] += 2
            if re.search(r"\b(?:in|at|to|from|near|across|of|into|toward|towards|past)\s+(?:the\s+)?$", before, re.I):
                place_signal[name] += 1

    candidates = []
    for name, n in total.items():
        if n < 2 or name in COMMON_CAPS:
            continue
        # Skip words that are normally lowercase (sentence-initial nouns like "Rain").
        if len(re.findall(rf"\b{re.escape(name.lower())}\b", text)) >= n:
            continue
        if place_signal[name] > person_signal[name]:
            continue
        if person_signal[name] == 0 and mid_counts[name] < 2:
            continue
        candidates.append((person_signal[name] * 2 + n, name))
    candidates.sort(reverse=True)

    bible: dict[str, str] = {}
    sents = sentences(text)
    for _, name in candidates:
        # Merge "Alice Smith" and "Alice".
        if any(name in other.split() or other in name.split() for other in bible):
            continue
        others = {n.lower() for _, n in candidates if n != name}
        bible[name] = describe_character(name, sents, text, others)
        if len(bible) >= limit:
            break
    return bible


LEAD_JUNK = set(
    """he she they it wore wears wearing had has have with and in a an the his her their its that which
    was were is are reached of on up to who whose always forgot pushed long carried held bought wrapped""".split()
)


# Words that end one idea and start another ("lenses that clicked down over her eyes").
BREAK_WORDS = set("her his their its the a an of over under with into onto on in to at by from and or that which".split())


def _clean_phrase(phrase: str) -> str:
    words = phrase.lower().strip(" ,.").split()
    # Keep only what follows the last break word, so we get "silver hair", not "woman with silver hair".
    for i in range(len(words) - 2, -1, -1):
        if words[i] in BREAK_WORDS:
            words = words[i + 1 :]
            break
    while words and words[0] in LEAD_JUNK:
        words.pop(0)
    return " ".join(words)


# Features that read fine on their own ("a face full of freckles" -> "freckles").
SOLO_FEATURES = {"freckles", "beard", "moustache", "mustache", "spectacles", "glasses", "tattoo", "scar", "braids", "curls"}


def describe_character(name: str, sents: list[str], text: str, others: set[str] | None = None) -> str:
    others = others or set()
    phrases: list[str] = []
    nearby = []
    for i, s in enumerate(sents):
        if re.search(rf"\b{re.escape(name)}\b", s):
            nearby.append(s)
            # The next sentence usually continues the description when it starts with a pronoun.
            if i + 1 < len(sents) and re.match(r"(?:He|She|His|Her|They|Their)\b", sents[i + 1]):
                nearby.append(sents[i + 1])
    for s in nearby[:40]:
        # Stop reading at the next character's name, so "Mara found Tobias, his white beard..."
        # doesn't give Mara a beard.
        own = s.find(name)
        cuts = [m.start() for o in others for m in re.finditer(rf"\b{re.escape(o)}\b", s, re.I) if m.start() > own]
        if cuts:
            s = s[: min(cuts)]
        for m in BODY_RE.finditer(s):
            phrases.append(re.sub(r"\s+", " ", m.group(1).lower()))
        for m in APPEARANCE_RE.finditer(s):
            phrase = _clean_phrase(m.group(1))
            if any(w in others for w in phrase.split()):
                continue
            if len(phrase.split()) >= 2 or phrase in SOLO_FEATURES:
                phrases.append(phrase)
    seen, unique = set(), []
    for p in phrases:
        key = p.split()[-1]
        if key not in seen:
            seen.add(key)
            unique.append(p)
    gender = _pronoun_gender(text, name)
    base = f"a {gender}" if gender else "a figure"
    if unique:
        nouns = {"man", "woman", "girl", "boy", "child", "lady", "gentleman"}
        has_body = any(p.split()[-1] in nouns for p in unique)
        lead = [] if has_body else [base]
        return ", ".join(lead + unique[:4])
    return f"{base} in simple period clothing"


def detect_genre(text: str) -> tuple[str, str]:
    words = Counter(re.findall(r"[a-z]+", text.lower()))
    scores = {g: sum(words[w] for w in vocab) for g, (vocab, _) in GENRES.items()}
    best = max(scores, key=scores.get)
    if scores[best] < 3:
        return "literary fiction", DEFAULT_STYLE
    return best, GENRES[best][1]


def detect_setting(text: str) -> str:
    words = Counter(re.findall(r"[a-z]+", text.lower()))
    places = [w for w, _ in Counter({w: words[w] for w in PLACE_WORDS if words[w]}).most_common(3)]
    return ", ".join(places)


def pick_visual_sentence(text: str, names: list[str]) -> tuple[str, list[str]]:
    narration = strip_dialogue(text)
    sents = sentences(narration) or sentences(text)
    best, best_score = "", -1.0
    for idx, s in enumerate(sents):
        words = re.findall(r"[a-z]+", s.lower())
        if len(words) < 5:
            continue
        score = sum(1 for w in words if w in VISUAL_WORDS)
        score += 1.5 * sum(1 for n in names if n in s)
        if len(words) < 9:
            score -= 2
        score -= 0.02 * max(0, len(words) - 35)  # prefer compact sentences
        score -= 0.01 * idx  # mild preference for the start of the page
        if score > best_score:
            best, best_score = s, score
    present = [n for n in names if re.search(rf"\b{re.escape(n)}\b", text)]
    return best or (sents[0] if sents else text[:200]), present


@register
class OfflineStoryModel(TextProvider):
    id = "offline"
    name = "Offline analyzer"
    description = (
        "Rule-based analysis that runs instantly with no model and no network. "
        "Good for trying Booktures out; plug in a real LLM for richer prompts."
    )
    local = True
    fields = []

    def check(self) -> str:
        return "Ready. Runs fully offline."

    def complete_json(self, system: str, user: str) -> dict:
        return {}

    def analyze_book(self, excerpt: str) -> dict:
        genre, style = detect_genre(excerpt)
        return {
            "title": "",
            "author": "",
            "genre": genre,
            "setting": detect_setting(excerpt),
            "global_art_style": style,
            "character_bible": find_characters(excerpt),
        }

    def describe_scene(self, page_text: str, ctx: SceneContext) -> dict:
        names = list(ctx.character_bible)
        sentence, present = pick_visual_sentence(page_text, names)
        visual = truncate_words(sentence, 45)
        lowered = visual.lower()
        if ctx.setting and not any(w in lowered for w in PLACE_WORDS):
            visual = f"{visual.rstrip('.…')}, near the {ctx.setting.split(', ')[0]}"
        return {
            "scene_summary": truncate_words(sentence, 28),
            "visual_description": visual,
            "characters": present[:3],
            "new_characters": {},
            "mood": "",
        }

