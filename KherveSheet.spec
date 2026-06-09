# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller build spec for KherveSheet.
#
#   pip install pyinstaller
#   pyinstaller KherveSheet.spec        # -> dist/KherveSheet/KherveSheet(.exe)
#
# Produces a one-dir build (recommended: the examples/ tree is sizeable and
# one-dir starts faster and keeps a stable on-disk resource folder).  The
# bundled data lands under dist/KherveSheet/_internal/ and is located at
# runtime via khervesheet/resources.py (sys._MEIPASS / the _internal dir).
#
# Written for PyInstaller 6.x.  On 5.x change ``PYZ(a.pure)`` to
# ``PYZ(a.pure, a.zipped_data)``.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)

# ── Generate the Windows .ico from the runtime make_app_icon() ─────
#
# Single source of truth for the green "KS" monogram lives in
# khervesheet/icons.py.  tools/generate_icon.py renders it at all 7
# sizes (16..256) into a multi-resolution ICO under build/.  The
# resulting file is referenced by the EXE() block below.
ICON_PATH = ROOT / "build" / "KherveSheet.ico"
if not ICON_PATH.exists():
    import subprocess as _sp
    _sp.run(
        [sys.executable, str(ROOT / "tools" / "generate_icon.py"),
         str(ICON_PATH)],
        check=True,
    )

# ── Data files shipped with the app (read-only at runtime) ───────────
datas = [
    ("examples", "examples"),                         # all .ksheet examples
    ("khervesheet/python_help.html", "khervesheet"),
    ("khervesheet/userguide.html", "khervesheet"),
]
binaries = []
hiddenimports = ["khervesheet"]

# Packages whose data files / submodules PyInstaller's built-in hooks may
# miss.  numpy / scipy / pandas / matplotlib / PyQt5 have good built-in
# hooks, so they are deliberately NOT collect_all'd here (that would bloat
# the build).  AI backends are optional — collected only if installed.
_collect = [
    "lmfit", "asteval", "uncertainties",   # curve-fitting (lmfit + deps)
    "qtawesome",                            # themed icon fonts
    "h5py",                                 # .ksheet (HDF5) I/O
    "pygit2",                               # per-document git
    "openpyxl",                             # Excel import/export
    "spellchecker",                         # bundled dictionary data
    "anthropic", "openai", "mistralai", "ollama",   # optional AI providers
    "certifi",                             # SSL certs for =PY HTTPS fetches
]
for _pkg in _collect:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass   # optional / not installed — skip

# Strip per-document git repos that should never be shipped.
datas = [(src, dst) for src, dst in datas
         if ".ksheet_versions" not in src and "/.git" not in src]

a = Analysis(
    ["KherveSheet.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide6", "PySide2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KherveSheet",
    icon=str(ICON_PATH),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KherveSheet",
)
