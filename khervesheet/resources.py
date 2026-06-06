"""Resource-path resolution — works both from source and when frozen.

When KherveSheet runs from source, bundled data (the ``examples/`` tree,
``python_help.html``, ``userguide.html``) lives next to / inside the
package.  When packaged with PyInstaller the same files are added to the
bundle via ``datas`` and must be located relative to ``sys._MEIPASS``
(``--onefile``) or the ``_internal`` dir beside the executable
(``--onedir``).  Centralising the lookup here keeps every caller correct
in both cases.

User-created data (templates the user saves) must NOT go into the
read-only bundle — it is written to a per-user, writable location instead.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_base() -> str:
    """Root directory that bundled resources are resolved against.

    - Frozen: ``sys._MEIPASS`` if present (PyInstaller sets it for both
      one-file and one-dir builds), else the executable's directory.
    - Source: the repository root (parent of the ``khervesheet`` package).
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return meipass
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def examples_dir():
    """Absolute path to the bundled ``examples/`` folder, or None."""
    d = os.path.join(resource_base(), "examples")
    return d if os.path.isdir(d) else None


def package_file(name: str) -> str:
    """Absolute path to a data file shipped *inside* the khervesheet
    package (e.g. ``python_help.html``, ``userguide.html``)."""
    if is_frozen():
        return os.path.join(resource_base(), "khervesheet", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def user_data_dir() -> str:
    """Per-user writable data directory (created on demand).

    Windows: ``%APPDATA%/KherveSheet``; macOS:
    ``~/Library/Application Support/KherveSheet``; Linux:
    ``$XDG_DATA_HOME/KherveSheet`` (or ``~/.local/share/KherveSheet``).
    """
    if sys.platform.startswith("win"):
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"),
                            "Library", "Application Support")
    else:
        root = (os.environ.get("XDG_DATA_HOME")
                or os.path.join(os.path.expanduser("~"), ".local", "share"))
    d = os.path.join(root, "KherveSheet")
    os.makedirs(d, exist_ok=True)
    return d


def user_templates_dir() -> str:
    """Writable folder where user-saved templates live (created on demand)."""
    d = os.path.join(user_data_dir(), "templates")
    os.makedirs(d, exist_ok=True)
    return d
