#!/usr/bin/env python3
"""Config manager for /watch plugin.

Reads ~/.config/watch/config.json, merges with defaults. Safe to import
anywhere in the scripts package — has no side effects on import.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / "config.json"

_OBSIDIAN_VAULT = (
    Path.home()
    / "OneDrive - L55 Conseils inc"
    / "ML Obsidian Vault"
    / "01 - Source Material"
)

DEFAULTS: dict[str, Any] = {
    "report_dir": str(
        _OBSIDIAN_VAULT
        if _OBSIDIAN_VAULT.parent.exists()
        else Path.home() / "Documents" / "video-notes"
    ),
    "default_template": "video-analysis",
    "save_transcript": True,
    "save_notable_frames": True,
    # Persistent frame cache — survives between Claude Code sessions.
    # Keyed by a hash of the source URL/path; prevents re-download on session restart.
    "work_cache_dir": str(Path.home() / ".cache" / "watch"),
    # Set true if your Obsidian vault uses [[Wikilinks]] (the default Obsidian setting).
    # Controls whether Visual Evidence images are embedded as ![[...]] or ![](...)
    "obsidian_wikilinks": True,
}


def load_config() -> dict[str, Any]:
    """Return config merged over defaults. Never raises."""
    if not CONFIG_FILE.exists():
        return DEFAULTS.copy()
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return {**DEFAULTS, **raw}
    except (json.JSONDecodeError, OSError):
        return DEFAULTS.copy()


def save_config(updates: dict[str, Any]) -> None:
    """Persist updates into config.json, merging with existing values."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_config()
    existing.update(updates)
    CONFIG_FILE.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    import sys
    cfg = load_config()
    json.dump(cfg, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
