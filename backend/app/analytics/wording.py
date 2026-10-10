"""Wording constraint (ARCHITECTURE.md §6.4).

No user-facing text may diagnose a malfunction or imply cause. Unit-tested on
``config/actions.json`` and on every generated issue string.
"""

from __future__ import annotations

import re

BANNED_WORDS = re.compile(r"\b(fault\w*|broken|wast\w*|caus\w*)\b", re.IGNORECASE)


def find_banned(text: str) -> list[str]:
    return BANNED_WORDS.findall(text or "")


def assert_clean(text: str) -> str:
    found = find_banned(text)
    if found:
        raise ValueError(f"banned wording {found!r} in: {text!r}")
    return text
