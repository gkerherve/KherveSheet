# KherveSheet — silent background auto-updater
# Copyright (C) 2026  Gwilherm Kerherve
# SPDX-License-Identifier: GPL-3.0-or-later

"""Silent auto-update against the Kherve-Downloads GitHub releases.

Releases for every Kherve app share one public repo
(``gkerherve/Kherve-Downloads``) and are told apart by their tag prefix,
so this module never uses ``/releases/latest`` — that would happily hand
back a KherveFitting build.  It lists releases and keeps only the ones
tagged ``khervesheet-v<version>``.

The flow is deliberately quiet: the check and the download happen on
background threads with no UI at all, and the user only ever sees a
dialog once a verified installer is sitting on disk ready to run.

Installing is a Windows-only affair — the shipped artefact is an Inno
Setup ``Setup_KherveSheet_<version>.exe``.  Because the app installs
under Program Files, the installer must elevate, so exactly one UAC
prompt is unavoidable; everything either side of it is silent.  The
running executable cannot replace itself, so a tiny detached batch
helper waits for this process to exit, runs the installer with
``/VERYSILENT``, and relaunches the app.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from PyQt5.QtCore import QObject, QSettings, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox, QProgressDialog

from . import APP_NAME, __version__
from .resources import is_frozen, user_data_dir

GITHUB_OWNER = "gkerherve"
GITHUB_REPO = "Kherve-Downloads"
RELEASES_URL = (f"https://api.github.com/repos/{GITHUB_OWNER}/"
                f"{GITHUB_REPO}/releases?per_page=30")
RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

#: Only releases whose tag starts with this belong to KherveSheet.
TAG_PREFIX = "khervesheet-v"
#: The asset we install from, e.g. ``Setup_KherveSheet_0.1.610.exe``.
INSTALLER_RE = re.compile(r"^Setup_KherveSheet_([0-9][0-9.]*)\.exe$", re.I)

NETWORK_TIMEOUT = 15          # seconds, per request
CHECK_INTERVAL = 24 * 3600    # don't re-check more often than daily
STARTUP_DELAY_MS = 20000      # let the app settle before touching the net

# Inno Setup switches: no wizard, no message boxes, no reboot, and close
# anything still holding our files (the app should already be gone).
INSTALLER_ARGS = (
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
    "/CLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS",
)

# QSettings keys.
KEY_AUTO_CHECK = "update/auto_check"
KEY_LAST_CHECK = "update/last_check"
KEY_SKIP = "update/skip_version"


# ── Version helpers ──────────────────────────────────────────────────

def version_tuple(text) -> tuple:
    """Numeric parts of a version string, as a comparable tuple.

    Tolerates everything we throw at it: ``0.1.610``, ``v0.1.610``,
    ``khervesheet-v0.1.610`` and the local ``0.1.610+9c0255f`` build
    string all collapse to ``(0, 1, 610)``.  Returns ``()`` when no
    version is present, which sorts below every real release.
    """
    m = re.search(r"(\d+(?:\.\d+)*)", str(text or ""))
    if not m:
        return ()
    return tuple(int(part) for part in m.group(1).split("."))


def current_version_tuple() -> tuple:
    """Version tuple of the running build."""
    return version_tuple(__version__)


# ── Release metadata ─────────────────────────────────────────────────

class Release:
    """One KherveSheet release plus the installer asset to fetch."""

    def __init__(self, version_text, tag, notes, page_url,
                 asset_name, asset_url, asset_size, digest):
        self.version_text = version_text
        self.version = version_tuple(version_text)
        self.tag = tag
        self.notes = notes or ""
        self.page_url = page_url or RELEASES_PAGE
        self.asset_name = asset_name
        self.asset_url = asset_url
        self.asset_size = asset_size or 0
        self.digest = digest or ""

    def is_newer_than_current(self) -> bool:
        return bool(self.version) and self.version > current_version_tuple()

    def __repr__(self):
        return f"<Release {self.version_text} asset={self.asset_name}>"


def _release_from_json(entry) -> "Release | None":
    """Build a Release from one GitHub API item, or None if it isn't ours."""
    if not isinstance(entry, dict):
        return None
    if entry.get("draft") or entry.get("prerelease"):
        return None
    tag = str(entry.get("tag_name") or "")
    if not tag.lower().startswith(TAG_PREFIX):
        return None
    version_text = tag[len(TAG_PREFIX):]
    if not version_tuple(version_text):
        return None

    # Prefer the exactly-named installer; fall back to any installer in
    # the release so a filename typo doesn't strand every client.
    assets = entry.get("assets") or []
    wanted = f"Setup_KherveSheet_{version_text}.exe".lower()
    chosen = None
    for asset in assets:
        name = str(asset.get("name") or "")
        if not INSTALLER_RE.match(name):
            continue
        if name.lower() == wanted:
            chosen = asset
            break
        if chosen is None:
            chosen = asset
    if chosen is None:
        return None

    return Release(
        version_text=version_text,
        tag=tag,
        notes=entry.get("body"),
        page_url=entry.get("html_url"),
        asset_name=str(chosen.get("name")),
        asset_url=str(chosen.get("browser_download_url") or ""),
        asset_size=int(chosen.get("size") or 0),
        digest=str(chosen.get("digest") or ""),
    )


def _request(url):
    return urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME}/{__version__}",
    })


def fetch_latest_release(timeout: int = NETWORK_TIMEOUT):
    """Newest published KherveSheet release, or None if there are none.

    Raises on network / API failure so callers can report it.
    """
    with urllib.request.urlopen(_request(RELEASES_URL),
                                timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list):
        return None
    best = None
    for entry in payload:
        rel = _release_from_json(entry)
        if rel is not None and (best is None or rel.version > best.version):
            best = rel
    return best


# ── Download cache ───────────────────────────────────────────────────

def update_cache_dir() -> str:
    """Writable folder the installer is downloaded into."""
    d = os.path.join(user_data_dir(), "updates")
    os.makedirs(d, exist_ok=True)
    return d


def purge_stale_downloads():
    """Delete installers for versions we're already running (or past).

    Called at startup so a successful update doesn't leave a 200 MB
    installer parked in the user's AppData forever.
    """
    current = current_version_tuple()
    try:
        names = os.listdir(update_cache_dir())
    except OSError:
        return
    for name in names:
        path = os.path.join(update_cache_dir(), name)
        m = INSTALLER_RE.match(name)
        stale = (m is not None and version_tuple(m.group(1)) <= current)
        # The batch helper deletes itself, but a declined UAC prompt or a
        # crash can strand it (and its log) — those are never useful later.
        stale = stale or name in ("apply_update.bat", "install.log")
        if not stale:
            continue
        try:
            os.remove(path)
        except OSError:
            pass


def _verify_digest(path: str, digest: str) -> bool:
    """Check a downloaded file against GitHub's ``sha256:...`` digest.

    Returns True when the digest is absent or in a form we don't know —
    the API only started publishing it recently and an unverifiable
    download is not the same as a corrupt one.
    """
    if not digest or not digest.lower().startswith("sha256:"):
        return True
    want = digest.split(":", 1)[1].strip().lower()
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == want


def download_installer(rel: Release, progress=None, should_abort=None) -> str:
    """Fetch *rel*'s installer into the cache and return its path.

    Downloads to a ``.part`` file and only renames once the digest checks
    out, so an interrupted download can never be mistaken for a complete
    one.  *progress* is called with ``(bytes_done, bytes_total)``.
    """
    dest = os.path.join(update_cache_dir(), rel.asset_name)
    if os.path.isfile(dest) and _verify_digest(dest, rel.digest):
        return dest                      # already fetched on a past run

    part = dest + ".part"
    with urllib.request.urlopen(_request(rel.asset_url),
                                timeout=NETWORK_TIMEOUT) as resp:
        total = int(resp.headers.get("Content-Length") or rel.asset_size or 0)
        done = 0
        with open(part, "wb") as fh:
            while True:
                if should_abort is not None and should_abort():
                    raise RuntimeError("cancelled")
                chunk = resp.read(1 << 18)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)

    if not _verify_digest(part, rel.digest):
        try:
            os.remove(part)
        except OSError:
            pass
        raise RuntimeError("downloaded installer failed its checksum")

    if os.path.exists(dest):
        os.remove(dest)
    os.replace(part, dest)
    return dest


# ── Handing over to the installer ────────────────────────────────────

_HELPER_BAT = """@echo off
setlocal
set "TRIES=0"
:wait
tasklist /FI "PID eq {pid}" /NH 2>nul | find "{pid}" >nul || goto run
set /a TRIES+=1
if %TRIES% GTR 120 goto run
ping -n 2 127.0.0.1 >nul
goto wait
:run
"{installer}" {args} /LOG="{log}"
start "" "{exe}"
del "%~f0"
"""

# PowerShell equivalent, used only when the paths involved can't be
# spelled in the console codepage (see _write_helper_bat).
_HELPER_PS = """$ErrorActionPreference = 'SilentlyContinue'
Wait-Process -Id {pid} -Timeout 240
Start-Process -FilePath '{installer}' -ArgumentList {args} -Wait
Start-Process -FilePath '{exe}'
"""


def _oem_encoding() -> str:
    """The console codepage cmd.exe reads .bat files in (e.g. ``cp850``).

    Batch files are decoded with the OEM codepage, *not* UTF-8, so a
    helper script naming a path under a non-ASCII user profile has to be
    written in that codepage or cmd will look for a mangled filename.
    """
    try:
        import ctypes
        return "cp%d" % ctypes.windll.kernel32.GetOEMCP()
    except Exception:                                      # noqa: BLE001
        return "utf-8"


def _write_helper_bat(script: str, body: str) -> bool:
    """Write the batch helper, or return False if it can't be encoded."""
    try:
        with open(script, "w", encoding=_oem_encoding(),
                  errors="strict", newline="\r\n") as fh:
            fh.write(body)
    except (LookupError, UnicodeEncodeError, OSError):
        return False
    return True


def _powershell_command(installer_path: str, exe: str) -> list:
    """Codepage-proof fallback: the same steps as a base64 PS command.

    ``-EncodedCommand`` takes UTF-16, so it carries any path Windows can
    produce.  It is only used when the batch route is unavailable — a
    plain .bat is far less likely to upset endpoint-protection software.
    """
    body = _HELPER_PS.format(
        pid=os.getpid(),
        installer=installer_path.replace("'", "''"),
        args=", ".join("'%s'" % a for a in INSTALLER_ARGS),
        exe=exe.replace("'", "''"),
    )
    import base64
    encoded = base64.b64encode(body.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive",
            "-WindowStyle", "Hidden", "-EncodedCommand", encoded]


def launch_installer(installer_path: str) -> bool:
    """Spawn the detached helper that installs the update and restarts us.

    Returns False when this isn't a Windows install we can update in
    place.  The caller is expected to quit immediately afterwards — the
    helper polls for this PID to disappear before touching any files.
    """
    if not sys.platform.startswith("win"):
        return False
    if not os.path.isfile(installer_path):
        return False

    cache = update_cache_dir()
    installer_path = os.path.abspath(installer_path)
    exe = os.path.abspath(sys.executable)
    script = os.path.join(cache, "apply_update.bat")
    body = _HELPER_BAT.format(
        pid=os.getpid(),
        installer=installer_path,
        args=" ".join(INSTALLER_ARGS),
        log=os.path.join(cache, "install.log"),
        exe=exe,
    )

    if _write_helper_bat(script, body):
        command = ["cmd.exe", "/c", script]
    else:
        command = _powershell_command(installer_path, exe)

    try:
        # CREATE_NO_WINDOW only. It must NOT be OR-ed with
        # DETACHED_PROCESS: Windows documents the two as mutually
        # exclusive, and in practice the helper then spawns without ever
        # running a line of the script. Either flag alone hides the
        # console, but a detached cmd.exe has none at all and dies just
        # as quietly. The helper outlives us regardless — Windows does
        # not reap children when their parent exits.
        subprocess.Popen(command, cwd=cache, close_fds=True,
                         creationflags=getattr(
                             subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return False
    return True


# ── Background workers ───────────────────────────────────────────────

class _CheckWorker(QThread):
    """Queries the releases API off the GUI thread."""

    found = pyqtSignal(object)     # Release or None
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.found.emit(fetch_latest_release())
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                self.failed.emit(
                    "GitHub is rate-limiting update checks right now. "
                    "Please try again later.")
            else:
                self.failed.emit(f"GitHub returned HTTP {exc.code}.")
        except Exception as exc:                       # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _DownloadWorker(QThread):
    """Streams the installer to disk off the GUI thread."""

    progress = pyqtSignal(int, int)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, rel, parent=None):
        super().__init__(parent)
        self._rel = rel
        self._abort = False

    def cancel(self):
        self._abort = True

    def run(self):
        try:
            path = download_installer(
                self._rel,
                progress=lambda d, t: self.progress.emit(d, t),
                should_abort=lambda: self._abort)
        except Exception as exc:                       # noqa: BLE001
            if not self._abort:
                self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(path)


# ── Manager ──────────────────────────────────────────────────────────

class UpdateManager(QObject):
    """Owns the check/download/prompt cycle for one main window."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._settings = QSettings("KherveSheet", "KherveSheet")
        self._check_worker = None
        self._download_worker = None
        self._progress_dlg = None
        self._silent = True
        self._release = None

    # ── Settings ─────────────────────────────────────────────────────
    @staticmethod
    def auto_check_enabled() -> bool:
        return QSettings("KherveSheet", "KherveSheet").value(
            KEY_AUTO_CHECK, True, type=bool)

    def _due_for_check(self) -> bool:
        try:
            last = float(self._settings.value(KEY_LAST_CHECK, 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        return (time.time() - last) >= CHECK_INTERVAL

    # ── Entry points ─────────────────────────────────────────────────
    def start_background_check(self):
        """Kick off the silent check, if one is warranted.

        Skipped entirely for source checkouts (there is no installed copy
        to replace) and for non-Windows, where no installer is published.
        """
        if not (is_frozen() and sys.platform.startswith("win")):
            return
        purge_stale_downloads()
        if not self.auto_check_enabled() or not self._due_for_check():
            return
        QTimer.singleShot(STARTUP_DELAY_MS, lambda: self._begin(silent=True))

    def check_now(self):
        """Help ▸ Check for Updates — same machinery, but it talks back."""
        self._begin(silent=False)

    # ── Check ────────────────────────────────────────────────────────
    def _begin(self, silent: bool):
        if self._check_worker is not None or self._download_worker is not None:
            if not silent:
                QMessageBox.information(
                    self._window, "Check for Updates",
                    "An update check is already running.")
            return
        self._silent = silent
        self._settings.setValue(KEY_LAST_CHECK, time.time())
        if not silent:
            self._window._status_msg("Checking for updates…")

        self._check_worker = _CheckWorker(self)
        self._check_worker.found.connect(self._on_found)
        self._check_worker.failed.connect(self._on_check_failed)
        self._check_worker.finished.connect(self._clear_check_worker)
        self._check_worker.start()

    def _clear_check_worker(self):
        self._check_worker = None

    def _on_check_failed(self, message: str):
        if self._silent:
            return
        self._window._status_msg("Ready")
        QMessageBox.warning(
            self._window, "Check for Updates",
            f"Could not check for updates.\n\n{message}")

    def _on_found(self, rel):
        if rel is None or not rel.is_newer_than_current():
            if not self._silent:
                self._window._status_msg("Ready")
                QMessageBox.information(
                    self._window, "Check for Updates",
                    f"{APP_NAME} {__version__} is up to date.")
            return

        # A silently-skipped version stays skipped until asked about again.
        if self._silent and str(self._settings.value(KEY_SKIP, "")) == \
                rel.version_text:
            return

        if not (is_frozen() and sys.platform.startswith("win")):
            self._offer_manual_download(rel)
            return

        self._release = rel
        self._start_download(rel)

    def _offer_manual_download(self, rel):
        """Source checkout / non-Windows: point at the release page."""
        self._window._status_msg("Ready")
        box = QMessageBox(self._window)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Update Available")
        box.setText(f"{APP_NAME} {rel.version_text} is available "
                    f"(you have {__version__}).")
        box.setInformativeText(
            "This copy runs from source, so it can't be updated "
            "automatically. Pull the latest commits, or download the "
            "installer from the release page.")
        open_btn = box.addButton("Open Release Page",
                                 QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is open_btn:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(rel.page_url))

    # ── Download ─────────────────────────────────────────────────────
    def _start_download(self, rel):
        self._download_worker = _DownloadWorker(rel, self)
        self._download_worker.done.connect(self._on_downloaded)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.finished.connect(self._clear_download_worker)

        if not self._silent:
            self._window._status_msg(
                f"Downloading {APP_NAME} {rel.version_text}…")
            dlg = QProgressDialog(
                f"Downloading {APP_NAME} {rel.version_text}…",
                "Cancel", 0, 100, self._window)
            dlg.setWindowTitle("Update")
            dlg.setAutoClose(False)
            dlg.setAutoReset(False)
            dlg.setMinimumDuration(0)
            dlg.canceled.connect(self._download_worker.cancel)
            self._progress_dlg = dlg
            self._download_worker.progress.connect(self._on_progress)
            dlg.show()

        self._download_worker.start()

    def _on_progress(self, done: int, total: int):
        if self._progress_dlg is None:
            return
        if total > 0:
            self._progress_dlg.setValue(int(done * 100 / total))
            self._progress_dlg.setLabelText(
                f"Downloading {APP_NAME} {self._release.version_text}… "
                f"{done / 1048576:.0f} / {total / 1048576:.0f} MB")

    def _clear_download_worker(self):
        self._download_worker = None
        self._close_progress()

    def _close_progress(self):
        if self._progress_dlg is not None:
            self._progress_dlg.close()
            self._progress_dlg = None
        # A silent check never wrote to the status bar, so it must not
        # clear whatever the user's own work has put there.
        if not self._silent:
            self._window._status_msg("Ready")

    def _on_download_failed(self, message: str):
        self._close_progress()
        if self._silent:
            return
        QMessageBox.warning(
            self._window, "Update",
            f"Could not download the update.\n\n{message}")

    # ── Prompt + install ─────────────────────────────────────────────
    def _on_downloaded(self, path: str):
        self._close_progress()
        rel = self._release
        if rel is None:
            return

        box = QMessageBox(self._window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Update Ready")
        box.setText(f"{APP_NAME} {rel.version_text} is ready to install.")
        box.setInformativeText(
            f"You are running {__version__}. The update has already been "
            f"downloaded — {APP_NAME} will close, update itself, and "
            f"reopen. Unsaved work is saved first.")
        if rel.notes.strip():
            box.setDetailedText(rel.notes.strip())
        install_btn = box.addButton("Restart && Update",
                                    QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        skip_btn = box.addButton("Skip This Version",
                                 QMessageBox.DestructiveRole)
        box.setDefaultButton(install_btn)
        box.exec_()

        clicked = box.clickedButton()
        if clicked is skip_btn:
            self._settings.setValue(KEY_SKIP, rel.version_text)
            return
        if clicked is not install_btn:
            return
        self._install(path)

    def _install(self, path: str):
        """Close the window, then hand over to the detached helper.

        ``close()`` runs the usual save-changes prompt; a user who backs
        out there has cancelled the update too, and the downloaded
        installer stays put for next time.
        """
        if not self._window.close():
            return
        if not launch_installer(path):
            QMessageBox.warning(
                self._window, "Update",
                "The update could not be started. The installer is at:\n\n"
                f"{path}")
            return
        QApplication.quit()
