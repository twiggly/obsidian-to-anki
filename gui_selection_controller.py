from __future__ import annotations

from typing import Callable, Sequence

from gui_state import sanitize_string_values


def set_folder_filters(
    app: object,
    folder_filters: list[str],
    render_tag_chips: Callable[..., list[object]],
) -> None:
    app.folder_filters = sanitize_string_values(folder_filters)
    if not hasattr(app.folder_filters_container, "winfo_children"):
        app.folder_filter_remove_buttons = []
        return
    app.folder_filter_remove_buttons = render_tag_chips(
        app.folder_filters_container,
        app.folder_filters,
        app.remove_folder_filter,
        disabled=app.is_busy,
        empty_text="No folders selected",
    )


def set_selected_tags(
    app: object,
    tags: list[str],
    render_tag_chips: Callable[..., list[object]],
) -> None:
    app.selected_tags = sanitize_string_values(tags)
    if not hasattr(app.selected_tags_container, "tk"):
        app.selected_tag_remove_buttons = []
        return
    app.selected_tag_remove_buttons = render_tag_chips(
        app.selected_tags_container,
        app.selected_tags,
        app.remove_tag,
        disabled=app.is_busy,
    )


def add_selected_tag(
    app: object,
    append_unique_value: Callable[[Sequence[str], str], list[str]],
) -> None:
    tag_value = app.tag_var.get().strip()
    updated_values = append_unique_value(
        app.get_selected_tags_from_listbox(),
        tag_value,
    )
    app.set_selected_tags_in_listbox(updated_values)
    if tag_value:
        app.tag_var.set("")
        app.tag_combobox.set("")


def remove_tag(app: object, tag: str) -> None:
    updated_values = [value for value in app.get_selected_tags_from_listbox() if value != tag]
    app.set_selected_tags_in_listbox(updated_values)


def add_folder_filter(
    app: object,
    add_folder_filter_from_dialog: Callable[[str, Sequence[str], Callable[[str], None]], list[str] | None],
) -> None:
    updated_values = add_folder_filter_from_dialog(
        app.vault_var.get(),
        app.get_folder_filters_from_listbox(),
        app.log,
    )
    if updated_values is not None:
        app.set_folder_filters_in_listbox(updated_values)


def remove_folder_filter(app: object, folder_filter: str) -> None:
    existing_values = app.get_folder_filters_from_listbox()
    updated_values = [value for value in existing_values if value != folder_filter]
    if updated_values != existing_values:
        app.log(f"Removed folder filter: {folder_filter}")
    app.set_folder_filters_in_listbox(updated_values)


def scan_vault_tags(
    app: object,
    build_tag_scan_request: Callable[[str, Sequence[str]], tuple[object, tuple[str, ...]]],
    start_tag_catalog_scan: Callable[..., None],
    messagebox_module: object,
) -> None:
    if app.is_busy:
        return

    try:
        vault_path, include_folders = build_tag_scan_request(
            app.vault_var.get(),
            app.get_folder_filters_from_listbox(),
        )
    except Exception as exc:
        messagebox_module.showerror(exc.title, exc.message)
        return

    app.set_busy(True)
    app.status_var.set("Scanning vault for tags…")
    app.log("Scanning vault to find available tags.")
    start_tag_catalog_scan(
        app.root,
        vault_path,
        include_folders,
        app.finish_tag_scan_success,
        app.finish_tag_scan_error,
    )


def finish_tag_scan_success(app: object, tag_names: tuple[str, ...]) -> None:
    app.set_busy(False)
    current_tag = app.tag_var.get().strip()
    app.tag_combobox.configure(values=tag_names)
    if not current_tag:
        app.tag_combobox.set("")
        app.tag_var.set("")
    if tag_names:
        message = f"Found {len(tag_names)} tags in the scanned vault."
    else:
        message = "No tags were found in the scanned vault."
    app.status_var.set(message)
    app.log(message)


def finish_tag_scan_error(
    app: object,
    error_message: str,
    details: str | None,
    messagebox_module: object,
) -> None:
    app.set_busy(False)
    app.status_var.set(error_message)
    if details is None:
        app.log(f"Error: {error_message}")
    else:
        app.log(error_message)
        app.log(details.rstrip())
    messagebox_module.showerror("Tag scan failed", error_message)
