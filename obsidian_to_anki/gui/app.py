from __future__ import annotations

from dataclasses import replace
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from ..anki.sync import OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME, normalize_anki_connect_url
from ..common import (
    duplicate_handling_display_label,
    duplicate_handling_from_display,
    format_target_tags,
)
from .bootstrap import (
    ANKI_FOCUS_REFRESH_DELAY_MS,
    ANKI_POLL_REFRESH_INTERVAL_MS,
    DEFAULT_ANKI_BACK_FIELD,
    DEFAULT_ANKI_CONNECT_URL,
    DEFAULT_ANKI_DECK,
    DEFAULT_ANKI_EXISTING_NOTES,
    DEFAULT_ANKI_FRONT_FIELD,
    DEFAULT_ANKI_NOTE_TYPE,
    DEFAULT_DUPLICATE_HANDLING,
    DEFAULT_FLATTEN_NOTE_LINKS,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_STATUS_MESSAGE,
    DEFAULT_TARGET_TAG,
    configure_root_window,
    initialize_form_variables,
    initialize_runtime_state,
    initialize_widget_placeholders,
)
from .anki_controller import (
    finish_anki_connection_check_error as finish_anki_connection_check_error_helper,
    finish_anki_connection_check_success as finish_anki_connection_check_success_helper,
    finish_anki_catalog_refresh_error as finish_anki_catalog_refresh_error_helper,
    finish_anki_catalog_refresh_success as finish_anki_catalog_refresh_success_helper,
    finish_anki_field_refresh_error as finish_anki_field_refresh_error_helper,
    finish_anki_field_refresh_success as finish_anki_field_refresh_success_helper,
    refresh_anki_connection as refresh_anki_connection_helper,
    refresh_anki_catalog as refresh_anki_catalog_helper,
    refresh_anki_catalog_if_needed as refresh_anki_catalog_if_needed_helper,
    refresh_anki_fields as refresh_anki_fields_helper,
    refresh_anki_fields_if_needed as refresh_anki_fields_if_needed_helper,
    set_anki_connection_status as set_anki_connection_status_helper,
    sync_anki_option_state as sync_anki_option_state_helper,
)
from .delivery_controller import (
    begin_delivery as begin_delivery_helper,
    finish_delivery_error as finish_delivery_error_helper,
    finish_delivery_success as finish_delivery_success_helper,
    finish_preview_error as finish_preview_error_helper,
    finish_preview_success as finish_preview_success_helper,
    log as log_helper,
    set_busy as set_busy_helper,
    start_preview as start_preview_helper,
)
from .logic import (
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
    recommended_deck_settings_confirmation_message,
    timing_breakdown_lines,
)
from .preview import show_preview_dialog
from .selection_controller import (
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
from .settings import delete_gui_settings, load_gui_settings, save_gui_settings
from .state import (
    apply_default_settings as apply_default_settings_helper,
    apply_saved_settings as apply_saved_settings_helper,
    collect_settings as collect_settings_helper,
    sync_status_details_visibility as sync_status_details_visibility_helper,
)
from .tasks import (
    start_anki_connection_check,
    start_anki_catalog_refresh,
    start_anki_deck_settings_update,
    start_anki_field_catalog_refresh,
    start_anki_note_type_install,
    start_delivery,
    start_preview_scan,
    start_tag_catalog_scan,
)
from .view import (
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
from .widgets import render_tag_chips
from ..models import (
    AnkiCatalog,
    AnkiDeckSettingsResult,
    AnkiFieldCatalog,
    AnkiNoteTypeInstallResult,
    AnkiPreflightResult,
    AnkiPreflightSummary,
    DeliveryResult,
    ExportOptions,
    ScanResult,
)

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


def recommended_deck_settings_preset_name(deck_name: str) -> str:
    return f"{OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME} - {deck_name}"


def remove_folder_filters(existing_filters: Sequence[str], selected_indexes: Sequence[int]) -> list[str]:
    selected = {index for index in selected_indexes if 0 <= index < len(existing_filters)}
    return [value for index, value in enumerate(existing_filters) if index not in selected]


def get_combobox_values(combobox: object) -> tuple[str, ...]:
    try:
        values = combobox.cget("values")
    except Exception:
        values = getattr(combobox, "values", ())

    if isinstance(values, tuple):
        return values
    if isinstance(values, list):
        return tuple(values)
    if isinstance(values, str):
        tk_obj = getattr(combobox, "tk", None)
        if tk_obj is not None and hasattr(tk_obj, "splitlist"):
            try:
                return tuple(tk_obj.splitlist(values))
            except Exception:
                pass
        return (values,) if values else ()
    return ()


class ExporterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        configure_root_window(self.root)
        initialize_form_variables(self, tk)
        initialize_runtime_state(self)
        initialize_widget_placeholders(self)

        self.build_ui()
        self.apply_default_settings()
        self.apply_saved_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self) -> None:
        build_main_window(self)
        self.sync_status_details_visibility()
        if hasattr(self.root, "bind"):
            self.root.bind("<FocusIn>", self.on_root_focus, add="+")

    def apply_default_settings(self) -> None:
        apply_default_settings_helper(
            self,
            default_output_path=DEFAULT_OUTPUT_PATH,
            default_target_tag=DEFAULT_TARGET_TAG,
            default_duplicate_handling=DEFAULT_DUPLICATE_HANDLING,
            default_flatten_note_links=DEFAULT_FLATTEN_NOTE_LINKS,
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
        self.cancel_anki_connection_refresh()
        self.stop_anki_connection_polling()
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

    def refresh_anki_catalog(
        self,
        show_error_dialog: bool = True,
        quiet: bool = False,
    ) -> None:
        refresh_anki_catalog_helper(
            self,
            normalize_anki_connect_url,
            start_anki_catalog_refresh,
            messagebox,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
        )

    def refresh_anki_connection(
        self,
        show_error_dialog: bool = True,
        quiet: bool = False,
    ) -> None:
        refresh_anki_connection_helper(
            self,
            normalize_anki_connect_url,
            start_anki_connection_check,
            messagebox,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
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

    def install_obsidian_definitions_note_type(self) -> None:
        if (
            self.is_busy
            or self._anki_catalog_loading
            or self._anki_field_loading
            or self._anki_note_type_install_loading
        ):
            return

        self._anki_note_type_install_loading = True
        self.set_busy(True)
        self.status_var.set(f"Installing the {OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME} note type…")
        self.log(f"Installing or updating the {OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME} note type in Anki.")
        start_anki_note_type_install(
            self.root,
            self.anki_connect_url_var.get(),
            self.finish_anki_note_type_install_success,
            self.finish_anki_note_type_install_error,
        )

    def apply_recommended_deck_settings(self) -> None:
        if (
            self.is_busy
            or self._anki_catalog_loading
            or self._anki_field_loading
            or self._anki_note_type_install_loading
            or self._anki_deck_settings_loading
        ):
            return

        deck_name = self.anki_deck_var.get().strip()
        if not deck_name:
            messagebox.showerror(
                "Deck settings update failed",
                "Choose an Anki deck before applying the recommended deck settings.",
            )
            return
        preset_name = recommended_deck_settings_preset_name(deck_name)
        if not messagebox.askyesno(
            "Apply recommended deck settings",
            recommended_deck_settings_confirmation_message(deck_name, preset_name),
        ):
            return

        self._anki_deck_settings_loading = True
        self.set_busy(True)
        self.status_var.set(f"Applying the recommended deck settings to '{deck_name}'…")
        self.log(f"Applying the recommended deck settings to '{deck_name}' in Anki.")
        start_anki_deck_settings_update(
            self.root,
            self.anki_connect_url_var.get(),
            deck_name,
            self.finish_anki_deck_settings_success,
            self.finish_anki_deck_settings_error,
        )

    def finish_anki_catalog_refresh_success(
        self,
        catalog: AnkiCatalog,
        *,
        quiet: bool = False,
    ) -> None:
        finish_anki_catalog_refresh_success_helper(self, catalog, set_combobox_choices, quiet=quiet)

    def finish_anki_catalog_refresh_error(
        self,
        error_message: str,
        details: str | None = None,
        *,
        show_error_dialog: bool = True,
        quiet: bool = False,
    ) -> None:
        finish_anki_catalog_refresh_error_helper(
            self,
            error_message,
            details,
            messagebox,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
        )

    def finish_anki_connection_check_success(
        self,
        normalized_url: str,
        *,
        quiet: bool = False,
    ) -> None:
        finish_anki_connection_check_success_helper(
            self,
            normalized_url,
            quiet=quiet,
        )

    def finish_anki_connection_check_error(
        self,
        error_message: str,
        details: str | None = None,
        *,
        show_error_dialog: bool = True,
        quiet: bool = False,
    ) -> None:
        finish_anki_connection_check_error_helper(
            self,
            error_message,
            details,
            messagebox,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
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

    def finish_anki_note_type_install_success(self, result: AnkiNoteTypeInstallResult) -> None:
        self._anki_note_type_install_loading = False
        self.set_busy(False)
        self.set_anki_connection_status("connected")

        message = (
            f"Installed the Anki note type '{result.note_type_name}' with forward and reverse definition cards."
            if result.created
            else f"Updated the Anki note type '{result.note_type_name}' with the latest templates and styling."
        )
        self.status_var.set(message)
        self.log(message)

        note_type_choices = sorted(
            set((*get_combobox_values(self.anki_note_type_combobox), result.note_type_name)),
            key=str.casefold,
        )
        resolved_note_type = set_combobox_choices(
            self.anki_note_type_combobox,
            note_type_choices,
            result.note_type_name,
        )
        self.anki_note_type_var.set(resolved_note_type)
        front_value, back_value = set_anki_field_choices(
            self.anki_front_field_combobox,
            self.anki_back_field_combobox,
            (DEFAULT_ANKI_FRONT_FIELD, DEFAULT_ANKI_BACK_FIELD),
            DEFAULT_ANKI_FRONT_FIELD,
            DEFAULT_ANKI_BACK_FIELD,
        )
        self.anki_front_field_var.set(front_value)
        self.anki_back_field_var.set(back_value)
        try:
            self._last_loaded_anki_url = normalize_anki_connect_url(self.anki_connect_url_var.get())
        except Exception:
            self._last_loaded_anki_url = None
        self._last_loaded_anki_note_type = resolved_note_type
        messagebox.showinfo("Note type ready", message)

    def finish_anki_note_type_install_error(
        self,
        error_message: str,
        details: str | None = None,
    ) -> None:
        self._anki_note_type_install_loading = False
        self.set_busy(False)
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        messagebox.showerror("Note type install failed", error_message)

    def finish_anki_deck_settings_success(self, result: AnkiDeckSettingsResult) -> None:
        self._anki_deck_settings_loading = False
        self.set_busy(False)
        self.set_anki_connection_status("connected")

        message = (
            f"Applied the recommended deck settings to '{result.deck_name}' using the preset '{result.preset_name}'."
            if result.created
            else f"Updated the recommended deck settings preset '{result.preset_name}' for '{result.deck_name}'."
        )
        self.status_var.set(message)
        self.log(message)
        messagebox.showinfo("Deck settings ready", message)

    def finish_anki_deck_settings_error(
        self,
        error_message: str,
        details: str | None = None,
    ) -> None:
        self._anki_deck_settings_loading = False
        self.set_busy(False)
        self.status_var.set(error_message)
        if details is None:
            self.log(f"Error: {error_message}")
        else:
            self.log(error_message)
            self.log(details.rstrip())
        messagebox.showerror("Deck settings update failed", error_message)

    def on_anki_connect_url_change(self, _: object | None = None) -> None:
        self.refresh_anki_catalog_if_needed()

    def on_anki_note_type_change(self, _: object | None = None) -> None:
        self.refresh_anki_fields_if_needed()

    def on_root_focus(self, _: object | None = None) -> None:
        if self.sync_to_anki_var.get():
            self.schedule_anki_connection_refresh()

    def cancel_anki_connection_refresh(self) -> None:
        after_id = self._anki_refresh_after_id
        self._anki_refresh_after_id = None
        if after_id is None or not hasattr(self.root, "after_cancel"):
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            return

    def schedule_anki_connection_refresh(self, delay_ms: int = ANKI_FOCUS_REFRESH_DELAY_MS) -> None:
        self.cancel_anki_connection_refresh()
        if not self.sync_to_anki_var.get():
            return
        if not hasattr(self.root, "after"):
            self.run_anki_connection_refresh()
            return
        self._anki_refresh_after_id = self.root.after(delay_ms, self.run_anki_connection_refresh)

    def run_anki_connection_refresh(self) -> None:
        self._anki_refresh_after_id = None
        if self.sync_to_anki_var.get():
            self.refresh_anki_connection(show_error_dialog=False, quiet=True)

    def stop_anki_connection_polling(self) -> None:
        after_id = self._anki_poll_after_id
        self._anki_poll_after_id = None
        if after_id is None or not hasattr(self.root, "after_cancel"):
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            return

    def start_anki_connection_polling(self) -> None:
        self.stop_anki_connection_polling()
        if not self.sync_to_anki_var.get() or not hasattr(self.root, "after"):
            return
        self._anki_poll_after_id = self.root.after(
            ANKI_POLL_REFRESH_INTERVAL_MS,
            self.run_anki_connection_poll,
        )

    def run_anki_connection_poll(self) -> None:
        self._anki_poll_after_id = None
        if not self.sync_to_anki_var.get():
            return
        self.refresh_anki_connection(show_error_dialog=False, quiet=True)
        self.start_anki_connection_polling()

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
                flatten_note_links=self.flatten_note_links_var.get(),
            )
        except FormValidationError as exc:
            messagebox.showerror(exc.title, exc.message)
            return None

    def set_busy(self, busy: bool) -> None:
        set_busy_helper(self, busy)

    def start_preview(self) -> None:
        start_preview_helper(
            self,
            replace_options=replace,
            format_target_tags=format_target_tags,
            start_preview_scan=start_preview_scan,
            messagebox_module=messagebox,
        )

    def finish_preview_success(
        self,
        options: ExportOptions,
        scan_result: ScanResult,
        anki_preflight_summary: AnkiPreflightSummary | None = None,
        anki_preflight_error: str | None = None,
        anki_preflight_result: AnkiPreflightResult | None = None,
    ) -> None:
        finish_preview_success_helper(
            self,
            options,
            scan_result,
            anki_preflight_summary,
            anki_preflight_error,
            anki_preflight_result,
            preview_no_matches_message=preview_no_matches_message,
            preview_ready_message=preview_ready_message,
            timing_breakdown_lines=timing_breakdown_lines,
            duplicate_front_warning_message=duplicate_front_warning_message,
            show_preview_dialog=show_preview_dialog,
            delivery_action_label=delivery_action_label,
            messagebox_module=messagebox,
        )

    def finish_preview_error(self, error_message: str, details: str | None = None) -> None:
        finish_preview_error_helper(
            self,
            error_message,
            details,
            messagebox_module=messagebox,
        )

    def begin_delivery(
        self,
        options: ExportOptions,
        scan_result: ScanResult,
        anki_preflight_result: AnkiPreflightResult | None = None,
    ) -> None:
        begin_delivery_helper(
            self,
            options,
            scan_result,
            anki_preflight_result,
            delivery_action_label=delivery_action_label,
            delivery_progress_message=delivery_progress_message,
            format_target_tags=format_target_tags,
            start_delivery=start_delivery,
        )

    def finish_delivery_success(
        self,
        options: ExportOptions,
        scan_result: ScanResult,
        delivery_result: DeliveryResult,
    ) -> None:
        finish_delivery_success_helper(
            self,
            options,
            scan_result,
            delivery_result,
            export_no_cards_message=export_no_cards_message,
            delivery_complete_message=delivery_complete_message,
            delivery_complete_title=delivery_complete_title,
            timing_breakdown_lines=timing_breakdown_lines,
            messagebox_module=messagebox,
        )

    def finish_delivery_error(self, error_message: str, details: str | None = None) -> None:
        finish_delivery_error_helper(
            self,
            error_message,
            details,
            messagebox_module=messagebox,
        )

    def log(self, message: str) -> None:
        log_helper(self, message)


def launch_gui() -> int:
    if tk is None or ttk is None or filedialog is None or messagebox is None:
        print("Error: Tkinter is not available in this Python installation.", file=sys.stderr)
        return 1

    root = tk.Tk()
    ExporterApp(root)
    root.mainloop()
    return 0
