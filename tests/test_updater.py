"""Unit tests for the silent auto-updater.

Exercises release selection, version comparison, download caching and the
installer hand-off script — everything except actually touching the
network or running an installer.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import hashlib
import io
import json
import os
import sys

import pytest

from khervesheet import updater


# ---------------------------------------------------------------------------
# Fixtures — a stand-in for the GitHub releases payload
# ---------------------------------------------------------------------------

def _asset(name, size=1234, digest=None):
    return {
        "name": name,
        "size": size,
        "browser_download_url": f"https://example.invalid/{name}",
        "digest": digest,
    }


def _entry(tag, assets=(), draft=False, prerelease=False, body="notes"):
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "body": body,
        "html_url": f"https://example.invalid/releases/{tag}",
        "assets": list(assets),
    }


def _ksheet(version):
    return _entry(f"khervesheet-v{version}",
                  [_asset(f"Setup_KherveSheet_{version}.exe")])


# ---------------------------------------------------------------------------
# Version parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("0.1.610", (0, 1, 610)),
    ("v0.1.610", (0, 1, 610)),
    ("khervesheet-v0.1.610", (0, 1, 610)),
    ("0.1.610+9c0255f", (0, 1, 610)),
    ("1.2", (1, 2)),
    ("", ()),
    (None, ()),
    ("nightly", ()),
])
def test_version_tuple(text, expected):
    assert updater.version_tuple(text) == expected


def test_version_tuple_orders_numerically_not_lexically():
    # "0.1.99" > "0.1.610" as strings; the tuple must disagree.
    assert updater.version_tuple("0.1.610") > updater.version_tuple("0.1.99")


def test_current_version_is_parseable():
    assert updater.current_version_tuple()


# ---------------------------------------------------------------------------
# Release selection
# ---------------------------------------------------------------------------

def test_release_from_json_reads_every_field():
    rel = updater._release_from_json(_ksheet("0.1.610"))
    assert rel is not None
    assert rel.version_text == "0.1.610"
    assert rel.version == (0, 1, 610)
    assert rel.tag == "khervesheet-v0.1.610"
    assert rel.asset_name == "Setup_KherveSheet_0.1.610.exe"
    assert rel.asset_url.endswith("Setup_KherveSheet_0.1.610.exe")
    assert rel.notes == "notes"


@pytest.mark.parametrize("entry", [
    _entry("khervesheet-v0.1.700",
           [_asset("Setup_KherveSheet_0.1.700.exe")], draft=True),
    _entry("khervesheet-v0.1.700",
           [_asset("Setup_KherveSheet_0.1.700.exe")], prerelease=True),
    # Another Kherve app sharing the downloads repo.
    _entry("khervefitting-v2.0.0", [_asset("Setup_KherveSheet_2.0.0.exe")]),
    # Untagged / unprefixed release.
    _entry("v0.1.700", [_asset("Setup_KherveSheet_0.1.700.exe")]),
    # Right release, but no installer to fetch (zip-only).
    _entry("khervesheet-v0.1.700", [_asset("KherveSheet_0.1.700.zip")]),
    _entry("khervesheet-vnightly", [_asset("Setup_KherveSheet_0.1.700.exe")]),
])
def test_release_from_json_rejects(entry):
    assert updater._release_from_json(entry) is None


def test_release_prefers_the_exactly_named_installer():
    entry = _entry("khervesheet-v0.1.610", [
        _asset("Setup_KherveSheet_0.1.609.exe"),
        _asset("Setup_KherveSheet_0.1.610.exe"),
    ])
    rel = updater._release_from_json(entry)
    assert rel.asset_name == "Setup_KherveSheet_0.1.610.exe"


def test_release_falls_back_to_any_installer():
    entry = _entry("khervesheet-v0.1.611",
                   [_asset("Setup_KherveSheet_0.1.610.exe")])
    rel = updater._release_from_json(entry)
    assert rel.asset_name == "Setup_KherveSheet_0.1.610.exe"


# ---------------------------------------------------------------------------
# fetch_latest_release
# ---------------------------------------------------------------------------

def _fake_urlopen(payload):
    class _Resp(io.BytesIO):
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    def opener(req, timeout=None):
        return _Resp(json.dumps(payload).encode("utf-8"))
    return opener


def test_fetch_latest_picks_highest_version(monkeypatch):
    payload = [_ksheet("0.1.600"), _ksheet("0.1.610"), _ksheet("0.1.605")]
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        _fake_urlopen(payload))
    assert updater.fetch_latest_release().version_text == "0.1.610"


def test_fetch_latest_ignores_other_apps(monkeypatch):
    payload = [_entry("khervefitting-v9.9.9",
                      [_asset("Setup_KherveFitting_9.9.9.exe")]),
               _ksheet("0.1.610")]
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        _fake_urlopen(payload))
    assert updater.fetch_latest_release().version_text == "0.1.610"


def test_fetch_latest_returns_none_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        _fake_urlopen([_entry("khervebook-v1.0.0")]))
    assert updater.fetch_latest_release() is None


def test_is_newer_than_current(monkeypatch):
    monkeypatch.setattr(updater, "current_version_tuple", lambda: (0, 1, 610))
    assert updater._release_from_json(
        _ksheet("0.1.611")).is_newer_than_current()
    assert not updater._release_from_json(
        _ksheet("0.1.610")).is_newer_than_current()
    assert not updater._release_from_json(
        _ksheet("0.1.609")).is_newer_than_current()


# ---------------------------------------------------------------------------
# Digest verification and the download cache
# ---------------------------------------------------------------------------

def test_verify_digest(tmp_path):
    f = tmp_path / "payload.bin"
    f.write_bytes(b"hello")
    good = hashlib.sha256(b"hello").hexdigest()
    assert updater._verify_digest(str(f), f"sha256:{good}")
    assert not updater._verify_digest(str(f), "sha256:" + "0" * 64)
    # No digest, or one we don't understand, is not a failure.
    assert updater._verify_digest(str(f), "")
    assert updater._verify_digest(str(f), "md5:whatever")


def test_purge_stale_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "current_version_tuple", lambda: (0, 1, 610))
    for name in ("Setup_KherveSheet_0.1.600.exe",
                 "Setup_KherveSheet_0.1.610.exe",
                 "Setup_KherveSheet_0.1.620.exe",
                 "apply_update.bat", "install.log", "keep-me.ksheet"):
        (tmp_path / name).write_text("x")

    updater.purge_stale_downloads()

    left = sorted(os.listdir(tmp_path))
    assert left == ["Setup_KherveSheet_0.1.620.exe", "keep-me.ksheet"]


def test_purge_survives_a_missing_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir",
                        lambda: str(tmp_path / "nope"))
    updater.purge_stale_downloads()      # must not raise


def test_download_reuses_a_verified_cached_installer(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    rel = updater._release_from_json(_ksheet("0.1.610"))
    cached = tmp_path / rel.asset_name
    cached.write_bytes(b"installer")
    rel.digest = "sha256:" + hashlib.sha256(b"installer").hexdigest()

    def _boom(*a, **k):
        raise AssertionError("should not hit the network")
    monkeypatch.setattr(updater.urllib.request, "urlopen", _boom)

    assert updater.download_installer(rel) == str(cached)


def test_download_rejects_a_corrupt_installer(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    rel = updater._release_from_json(_ksheet("0.1.610"))
    rel.digest = "sha256:" + "0" * 64

    class _Resp(io.BytesIO):
        headers = {"Content-Length": "9"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(b"installer"))

    with pytest.raises(RuntimeError):
        updater.download_installer(rel)
    # Nothing half-downloaded is left claiming to be the installer.
    assert os.listdir(tmp_path) == []


def test_download_writes_and_reports_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    rel = updater._release_from_json(_ksheet("0.1.610"))

    class _Resp(io.BytesIO):
        headers = {"Content-Length": "9"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    monkeypatch.setattr(updater.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(b"installer"))
    seen = []
    path = updater.download_installer(rel, progress=lambda d, t: seen.append(
        (d, t)))

    assert open(path, "rb").read() == b"installer"
    assert seen and seen[-1] == (9, 9)


# ---------------------------------------------------------------------------
# Installer hand-off
# ---------------------------------------------------------------------------

def test_launch_installer_refuses_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    assert not updater.launch_installer(str(tmp_path / "nope.exe"))


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason="Windows-only hand-off")
def test_launch_installer_never_combines_no_window_with_detached(
        tmp_path, monkeypatch):
    # Regression: CREATE_NO_WINDOW | DETACHED_PROCESS is an illegal
    # combination — Popen succeeds but the helper never runs a line, so
    # the update silently does nothing.
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    installer = tmp_path / "Setup_KherveSheet_0.1.620.exe"
    installer.write_bytes(b"MZ")

    seen = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
            seen["flags"] = kw.get("creationflags", 0)
    monkeypatch.setattr(updater.subprocess, "Popen", _FakePopen)

    assert updater.launch_installer(str(installer))
    detached = 0x00000008
    assert not seen["flags"] & detached
    assert seen["flags"] == updater.subprocess.CREATE_NO_WINDOW
    assert seen["cmd"][0] == "cmd.exe"


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason="Windows-only hand-off")
def test_launch_installer_falls_back_when_the_bat_cannot_be_written(
        tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "update_cache_dir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "_write_helper_bat",
                        lambda script, body: False)
    installer = tmp_path / "Setup_KherveSheet_0.1.620.exe"
    installer.write_bytes(b"MZ")

    seen = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
    monkeypatch.setattr(updater.subprocess, "Popen", _FakePopen)

    assert updater.launch_installer(str(installer))
    assert seen["cmd"][0] == "powershell.exe"


def test_helper_bat_is_written_in_the_console_codepage(tmp_path,
                                                       monkeypatch):
    # cmd reads .bat in the OEM codepage; a cp1252-only name must survive.
    monkeypatch.setattr(updater, "_oem_encoding", lambda: "cp1252")
    script = tmp_path / "apply_update.bat"
    assert updater._write_helper_bat(str(script), "echo Bj\u00f6rn\n")
    assert script.read_bytes().decode("cp1252") == "echo Bj\u00f6rn\r\n"


def test_helper_bat_refuses_paths_the_codepage_cannot_spell(tmp_path,
                                                            monkeypatch):
    # A Cyrillic profile name on a Western codepage: writing it would
    # silently mangle the path, so the batch route must decline.
    monkeypatch.setattr(updater, "_oem_encoding", lambda: "cp850")
    script = tmp_path / "apply_update.bat"
    assert not updater._write_helper_bat(
        str(script), "echo C:\\Users\\\u0410\u043d\u043d\u0430\n")


def test_powershell_fallback_is_decodable_and_complete():
    import base64
    cmd = updater._powershell_command(
        r"C:\Users\Anna\Setup_KherveSheet_0.1.620.exe",
        r"C:\Program Files\KherveSheet\KherveSheet.exe")
    assert cmd[0] == "powershell.exe"
    assert "-EncodedCommand" in cmd
    body = base64.b64decode(cmd[-1]).decode("utf-16-le")
    assert f"Wait-Process -Id {os.getpid()}" in body
    assert "'/VERYSILENT'" in body
    assert r"Start-Process -FilePath 'C:\Program Files\KherveSheet" in body


def test_powershell_fallback_escapes_quotes_in_paths():
    import base64
    cmd = updater._powershell_command(r"C:\Users\O'Brien\Setup.exe",
                                      r"C:\App\KherveSheet.exe")
    body = base64.b64decode(cmd[-1]).decode("utf-16-le")
    assert r"'C:\Users\O''Brien\Setup.exe'" in body


def test_helper_script_waits_then_installs_and_restarts():
    body = updater._HELPER_BAT.format(
        pid=4321, installer=r"C:\cache\Setup_KherveSheet_0.1.620.exe",
        args=" ".join(updater.INSTALLER_ARGS), log=r"C:\cache\install.log",
        exe=r"C:\Program Files\KherveSheet\KherveSheet.exe")
    # Waits for this process to die before replacing any files.
    assert 'tasklist /FI "PID eq 4321"' in body
    assert "/VERYSILENT" in body and "/SUPPRESSMSGBOXES" in body
    assert "/NORESTARTAPPLICATIONS" in body
    # Relaunches the app and cleans itself up.
    assert r'start "" "C:\Program Files\KherveSheet\KherveSheet.exe"' in body
    assert 'del "%~f0"' in body
