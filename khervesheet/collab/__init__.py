"""Live co-editing: several KherveSheet windows editing one workbook.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

The workbook is mirrored into a Yjs document (pycrdt) that a small
server relays between everyone in the same room:

- ``model``   — Qt-free document layout, snapshots and diffs.
- ``session`` — the client: WebSocket, sync protocol, applying edits.
- ``server``  — the relay, ``python -m khervesheet.collab.server``.
- ``dialogs`` — File ▸ Live Sharing dialogs.
"""
