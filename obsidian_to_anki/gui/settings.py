from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_GUI_SETTINGS_PATH = Path.home() / ".obsidian-to-anki-gui.json"
GUI_SETTINGS_KEYS = {
    "vault": str,
    "output": str,
    "write_tsv": bool,
    "tag": str,
    "tags": list,
    "html_output": bool,
    "skip_empty": bool,
    "italicize_quoted_text": bool,
    "flatten_note_links": bool,
    "duplicate_handling": str,
    "include_folders": list,
    "sync_to_anki": bool,
    "anki_connect_url": str,
    "anki_deck": str,
    "anki_note_type": str,
    "anki_front_field": str,
    "anki_back_field": str,
    "anki_existing_notes": str,
}


def gui_settings_path(path: Path | None = None) -> Path:
    return path or DEFAULT_GUI_SETTINGS_PATH


def sanitize_gui_settings(raw_settings: object) -> dict[str, object]:
    if not isinstance(raw_settings, dict):
        return {}

    sanitized: dict[str, object] = {}
    for key, expected_type in GUI_SETTINGS_KEYS.items():
        value = raw_settings.get(key)
        if expected_type is list:
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                sanitized[key] = list(value)
            continue
        if isinstance(value, expected_type):
            sanitized[key] = value
    return sanitized


def load_gui_settings(path: Path | None = None) -> dict[str, object]:
    resolved_path = gui_settings_path(path)
    if not resolved_path.exists():
        return {}
    try:
        raw_settings = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return sanitize_gui_settings(raw_settings)


def save_gui_settings(settings: dict[str, object], path: Path | None = None) -> Path:
    resolved_path = gui_settings_path(path)
    resolved_path.write_text(
        json.dumps(sanitize_gui_settings(settings), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return resolved_path


def delete_gui_settings(path: Path | None = None) -> None:
    resolved_path = gui_settings_path(path)
    try:
        resolved_path.unlink()
    except FileNotFoundError:
        return
