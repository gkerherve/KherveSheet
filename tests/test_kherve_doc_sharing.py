"""Sharing through KherveDOC: its collaboration protocol and links.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

pytest.importorskip("pycrdt")

from khervesheet.collab import hocuspocus  # noqa: E402
from khervesheet.collab.kherve_doc import KherveDoc, document_id_from  # noqa: E402

DOC = "15aefe9a-f9d3-4ff8-a72d-3c4e65b34eeb"


def test_var_uint_and_string_round_trip():
    for n in (0, 1, 127, 128, 300, 2 ** 31):
        encoded = hocuspocus.write_var_uint(n)
        assert hocuspocus.read_var_uint(encoded, 0) == (n, len(encoded))
    text = "Données é ✓"
    encoded = hocuspocus.write_var_string(text)
    assert hocuspocus.read_var_string(encoded, 0) == (text, len(encoded))


def test_messages_carry_the_document_name_first():
    from pycrdt import Doc, create_sync_message
    inner = create_sync_message(Doc())
    framed = hocuspocus.frame(DOC, inner)
    document, kind, rest = hocuspocus.parse(framed)
    assert (document, kind) == (DOC, hocuspocus.SYNC)
    assert bytes([kind]) + rest == inner


def test_authentication_messages():
    document, kind, rest = hocuspocus.parse(hocuspocus.auth_message(DOC))
    assert (document, kind) == (DOC, hocuspocus.AUTH)
    assert rest == bytes([hocuspocus.AUTH_TOKEN, 0])      # empty token
    granted = bytes([hocuspocus.AUTH_OK]) + hocuspocus.write_var_string(
        "readonly")
    assert hocuspocus.parse_auth(granted) == (True, "readonly")
    denied = bytes([hocuspocus.AUTH_DENIED]) + hocuspocus.write_var_string(
        "permission-denied")
    assert hocuspocus.parse_auth(denied) == (False, "permission-denied")


def test_document_links():
    assert document_id_from(f"http://localhost:3000/docs/{DOC}/") == DOC
    assert document_id_from(DOC.upper()) == DOC
    assert document_id_from("not a link") is None


def test_addresses_without_a_server_round_trip():
    kd = KherveDoc("http://localhost:3000/", api="http://localhost:8071",
                   session="abc")
    kd._config = {"COLLABORATION_WS_URL": "ws://localhost:4444/collaboration/ws/"}
    assert kd.ws_url(DOC) == \
        f"ws://localhost:4444/collaboration/ws/?room={DOC}"
    assert kd.page_url(DOC) == f"http://localhost:3000/docs/{DOC}/"
    headers = kd.ws_headers()
    assert headers["Origin"] == "http://localhost:3000"
    assert "docs_sessionid=abc" in headers["Cookie"]
    assert kd.login_url().startswith(
        "http://localhost:8071/api/v1.0/authenticate/?returnTo=")
