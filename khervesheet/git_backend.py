"""Per-document Git repo with auto-commit on save.

Each .ksheet file lives in a directory that is also its own git repo.
Every save creates a commit so the user can browse the full edit history
locally or on GitHub.

Falls back gracefully if pygit2 is unavailable: every function becomes
a no-op and returns False, so the editor still works.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import pygit2
    _PYGIT2_OK = True
except Exception:
    pygit2 = None  # type: ignore
    _PYGIT2_OK = False


def is_available() -> bool:
    return _PYGIT2_OK


def _find_enclosing_repo(repo_dir: Path) -> Path | None:
    """Walk up the directory tree; if any ancestor has a .git, return it."""
    cur = repo_dir.resolve()
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return None


def init_repo(repo_dir: Path) -> bool:
    """Initialise a git repo in `repo_dir` if one doesn't already exist."""
    if not _PYGIT2_OK:
        return False
    repo_dir.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").exists():
        return True
    if _find_enclosing_repo(repo_dir) is not None:
        return True
    pygit2.init_repository(str(repo_dir), bare=False)
    head_file = repo_dir / ".git" / "HEAD"
    head_file.write_text("ref: refs/heads/dev\n", encoding="utf-8")
    return True


def _repo_for(repo_dir: Path) -> "pygit2.Repository | None":
    """Return the pygit2.Repository governing `repo_dir`."""
    try:
        if (repo_dir / ".git").exists():
            return pygit2.Repository(str(repo_dir))
        enclosing = _find_enclosing_repo(repo_dir)
        return pygit2.Repository(str(enclosing)) if enclosing else None
    except Exception:
        return None


def _signature(repo: "pygit2.Repository | None" = None) -> "pygit2.Signature":
    """Build a commit signature, preferring the user's git identity."""
    if repo is not None:
        try:
            return repo.default_signature
        except (KeyError, pygit2.GitError):
            pass
    return pygit2.Signature(
        "KherveSheet", "khervesheet@local",
        int(datetime.now().timestamp()), 0)


def commit_all(repo_dir: Path, message: str | None = None,
               file_stem: str | None = None) -> str | None:
    """Stage files and create a commit. Returns hex OID or None."""
    if not _PYGIT2_OK:
        return None
    init_repo(repo_dir)

    repo = _repo_for(repo_dir)
    if repo is None:
        return None
    index = repo.index
    if file_stem:
        repo_root = Path(repo.workdir)
        for p in repo_root.iterdir():
            if p.name.startswith(file_stem) and p.is_file():
                rel = str(p.relative_to(repo_root)).replace("\\", "/")
                index.add(rel)
    else:
        index.add_all()
    index.write()

    new_tree_oid = index.write_tree()
    parents: list[str] = []
    if not repo.head_is_unborn:
        head_commit = repo.head.peel(pygit2.Commit)
        if head_commit.tree_id == new_tree_oid:
            return None
        parents = [head_commit.id]

    sig = _signature(repo)
    msg = message or f"Edit at {datetime.now().isoformat(timespec='seconds')}"
    commit_oid = repo.create_commit(
        "HEAD" if repo.head_is_unborn else repo.head.name,
        sig, sig, msg, new_tree_oid, parents,
    )
    return str(commit_oid)


def _credentials_callbacks() -> "pygit2.RemoteCallbacks":
    try:
        return pygit2.RemoteCallbacks(
            credentials=pygit2.KeypairFromAgent("git"))
    except Exception:
        return pygit2.RemoteCallbacks()


def get_remotes(repo_dir: Path) -> list[tuple[str, str]]:
    """Return [(name, url), ...] for every configured remote."""
    if not _PYGIT2_OK:
        return []
    repo = _repo_for(repo_dir)
    if repo is None:
        return []
    return [(r.name, r.url) for r in repo.remotes]


def set_remote(repo_dir: Path, name: str, url: str) -> bool:
    """Add or update a remote. Returns True on success."""
    if not _PYGIT2_OK or not name or not url:
        return False
    init_repo(repo_dir)
    repo = _repo_for(repo_dir)
    if repo is None:
        return False
    try:
        existing = {r.name for r in repo.remotes}
        if name in existing:
            repo.remotes.set_url(name, url)
        else:
            repo.remotes.create(name, url)
        return True
    except Exception:
        return False


def remove_remote(repo_dir: Path, name: str) -> bool:
    if not _PYGIT2_OK:
        return False
    repo = _repo_for(repo_dir)
    if repo is None:
        return False
    try:
        repo.remotes.delete(name)
        return True
    except Exception:
        return False


def current_branch(repo_dir: Path) -> str | None:
    """Short name of the current branch, or None."""
    if not _PYGIT2_OK:
        return None
    try:
        repo = _repo_for(repo_dir)
        if repo is None or repo.head_is_unborn or repo.head_is_detached:
            return None
        name = repo.head.name
        if name.startswith("refs/heads/"):
            return name[len("refs/heads/"):]
        return name
    except Exception:
        return None


def pull(repo_dir: Path, remote_name: str = "origin") -> tuple[bool, str]:
    """Fetch and fast-forward. Returns (ok, message)."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    if remote_name not in [r.name for r in repo.remotes]:
        return False, f"No remote named {remote_name!r} is configured."
    remote = repo.remotes[remote_name]

    def _fetch() -> tuple[bool, str]:
        for cb in (_credentials_callbacks(), None):
            try:
                remote.fetch(callbacks=cb) if cb else remote.fetch()
                return True, ""
            except Exception as exc:
                last = str(exc)
        return False, last

    ok, err = _fetch()
    if not ok:
        return False, f"Fetch failed: {err}"

    branch = current_branch(repo_dir)
    if branch is None:
        return False, "Repository has no current branch."
    upstream_ref = f"refs/remotes/{remote_name}/{branch}"
    try:
        upstream_oid = repo.lookup_reference(upstream_ref).target
    except Exception:
        return False, (
            f"Remote {remote_name!r} has no branch {branch!r}.")

    head_oid = repo.head.target
    if head_oid == upstream_oid:
        return True, "Already up to date."
    merge_analysis, _ = repo.merge_analysis(upstream_oid)
    if merge_analysis & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        return True, "Already up to date."
    if not (merge_analysis & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD):
        return False, (
            "Local branch has diverged — only fast-forward is supported. "
            "Resolve the merge from a terminal.")

    walker = repo.walk(upstream_oid, pygit2.GIT_SORT_NONE)
    walker.hide(head_oid)
    incoming = sum(1 for _ in walker)
    try:
        repo.checkout_tree(repo.get(upstream_oid))
        repo.references.get(repo.head.name).set_target(upstream_oid)
        repo.set_head(repo.head.name)
    except Exception as exc:
        return False, f"Fast-forward failed: {exc}"
    plural = "" if incoming == 1 else "s"
    return True, f"Pulled {incoming} commit{plural} from {remote_name}/{branch}."


def _system_git_available() -> bool:
    return shutil.which("git") is not None


def _git_cli_push(repo_dir: Path, remote_name: str,
                  ref: str) -> tuple[bool, str]:
    try:
        kw: dict = dict(cwd=str(repo_dir), capture_output=True,
                        text=True, timeout=60)
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(["git", "push", remote_name, ref], **kw)
    except subprocess.TimeoutExpired:
        return False, "git push timed out after 60s."
    except FileNotFoundError:
        return False, "System git is not on PATH."
    if proc.returncode == 0:
        return True, f"Pushed to {remote_name}."
    err = (proc.stderr or proc.stdout or "").strip()
    for line in reversed(err.splitlines()):
        line = line.strip()
        if line.startswith(("fatal:", "error:", "remote:")):
            return False, line
    return False, err.splitlines()[-1] if err else \
        f"git push exited with code {proc.returncode}."


def push(repo_dir: Path, remote_name: str = "origin",
         branch: str = "main") -> tuple[bool, str]:
    """Push to remote. Returns (ok, message)."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    if not (repo_dir / ".git").exists():
        return False, "Not a git repository."

    libgit2_err = ""
    head_ref = None
    remote_url = ""
    try:
        repo = pygit2.Repository(str(repo_dir))
        if remote_name not in [r.name for r in repo.remotes]:
            return False, f"No remote named {remote_name!r} is configured."
        remote = repo.remotes[remote_name]
        remote_url = remote.url
        if repo.head_is_unborn:
            return False, "Repository has no commits yet — save first."
        head_ref = repo.head.name
        refspec = f"{head_ref}:{head_ref}"

        try:
            cb = pygit2.RemoteCallbacks(
                credentials=pygit2.KeypairFromAgent("git"))
            remote.push([refspec], callbacks=cb)
            return True, f"Pushed to {remote_name}."
        except Exception as exc:
            libgit2_err = str(exc)
        try:
            remote.push([refspec])
            return True, f"Pushed to {remote_name}."
        except Exception as exc:
            libgit2_err = str(exc)
    except Exception as exc:
        libgit2_err = str(exc)

    if head_ref and _system_git_available():
        ok, msg = _git_cli_push(repo_dir, remote_name, head_ref)
        return ok, msg

    hint = ""
    if remote_url.startswith("http"):
        hint = (" Tip: install Git for Windows so the credential "
                "manager handles your token, or use SSH.")
    return False, f"Push failed: {libgit2_err}.{hint}"


def restore_to_commit(repo_dir: Path, oid: str,
                      paths: list[str] | None = None) -> tuple[bool, str]:
    """Reset working tree files to their state at `oid` without moving HEAD."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    try:
        commit = repo.get(oid)
        if commit is None:
            return False, f"Commit {oid[:8]!r} not found."
        commit = commit.peel(pygit2.Commit)
        tree = commit.tree
    except Exception as exc:
        return False, f"Could not read commit: {exc}"
    try:
        if paths:
            for p in paths:
                try:
                    entry = tree[p]
                except KeyError:
                    continue
                blob = repo.get(entry.id)
                if blob is None:
                    continue
                target = repo_dir / p
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob.data)
        else:
            repo.checkout_tree(
                tree,
                strategy=(pygit2.GIT_CHECKOUT_FORCE
                          | pygit2.GIT_CHECKOUT_RECREATE_MISSING),
            )
    except Exception as exc:
        return False, f"Restore failed: {exc}"
    return True, f"Restored files to {oid[:8]}."


def history(repo_dir: Path, limit: int = 50) -> list[tuple[str, str, str]]:
    """Return [(short_oid, iso_time, message_first_line), ...] newest first."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []
    out: list[tuple[str, str, str]] = []
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        out.append((
            str(commit.id)[:8],
            datetime.fromtimestamp(commit.commit_time).isoformat(
                timespec="seconds"),
            commit.message.splitlines()[0] if commit.message else "",
        ))
        if len(out) >= limit:
            break
    return out


def history_detailed(repo_dir: Path, limit: int = 200) -> list[dict]:
    """Richer version for the GUI commit-browser."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []
    out: list[dict] = []
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        msg = (commit.message or "").rstrip()
        lines = msg.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:]).strip("\n") if len(lines) > 1 else ""
        author = commit.author
        out.append({
            "oid": str(commit.id),
            "short_oid": str(commit.id)[:8],
            "timestamp": datetime.fromtimestamp(
                commit.commit_time).isoformat(timespec="seconds"),
            "epoch": int(commit.commit_time),
            "author": f"{author.name} <{author.email}>",
            "subject": subject,
            "body": body,
        })
        if len(out) >= limit:
            break
    return out


def history_graph(repo_dir: Path, limit: int = 300) -> list[dict]:
    """Build a commit list with graph-rail info for DAG visualisation."""
    if not _PYGIT2_OK:
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []

    branch_map: dict[str, list[str]] = {}
    for ref_name in repo.references:
        if ref_name.startswith("refs/heads/"):
            short = ref_name[len("refs/heads/"):]
            try:
                oid = str(repo.references[ref_name].peel(
                    pygit2.Commit).id)
            except Exception:
                continue
            branch_map.setdefault(oid, []).append(short)
        elif ref_name.startswith("refs/remotes/"):
            parts = ref_name[len("refs/remotes/"):].split("/", 1)
            if len(parts) == 2 and parts[1] != "HEAD":
                try:
                    oid = str(repo.references[ref_name].peel(
                        pygit2.Commit).id)
                except Exception:
                    continue
                branch_map.setdefault(oid, []).append(
                    f"{parts[0]}/{parts[1]}")

    seen: set[str] = set()
    raw_commits: list = []
    for ref_name in repo.references:
        try:
            tip = repo.references[ref_name].peel(pygit2.Commit)
        except Exception:
            continue
        for commit in repo.walk(
                tip.id,
                pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
            oid = str(commit.id)
            if oid in seen:
                continue
            seen.add(oid)
            raw_commits.append(commit)
            if len(raw_commits) >= limit:
                break
        if len(raw_commits) >= limit:
            break

    raw_commits.sort(key=lambda c: -c.commit_time)

    active: list[str | None] = []
    rows: list[dict] = []
    for commit in raw_commits:
        oid = str(commit.id)
        parent_oids = [str(p.id) for p in commit.parents]
        msg = (commit.message or "").rstrip()
        lines = msg.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:]).strip("\n") if len(lines) > 1 else ""
        author = commit.author

        if oid in active:
            rail = active.index(oid)
        else:
            if None in active:
                rail = active.index(None)
                active[rail] = oid
            else:
                rail = len(active)
                active.append(oid)

        rails_before = [(i, i) for i, a in enumerate(active)
                        if a is not None]

        if not parent_oids:
            active[rail] = None
        elif len(parent_oids) == 1:
            active[rail] = parent_oids[0]
        else:
            active[rail] = parent_oids[0]
            for extra_parent in parent_oids[1:]:
                if extra_parent not in active:
                    if None in active:
                        slot = active.index(None)
                        active[slot] = extra_parent
                    else:
                        active.append(extra_parent)

        while active and active[-1] is None:
            active.pop()

        rails_after = [(i, i) for i, a in enumerate(active)
                       if a is not None]

        rows.append({
            "oid": oid,
            "short_oid": oid[:8],
            "timestamp": datetime.fromtimestamp(
                commit.commit_time).isoformat(timespec="seconds"),
            "epoch": int(commit.commit_time),
            "author": f"{author.name} <{author.email}>",
            "subject": subject,
            "body": body,
            "parents": parent_oids,
            "rail": rail,
            "rails_before": rails_before,
            "rails_after": rails_after,
            "branches": branch_map.get(oid, []),
            "is_merge": len(parent_oids) > 1,
        })

    return rows


def diff_for_commit(repo_dir: Path, oid: str) -> str:
    """Return the unified diff for the given commit."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return ""
    repo = _repo_for(repo_dir)
    if repo is None:
        return ""
    try:
        commit = repo.get(oid)
        if commit is None:
            return ""
        commit = commit.peel(pygit2.Commit)
    except Exception:
        return ""
    parents = list(commit.parents)
    try:
        if parents:
            diff = repo.diff(parents[0], commit, context_lines=3)
        else:
            diff = commit.tree.diff_to_tree(swap=True, context_lines=3)
    except Exception:
        return ""
    return diff.patch or ""


def list_branches(repo_dir: Path) -> list[dict]:
    """Return info about every local and remote-tracking branch."""
    if not _PYGIT2_OK:
        return []
    repo = _repo_for(repo_dir)
    if repo is None:
        return []
    cur = current_branch(repo_dir)
    out: list[dict] = []
    for ref_name in repo.references:
        if ref_name.startswith("refs/heads/"):
            short = ref_name[len("refs/heads/"):]
            try:
                oid = str(repo.references[ref_name].peel(
                    pygit2.Commit).id)
            except Exception:
                continue
            out.append({"name": short, "ref": ref_name, "oid": oid,
                        "current": short == cur, "remote": None})
        elif ref_name.startswith("refs/remotes/"):
            parts = ref_name[len("refs/remotes/"):].split("/", 1)
            if len(parts) == 2 and parts[1] != "HEAD":
                try:
                    oid = str(repo.references[ref_name].peel(
                        pygit2.Commit).id)
                except Exception:
                    continue
                out.append({"name": parts[1], "ref": ref_name, "oid": oid,
                            "current": False, "remote": parts[0]})
    return out


def create_branch(repo_dir: Path, name: str,
                  start_oid: str | None = None) -> tuple[bool, str]:
    """Create a new local branch."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    if repo.head_is_unborn:
        return False, "Repository has no commits yet — save first."
    try:
        if start_oid:
            target = repo.get(start_oid).peel(pygit2.Commit)
        else:
            target = repo.head.peel(pygit2.Commit)
        repo.branches.local.create(name, target)
        return True, f"Branch '{name}' created."
    except Exception as exc:
        return False, str(exc)


def switch_branch(repo_dir: Path, name: str) -> tuple[bool, str]:
    """Switch HEAD to an existing local branch."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    ref = f"refs/heads/{name}"
    try:
        branch_ref = repo.references[ref]
    except KeyError:
        return False, f"Branch '{name}' does not exist."
    try:
        commit = branch_ref.peel(pygit2.Commit)
        repo.checkout_tree(commit, strategy=pygit2.GIT_CHECKOUT_SAFE)
        repo.set_head(ref)
        return True, f"Switched to branch '{name}'."
    except Exception as exc:
        return False, str(exc)


def delete_branch(repo_dir: Path, name: str) -> tuple[bool, str]:
    """Delete a local branch."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    cur = current_branch(repo_dir)
    if name == cur:
        return False, "Cannot delete the branch you are currently on."
    try:
        branch = repo.branches.local[name]
        branch.delete()
        return True, f"Branch '{name}' deleted."
    except KeyError:
        return False, f"Branch '{name}' does not exist."
    except Exception as exc:
        return False, str(exc)
