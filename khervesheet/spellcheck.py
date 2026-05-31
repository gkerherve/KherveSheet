"""Live English spell-checking helpers.

Wraps ``pyspellchecker`` behind a cached singleton so the cell delegate
can ask "is this word misspelled?" cheaply on every repaint, and the
context menu can fetch correction suggestions.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
from typing import Iterator, List, Optional, Tuple

# Words are runs of letters, optionally joined by an apostrophe
# (don't, it's).  Digits break a word so "abc123" is not flagged.
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")

_checker = None
_checker_tried = False
# Per-word memo: word_lower -> True if misspelled.  Bounded so a huge
# sheet can't grow it without limit.
_miss_cache: dict = {}
_CACHE_MAX = 20000
# Words the user chose to ignore for this session.
_ignored: set = set()


def get_checker():
    """Return the shared SpellChecker, or None if the lib is missing."""
    global _checker, _checker_tried
    if _checker is None and not _checker_tried:
        _checker_tried = True
        try:
            from spellchecker import SpellChecker
            _checker = SpellChecker()
        except Exception:
            _checker = None
    return _checker


def available() -> bool:
    return get_checker() is not None


def ignore_word(word: str) -> None:
    """Stop flagging *word* for the rest of the session."""
    _ignored.add(word.lower())
    _miss_cache[word.lower()] = False


def is_misspelled(word: str) -> bool:
    """True when *word* is unknown to the dictionary.  Cached."""
    if len(word) < 2:
        return False
    key = word.lower()
    if key in _ignored:
        return False
    cached = _miss_cache.get(key)
    if cached is not None:
        return cached
    checker = get_checker()
    if checker is None:
        return False
    # A token is fine if any case-form is known (proper nouns, I'm).
    result = bool(checker.unknown([key]))
    if len(_miss_cache) < _CACHE_MAX:
        _miss_cache[key] = result
    return result


def suggestions(word: str, limit: int = 8) -> List[str]:
    """Return up to *limit* correction candidates for *word*."""
    checker = get_checker()
    if checker is None:
        return []
    cands = checker.candidates(word)
    if not cands:
        return []
    # Put the single most likely correction first.
    best = checker.correction(word)
    ordered = [best] + [c for c in cands if c != best] if best else list(cands)
    return ordered[:limit]


def should_check(text: Optional[str]) -> bool:
    """Skip formulas, blanks and purely numeric cells."""
    if not text:
        return False
    if text.startswith("="):
        return False
    try:
        float(text)
        return False
    except (ValueError, TypeError):
        return True


def iter_word_spans(text: str, fm, x_left: int, width: int,
                    align: int) -> Iterator[Tuple[int, int, str, int, int]]:
    """Yield (char_start, char_end, word, x0, x1) for each word.

    *fm* is a QFontMetrics; geometry is laid out for a single line so
    underlines and hit-testing agree.  Horizontal *align* is honoured
    (left / centre / right) relative to ``x_left`` and ``width``.
    """
    from PyQt5.QtCore import Qt
    advance = fm.horizontalAdvance
    total = advance(text)
    if align & Qt.AlignHCenter:
        base = x_left + (width - total) / 2
    elif align & Qt.AlignRight:
        base = x_left + width - total
    else:
        base = x_left
    for m in WORD_RE.finditer(text):
        s, e = m.start(), m.end()
        x0 = base + advance(text[:s])
        x1 = base + advance(text[:e])
        yield s, e, m.group(0), int(x0), int(x1)
