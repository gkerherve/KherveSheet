"""KherveDOC as KherveSheet's sharing server: its REST API and live rooms.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

A shared workbook is a KherveDOC document of kind "sheet": KherveDOC keeps
it, lists it, controls who may open or edit it, and its collaboration
server relays live edits between KherveSheet windows and browsers
(KherveCELL). KherveSheet signs in once (see signin.py) and then acts with
the user's KherveDOC session, like the web app does.
"""

from __future__ import annotations

import base64
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

SESSION_COOKIE = "docs_sessionid"
CSRF_COOKIE = "csrftoken"
TIMEOUT_S = 15


class KherveDocError(Exception):
    """A KherveDOC request failed; ``status`` is the HTTP status (or 0)."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class NotSignedIn(KherveDocError):
    pass


class KherveDoc:
    """The user's KherveDOC server, reached with their session."""

    def __init__(self, server: str, api: Optional[str] = None,
                 session: str = "", csrf: str = ""):
        self.server = server.rstrip("/")
        self.api = (api or "").rstrip("/") or None
        self.session = session
        # Django's CSRF check compares this cookie with a header of the same
        # value; a native client may choose it (like a browser, once).
        self.csrf = csrf or secrets.token_hex(16)
        self._config: Optional[dict] = None

    # ── Addresses ────────────────────────────────────────────────────
    def discover(self) -> str:
        """The API's origin: the server itself in production, or the dev
        backend next to it (localhost:3000 → localhost:8071)."""
        if self.api:
            return self.api
        candidates = [self.server]
        parsed = urllib.parse.urlsplit(self.server)
        if parsed.port == 3000:
            candidates.append(f"{parsed.scheme}://{parsed.hostname}:8071")
        for origin in candidates:
            try:
                self._config = self._get_json(f"{origin}/api/v1.0/config/",
                                              auth=False)
                self.api = origin
                return origin
            except KherveDocError:
                continue
        raise KherveDocError(f"No KherveDOC server answers at {self.server}")

    def config(self) -> dict:
        if self._config is None:
            self.discover()
            if self._config is None:
                self._config = self._get_json(
                    f"{self.api}/api/v1.0/config/", auth=False)
        return self._config

    def ws_url(self, document: str) -> str:
        base = self.config().get("COLLABORATION_WS_URL") or (
            self.server.replace("http", "ws", 1) + "/collaboration/ws/")
        return f"{base}?room={document}"

    def page_url(self, document: str) -> str:
        return f"{self.server}/docs/{document}/"

    def login_url(self) -> str:
        return (f"{self.discover()}/api/v1.0/authenticate/?returnTo="
                + urllib.parse.quote(self.server + "/", safe=""))

    def ws_headers(self) -> Dict[str, str]:
        """What the collaboration server checks: the session and origin."""
        return {"Cookie": self._cookie_header(), "Origin": self.server}

    # ── Requests ─────────────────────────────────────────────────────
    def _cookie_header(self) -> str:
        return f"{SESSION_COOKIE}={self.session}; {CSRF_COOKIE}={self.csrf}"

    def _request(self, method: str, url: str, body=None, auth=True,
                 raw=False):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Cookie"] = self._cookie_header()
            headers["X-CSRFToken"] = self.csrf
            headers["Origin"] = self.server
            headers["Referer"] = self.server + "/"
        request = urllib.request.Request(url, data=data, method=method,
                                         headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and auth:
                raise NotSignedIn("Not signed in to KherveDOC", exc.code)
            detail = exc.read().decode(errors="replace")[:300]
            raise KherveDocError(f"KherveDOC answered {exc.code}: {detail}",
                                 exc.code)
        except (urllib.error.URLError, OSError) as exc:
            raise KherveDocError(f"KherveDOC could not be reached: {exc}")
        if raw:
            return payload
        return json.loads(payload) if payload else None

    def _get_json(self, url, auth=True):
        return self._request("GET", url, auth=auth)

    def _api(self, method: str, path: str, body=None, raw=False):
        return self._request(method, f"{self.discover()}/api/v1.0/{path}",
                             body, raw=raw)

    # ── The user and their spreadsheets ──────────────────────────────
    def me(self) -> dict:
        """The signed-in user; raises NotSignedIn otherwise."""
        user = self._api("GET", "users/me/")
        if not user or not user.get("id"):
            raise NotSignedIn("Not signed in to KherveDOC")
        return user

    def spreadsheets(self) -> List[dict]:
        """Spreadsheets the user can open, most recently changed first."""
        found: List[dict] = []
        path = "documents/?ordering=-updated_at&page_size=100"
        for _ in range(20):
            page = self._api("GET", path)
            found.extend(d for d in page.get("results", [])
                         if d.get("kind") == "sheet")
            nxt = page.get("next")
            if not nxt:
                break
            path = nxt.split("/api/v1.0/", 1)[1]
        return found

    def document(self, document: str) -> dict:
        return self._api("GET", f"documents/{document}/")

    def create_spreadsheet(self, title: str) -> dict:
        return self._api("POST", "documents/",
                         {"title": title, "kind": "sheet"})

    def content(self, document: str) -> Optional[bytes]:
        """The saved Yjs update of a document, or None if it has none."""
        try:
            raw = self._api("GET", f"documents/{document}/content/", raw=True)
        except KherveDocError as exc:
            if exc.status == 404:
                return None
            raise
        text = raw.decode().strip()
        if text.startswith("{"):
            text = json.loads(text).get("content") or ""
        return base64.b64decode(text) if text else None

    def save_content(self, document: str, update: bytes) -> None:
        self._api("PATCH", f"documents/{document}/content/", {
            "content": base64.b64encode(update).decode(),
            "websocket": True,
        })

    def invite(self, document: str, email: str, role: str = "editor") -> str:
        """Give *email* access: directly if they have an account, else by
        an invitation e-mail. Returns "access" or "invitation"."""
        email = email.strip()
        users = self._api("GET", "users/?q=" + urllib.parse.quote(email))
        results = users.get("results", users) if isinstance(users, dict) \
            else users
        match = next((u for u in results or []
                      if (u.get("email") or "").lower() == email.lower()),
                     None)
        if match:
            self._api("POST", f"documents/{document}/accesses/",
                      {"user_id": match["id"], "role": role})
            return "access"
        self._api("POST", f"documents/{document}/invitations/",
                  {"email": email, "role": role})
        return "invitation"


def document_id_from(text: str) -> Optional[str]:
    """The document id in a KherveDOC link (…/docs/<id>/) or a bare id."""
    import re
    m = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}"
        r"-[0-9a-fA-F]{12}", text or "")
    return m.group(0).lower() if m else None
