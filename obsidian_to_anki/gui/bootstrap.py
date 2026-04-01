from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..common import duplicate_handling_display_label

if TYPE_CHECKING:
    import tkinter as tk


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
DEFAULT_STATUS_MESSAGE = "Choose a vault folder, then turn on Output TSV or enable direct Anki sync."
ANKI_FOCUS_REFRESH_DELAY_MS = 750
ANKI_POLL_REFRESH_INTERVAL_MS = 15000


def configure_root_window(root: tk.Tk) -> None:
    root.title("Obsidian to Anki")
    root.geometry("800x560")
    root.minsize(600, 560)


def initialize_form_variables(app: object, tk_module: object) -> None:
    app.vault_var = tk_module.StringVar()
    app.output_var = tk_module.StringVar(value=DEFAULT_OUTPUT_PATH)
    app.write_tsv_var = tk_module.BooleanVar(value=False)
    app.tag_var = tk_module.StringVar(value=DEFAULT_TARGET_TAG)
    app.html_var = tk_module.BooleanVar(value=False)
    app.skip_empty_var = tk_module.BooleanVar(value=True)
    app.quoted_italic_var = tk_module.BooleanVar(value=False)
    app.flatten_note_links_var = tk_module.BooleanVar(value=DEFAULT_FLATTEN_NOTE_LINKS)
    app.duplicate_handling_var = tk_module.StringVar(value=DEFAULT_DUPLICATE_HANDLING)
    app.duplicate_handling_display_var = tk_module.StringVar(
        value=duplicate_handling_display_label(DEFAULT_DUPLICATE_HANDLING)
    )
    app.sync_to_anki_var = tk_module.BooleanVar(value=False)
    app.anki_connect_url_var = tk_module.StringVar(value=DEFAULT_ANKI_CONNECT_URL)
    app.anki_deck_var = tk_module.StringVar(value=DEFAULT_ANKI_DECK)
    app.anki_note_type_var = tk_module.StringVar(value=DEFAULT_ANKI_NOTE_TYPE)
    app.anki_front_field_var = tk_module.StringVar(value=DEFAULT_ANKI_FRONT_FIELD)
    app.anki_back_field_var = tk_module.StringVar(value=DEFAULT_ANKI_BACK_FIELD)
    app.anki_existing_notes_var = tk_module.StringVar(value=DEFAULT_ANKI_EXISTING_NOTES)
    app.anki_connection_var = tk_module.StringVar(value="Sync off")
    app.status_var = tk_module.StringVar(value=DEFAULT_STATUS_MESSAGE)
    app.status_details_var = tk_module.StringVar(value="Show Details")


def initialize_runtime_state(app: object) -> None:
    app.is_busy = False
    app.status_details_visible = False
    app._anki_catalog_loading = False
    app._anki_field_loading = False
    app._last_loaded_anki_url = None
    app._last_loaded_anki_note_type = None
    app._pending_anki_catalog_url = None
    app._pending_anki_field_key = None
    app._anki_note_type_install_loading = False
    app._anki_deck_settings_loading = False
    app._anki_refresh_after_id = None
    app._anki_poll_after_id = None
    app.selected_tags = []
    app.folder_filters = []


def initialize_widget_placeholders(app: object) -> None:
    app.folder_filters_container = None
    app.folder_filter_remove_buttons = []
    app.output_tsv_checkbutton = None
    app.output_entry = None
    app.output_button = None
    app.html_checkbutton = None
    app.quoted_italic_checkbutton = None
    app.flatten_note_links_checkbutton = None
    app.duplicate_handling_combobox = None
    app.tag_combobox = None
    app.selected_tags_container = None
    app.selected_tag_remove_buttons = []
    app.tag_scan_button = None
    app.add_folder_button = None
    app.sync_to_anki_checkbutton = None
    app.anki_connection_indicator = None
    app.anki_connect_url_entry = None
    app.anki_deck_combobox = None
    app.anki_note_type_combobox = None
    app.anki_front_field_combobox = None
    app.anki_back_field_combobox = None
    app.anki_existing_notes_combobox = None
    app.install_note_type_button = None
    app.apply_deck_settings_button = None
    app.reset_button = None
    app.preview_button = None
    app.status_toggle_button = None
    app.log_widget = None
