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

IS_MAC = sys.platform == "darwin"

# UPX mangles Mach-O load commands and invalidates the ad-hoc signature
# PyInstaller applies, which on Apple Silicon means the app is killed at
# launch rather than merely unpacking slowly.  Compress on Windows only.
USE_UPX = not IS_MAC

# ── Generate the platform icon from the runtime app mark ────────────
#
# Single source of truth for the green "KS" monogram lives in
# khervesheet/icons.py.  tools/generate_icon.py renders it into a
# multi-resolution ICO (Windows, 16..256) or ICNS (macOS, 16..1024)
# under build/.  The resulting file is referenced by EXE()/BUNDLE().
ICON_PATH = ROOT / "build" / (
    "KherveSheet.icns" if IS_MAC else "KherveSheet.ico")
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
# QtNetwork backs the MCP bridge and QtWebSockets live sharing; both are
# only reached through lazy imports, so name them explicitly.
hiddenimports = ["khervesheet", "PyQt5.QtNetwork", "PyQt5.QtWebSockets",
                 # =PY cells import it at run time, which analysis can't
                 # see; two shipped examples need it.
                 "pandas"]

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
    "pycrdt", "anyio", "sqlite_anyio",     # live sharing (Yjs documents)
    "hypercorn", "h11", "wsproto",         # live sharing: hosted server
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
#
# This has to run on a.datas *after* Analysis, not on the `datas` list above:
# ("examples", "examples") is a directory tuple that PyInstaller only expands
# into individual files during Analysis, so filtering the tuple here matches
# nothing and the whole .ksheet_versions tree ships anyway. Those paths are
# also deep enough to push the Inno Setup compile past MAX_PATH and abort it.
def _keep(path):
    parts = Path(path).parts
    return ".ksheet_versions" not in parts and ".git" not in parts

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

_before = len(a.datas)
a.datas = TOC([(dst, src, kind) for dst, src, kind in a.datas if _keep(dst)])
print(f"KherveSheet.spec: stripped {_before - len(a.datas)} "
      f".ksheet_versions/.git files from the bundle")

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
    upx=USE_UPX,
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
    upx=USE_UPX,
    upx_exclude=[],
    name="KherveSheet",
)

# ── macOS .app bundle ────────────────────────────────────────────────
#
# COLLECT alone yields dist/KherveSheet/ — a bare folder Finder will not
# treat as an application.  BUNDLE wraps it into KherveSheet.app with the
# Info.plist that makes the Dock icon, the document associations and the
# Retina-native rendering work.
if IS_MAC:
    # CFBundleShortVersionString must be dot-separated digits; the
    # git-derived string carries a "+sha" suffix Finder would reject.
    _short_version = "0.1.0"
    if _version_file.is_file():
        _short_version = _version_file.read_text(
            encoding="utf-8").strip().split("+")[0] or _short_version

    _doc_types = [
        {
            "CFBundleTypeName": "KherveSheet Workbook",
            "CFBundleTypeExtensions": ["ksheet"],
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Owner",
            "CFBundleTypeIconFile": ICON_PATH.name,
        },
        {
            "CFBundleTypeName": "Comma-Separated Values",
            "CFBundleTypeExtensions": ["csv"],
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Alternate",
        },
        {
            "CFBundleTypeName": "Excel Workbook",
            "CFBundleTypeExtensions": ["xlsx", "xlsm"],
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Alternate",
        },
    ]

    app = BUNDLE(
        coll,
        name="KherveSheet.app",
        icon=str(ICON_PATH),
        bundle_identifier="com.kerherve.khervesheet",
        version=_short_version,
        info_plist={
            "CFBundleName": "KherveSheet",
            "CFBundleDisplayName": "KherveSheet",
            "CFBundleShortVersionString": _short_version,
            "CFBundleVersion": _short_version,
            "LSMinimumSystemVersion": "11.0",
            # Without this the app renders at 1x and scales up — every
            # glyph in the grid looks blurred on a Retina display.
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "CFBundleDocumentTypes": _doc_types,
            "NSHumanReadableCopyright":
                "Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0.",
        },
    )
