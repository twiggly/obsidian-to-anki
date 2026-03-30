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
from gui_anki_controller import (
    finish_anki_catalog_refresh_error as finish_anki_catalog_refresh_error_helper,
    finish_anki_catalog_refresh_success as finish_anki_catalog_refresh_success_helper,
    finish_anki_field_refresh_error as finish_anki_field_refresh_error_helper,
    finish_anki_field_refresh_success as finish_anki_field_refresh_success_helper,
    refresh_anki_catalog as refresh_anki_catalog_helper,
    refresh_anki_catalog_if_needed as refresh_anki_catalog_if_needed_helper,
    refresh_anki_fields as refresh_anki_fields_helper,
    refresh_anki_fields_if_needed as refresh_anki_fields_if_needed_helper,
    set_anki_connection_status as set_anki_connection_status_helper,
    sync_anki_option_state as sync_anki_option_state_helper,
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
from gui_selection_controller import (
    add_folder_filter as add_folder_filter_helper,
    add_selected_tag as add_selected_tag_helper,
    finish_tag_scan_error as finish_tag_scan_error_helper,
    finish_tag_scan_success as finish_tag_scan_success_helper,
    remove_folder_filter as remove_folder_filter_helper,
    remove_tag as remove_tag_helper,
    scan_vault_tags as scan_vault_tags_helper,
    set_folder_filters as set_folder_filters_helper,
    set_selected_tags as set_selected_tags_helper,
)
from gui_settings import delete_gui_settings, load_gui_settings, save_gui_settings
from gui_state import (
    apply_default_settings as apply_default_settings_helper,
    apply_saved_settings as apply_saved_settings_helper,
    collect_settings as collect_settings_helper,
    sync_status_details_visibility as sync_status_details_visibility_helper,
)
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
    set_anki_field_choices,
    set_combobox_choices,
    sync_anki_option_state,
    sync_html_option_state,
    sync_output_option_state,
)
from gui_widgets import render_tag_chips
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
        apply_default_settings_helper(
            self,
            default_output_path=DEFAULT_OUTPUT_PATH,
            default_target_tag=DEFAULT_TARGET_TAG,
            default_duplicate_handling=DEFAULT_DUPLICATE_HANDLING,
            default_anki_connect_url=DEFAULT_ANKI_CONNECT_URL,
            default_anki_deck=DEFAULT_ANKI_DECK,
            default_anki_note_type=DEFAULT_ANKI_NOTE_TYPE,
            default_anki_front_field=DEFAULT_ANKI_FRONT_FIELD,
            default_anki_back_field=DEFAULT_ANKI_BACK_FIELD,
            default_anki_existing_notes=DEFAULT_ANKI_EXISTING_NOTES,
            default_status_message=DEFAULT_STATUS_MESSAGE,
        )

    def apply_saved_settings(self) -> None:
        apply_saved_settings_helper(
            self,
            load_gui_settings(),
            default_duplicate_handling=DEFAULT_DUPLICATE_HANDLING,
        )

    def collect_settings(self) -> dict[str, object]:
        return collect_settings_helper(self)

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
        sync_status_details_visibility_helper(self)

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
        set_anki_connection_status_helper(self, status)

    def sync_anki_option_state(self) -> None:
        sync_anki_option_state_helper(self, sync_anki_option_state)

    def refresh_anki_catalog_if_needed(self) -> None:
        refresh_anki_catalog_if_needed_helper(self, normalize_anki_connect_url)

    def refresh_anki_fields_if_needed(self) -> None:
        refresh_anki_fields_if_needed_helper(self, normalize_anki_connect_url)

    def refresh_anki_catalog(self, show_error_dialog: bool = True) -> None:
        refresh_anki_catalog_helper(
            self,
            normalize_anki_connect_url,
            start_anki_catalog_refresh,
            messagebox,
            show_error_dialog=show_error_dialog,
        )

    def refresh_anki_fields(
        self,
        note_type_name: str | None = None,
        show_error_dialog: bool = True,
    ) -> None:
        refresh_anki_fields_helper(
            self,
            normalize_anki_connect_url,
            start_anki_field_catalog_refresh,
            messagebox,
            note_type_name=note_type_name,
            show_error_dialog=show_error_dialog,
        )

    def finish_anki_catalog_refresh_success(self, catalog: AnkiCatalog) -> None:
        finish_anki_catalog_refresh_success_helper(self, catalog, set_combobox_choices)

    def finish_anki_catalog_refresh_error(
        self,
        error_message: str,
        details: str | None = None,
        *,
        show_error_dialog: bool = True,
    ) -> None:
        finish_anki_catalog_refresh_error_helper(
            self,
            error_message,
            details,
            messagebox,
            show_error_dialog=show_error_dialog,
        )

    def finish_anki_field_refresh_success(self, field_catalog: AnkiFieldCatalog) -> None:
        finish_anki_field_refresh_success_helper(self, field_catalog, set_anki_field_choices)

    def finish_anki_field_refresh_error(
        self,
        error_message: str,
        details: str | None = None,
        *,
        show_error_dialog: bool = True,
    ) -> None:
        finish_anki_field_refresh_error_helper(
            self,
            error_message,
            details,
            messagebox,
            show_error_dialog=show_error_dialog,
        )

    def on_anki_connect_url_change(self, _: object | None = None) -> None:
        self.refresh_anki_catalog_if_needed()

    def on_anki_note_type_change(self, _: object | None = None) -> None:
        self.refresh_anki_fields_if_needed()

    def get_folder_filters_from_listbox(self) -> list[str]:
        return list(self.folder_filters)

    def set_folder_filters_in_listbox(self, folder_filters: list[str]) -> None:
        set_folder_filters_helper(self, folder_filters, render_tag_chips)

    def get_selected_tags_from_listbox(self) -> list[str]:
        return list(self.selected_tags)

    def set_selected_tags_in_listbox(self, tags: list[str]) -> None:
        set_selected_tags_helper(self, tags, render_tag_chips)

    def add_selected_tag(self, _: object | None = None) -> None:
        add_selected_tag_helper(self, append_unique_value)

    def remove_tag(self, tag: str) -> None:
        remove_tag_helper(self, tag)

    def add_folder_filter(self) -> None:
        add_folder_filter_helper(self, add_folder_filter_from_dialog)

    def remove_folder_filter(self, folder_filter: str) -> None:
        remove_folder_filter_helper(self, folder_filter)

    def scan_vault_tags(self) -> None:
        scan_vault_tags_helper(self, build_tag_scan_request, start_tag_catalog_scan, messagebox)

    def finish_tag_scan_success(self, tag_names: tuple[str, ...]) -> None:
        finish_tag_scan_success_helper(self, tag_names)

    def finish_tag_scan_error(self, error_message: str, details: str | None = None) -> None:
        finish_tag_scan_error_helper(self, error_message, details, messagebox)

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
