from __future__ import annotations

from typing import Sequence

from common import duplicate_handling_display_label, normalize_duplicate_handling


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
    default_anki_connect_url: str,
    default_anki_deck: str,
    default_anki_note_type: str,
    default_anki_front_field: str,
    default_anki_back_field: str,
    default_anki_existing_notes: str,
    default_status_message: str,
) -> None:
    app.vault_var.set("")
    app.output_var.set(default_output_path)
    app.write_tsv_var.set(True)
    app.tag_var.set(default_target_tag)
    app.set_selected_tags_in_listbox([])
    app.html_var.set(False)
    app.skip_empty_var.set(False)
    app.quoted_italic_var.set(False)
    app.duplicate_handling_var.set(default_duplicate_handling)
    app.duplicate_handling_display_var.set(
        duplicate_handling_display_label(default_duplicate_handling)
    )
    app.set_folder_filters_in_listbox([])
    app.sync_to_anki_var.set(False)
    app.anki_connect_url_var.set(default_anki_connect_url)
    app.anki_deck_var.set(default_anki_deck)
    app.anki_note_type_var.set(default_anki_note_type)
    app.anki_front_field_var.set(default_anki_front_field)
    app.anki_back_field_var.set(default_anki_back_field)
    app.anki_existing_notes_var.set(default_anki_existing_notes)
    app._last_loaded_anki_url = None
    app._last_loaded_anki_note_type = None
    app._pending_anki_catalog_url = None
    app._pending_anki_field_key = None
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
    app.vault_var.set(str(settings.get("vault", app.vault_var.get())))
    app.output_var.set(str(settings.get("output", app.output_var.get())))
    app.write_tsv_var.set(bool(settings.get("write_tsv", app.write_tsv_var.get())))
    app.tag_var.set(str(settings.get("tag", app.tag_var.get())))

    saved_tags = settings.get("tags")
    cleaned_saved_tags = sanitize_string_values(saved_tags) if isinstance(saved_tags, list) else []
    if cleaned_saved_tags:
        app.set_selected_tags_in_listbox(cleaned_saved_tags)
    else:
        app.tag_var.set("")
        app.set_selected_tags_in_listbox([])

    app.html_var.set(bool(settings.get("html_output", app.html_var.get())))
    app.skip_empty_var.set(bool(settings.get("skip_empty", app.skip_empty_var.get())))
    app.quoted_italic_var.set(
        bool(settings.get("italicize_quoted_text", app.quoted_italic_var.get()))
    )

    saved_duplicate_handling = str(
        settings.get("duplicate_handling", app.duplicate_handling_var.get())
    )
    try:
        normalized_duplicate_handling = normalize_duplicate_handling(saved_duplicate_handling)
    except Exception:
        normalized_duplicate_handling = default_duplicate_handling
    app.duplicate_handling_var.set(normalized_duplicate_handling)
    app.duplicate_handling_display_var.set(
        duplicate_handling_display_label(normalized_duplicate_handling)
    )

    app.sync_to_anki_var.set(bool(settings.get("sync_to_anki", app.sync_to_anki_var.get())))
    app.anki_connect_url_var.set(
        str(settings.get("anki_connect_url", app.anki_connect_url_var.get()))
    )
    app.anki_deck_var.set(str(settings.get("anki_deck", app.anki_deck_var.get())))
    app.anki_note_type_var.set(str(settings.get("anki_note_type", app.anki_note_type_var.get())))
    app.anki_front_field_var.set(
        str(settings.get("anki_front_field", app.anki_front_field_var.get()))
    )
    app.anki_back_field_var.set(
        str(settings.get("anki_back_field", app.anki_back_field_var.get()))
    )
    app.anki_existing_notes_var.set(
        str(settings.get("anki_existing_notes", app.anki_existing_notes_var.get()))
    )

    include_folders = settings.get("include_folders", [])
    if isinstance(include_folders, list):
        app.set_folder_filters_in_listbox(include_folders)

    app.sync_output_option_state()
    app.sync_html_option_state()
    app.sync_anki_option_state()


def collect_settings(app: object) -> dict[str, object]:
    return {
        "vault": app.vault_var.get(),
        "output": app.output_var.get(),
        "write_tsv": app.write_tsv_var.get(),
        "tag": app.tag_var.get(),
        "tags": app.get_selected_tags_from_listbox(),
        "html_output": app.html_var.get(),
        "skip_empty": app.skip_empty_var.get(),
        "italicize_quoted_text": app.quoted_italic_var.get(),
        "duplicate_handling": app.duplicate_handling_var.get(),
        "include_folders": app.get_folder_filters_from_listbox(),
        "sync_to_anki": app.sync_to_anki_var.get(),
        "anki_connect_url": app.anki_connect_url_var.get(),
        "anki_deck": app.anki_deck_var.get(),
        "anki_note_type": app.anki_note_type_var.get(),
        "anki_front_field": app.anki_front_field_var.get(),
        "anki_back_field": app.anki_back_field_var.get(),
        "anki_existing_notes": app.anki_existing_notes_var.get(),
    }


def sync_status_details_visibility(app: object) -> None:
    if app.status_details_visible:
        app.status_details_var.set("Hide Details")
        app.log_widget.grid()
    else:
        app.status_details_var.set("Show Details")
        app.log_widget.grid_remove()
