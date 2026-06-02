"""AI provider adapters — Anthropic, Mistral, and Ollama.

Each provider speaks a different wire format, so the conversation is
kept in a single *provider-neutral* history and converted on the fly.

Neutral history is a list of "turn" dicts:
  - {"role": "user", "text": str}
  - {"role": "assistant", "text": str, "tool_calls": [
        {"id": str, "name": str, "input": dict}, ...]}
  - {"role": "tool_results", "results": [
        {"id": str, "name": str, "content": str(json)}, ...]}

A provider's :meth:`run_turn` runs the full agentic loop: it calls the
model, streams text via *emit_text*, executes any requested tools via
the blocking *run_tool* callback, and appends both the assistant turn
and the tool-result turn back onto *history*.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple


# ── Provider catalogue (read by the settings dialog) ───────────────

PROVIDERS: Dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "needs_key": True,
        "needs_host": False,
        "models": [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-haiku-4-5-20251001",
        ],
        "default_model": "claude-sonnet-4-20250514",
    },
    "mistral": {
        "label": "Mistral AI",
        "needs_key": True,
        "needs_host": False,
        "models": [
            "mistral-large-latest",
            "mistral-small-latest",
            "open-mistral-nemo",
            "ministral-8b-latest",
        ],
        "default_model": "mistral-large-latest",
    },
    "ollama": {
        "label": "Ollama (local)",
        "needs_key": False,
        "needs_host": True,
        "models": [
            "llama3.1",
            "qwen2.5",
            "mistral-nemo",
            "firefunction-v2",
        ],
        "default_model": "llama3.1",
        "default_host": "http://localhost:11434",
    },
}

DEFAULT_HOST = "http://localhost:11434"

_MAX_TOKENS = 4096


# ── Format converters ──────────────────────────────────────────────

def _get(obj: Any, key: str, default=None):
    """Read *key* from a dict or attribute-style object (SDK responses)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _anthropic_tools(tools: List[dict]) -> List[dict]:
    # Already in Anthropic shape: name, description, input_schema.
    return tools


def _openai_tools(tools: List[dict]) -> List[dict]:
    """Convert neutral tool defs to OpenAI/Mistral/Ollama function shape."""
    out = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        })
    return out


def _anthropic_messages(history: List[dict]) -> List[dict]:
    msgs: List[dict] = []
    for turn in history:
        role = turn["role"]
        if role == "user":
            imgs = turn.get("images") or []
            if imgs:
                content = [{
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": im.get("media_type", "image/png"),
                        "data": im["data"],
                    },
                } for im in imgs]
                content.append({"type": "text",
                                "text": turn.get("text") or "."})
                msgs.append({"role": "user", "content": content})
            else:
                msgs.append({"role": "user", "content": turn["text"]})
        elif role == "assistant":
            content: List[dict] = []
            if turn.get("text"):
                content.append({"type": "text", "text": turn["text"]})
            for tc in turn.get("tool_calls") or []:
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["input"],
                })
            if not content:
                content.append({"type": "text", "text": "."})
            msgs.append({"role": "assistant", "content": content})
        elif role == "tool_results":
            content = [{
                "type": "tool_result",
                "tool_use_id": r["id"],
                "content": r["content"],
            } for r in turn["results"]]
            msgs.append({"role": "user", "content": content})
    return msgs


def _openai_messages(system: str, history: List[dict]) -> List[dict]:
    msgs: List[dict] = [{"role": "system", "content": system}]
    for turn in history:
        role = turn["role"]
        if role == "user":
            imgs = turn.get("images") or []
            if imgs:
                content = [{"type": "text", "text": turn.get("text") or ""}]
                for im in imgs:
                    mt = im.get("media_type", "image/png")
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mt};base64,{im['data']}",
                        },
                    })
                msgs.append({"role": "user", "content": content})
            else:
                msgs.append({"role": "user", "content": turn["text"]})
        elif role == "assistant":
            m: dict = {"role": "assistant",
                       "content": turn.get("text") or ""}
            tcs = turn.get("tool_calls") or []
            if tcs:
                m["tool_calls"] = [{
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["input"]),
                    },
                } for tc in tcs]
            msgs.append(m)
        elif role == "tool_results":
            for r in turn["results"]:
                msgs.append({
                    "role": "tool",
                    "tool_call_id": r["id"],
                    "name": r["name"],
                    "content": r["content"],
                })
    return msgs


def _ollama_messages(system: str, history: List[dict]) -> List[dict]:
    msgs: List[dict] = [{"role": "system", "content": system}]
    for turn in history:
        role = turn["role"]
        if role == "user":
            m = {"role": "user", "content": turn.get("text") or ""}
            imgs = turn.get("images") or []
            if imgs:
                m["images"] = [im["data"] for im in imgs]
            msgs.append(m)
        elif role == "assistant":
            m: dict = {"role": "assistant",
                       "content": turn.get("text") or ""}
            tcs = turn.get("tool_calls") or []
            if tcs:
                m["tool_calls"] = [{
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["input"],
                    },
                } for tc in tcs]
            msgs.append(m)
        elif role == "tool_results":
            for r in turn["results"]:
                msgs.append({
                    "role": "tool",
                    "tool_name": r["name"],
                    "content": r["content"],
                })
    return msgs


# ── Base provider ──────────────────────────────────────────────────

class _Provider:
    """Drives the agentic loop; subclasses supply API specifics."""

    name = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg            # api_key, model, host
        self._client = None

    def _make_client(self):
        raise NotImplementedError

    def _call(self, system: str, tools: List[dict],
              history: List[dict]) -> Tuple[str, List[dict]]:
        """Return (assistant_text, tool_calls)."""
        raise NotImplementedError

    def humanize(self, exc: Exception) -> str:
        return str(exc)

    def run_turn(self, system: str, tools: List[dict],
                 history: List[dict],
                 emit_text: Callable[[str], None],
                 run_tool: Callable[[str, dict], dict],
                 cancelled: Callable[[], bool]) -> None:
        if self._client is None:
            self._client = self._make_client()
        while not cancelled():
            text, tool_calls = self._call(system, tools, history)
            if text:
                emit_text(text)
            history.append({
                "role": "assistant",
                "text": text or "",
                "tool_calls": tool_calls,
            })
            if not tool_calls:
                break
            results = []
            for tc in tool_calls:
                if cancelled():
                    break
                out = run_tool(tc["name"], tc["input"])
                results.append({
                    "id": tc["id"],
                    "name": tc["name"],
                    "content": json.dumps(out),
                })
            history.append({"role": "tool_results", "results": results})


# ── Anthropic ──────────────────────────────────────────────────────

class AnthropicProvider(_Provider):
    name = "anthropic"

    def _make_client(self):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "The 'anthropic' package is not installed.\n"
                "Install it with:  pip install anthropic")
        self._sdk = anthropic
        return anthropic.Anthropic(api_key=self.cfg["api_key"])

    def _call(self, system, tools, history):
        resp = self._client.messages.create(
            model=self.cfg["model"],
            max_tokens=_MAX_TOKENS,
            system=system,
            tools=_anthropic_tools(tools),
            messages=_anthropic_messages(history),
        )
        text_parts: List[str] = []
        tool_calls: List[dict] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return "".join(text_parts), tool_calls

    def humanize(self, exc):
        sdk = getattr(self, "_sdk", None)
        if sdk is not None:
            if isinstance(exc, sdk.AuthenticationError):
                return "Invalid API key. Check it in AI Chat settings."
            if isinstance(exc, sdk.RateLimitError):
                return "Rate limit reached. Please wait and try again."
            if isinstance(exc, sdk.APIConnectionError):
                return "Cannot reach the Claude API. Check your connection."
        return str(exc)


# ── Mistral ────────────────────────────────────────────────────────

class MistralProvider(_Provider):
    name = "mistral"

    def _make_client(self):
        try:
            from mistralai import Mistral
        except ImportError:
            raise RuntimeError(
                "The 'mistralai' package is not installed.\n"
                "Install it with:  pip install mistralai")
        return Mistral(api_key=self.cfg["api_key"])

    def _call(self, system, tools, history):
        resp = self._client.chat.complete(
            model=self.cfg["model"],
            messages=_openai_messages(system, history),
            tools=_openai_tools(tools),
            tool_choice="auto",
            max_tokens=_MAX_TOKENS,
        )
        msg = resp.choices[0].message
        text = msg.content or ""
        if isinstance(text, list):  # some SDKs return content chunks
            text = "".join(
                _get(c, "text", "") for c in text if _get(c, "text"))
        tool_calls: List[dict] = []
        for i, tc in enumerate(getattr(msg, "tool_calls", None) or []):
            fn = tc.function
            args = fn.arguments
            if isinstance(args, str):
                args = json.loads(args or "{}")
            tool_calls.append({
                "id": getattr(tc, "id", None) or f"call_{i}",
                "name": fn.name,
                "input": args,
            })
        return text, tool_calls

    def humanize(self, exc):
        s = str(exc)
        if "401" in s or "Unauthorized" in s:
            return "Invalid Mistral API key. Check it in AI Chat settings."
        if "429" in s:
            return "Mistral rate limit reached. Please wait and try again."
        return s


# ── Ollama ─────────────────────────────────────────────────────────

class OllamaProvider(_Provider):
    name = "ollama"

    def _make_client(self):
        try:
            import ollama
        except ImportError:
            raise RuntimeError(
                "The 'ollama' package is not installed.\n"
                "Install it with:  pip install ollama")
        host = self.cfg.get("host") or DEFAULT_HOST
        return ollama.Client(host=host)

    def _call(self, system, tools, history):
        resp = self._client.chat(
            model=self.cfg["model"],
            messages=_ollama_messages(system, history),
            tools=_openai_tools(tools),
        )
        msg = _get(resp, "message", {})
        text = _get(msg, "content", "") or ""
        tool_calls: List[dict] = []
        raw_calls = _get(msg, "tool_calls", None) or []
        for i, tc in enumerate(raw_calls):
            fn = _get(tc, "function", {})
            name = _get(fn, "name", "")
            args = _get(fn, "arguments", {})
            if isinstance(args, str):
                args = json.loads(args or "{}")
            tool_calls.append({
                "id": f"call_{i}",
                "name": name,
                "input": args,
            })
        return text, tool_calls

    def humanize(self, exc):
        s = str(exc)
        if "Connection" in s or "refused" in s or "ConnectError" in s:
            return ("Cannot reach Ollama. Is it running?  "
                    "Start it with 'ollama serve'.")
        return s


# ── Factory ────────────────────────────────────────────────────────

_REGISTRY = {
    "anthropic": AnthropicProvider,
    "mistral": MistralProvider,
    "ollama": OllamaProvider,
}


def make_provider(name: str, cfg: dict) -> _Provider:
    """Instantiate a provider by name (defaults to Anthropic)."""
    cls = _REGISTRY.get(name, AnthropicProvider)
    return cls(cfg)
