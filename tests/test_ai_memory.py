"""The AI conversation must survive closing KherveSheet.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json

import pytest

from khervesheet import ai_memory

#: Captured before any test redirects it.
_REAL_PATH = ai_memory.path


@pytest.fixture(autouse=True)
def _own_store(tmp_path, monkeypatch):
    target = tmp_path / "ai_conversation.json"
    monkeypatch.setattr(ai_memory, "path", lambda: target)
    return target


def test_a_conversation_survives_a_restart(_own_store):
    turns = [{"role": "user", "text": "sum column B"},
             {"role": "assistant", "text": "done"}]
    ai_memory.save(turns)
    assert ai_memory.load() == turns


def test_tool_turns_are_kept(_own_store):
    """A turn's tool calls and their results must travel together, or the
    reloaded history is one the messages API rejects."""
    turns = [
        {"role": "user", "text": "chart it"},
        {"role": "assistant", "text": "",
         "tool_calls": [{"id": "t1", "name": "make_chart", "input": {}}]},
        {"role": "tool_results", "results": [{"id": "t1", "content": "ok"}]},
    ]
    ai_memory.save(turns)
    assert ai_memory.load() == turns


def test_image_payloads_are_not_written_to_disk(_own_store):
    ai_memory.save([{"role": "user", "text": "look",
                     "images": [{"media_type": "image/png",
                                 "data": "A" * 200_000}]}])
    assert "AAAA" not in _own_store.read_text(encoding="utf-8")
    assert ai_memory.IMAGE_NOTE in ai_memory.load()[0]["text"]


def test_a_huge_conversation_is_capped_not_dumped(_own_store):
    big = [{"role": "user", "text": "x" * 100_000} for _ in range(80)]
    ai_memory.save(big)
    assert _own_store.stat().st_size <= ai_memory.MAX_BYTES
    assert ai_memory.load()                       # but something survived


def test_no_saved_conversation_is_not_an_error(_own_store):
    assert ai_memory.load() == []


def test_a_corrupt_file_is_ignored(_own_store):
    _own_store.parent.mkdir(parents=True, exist_ok=True)
    _own_store.write_text("{ not json", encoding="utf-8")
    assert ai_memory.load() == []


def test_junk_turns_are_filtered_out(_own_store):
    _own_store.parent.mkdir(parents=True, exist_ok=True)
    _own_store.write_text(json.dumps({"version": 1, "turns": [
        {"role": "user", "text": "keep me"},
        {"role": "system", "text": "not a chat turn"},
        "a bare string",
    ]}), encoding="utf-8")
    assert ai_memory.load() == [{"role": "user", "text": "keep me"}]


def test_forget_clears_it(_own_store):
    ai_memory.save([{"role": "user", "text": "hello"}])
    ai_memory.forget()
    assert ai_memory.load() == []
    ai_memory.forget()                            # already gone: still fine


def test_an_unwritable_profile_does_not_break_the_chat(monkeypatch):
    import pathlib
    monkeypatch.setattr(ai_memory, "path",
                        lambda: pathlib.Path("\0bad/x.json"))
    ai_memory.save([{"role": "user", "text": "hi"}])   # must not raise
    assert ai_memory.load() == []


def test_the_store_is_app_specific_and_name_independent():
    """AppDataLocation folds in the application name, so it moves about
    depending on whether QApplication has been named — and collides with
    the sibling Kherve apps when it has not."""
    where = _REAL_PATH()
    assert where.parent.name == "KherveSheet"
    assert where.name == "ai_conversation.json"


def test_a_history_truncated_mid_exchange_is_made_safe_on_load():
    """Saved files are never trusted: the backend re-trims whatever comes
    back, so an assistant turn whose tool results were cut off cannot
    reach the API."""
    from khervesheet.ai_backend import _trim_messages

    dangling = [
        {"role": "user", "text": "chart it"},
        {"role": "assistant", "text": "",
         "tool_calls": [{"id": "t1", "name": "make_chart", "input": {}}]},
    ]
    safe = _trim_messages(dangling)
    assert all(not t.get("tool_calls") for t in safe)
