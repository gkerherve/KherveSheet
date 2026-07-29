"""Persistence for the AI conversation, so it survives closing the app.

The backend already keeps a sliding window of the last ``_MAX_TURNS``
turns, so a long session degrades instead of hitting the provider's
context limit. What it had no answer for was quitting: the turns lived
only on the ``AiBridge``, so closing KherveSheet threw away the whole
conversation — including everything the assistant had worked out about
the workbook you were still in the middle of.

This writes that window to JSON under the user's app-data folder and
reads it back on start. Two deliberate limits:

* **Image payloads are not persisted.** A pasted screenshot is megabytes
  of base64; keeping it would bloat the profile folder for something the
  model rarely needs a second time. A note takes its place.
* **Tool turns are saved as they are, but never trusted on load.** The
  backend re-runs ``_trim_messages`` over whatever comes back, so a file
  truncated mid-exchange cannot produce a history the messages API will
  reject (an assistant turn whose tool calls have no results).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from PyQt5.QtCore import QStandardPaths

#: Left in place of a screenshot that was not written to disk.
IMAGE_NOTE = "[image not kept when the conversation was saved]"

#: Refuse to write more than this. Tool results can be large, and a
#: multi-megabyte file in the profile folder is a bug, not a feature.
MAX_BYTES = 4 * 1024 * 1024


def path() -> Path:
    """Where the conversation lives.

    GenericDataLocation plus an explicit app folder, not AppDataLocation:
    that one already folds in the application name, so it resolves
    somewhere different depending on whether QApplication has been named
    yet — and to the bare profile folder, shared with every sibling
    Kherve app, when it has not.
    """
    folder = QStandardPaths.writableLocation(
        QStandardPaths.GenericDataLocation)
    return Path(folder or ".") / "KherveSheet" / "ai_conversation.json"


def _without_images(turn: dict) -> dict:
    if not turn.get("images"):
        return turn
    stripped = dict(turn)
    stripped.pop("images", None)
    text = str(stripped.get("text") or "")
    stripped["text"] = f"{text}\n{IMAGE_NOTE}" if text else IMAGE_NOTE
    return stripped


def save(messages: List[dict]):
    """Write the conversation out, without image payloads."""
    turns = [_without_images(t) for t in (messages or [])
             if isinstance(t, dict) and t.get("role")]
    target = path()
    try:
        blob = json.dumps({"version": 1, "turns": turns})
    except (TypeError, ValueError):
        return              # something unserialisable: skip this save
    # Drop from the oldest end until it fits rather than writing a huge file.
    while len(blob) > MAX_BYTES and len(turns) > 1:
        turns = turns[1:]
        blob = json.dumps({"version": 1, "turns": turns})
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blob, encoding="utf-8")
    except (OSError, ValueError):
        pass                # a read-only profile must not break the chat


def load() -> List[dict]:
    """The saved turns, or []. The caller must still sanitise them —
    see the module note about tool turns."""
    try:
        doc = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    turns = doc.get("turns") if isinstance(doc, dict) else None
    if not isinstance(turns, list):
        return []
    return [t for t in turns
            if isinstance(t, dict)
            and t.get("role") in ("user", "assistant", "tool_results")]


def forget():
    """Drop the saved conversation (the Clear conversation button)."""
    try:
        path().unlink()
    except (OSError, ValueError):
        pass
