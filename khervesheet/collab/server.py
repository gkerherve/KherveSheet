"""Relay server for KherveSheet live co-editing.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Run with::

    python -m khervesheet.collab.server --port 1235

Each shared workbook is a room: ``ws://host:1235/<room>``.  The server
speaks the standard Yjs WebSocket protocol, keeps every room in a SQLite
file so shared workbooks survive restarts, and never evaluates cells.
The room name is the secret that grants access: share links only with
the people who should edit the workbook.
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import re

DEFAULT_PORT = 1235
DEFAULT_DB = os.path.join(os.path.expanduser("~"), ".khervesheet",
                          "live-rooms.db")
ROOM_NAME = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def build_app(db_path: str):
    """The ASGI application: a Yjs WebSocket server with SQLite storage."""
    from pycrdt.store import SQLiteYStore, YDocNotFound
    from pycrdt.websocket import ASGIServer, WebsocketServer, YRoom

    class Store(SQLiteYStore):
        pass

    Store.db_path = db_path

    class PersistentServer(WebsocketServer):
        async def get_room(self, name: str) -> YRoom:
            if name not in self.rooms:
                store = Store(path=name, log=self.log)
                room = YRoom(ready=False, ystore=store, log=self.log,
                             exception_handler=self.exception_handler)
                self.rooms[name] = room
                await self.start_room(room)
                async with store.start_lock:
                    if not store.started.is_set():
                        await self._task_group.start(store.start)
                try:
                    await store.apply_updates(room.ydoc)
                except YDocNotFound:
                    pass
                room.ready = True
            room = self.rooms[name]
            await self.start_room(room)
            return room

        async def delete_room(self, *, name=None, room=None) -> None:
            await super().delete_room(name=name, room=room)
            # pycrdt objects must be freed on the thread that made them;
            # collect a closed room here rather than whenever (and on
            # whichever thread) the garbage collector next runs.
            gc.collect()

    websocket_server = PersistentServer(auto_clean_rooms=True)

    def refuse_bad_rooms(_message, scope) -> bool:
        return not ROOM_NAME.match(scope.get("path", "").strip("/"))

    app = ASGIServer(websocket_server, on_connect=refuse_bad_rooms)
    return app, websocket_server


async def serve(host: str, port: int, db_path: str,
                shutdown_trigger=None) -> None:
    from hypercorn.asyncio import serve as hypercorn_serve
    from hypercorn.config import Config

    app, websocket_server = build_app(db_path)
    config = Config()
    config.bind = [f"{host}:{port}"]
    async with websocket_server:
        logging.getLogger(__name__).info(
            "KherveSheet live server on ws://%s:%d (rooms in %s)",
            host, port, db_path)
        await hypercorn_serve(app, config, shutdown_trigger=shutdown_trigger)


class BackgroundServer:
    """The relay run inside KherveSheet itself, on a background thread.

    For hosting from one person's computer: the thread only runs asyncio
    and never touches Qt.
    """

    def __init__(self, host: str, port: int, db_path: str):
        self.host, self.port, self.db_path = host, port, db_path
        self._loop = None
        self._stop = None
        self._thread = None
        self.error = None

    def start(self) -> None:
        import asyncio
        import threading

        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)),
                    exist_ok=True)
        ready = threading.Event()

        def run():
            self._loop = asyncio.new_event_loop()
            self._stop = asyncio.Event()

            async def main():
                ready.set()
                await serve(self.host, self.port, self.db_path,
                            shutdown_trigger=self._stop.wait)

            try:
                self._loop.run_until_complete(main())
            except Exception as exc:  # port in use, missing module…
                self.error = exc
                ready.set()
            finally:
                self._loop.close()

        self._thread = threading.Thread(
            target=run, name="khervesheet-live-server", daemon=True)
        self._thread.start()
        ready.wait(5)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def stop(self) -> None:
        if self._loop is not None and self.running:
            self._loop.call_soon_threadsafe(self._stop.set)
            self._thread.join(3)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Relay server for KherveSheet live co-editing.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="interface to listen on (0.0.0.0 for a LAN)")
    parser.add_argument("--port", type=int, default=1235)
    parser.add_argument(
        "--db", default=DEFAULT_DB,
        help="SQLite file keeping the shared workbooks")
    args = parser.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    import asyncio
    asyncio.run(serve(args.host, args.port, args.db))


if __name__ == "__main__":
    main()
