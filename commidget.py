#!/usr/bin/env python3
"""commidget — macOS menu-bar widget that nags you about uncommitted git changes."""

import json
import os
import random
import subprocess
import time
from pathlib import Path

import rumps

CONFIG_DIR = Path.home() / ".commidget"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "state.json"

DEFAULT_CONFIG = {
    "scan_dir": str(Path.home() / "Documents"),
    "scan_interval_seconds": 300,
    "stale_threshold_hours": 24,
    "renag_interval_hours": 12,
    "max_depth": 5,
}

NAGS_SINGLE = [
    "{repo} has {n} uncommitted change{s} aged {age}. Maybe... commit them?",
    "{repo}: {n} change{s} loitering for {age}. Your future self is unimpressed.",
    "Pssst — {repo} is sitting on {n} change{s}, oldest {age}. Just sayin'.",
    "{repo}: {n} uncommitted file{s}, oldest {age}. Not aging like wine.",
    "Hey. {repo} → {n} change{s}, {age} old. `git commit` is right there.",
]

NAGS_MULTI = [
    "{count} repos with stale changes: {names}. Get on it.",
    "Stale alert — {names}. Your git history is gathering dust.",
    "{names} — none of these have been committed in over a day. Disappointing.",
    "You've got uncommitted work languishing in {names}. Just commit, mate.",
    "{count} repos overdue for a commit: {names}. Tsk.",
]


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(default) if isinstance(default, dict) else default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def find_git_repos(root, max_depth):
    root = Path(root).expanduser()
    if not root.exists():
        return

    def walk(path, depth):
        try:
            entries = list(path.iterdir())
        except (PermissionError, OSError):
            return
        if any(e.name == ".git" for e in entries):
            yield path
            return
        if depth >= max_depth:
            return
        for e in entries:
            if not e.is_dir() or e.is_symlink():
                continue
            if e.name.startswith("."):
                continue
            if e.name in ("node_modules", "venv", ".venv", "__pycache__", "Library"):
                continue
            yield from walk(e, depth + 1)

    yield from walk(root, 0)


def _status_glyph(xy):
    """Map two-char porcelain status to a single visible glyph."""
    if xy == "??":
        return "?"
    # prefer the worktree (unstaged) char if present, else the index char
    for c in (xy[1], xy[0]):
        if c not in (" ", ""):
            return c
    return "·"


def repo_status(repo_path):
    """Return (files, oldest_mtime). files is a list of (glyph, relpath) tuples."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return [], None

    if result.returncode != 0:
        return [], None

    files = []
    oldest = None
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        xy = line[:2]
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        rest = rest.strip().strip('"')
        if not rest:
            continue
        files.append((_status_glyph(xy), rest))
        try:
            mtime = (repo_path / rest).stat().st_mtime
        except OSError:
            continue
        if oldest is None or mtime < oldest:
            oldest = mtime

    return files, oldest


def format_age(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h"
    return f"{int(seconds / 86400)}d"


def _as_str(s):
    """AppleScript string literal: escape backslash and double-quote, strip newlines."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


def macos_notify(title, message):
    script = (
        f"display notification {_as_str(message)} "
        f"with title {_as_str(title)} "
        f'sound name "Submarine"'
    )
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


class Commidget(rumps.App):
    def __init__(self):
        super().__init__("commidget", title="⎇", quit_button=None)
        self.config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
        for k, v in DEFAULT_CONFIG.items():
            self.config.setdefault(k, v)
        save_json(CONFIG_FILE, self.config)
        self.state = load_json(STATE_FILE, {})
        self.repos = []
        self._first_tick = True
        self.timer = rumps.Timer(self._tick, self.config["scan_interval_seconds"])
        self.refresh()
        # rumps Timer fires immediately on start(); the first tick will be a no-op refresh
        self.timer.start()

    def _tick(self, _):
        if self._first_tick:
            self._first_tick = False
            return
        self.refresh()

    def refresh(self):
        scan_dir = self.config["scan_dir"]
        repos = []
        for repo_path in find_git_repos(scan_dir, self.config["max_depth"]):
            files, oldest = repo_status(repo_path)
            if files:
                repos.append((repo_path, files, oldest))
        repos.sort(key=lambda r: (-len(r[1]), str(r[0])))
        self.repos = repos
        self._update_menu()
        self._maybe_notify()
        save_json(STATE_FILE, self.state)

    def _update_menu(self):
        total = sum(len(r[1]) for r in self.repos)
        self.title = f"⎇ {total}" if total else "⎇"

        items = []
        scan_dir = self.config["scan_dir"]
        if not self.repos:
            items.append(rumps.MenuItem(f"✓ all clean in {Path(scan_dir).name}", callback=None))
        else:
            header = (
                f"{total} change{'s' if total != 1 else ''} "
                f"across {len(self.repos)} repo{'s' if len(self.repos) != 1 else ''}"
            )
            items.append(rumps.MenuItem(header, callback=None))
            items.append(rumps.separator)
            now = time.time()
            seen_labels = {}
            for path, files, oldest in self.repos:
                try:
                    rel = path.relative_to(scan_dir)
                    display = str(rel)
                except ValueError:
                    display = path.name
                age_str = ""
                if oldest is not None:
                    age_str = f"  [{format_age(now - oldest)}]"
                label = f"{display}: {len(files)}{age_str}"
                if label in seen_labels:
                    seen_labels[label] += 1
                    label = f"{label} ({seen_labels[label]})"
                else:
                    seen_labels[label] = 1
                parent = rumps.MenuItem(label)
                parent.add(rumps.MenuItem("open repo in Finder", callback=self._open_path(path)))
                parent.add(rumps.separator)
                seen_files = {}
                for glyph, relpath in files:
                    file_label = f"{glyph}  {relpath}"
                    if file_label in seen_files:
                        seen_files[file_label] += 1
                        file_label = f"{file_label} ({seen_files[file_label]})"
                    else:
                        seen_files[file_label] = 1
                    parent.add(rumps.MenuItem(file_label, callback=self._open_path(path / relpath)))
                items.append(parent)

        items.append(rumps.separator)
        items.append(rumps.MenuItem(f"scan dir: {scan_dir}", callback=None))
        items.append(rumps.MenuItem("change scan directory…", callback=self.change_scan_dir))
        items.append(rumps.MenuItem("refresh now", callback=self.manual_refresh))
        items.append(rumps.separator)
        items.append(rumps.MenuItem("quit commidget", callback=rumps.quit_application))

        self.menu.clear()
        self.menu.update(items)

    def _open_path(self, path):
        def cb(_):
            subprocess.run(["open", str(path)], check=False)
        return cb

    def change_scan_dir(self, _):
        script = (
            'POSIX path of (choose folder with prompt '
            '"Select directory to scan for git repos:")'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=300,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return
        new_dir = result.stdout.strip()
        if not new_dir:
            return
        self.config["scan_dir"] = new_dir.rstrip("/")
        save_json(CONFIG_FILE, self.config)
        self.state = {}
        self.refresh(initial=True)

    def manual_refresh(self, _):
        self.refresh()

    def _maybe_notify(self):
        threshold = self.config["stale_threshold_hours"] * 3600
        renag = self.config["renag_interval_hours"] * 3600
        now = time.time()
        current_keys = set()
        to_nag = []  # (path, count, age_seconds)
        for path, files, oldest in self.repos:
            key = str(path)
            current_keys.add(key)
            if oldest is None:
                continue
            age = now - oldest
            if age < threshold:
                self.state.pop(key, None)
                continue
            last_notified = self.state.get(key, {}).get("last_notified", 0)
            if now - last_notified < renag:
                continue
            to_nag.append((path, len(files), age))
        for key in list(self.state.keys()):
            if key not in current_keys:
                del self.state[key]
        if not to_nag:
            return
        if len(to_nag) == 1:
            path, count, age = to_nag[0]
            msg = random.choice(NAGS_SINGLE).format(
                repo=path.name,
                n=count,
                s="s" if count != 1 else "",
                age=format_age(age),
            )
        else:
            names = ", ".join(f"{p.name} ({format_age(a)})" for p, _, a in to_nag)
            msg = random.choice(NAGS_MULTI).format(count=len(to_nag), names=names)
        macos_notify("commidget", msg)
        for path, _, _ in to_nag:
            self.state[str(path)] = {"last_notified": now}


if __name__ == "__main__":
    Commidget().run()
