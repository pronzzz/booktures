"""Small text helpers shared by the pipeline and the offline story model."""

from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = set(
    """a about above after again against all am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from further had
    has have having he her here hers herself him himself his how i if in into is it its itself just
    me more most my myself no nor not now of off on once only or other our ours ourselves out over
    own same she should so some such than that the their theirs them themselves then there these
    they this those through to too under until up very was we were what when where which while who
    whom why will with would you your yours yourself yourselves said says say one two also back
    like still even much well way upon""".split()
)

_WORD = re.compile(r"[a-zA-Z][a-zA-Z'\-]+")


def tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "") if w.lower() not in STOPWORDS]


def similarity(a: str, b: str) -> float:
    """Cosine similarity of word counts (0..1). Cheap enough to run on every page."""
    ca, cb = Counter(tokens(a)), Counter(tokens(b))
    if not ca or not cb:
        return 0.0
    dot = sum(ca[w] * cb[w] for w in ca.keys() & cb.keys())
    norm = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return dot / norm if norm else 0.0


_SENTENCE = re.compile(r"(?<=[.!?…])[\"'”’)]*\s+(?=[\"'“‘(]*[A-Z0-9])")


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def strip_dialogue(text: str) -> str:
    """Remove quoted speech so only narration is left."""
    text = re.sub(r"[“\"][^”\"]{0,400}[”\"]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    return " ".join(words[:limit]).rstrip(",;:") + "…"
