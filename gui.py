from __future__ import annotations

from dataclasses import replace
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from anki_sync import normalize_anki_connect_url
from common import (
    duplicate_handling_display_label,
    duplicate_handling_from_display,
    format_target_tags,
    normalize_duplicate_handling,
)
from gui_logic import (
    FormValidationError,
    build_export_options_from_values,
    build_tag_scan_request,
    delivery_action_label,
    delivery_complete_message,
    delivery_complete_title,
    delivery_progress_message,
    duplicate_front_warning_message,
    export_no_cards_message,
    preview_no_matches_message,
    preview_ready_message,
    timing_breakdown_lines,
)
from gui_preview import show_preview_dialog
from gui_settings import delete_gui_settings, load_gui_settings, save_gui_settings
from gui_tasks import (
    start_anki_catalog_refresh,
    start_anki_field_catalog_refresh,
    start_delivery,
    start_preview_scan,
    start_tag_catalog_scan,
)
from gui_view import (
    add_folder_filter_from_dialog,
    append_folder_filter,
    append_unique_value,
    build_main_window,
    choose_output,
    choose_vault,
    get_folder_filters,
    render_tag_chips,
    set_anki_field_choices,
    set_combobox_choices,
    sync_anki_option_state,
    sync_html_option_state,
    sync_output_option_state,
)
from models import AnkiCatalog, AnkiFieldCatalog, DeliveryResult, ExportOptions, ScanResult

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
else:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        tk = None
        filedialog = None
        messagebox = None
        ttk = None


def sanitize_tag_values(values: Sequence[object]) -> list[str]:
    cleaned_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        cleaned_values.append(cleaned)

    return cleaned_values


def remove_folder_filters(existing_filters: Sequence[str], selected_indexes: Sequence[int]) -> list[str]:
    selected = {index for index in selected_indexes if 0 <= index < len(existing_filters)}
    return [value for index, value in enumerate(existing_filters) if index not in selected]


DEFAULT_OUTPUT_PATH = str(Path.home() / "Desktop" / "obsidian-to-anki.tsv")
DEFAULT_TARGET_TAG = ""
DEFAULT_ANKI_CONNECT_URL = "http://127.0.0.1:8765"
DEFAULT_ANKI_DECK = "Default"
DEFAULT_ANKI_NOTE_TYPE = "Basic"
DEFAULT_ANKI_FRONT_FIELD = "Front"
DEFAULT_ANKI_BACK_FIELD = "Back"
DEFAULT_ANKI_EXISTING_NOTES = "update"
DEFAULT_DUPLICATE_HANDLING = "error"
DEFAULT_STATUS_MESSAGE = "Choose a vault folder and an output file or enable direct Anki sync."


class ExporterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Obsidian to Anki")
        self.root.geometry("800x560")
        self.root.minsize(600, 560)

        self.vault_var = tk.StringVar()
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_PATH)
        self.write_tsv_var = tk.BooleanVar(value=True)
        self.tag_var = tk.StringVar(value=DEFAULT_TARGET_TAG)
        self.html_var = tk.BooleanVar(value=False)
        self.skip_empty_var = tk.BooleanVar(value=False)
        self.quoted_italic_var = tk.BooleanVar(value=False)
        self.duplicate_handling_var = tk.StringVar(value=DEFAULT_DUPLICATE_HANDLING)
        self.duplicate_handling_display_var = tk.StringVar(
            value=duplicate_handling_display_label(DEFAULT_DUPLICATE_HANDLING)
        )
        self.sync_to_anki_var = tk.BooleanVar(value=False)
        self.anki_connect_url_var = tk.StringVar(value=DEFAULT_ANKI_CONNECT_URL)
        self.anki_deck_var = tk.StringVar(value=DEFAULT_ANKI_DECK)
        self.anki_note_type_var = tk.StringVar(value=DEFAULT_ANKI_NOTE_TYPE)
        self.anki_front_field_var = tk.StringVar(value=DEFAULT_ANKI_FRONT_FIELD)
        self.anki_back_field_var = tk.StringVar(value=DEFAULT_ANKI_BACK_FIELD)
        self.anki_existing_notes_var = tk.StringVar(value=DEFAULT_ANKI_EXISTING_NOTES)
        self.anki_connection_var = tk.StringVar(value="Sync off")
        self.status_var = tk.StringVar(value=DEFAULT_STATUS_MESSAGE)
        self.status_details_var = tk.StringVar(value="Show Details")
        self.is_busy = False
        self.status_details_visible = False
        self._anki_catalog_loading = False
        self._anki_field_loading = False
        self._last_loaded_anki_url: str | None = None
        self._last_loaded_anki_note_type: str | None = None
        self._pending_anki_catalog_url: str | None = None
        self._pending_anki_field_key: tuple[str, str] | None = None
        self.selected_tags: list[str] = []
        self.folder_filters: list[str] = []

        self.folder_filters_container: tk.Frame
        self.folder_filter_remove_buttons: list[tk.Label]
        self.output_tsv_checkbutton: ttk.Checkbutton
        self.output_entry: ttk.Entry
        self.output_button: ttk.Button
        self.html_checkbutton: ttk.Checkbutton
        self.quoted_italic_checkbutton: ttk.Checkbutton
        self.duplicate_handling_combobox: ttk.Combobox
        self.tag_combobox: ttk.Combobox
        self.selected_tags_container: tk.Frame
        self.selected_tag_remove_buttons: list[tk.Button]
        self.tag_scan_button: ttk.Button
        self.add_folder_button: ttk.Button
        self.sync_to_anki_checkbutton: ttk.Checkbutton
        self.anki_connection_indicator: ttk.Label
        self.anki_connect_url_entry: ttk.Entry
        self.anki_deck_combobox: ttk.Combobox
        self.anki_note_type_combobox: ttk.Combobox
        self.anki_front_field_combobox: ttk.Combobox
        self.anki_back_field_combobox: ttk.Combobox
        self.anki_existing_notes_combobox: ttk.Combobox
        self.reset_button: ttk.Button
        self.preview_button: ttk.Button
        self.status_toggle_button: ttk.Button
        self.log_widget: tk.Text

        self.build_ui()
        self.apply_default_settings()
        self.apply_saved_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self) -> None:
        build_main_window(self)
        self.sync_status_details_visibility()

    def apply_default_settings(self) -> None:
        self.vault_var.set("")
        self.output_var.set(DEFAULT_OUTPUT_PATH)
        self.write_tsv_var.set(True)
        self.tag_var.set(DEFAULT_TARGET_TAG)
        self.set_selected_tags_in_listbox([])
        self.html_var.set(False)
        self.skip_empty_var.set(False)
        self.quoted_italic_var.set(False)
        self.duplicate_handling_var.set(DEFAULT_DUPLICATE_HANDLING)
        self.duplicate_handling_display_var.set(
            duplicate_handling_display_label(DEFAULT_DUPLICATE_HANDLING)
        )
        self.set_folder_filters_in_listbox([])
        self.sync_to_anki_var.set(False)
        self.anki_connect_url_var.set(DEFAULT_ANKI_CONNECT_URL)
        self.anki_deck_var.set(DEFAULT_ANKI_DECK)
        self.anki_note_type_var.set(DEFAULT_ANKI_NOTE_TYPE)
        self.anki_front_field_var.set(DEFAULT_ANKI_FRONT_FIELD)
        self.anki_back_field_var.set(DEFAULT_ANKI_BACK_FIELD)
        self.anki_existing_notes_var.set(DEFAULT_ANKI_EXISTING_NOTES)
        self._last_loaded_anki_url = None
        self._last_loaded_anki_note_type = None
        self._pending_anki_catalog_url = None
        self._pending_anki_field_key = None
        self.status_var.set(DEFAULT_STATUS_MESSAGE)
        self.sync_output_option_state()
        self.sync_html_option_state()
        self.sync_anki_option_state()

    def apply_saved_settings(self) -> None:
        settings = load_gui_settings()
        self.vault_var.set(str(settings.get("vault", self.vault_var.get())))
        self.output_var.set(str(settings.get("output", self.output_var.get())))
        self.write_tsv_var.set(bool(settings.get("write_tsv", self.write_tsv_var.get())))
        self.tag_var.set(str(settings.get("tag", self.tag_var.get())))
        saved_tags = settings.get("tags")
        cleaned_saved_tags = sanitize_tag_values(saved_tags) if isinstance(saved_tags, list) else []
        if cleaned_saved_tags:
            self.set_selected_tags_in_listbox(cleaned_saved_tags)
        else:
            self.tag_var.set("")
            self.set_selected_tags_in_listbox([])
        self.html_var.set(bool(settings.get("html_output", self.html_var.get())))
        self.skip_empty_var.set(bool(settings.get("skip_empty", self.skip_empty_var.get())))
        self.quoted_italic_var.set(
            bool(settings.get("italicize_quoted_text", self.quoted_italic_var.get()))
        )
        saved_duplicate_handling = str(
            settings.get("duplicate_handling", self.duplicate_handling_var.get())
        )
        try:
            normalized_duplicate_handling = normalize_duplicate_handling(saved_duplicate_handling)
        except Exception:
            normalized_duplicate_handling = DEFAULT_DUPLICATE_HANDLING
        self.duplicate_handling_var.set(normalized_duplicate_handling)
        self.duplicate_handling_display_var.set(
            duplicate_handling_display_label(normalized_duplicate_handling)
        )
        self.sync_to_anki_var.set(bool(settings.get("sync_to_anki", self.sync_to_anki_var.get())))
        self.anki_connect_url_var.set(
            str(settings.get("anki_connect_url", self.anki_connect_url_var.get()))
        )
        self.anki_deck_var.set(str(settings.get("anki_deck", self.anki_deck_var.get())))
        self.anki_note_type_var.set(str(settings.get("anki_note_type", self.anki_note_type_var.get())))
        self.anki_front_field_var.set(
            str(settings.get("anki_front_field", self.anki_front_field_var.get()))
        )
        self.anki_back_field_var.set(str(settings.get("anki_back_field", self.anki_back_field_var.get())))
        self.anki_existing_notes_var.set(
            str(settings.get("anki_existing_notes", self.anki_existing_notes_var.get()))
        )
        include_folders = settings.get("include_folders", [])
        if isinstance(include_folders, list):
            self.set_folder_filters_in_listbox(include_folders)
        self.sync_output_option_state()
        self.sync_html_option_state()
        self.sync_anki_option_state()

    def collect_settings(self) -> dict[str, object]:
        return {
            "vault": self.vault_var.get(),
            "output": self.output_var.get(),
            "write_tsv": self.write_tsv_var.get(),
            "tag": self.tag_var.get(),
            "tags": self.get_selected_tags_from_listbox(),
            "html_output": self.html_var.get(),
            "skip_empty": self.skip_empty_var.get(),
            "italicize_quoted_text": self.quoted_italic_var.get(),
            "duplicate_handling": self.duplicate_handling_var.get(),
            "include_folders": self.get_folder_filters_from_listbox(),
            "sync_to_anki": self.sync_to_anki_var.get(),
            "anki_connect_url": self.anki_connect_url_var.get(),
            "anki_deck": self.anki_deck_var.get(),
            "anki_note_type": self.anki_note_type_var.get(),
            "anki_front_field": self.anki_front_field_var.get(),
            "anki_back_field": self.anki_back_field_var.get(),
            "anki_existing_notes": self.anki_existing_notes_var.get(),
        }

    def save_settings(self) -> None:
        save_gui_settings(self.collect_settings())

    def close(self) -> None:
        try:
            self.save_settings()
        except OSError as exc:
            self.log(f"Error saving settings: {exc}")
        self.root.destroy()

    def choose_vault(self) -> None:
        choose_vault(self.vault_var, self.log)

    def choose_output(self) -> None:
        choose_output(self.output_var, self.log)

    def reset_settings(self) -> None:
        if self.is_busy:
            return
        if not messagebox.askyesno(
            "Reset settings",
            "Reset the app back to its default settings?",
        ):
            return
        try:
            delete_gui_settings()
        except OSError as exc:
            messagebox.showerror("Reset failed", f"Could not delete saved settings: {exc}")
            return
        self.apply_default_settings()
        self.log("Settings reset to defaults.")

    def sync_html_option_state(self) -> None:
        sync_html_option_state(self.html_var.get(), self.quoted_italic_checkbutton)

    def sync_output_option_state(self) -> None:
        sync_output_option_state(
            self.write_tsv_var.get(),
            [self.output_entry, self.output_button],
        )

    def sync_status_details_visibility(self) -> None:
        if self.status_details_visible:
            self.status_details_var.set("Hide Details")
            self.log_widget.grid()
        else:
            self.status_details_var.set("Show Details")
            self.log_widget.grid_remove()

    def toggle_status_details(self) -> None:
        self.status_details_visible = not self.status_details_visible
        self.sync_status_details_visibility()

    def on_duplicate_handling_change(self, _: object | None = None) -> None:
        try:
            normalized = duplicate_handling_from_display(self.duplicate_handling_display_var.get())
        except Exception:
            normalized = DEFAULT_DUPLICATE_HANDLING
        self.duplicate_handling_var.set(normalized)
        self.duplicate_handling_display_var.set(duplicate_handling_display_label(normalized))

    def set_anki_connection_status(self, status: str) -> None:
        status_map = {
            "off": ("Sync off", "AnkiOff.TLabel"),
            "loading": ("Connecting…", "AnkiPending.TLabel"),
            "connected": ("Connected", "AnkiConnected.TLabel"),
            "error": ("Connection failed", "AnkiError.TLabel"),
        }
        text, style_name = status_map.get(status, status_map["off"])
        self.anki_connection_var.set(text)
        self.anki_connection_indicator.configure(style=style_name)

    def sync_anki_option_state(self) -> None:
        sync_enabled = self.sync_to_anki_var.get()
        sync_anki_option_state(
            sync_enabled,
            [
                self.anki_connect_url_entry,
                self.anki_deck_combobox,
                self.anki_note_type_combobox,
                self.anki_front_field_combobox,
                self.anki_back_field_combobox,
                self.anki_existing_notes_combobox,
            ],
        )
        if sync_enabled:
            if self._last_loaded_anki_url is not None:
                self.set_anki_connection_status("connected")
            self.refresh_anki_catalog_if_needed()
        else:
            self.set_anki_connection_status("off")

    def refresh_anki_catalog_if_needed(self) -> None:
        if not self.sync_to_anki_var.get():
            return
        try:
            normalized_url = normalize_anki_connect_url(self.anki_connect_url_var.get())
        except FormValidationError:
            return
        except Exception:
            return
        if normalized_url == self._last_loaded_anki_url:
            self.refresh_anki_fields_if_needed()
            return
        self.refresh_anki_catalog(show_error_dialog=False)

    def refresh_anki_fields_if_needed(self) -> None:
        if not self.sync_to_anki_var.get():
            return
        note_type_name = self.anki_note_type_var.get().strip()
        if not note_type_name:
            return
        try:
            normalized_url = normalize_anki_connect_url(self.anki_connect_url_var.get())
        except Exception:
            return
        if (
            normalized_url == self._last_loaded_anki_url
            and note_type_name == self._last_loaded_anki_note_type
        ):
            return
        self.refresh_anki_fields(note_type_name=note_type_name, show_error_dialog=False)

    def refresh_anki_catalog(self, show_error_dialog: bool = True) -> None:
        if self.is_busy or self._anki_catalog_loading:
            return

        try:
            normalized_url = normalize_anki_connect_url(self.anki_connect_url_var.get())
        except Exception as exc:
            self.set_anki_connection_status("error")
            self.status_var.set(str(exc))
            self.log(f"Error: {exc}")
            if show_error_dialog:
                messagebox.showerror("Anki refresh failed", str(exc))
            return
        self._anki_catalog_loading = True
        self._pending_anki_catalog_url = normalized_url
        self.set_anki_connection_status("loading")
        self.status_var.set("Loading Anki decks and note types…")
        self.log("Loading deck and note type lists from AnkiConnect.")
        start_anki_catalog_refresh(
            self.root,
            normalized_url,
            self.finish_anki_catalog_refresh_success,
            lambda error_message, details=None: self.finish_anki_catalog_refresh_error(
                error_message,
                details,
                show_error_dialog=show_error_dialog,
            ),
        )

    def refresh_anki_fields(
        self,
        note_type_name: str | None = None,
        show_error_dialog: bool = True,
    ) -> None:
        if self.is_busy or self._anki_field_loading or not self.sync_to_anki_var.get():
            return

        resolved_note_type = (note_type_name or self.anki_note_type_var.get()).strip()
        if not resolved_note_type:
            return
        try:
            normalized_url = normalize_anki_connect_url(self.anki_connect_url_var.get())
        except Exception as exc:
            self.status_var.set(str(exc))
            self.log(f"Error: {exc}")
            if show_error_dialog:
                messagebox.showerror("Anki field refresh failed", str(exc))
            return
        self._anki_field_loading = True
        self._pending_anki_field_key = (normalized_url, resolved_note_type)
        self.status_var.set(f"Loading fields for note type '{resolved_note_type}'…")
        self.log(f"Loading Anki field names for note type '{resolved_note_type}'.")
        start_anki_field_catalog_refresh(
            self.root,
            normalized_url,
            resolved_note_type,
            self.finish_anki_field_refresh_success,
            lambda error_message, details=None: self.finish_anki_field_refresh_error(
                error_message,
                details,
                show_error_dialog=show_error_dialog,
            ),
        )

    def finish_anki_catalog_refresh_success(self, catalog: AnkiCatalog) -> None:
        self._anki_catalog_loading = False
        self._last_loaded_anki_url = self._pending_anki_catalog_url
        self._pending_anki_catalog_url = None
        set_combobox_choices(self.anki_deck_combobox, catalog.deck_names, self.anki_deck_var.get())
        set_combobox_choices(
            self.anki_note_type_combobox,
            catalog.note_type_names,
            self.anki_note_type_var.get(),
        )
        self.set_anki_connection_status("connected")
        loaded_message = (
            f"Loaded {len(catalog.deck_names)} decks and {len(catalog.note_type_names)} note types from AnkiConnect."
        )
        self.status_var.set(loaded_message)
        self.log(loaded_message)
        self.refresh_anki_fields_if_needed()

    def finish_anki_catalog_refresh_error(
        self,
        error_message: str,
        details: str | None = None,
        *,
        show_error_dialog: bool = True,
    ) -> None:
        self._anki_catalog_loading = False
        self._pending_anki_catalog_url = None
        self.set_anki_connection_status("error")
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        if show_error_dialog:
            messagebox.showerror("Anki refresh failed", error_message)

    def finish_anki_field_refresh_success(self, field_catalog: AnkiFieldCatalog) -> None:
        self._anki_field_loading = False
        if self._pending_anki_field_key is not None:
            self._last_loaded_anki_url, self._last_loaded_anki_note_type = self._pending_anki_field_key
        self._pending_anki_field_key = None
        set_anki_field_choices(
            self.anki_front_field_combobox,
            self.anki_back_field_combobox,
            field_catalog.field_names,
            self.anki_front_field_var.get(),
            self.anki_back_field_var.get(),
        )
        loaded_message = (
            f"Loaded {len(field_catalog.field_names)} fields for note type '{field_catalog.note_type_name}'."
        )
        self.status_var.set(loaded_message)
        self.log(loaded_message)

    def finish_anki_field_refresh_error(
        self,
        error_message: str,
        details: str | None = None,
        *,
        show_error_dialog: bool = True,
    ) -> None:
        self._anki_field_loading = False
        self._pending_anki_field_key = None
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        if show_error_dialog:
            messagebox.showerror("Anki field refresh failed", error_message)

    def on_anki_connect_url_change(self, _: object | None = None) -> None:
        self.refresh_anki_catalog_if_needed()

    def on_anki_note_type_change(self, _: object | None = None) -> None:
        self.refresh_anki_fields_if_needed()

    def get_folder_filters_from_listbox(self) -> list[str]:
        return list(self.folder_filters)

    def set_folder_filters_in_listbox(self, folder_filters: list[str]) -> None:
        self.folder_filters = sanitize_tag_values(folder_filters)
        if not hasattr(self.folder_filters_container, "winfo_children"):
            self.folder_filter_remove_buttons = []
            return
        self.folder_filter_remove_buttons = render_tag_chips(
            self.folder_filters_container,
            self.folder_filters,
            self.remove_folder_filter,
            disabled=self.is_busy,
            empty_text="No folders selected",
        )

    def get_selected_tags_from_listbox(self) -> list[str]:
        return list(self.selected_tags)

    def set_selected_tags_in_listbox(self, tags: list[str]) -> None:
        self.selected_tags = sanitize_tag_values(tags)
        if not hasattr(self.selected_tags_container, "tk"):
            self.selected_tag_remove_buttons = []
            return
        self.selected_tag_remove_buttons = render_tag_chips(
            self.selected_tags_container,
            self.selected_tags,
            self.remove_tag,
            disabled=self.is_busy,
        )

    def add_selected_tag(self, _: object | None = None) -> None:
        tag_value = self.tag_var.get().strip()
        updated_values = append_unique_value(
            self.get_selected_tags_from_listbox(),
            tag_value,
        )
        self.set_selected_tags_in_listbox(updated_values)
        if tag_value:
            self.tag_var.set("")
            self.tag_combobox.set("")

    def remove_tag(self, tag: str) -> None:
        updated_values = [value for value in self.get_selected_tags_from_listbox() if value != tag]
        self.set_selected_tags_in_listbox(updated_values)

    def add_folder_filter(self) -> None:
        updated_values = add_folder_filter_from_dialog(
            self.vault_var.get(),
            self.get_folder_filters_from_listbox(),
            self.log,
        )
        if updated_values is not None:
            self.set_folder_filters_in_listbox(updated_values)

    def remove_folder_filter(self, folder_filter: str) -> None:
        updated_values = [value for value in self.get_folder_filters_from_listbox() if value != folder_filter]
        if updated_values != self.get_folder_filters_from_listbox():
            self.log(f"Removed folder filter: {folder_filter}")
        self.set_folder_filters_in_listbox(updated_values)

    def scan_vault_tags(self) -> None:
        if self.is_busy:
            return

        try:
            vault_path, include_folders = build_tag_scan_request(
                self.vault_var.get(),
                self.get_folder_filters_from_listbox(),
            )
        except FormValidationError as exc:
            messagebox.showerror(exc.title, exc.message)
            return

        self.set_busy(True)
        self.status_var.set("Scanning vault for tags…")
        self.log("Scanning vault to find available tags.")
        start_tag_catalog_scan(
            self.root,
            vault_path,
            include_folders,
            self.finish_tag_scan_success,
            self.finish_tag_scan_error,
        )

    def finish_tag_scan_success(self, tag_names: tuple[str, ...]) -> None:
        self.set_busy(False)
        current_tag = self.tag_var.get().strip()
        self.tag_combobox.configure(values=tag_names)
        if not current_tag:
            self.tag_combobox.set("")
            self.tag_var.set("")
        if tag_names:
            message = f"Found {len(tag_names)} tags in the scanned vault."
        else:
            message = "No tags were found in the scanned vault."
        self.status_var.set(message)
        self.log(message)

    def finish_tag_scan_error(self, error_message: str, details: str | None = None) -> None:
        self.set_busy(False)
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        messagebox.showerror("Tag scan failed", error_message)

    def build_options_from_form(self) -> ExportOptions | None:
        try:
            return build_export_options_from_values(
                self.vault_var.get(),
                self.output_var.get(),
                self.get_selected_tags_from_listbox(),
                self.html_var.get(),
                self.skip_empty_var.get(),
                self.quoted_italic_var.get(),
                self.get_folder_filters_from_listbox(),
                self.duplicate_handling_var.get(),
                self.sync_to_anki_var.get(),
                self.anki_connect_url_var.get(),
                self.anki_deck_var.get(),
                self.anki_note_type_var.get(),
                self.anki_front_field_var.get(),
                self.anki_back_field_var.get(),
                self.anki_existing_notes_var.get(),
                write_tsv=self.write_tsv_var.get(),
            )
        except FormValidationError as exc:
            messagebox.showerror(exc.title, exc.message)
            return None

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        if busy:
            self.preview_button.state(["disabled"])
            self.reset_button.state(["disabled"])
            self.tag_scan_button.state(["disabled"])
            self.add_folder_button.state(["disabled"])
        else:
            self.preview_button.state(["!disabled"])
            self.reset_button.state(["!disabled"])
            self.tag_scan_button.state(["!disabled"])
            self.add_folder_button.state(["!disabled"])
        self.set_selected_tags_in_listbox(self.get_selected_tags_from_listbox())
        self.set_folder_filters_in_listbox(self.get_folder_filters_from_listbox())

    def start_preview(self) -> None:
        if self.is_busy:
            return

        options = self.build_options_from_form()
        if options is None:
            return

        self.set_busy(True)
        self.status_var.set("Generating preview…")
        self.log(
            f"Generating preview for {format_target_tags(options.target_tag, options.additional_target_tags)}"
        )
        preview_options = (
            replace(options, duplicate_handling="warn")
            if options.duplicate_handling == "error"
            else options
        )
        start_preview_scan(
            self.root,
            preview_options,
            lambda _completed_options, scan_result: self.finish_preview_success(options, scan_result),
            self.finish_preview_error,
        )

    def finish_preview_success(self, options: ExportOptions, scan_result: ScanResult) -> None:
        self.set_busy(False)
        if scan_result.total_matches == 0:
            message = preview_no_matches_message(
                options.target_tag,
                options.additional_target_tags,
                options.include_folders,
            )
            self.status_var.set(message)
            self.log(message)
            messagebox.showinfo("No matching cards", message)
            return

        message = preview_ready_message(scan_result)
        self.status_var.set(message)
        self.log(message)
        for line in timing_breakdown_lines(scan_result):
            self.log(line)

        warning_message = duplicate_front_warning_message(
            scan_result.duplicate_fronts,
            options.duplicate_handling,
        )
        if warning_message is not None:
            duplicate_count = len(scan_result.duplicate_fronts)
            self.log(f"Detected {duplicate_count} duplicate fronts.")
            messagebox.showwarning("Duplicate fronts detected", warning_message)
            if options.duplicate_handling == "error":
                stop_message = "Duplicate fronts detected. Resolve them or choose skip or suffix to continue."
                self.status_var.set(stop_message)
                self.log(stop_message)
                return

        show_preview_dialog(
            self.root,
            options,
            scan_result,
            on_confirm=lambda: self.begin_delivery(options, scan_result),
            action_label=delivery_action_label(options),
        )

    def finish_preview_error(self, error_message: str, details: str | None = None) -> None:
        self.set_busy(False)
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        messagebox.showerror("Preview failed", error_message)

    def begin_delivery(self, options: ExportOptions, scan_result: ScanResult) -> None:
        if self.is_busy:
            return

        self.set_busy(True)
        progress_message = delivery_progress_message(options)
        self.status_var.set(progress_message)
        self.log(
            f"Starting {delivery_action_label(options).lower()} for "
            f"{format_target_tags(options.target_tag, options.additional_target_tags)}"
        )
        start_delivery(
            self.root,
            options,
            scan_result,
            self.finish_delivery_success,
            self.finish_delivery_error,
        )

    def finish_delivery_success(
        self,
        options: ExportOptions,
        scan_result: ScanResult,
        delivery_result: DeliveryResult,
    ) -> None:
        self.set_busy(False)
        if scan_result.total_matches == 0:
            message = export_no_cards_message(
                options.target_tag,
                options.additional_target_tags,
                options.include_folders,
            )
            self.status_var.set(message)
            self.log(message)
            messagebox.showinfo("No cards exported", message)
            return

        message = delivery_complete_message(
            options,
            delivery_result,
            len(scan_result.duplicate_fronts),
        )
        self.status_var.set(message)
        self.log(message)
        for line in timing_breakdown_lines(scan_result, delivery_result):
            self.log(line)
        if delivery_result.report_text is not None:
            for line in delivery_result.report_text.rstrip().splitlines():
                self.log(line)
        messagebox.showinfo(delivery_complete_title(options), message)

    def finish_delivery_error(self, error_message: str, details: str | None = None) -> None:
        self.set_busy(False)
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        messagebox.showerror("Delivery failed", error_message)

    def log(self, message: str) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", message + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")


def launch_gui() -> int:
    if tk is None or ttk is None or filedialog is None or messagebox is None:
        print("Error: Tkinter is not available in this Python installation.", file=sys.stderr)
        return 1

    root = tk.Tk()
    ExporterApp(root)
    root.mainloop()
    return 0
