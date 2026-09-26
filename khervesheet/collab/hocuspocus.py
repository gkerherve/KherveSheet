"""The Hocuspocus protocol, as spoken by KherveDOC's collaboration server.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

A Hocuspocus message is a Yjs (y-websocket) message with the document's
name in front::

    varString(document) · varUint(type) · payload

so pycrdt's sync and awareness messages travel unchanged inside.  Before
anything else the client sends an authentication message; the server
answers "authenticated" (saying whether the user may edit) or "permission
denied".  KherveDOC checks the user from the session cookie sent with the
WebSocket request, so the token itself is empty.
"""

from __future__ import annotations

from typing import Tuple

SYNC = 0
AWARENESS = 1
AUTH = 2
QUERY_AWARENESS = 3
SYNC_REPLY = 4
STATELESS = 5
BROADCAST_STATELESS = 6
CLOSE = 7
SYNC_STATUS = 8

AUTH_TOKEN = 0
AUTH_DENIED = 1
AUTH_OK = 2


def write_var_uint(n: int) -> bytes:
    out = bytearray()
    while n > 0x7F:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    out.append(n)
    return bytes(out)


def read_var_uint(data: bytes, pos: int) -> Tuple[int, int]:
    n = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        n |= (byte & 0x7F) << shift
        if byte < 0x80:
            return n, pos
        shift += 7


def write_var_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return write_var_uint(len(raw)) + raw


def read_var_string(data: bytes, pos: int) -> Tuple[str, int]:
    length, pos = read_var_uint(data, pos)
    return data[pos:pos + length].decode("utf-8"), pos + length


def frame(document: str, message: bytes) -> bytes:
    """A y-websocket *message* (type byte first) for *document*."""
    return write_var_string(document) + message


def auth_message(document: str, token: str = "") -> bytes:
    return frame(document, write_var_uint(AUTH) + write_var_uint(AUTH_TOKEN)
                 + write_var_string(token))


def parse(data: bytes) -> Tuple[str, int, bytes]:
    """(document, message type, the rest) of an incoming message."""
    document, pos = read_var_string(data, 0)
    kind, pos = read_var_uint(data, pos)
    return document, kind, data[pos:]


def parse_auth(rest: bytes) -> Tuple[bool, str]:
    """(granted, scope or reason) of an AUTH message's rest.

    The scope is "readonly" or "read-write"."""
    sub, pos = read_var_uint(rest, 0)
    text, _ = read_var_string(rest, pos) if pos < len(rest) else ("", pos)
    return sub == AUTH_OK, text
