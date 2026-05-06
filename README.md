# commidget

A macOS menu-bar widget that nags you about uncommitted git changes.

- Lives in the menu bar next to your clock/battery (`⎇ N` where N is total uncommitted changes).
- Click the icon to see every repo under your scan directory and how many uncommitted changes each has, with the age of the oldest change.
- Sends a (lightly berating) macOS notification when changes have been sitting uncommitted for more than 24 hours.

## Install

Already done in this directory:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```
./run.sh
```

Look for `⎇` in the top-right menu bar.

## Run at login

```
./install-autostart.sh
```

Removes:

```
./uninstall-autostart.sh
```

## Configure

Click the menu-bar icon → "change scan directory…" to pick a different folder.

Or edit `~/.commidget/config.json` directly:

```json
{
  "scan_dir": "/Users/hugo/Documents",
  "scan_interval_seconds": 300,
  "stale_threshold_hours": 24,
  "renag_interval_hours": 12,
  "max_depth": 5
}
```

After editing, quit commidget from the menu and re-launch.

## Notes

- Change age is inferred from the mtime of the modified files, so it survives restarts and accurately reflects how long each change has actually been sitting.
- One combined notification per refresh — if multiple repos go stale at once you get a single nag, not a flood.
- Per-repo cooldown (`renag_interval_hours`) prevents the same repo from being mentioned more than once per 12 hours.
- Skips `node_modules`, `.venv`, `__pycache__`, etc. while walking. Doesn't descend into a repo once it finds one.

## Files

- `commidget.py` — the app
- `run.sh` — launcher (uses `.venv`)
- `install-autostart.sh` / `uninstall-autostart.sh` — LaunchAgent setup
- `~/.commidget/config.json` — settings
- `~/.commidget/state.json` — per-repo notification cooldowns
# commidget
