from __future__ import annotations

from collections.abc import Sequence

from ..common import duplicate_handling_display_label, normalize_duplicate_handling
from ..models import ExportError
from .settings import _SCALAR_SETTINGS


def report_gui_error(
    app: object,
    error_message: str,
    details: str | None = None,
    *,
    title: str,
    messagebox_module: object,
    show_error_dialog: bool = True,
    quiet: bool = False,
) -> None:
    if quiet:
        return
    app.status_var.set(error_message)
    if details is None:
        app.log(f"Error: {error_message}")
    else:
        app.log(error_message)
        app.log(details.rstrip())
    if show_error_dialog:
        messagebox_module.showerror(title, error_message)


def sanitize_string_values(values: Sequence[object]) -> list[str]:
    cleaned_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        cleaned_values.append(cleaned)

    return cleaned_values


def apply_default_settings(
    app: object,
    *,
    default_output_path: str,
    default_target_tag: str,
    default_duplicate_handling: str,
    default_flatten_note_links: bool,
    default_anki_connect_url: str,
    default_anki_deck: str,
    default_anki_note_type: str,
    default_anki_front_field: str,
    default_anki_back_field: str,
    default_anki_existing_notes: str,
    default_status_message: str,
) -> None:
    overrides = {
        "output": default_output_path,
        "tag": default_target_tag,
        "duplicate_handling": default_duplicate_handling,
        "flatten_note_links": default_flatten_note_links,
        "anki_connect_url": default_anki_connect_url,
        "anki_deck": default_anki_deck,
        "anki_note_type": default_anki_note_type,
        "anki_front_field": default_anki_front_field,
        "anki_back_field": default_anki_back_field,
        "anki_existing_notes": default_anki_existing_notes,
    }
    for key, (variable_name, default) in _SCALAR_SETTINGS.items():
        getattr(app, variable_name).set(overrides.get(key, default))
    app.set_selected_tags_in_listbox([])
    app.skip_empty_var.set(True)
    app.duplicate_handling_display_var.set(
        duplicate_handling_display_label(default_duplicate_handling)
    )
    app.set_folder_filters_in_listbox([])
    app._last_loaded_anki_url = None
    app._last_loaded_anki_note_type = None
    app._pending_anki_catalog_url = None
    app._pending_anki_field_key = None
    app._anki_connection_check_loading = False
    app.status_var.set(default_status_message)
    app.sync_output_option_state()
    app.sync_html_option_state()
    app.sync_anki_option_state()


def apply_saved_settings(
    app: object,
    settings: dict[str, object],
    *,
    default_duplicate_handling: str,
) -> None:
    for key, (variable_name, default) in _SCALAR_SETTINGS.items():
        if key in {"skip_empty", "duplicate_handling"}:
            continue
        variable = getattr(app, variable_name)
        variable.set(type(default)(settings.get(key, variable.get())))

    saved_tags = settings.get("tags")
    cleaned_saved_tags = sanitize_string_values(saved_tags) if isinstance(saved_tags, list) else []
    if cleaned_saved_tags:
        app.set_selected_tags_in_listbox(cleaned_saved_tags)
    else:
        app.tag_var.set("")
        app.set_selected_tags_in_listbox([])

    app.skip_empty_var.set(True)

    saved_duplicate_handling = str(
        settings.get("duplicate_handling", app.duplicate_handling_var.get())
    )
    try:
        normalized_duplicate_handling = normalize_duplicate_handling(saved_duplicate_handling)
    except ExportError:
        normalized_duplicate_handling = default_duplicate_handling
    app.duplicate_handling_var.set(normalized_duplicate_handling)
    app.duplicate_handling_display_var.set(
        duplicate_handling_display_label(normalized_duplicate_handling)
    )

    include_folders = settings.get("include_folders", [])
    if isinstance(include_folders, list):
        app.set_folder_filters_in_listbox(include_folders)

    app.sync_output_option_state()
    app.sync_html_option_state()
    app.sync_anki_option_state()


def collect_settings(app: object) -> dict[str, object]:
    return {
        **{
            key: getattr(app, variable_name).get()
            for key, (variable_name, _) in _SCALAR_SETTINGS.items()
        },
        "tags": app.get_selected_tags_from_listbox(),
        "include_folders": app.get_folder_filters_from_listbox(),
    }


def sync_status_details_visibility(app: object) -> None:
    if app.status_details_visible:
        app.status_details_var.set("Hide Details")
        app.log_widget.grid()
    else:
        app.status_details_var.set("Show Details")
        app.log_widget.grid_remove()
