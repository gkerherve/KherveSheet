"""AI provider adapters — Anthropic, OpenAI, Mistral, and Ollama.

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
        "module": "anthropic",
        "pip": "anthropic",
        "needs_key": True,
        "needs_host": False,
        "refreshable": True,
        "models": [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-haiku-4-5-20251001",
        ],
        "default_model": "claude-sonnet-4-20250514",
    },
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "module": "openai",
        "pip": "openai",
        "needs_key": True,
        "needs_host": False,
        "refreshable": True,
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "o3-mini",
        ],
        "default_model": "gpt-4o",
    },
    "mistral": {
        "label": "Mistral AI",
        "module": "mistralai",
        "pip": "mistralai",
        "needs_key": True,
        "needs_host": False,
        "refreshable": True,
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
        "module": "ollama",
        "pip": "ollama",
        "needs_key": False,
        "needs_host": True,
        "refreshable": True,
        "models": [
            "llama3.1",
            "qwen2.5",
            "mistral-nemo",
            "firefunction-v2",
        ],
        "default_model": "llama3.1",
        "default_host": "http://localhost:11434",
    },
    "local": {
        "label": "Local AI (OpenAI-compatible)",
        "module": "openai",
        "pip": "openai",
        "needs_key": False,
        "needs_host": True,
        "refreshable": True,
        "models": [
            "default",
        ],
        "default_model": "default",
        "default_host": "http://localhost:1234/v1",
    },
}

DEFAULT_HOST = "http://localhost:11434"

_MAX_TOKENS = 16384


def is_available(provider_name: str) -> bool:
    """True if the provider's Python SDK is importable in this env."""
    import importlib.util
    spec = PROVIDERS.get(provider_name)
    if not spec:
        return False
    try:
        return importlib.util.find_spec(spec["module"]) is not None
    except (ImportError, ValueError):
        return False


def fetch_models(provider_name: str, api_key: str = "",
                 host: str = "") -> List[str]:
    """Query the provider for its available models.

    Returns a list of model-id strings, or raises on failure.
    Only meaningful for providers with ``refreshable: True``.
    """
    if provider_name == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.models.list(limit=100)
        names = []
        items = resp.data if hasattr(resp, "data") else []
        for m in items:
            mid = m.id if hasattr(m, "id") else (
                m.get("id", "") if isinstance(m, dict) else "")
            if mid:
                names.append(mid)
        return sorted(names) or PROVIDERS["anthropic"]["models"]

    if provider_name == "openai":
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.models.list()
        names = []
        for m in resp.data:
            mid = m.id if hasattr(m, "id") else (
                m.get("id", "") if isinstance(m, dict) else "")
            # Filter to chat-capable models (gpt-*, o1-*, o3-*, chatgpt-*)
            if mid and any(mid.startswith(p) for p in
                          ("gpt-", "o1-", "o3-", "o4-", "chatgpt-")):
                names.append(mid)
        return sorted(names) or PROVIDERS["openai"]["models"]

    if provider_name == "ollama":
        import ollama
        client = ollama.Client(host=host or DEFAULT_HOST)
        resp = client.list()
        models = resp.get("models", []) if isinstance(resp, dict) else []
        if not models and hasattr(resp, "models"):
            models = resp.models or []
        names = []
        for m in models:
            name = m.get("name", "") if isinstance(m, dict) else getattr(m, "name", "")
            if name:
                names.append(name.split(":")[0] if ":" in name else name)
        return sorted(set(names)) or ["llama3.1"]

    if provider_name == "mistral":
        from mistralai import Mistral
        client = Mistral(api_key=api_key)
        resp = client.models.list()
        models = resp.data if hasattr(resp, "data") else []
        names = []
        for m in models:
            mid = m.id if hasattr(m, "id") else (m.get("id", "") if isinstance(m, dict) else "")
            if mid:
                names.append(mid)
        return sorted(names) or ["mistral-large-latest"]

    if provider_name == "local":
        import openai
        base = host or PROVIDERS["local"]["default_host"]
        client = openai.OpenAI(api_key="not-needed", base_url=base)
        resp = client.models.list()
        names = []
        for m in resp.data:
            mid = m.id if hasattr(m, "id") else (
                m.get("id", "") if isinstance(m, dict) else "")
            if mid:
                names.append(mid)
        return sorted(names) or ["default"]

    return PROVIDERS.get(provider_name, {}).get("models", [])


# ── Format converters ──────────────────────────────────────────────

def _get(obj: Any, key: str, default=None):
    """Read *key* from a dict or attribute-style object (SDK responses)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_CACHE_CONTROL = {"type": "ephemeral"}


def _anthropic_tools(tools: List[dict]) -> List[dict]:
    # Already in Anthropic shape: name, description, input_schema.
    # Mark the LAST tool with cache_control so the whole (static) tool
    # block is cached and not re-read on every agentic round-trip.
    if not tools:
        return tools
    out = list(tools)
    last = dict(out[-1])
    last["cache_control"] = _CACHE_CONTROL
    out[-1] = last
    return out


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


def _add_rolling_cache(msgs: List[dict]) -> None:
    """Mark the last content block as cacheable (in place).

    This adds a rolling cache breakpoint at the tail of the growing
    conversation so each subsequent agentic round-trip only re-reads
    the few new blocks, not the entire history.
    """
    if not msgs:
        return
    last = msgs[-1]
    content = last.get("content")
    if isinstance(content, str):
        last["content"] = [{
            "type": "text",
            "text": content or ".",
            "cache_control": _CACHE_CONTROL,
        }]
    elif isinstance(content, list) and content:
        block = dict(content[-1])
        block["cache_control"] = _CACHE_CONTROL
        content[-1] = block


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
            stop = False
            for tc in tool_calls:
                if cancelled():
                    stop = True
                    # Provide a dummy result for every remaining call so
                    # the history stays valid for the Anthropic API.
                    results.append({
                        "id": tc["id"],
                        "name": tc["name"],
                        "content": json.dumps({"error": "cancelled"}),
                    })
                    continue
                out = run_tool(tc["name"], tc["input"])
                results.append({
                    "id": tc["id"],
                    "name": tc["name"],
                    "content": json.dumps(out),
                })
            history.append({"role": "tool_results", "results": results})
            if stop:
                break


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
        # Cache the static system prompt + tools and add a rolling
        # breakpoint on the conversation tail so each agentic round-trip
        # re-reads only the new blocks, not the whole prefix.  This is
        # the difference between a snappy build and a multi-minute stall.
        msgs = _anthropic_messages(history)
        _add_rolling_cache(msgs)
        resp = self._client.messages.create(
            model=self.cfg["model"],
            max_tokens=_MAX_TOKENS,
            system=[{
                "type": "text",
                "text": system,
                "cache_control": _CACHE_CONTROL,
            }],
            tools=_anthropic_tools(tools),
            messages=msgs,
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


# ── OpenAI ─────────────────────────────────────────────────────────

class OpenAIProvider(_Provider):
    name = "openai"

    def _make_client(self):
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "The 'openai' package is not installed.\n"
                "Install it with:  pip install openai")
        self._sdk = openai
        return openai.OpenAI(api_key=self.cfg["api_key"])

    def _call(self, system, tools, history):
        resp = self._client.chat.completions.create(
            model=self.cfg["model"],
            messages=_openai_messages(system, history),
            tools=_openai_tools(tools) or None,
            max_tokens=_MAX_TOKENS,
        )
        msg = resp.choices[0].message
        text = msg.content or ""
        tool_calls: List[dict] = []
        for i, tc in enumerate(msg.tool_calls or []):
            fn = tc.function
            args = fn.arguments
            if isinstance(args, str):
                args = json.loads(args or "{}")
            tool_calls.append({
                "id": tc.id or f"call_{i}",
                "name": fn.name,
                "input": args,
            })
        return text, tool_calls

    def humanize(self, exc):
        sdk = getattr(self, "_sdk", None)
        if sdk is not None:
            if isinstance(exc, sdk.AuthenticationError):
                return "Invalid OpenAI API key. Check it in AI Chat settings."
            if isinstance(exc, sdk.RateLimitError):
                return "OpenAI rate limit reached. Please wait and try again."
            if isinstance(exc, sdk.APIConnectionError):
                return "Cannot reach the OpenAI API. Check your connection."
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


# ── Local (OpenAI-compatible) ──────────────────────────────────────

class LocalProvider(_Provider):
    """Any local server that exposes an OpenAI-compatible /v1 API.

    Works with LM Studio, llama.cpp server, Ollama (OpenAI mode),
    text-generation-webui, LocalAI, and similar tools.
    """
    name = "local"

    def _make_client(self):
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "The 'openai' package is not installed.\n"
                "Install it with:  pip install openai")
        self._sdk = openai
        base = self.cfg.get("host") or PROVIDERS["local"]["default_host"]
        return openai.OpenAI(
            api_key=self.cfg.get("api_key") or "not-needed",
            base_url=base)

    def _call(self, system, tools, history):
        kw = dict(
            model=self.cfg["model"],
            messages=_openai_messages(system, history),
            max_tokens=_MAX_TOKENS,
        )
        # Only pass tools if the server advertises tool support;
        # many local models don't, so avoid crashing.
        oai_tools = _openai_tools(tools)
        if oai_tools:
            kw["tools"] = oai_tools
        resp = self._client.chat.completions.create(**kw)
        msg = resp.choices[0].message
        text = msg.content or ""
        tool_calls: List[dict] = []
        for i, tc in enumerate(msg.tool_calls or []):
            fn = tc.function
            args = fn.arguments
            if isinstance(args, str):
                args = json.loads(args or "{}")
            tool_calls.append({
                "id": tc.id or f"call_{i}",
                "name": fn.name,
                "input": args,
            })
        return text, tool_calls

    def humanize(self, exc):
        s = str(exc)
        if "Connection" in s or "refused" in s or "ConnectError" in s:
            host = self.cfg.get("host") or PROVIDERS["local"]["default_host"]
            return (f"Cannot reach local AI server at {host}.\n"
                    "Make sure your local server is running.")
        return s


# ── Factory ────────────────────────────────────────────────────────

_REGISTRY = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "mistral": MistralProvider,
    "ollama": OllamaProvider,
    "local": LocalProvider,
}


def make_provider(name: str, cfg: dict) -> _Provider:
    """Instantiate a provider by name (defaults to Anthropic)."""
    cls = _REGISTRY.get(name, AnthropicProvider)
    return cls(cfg)
