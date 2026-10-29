"""Content screening for image prompts.

"standard" mode screens prompts with a keyword list and, if the story model
offers moderation (OpenAI does), asks it too. Flagged pages get a neutral
placeholder scene instead of the original prompt. "off" skips all checks.
"""

from __future__ import annotations

import re

from booktures.plugins import TextProvider

SAFE_PLACEHOLDER = "a closed antique book resting on a wooden desk beside a candle, soft warm light"

_BLOCKLIST = [
    r"nud(e|ity)", r"naked", r"topless", r"sex(ual|ually)?", r"porn\w*", r"genital\w*", r"erotic\w*",
    r"gore", r"gory", r"dismember\w*", r"decapitat\w*", r"disembowel\w*", r"mutilat\w*",
    r"entrails", r"torture[sd]?", r"rape[sd]?", r"suicide", r"self[- ]harm",
]
_BLOCK_RE = re.compile(r"\b(" + "|".join(_BLOCKLIST) + r")\b", re.I)


def keyword_flagged(text: str) -> bool:
    return bool(_BLOCK_RE.search(text or ""))


def is_safe(prompt: str, mode: str, provider: TextProvider | None = None) -> bool:
    if mode == "off":
        return True
    if keyword_flagged(prompt):
        return False
    if provider is not None:
        try:
            verdict = provider.moderate(prompt)
        except Exception:  # noqa: BLE001 - fall back to the keyword screen
            verdict = None
        if verdict is False:
            return False
    return True
