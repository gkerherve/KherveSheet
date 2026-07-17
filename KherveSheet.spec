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

# Bake the resolved version into the frozen build — a PyInstaller bundle
# never ships .git, so without this khervesheet/_version.py would fall
# back to the placeholder "0.1.0". Write this file with the real
# git-derived version just before invoking PyInstaller.
_version_file = ROOT / "khervesheet" / "VERSION"
if _version_file.is_file():
    datas.append((str(_version_file), "khervesheet"))
binaries = []
hiddenimports = ["khervesheet"]

# Packages whose data files / submodules PyInstaller's built-in hooks may
# miss.  numpy / scipy / pandas / matplotlib / PyQt5 have good built-in
# hooks, so they are deliberately NOT collect_all'd here (that would bloat
# the build).  AI backends are optional — collected only if installed.
#
# Split into required vs optional.  A missing *required* package must abort
# the build: silently skipping one produces an .exe that looks fine, ships
# to users, and only fails when someone opens a .ksheet.  Optional AI
# backends may legitimately be absent, so those still skip quietly.
_REQUIRED = [
    "lmfit", "asteval", "uncertainties",   # curve-fitting (lmfit + deps)
    "qtawesome",                            # themed icon fonts
    "h5py",                                 # .ksheet (HDF5) I/O
    "pygit2",                               # per-document git
    "openpyxl",                             # Excel import/export
    "spellchecker",                         # bundled dictionary data
    "certifi",                             # SSL certs for =PY HTTPS fetches
]
_OPTIONAL = ["anthropic", "openai", "mistralai", "ollama"]

_missing = []
for _pkg in _REQUIRED + _OPTIONAL:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception as _exc:
        if _pkg in _REQUIRED:
            _missing.append(f"{_pkg} ({type(_exc).__name__}: {_exc})")
        # optional backend — skip quietly

if _missing:
    raise SystemExit(
        "KherveSheet.spec: required packages unavailable in the build "
        "environment:\n  - " + "\n  - ".join(_missing) +
        "\n\nInstall them (pip install -r requirements.txt) and rebuild. "
        "Shipping without these produces a broken .exe.")

# h5py's compiled extensions and hdf5.dll must survive into the bundle;
# assert it here rather than discovering it from a user bug report.
if not any("h5py" in _dst for _src, _dst in binaries):
    raise SystemExit(
        "KherveSheet.spec: h5py collected no binaries — the HDF5 extension "
        "modules are missing and .ksheet files would fail to open.")

# Strip per-document git repos that should never be shipped.
def _keep(path):
    parts = Path(path).parts
    return ".ksheet_versions" not in parts and ".git" not in parts
datas = [(src, dst) for src, dst in datas if _keep(src)]

a = Analysis(
    ["KherveSheet.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide6", "PySide2", "PyQt6", "torch", "xarray"],
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
