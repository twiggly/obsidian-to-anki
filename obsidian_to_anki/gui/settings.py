from __future__ import annotations

import json
from pathlib import Path

DEFAULT_GUI_SETTINGS_PATH = Path.home() / ".obsidian-to-anki-gui.json"
DEFAULT_OUTPUT_PATH = str(Path.home() / "Desktop" / "obsidian-to-anki.tsv")
DEFAULT_TARGET_TAG = ""
DEFAULT_ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DEFAULT_ANKI_DECK = "Default"
DEFAULT_ANKI_NOTE_TYPE = "Basic"
DEFAULT_ANKI_FRONT_FIELD = "Front"
DEFAULT_ANKI_BACK_FIELD = "Back"
DEFAULT_ANKI_EXISTING_NOTES = "update"
DEFAULT_DUPLICATE_HANDLING = "error"
DEFAULT_FLATTEN_NOTE_LINKS = False

_SCALAR_SETTINGS = {
    "vault": ("vault_var", ""),
    "output": ("output_var", DEFAULT_OUTPUT_PATH),
    "write_tsv": ("write_tsv_var", False),
    "tag": ("tag_var", DEFAULT_TARGET_TAG),
    "html_output": ("html_var", False),
    "skip_empty": ("skip_empty_var", True),
    "italicize_quoted_text": ("quoted_italic_var", False),
    "flatten_note_links": ("flatten_note_links_var", DEFAULT_FLATTEN_NOTE_LINKS),
    "duplicate_handling": ("duplicate_handling_var", DEFAULT_DUPLICATE_HANDLING),
    "sync_to_anki": ("sync_to_anki_var", False),
    "anki_connect_url": ("anki_connect_url_var", DEFAULT_ANKI_CONNECT_URL),
    "anki_deck": ("anki_deck_var", DEFAULT_ANKI_DECK),
    "anki_note_type": ("anki_note_type_var", DEFAULT_ANKI_NOTE_TYPE),
    "anki_front_field": ("anki_front_field_var", DEFAULT_ANKI_FRONT_FIELD),
    "anki_back_field": ("anki_back_field_var", DEFAULT_ANKI_BACK_FIELD),
    "anki_existing_notes": ("anki_existing_notes_var", DEFAULT_ANKI_EXISTING_NOTES),
}
GUI_SETTINGS_KEYS = {
    **{key: type(default) for key, (_, default) in _SCALAR_SETTINGS.items()},
    "tags": list,
    "include_folders": list,
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
    except OSError, json.JSONDecodeError:
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
