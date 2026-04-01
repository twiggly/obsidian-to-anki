from __future__ import annotations

from typing import Callable


def set_anki_connection_status(app: object, status: str) -> None:
    status_map = {
        "off": ("Sync off", "AnkiOff.TLabel"),
        "loading": ("Checking…", "AnkiPending.TLabel"),
        "connected": ("Connected", "AnkiConnected.TLabel"),
        "error": ("Connection failed", "AnkiError.TLabel"),
    }
    text, style_name = status_map.get(status, status_map["off"])
    app.anki_connection_var.set(text)
    app.anki_connection_indicator.configure(style=style_name)


def sync_anki_option_state(
    app: object,
    apply_widget_state: Callable[[bool, object], None],
) -> None:
    sync_enabled = app.sync_to_anki_var.get()
    apply_widget_state(
        sync_enabled,
        [
            app.anki_connect_url_entry,
            app.anki_deck_combobox,
            app.anki_note_type_combobox,
            app.anki_front_field_combobox,
            app.anki_back_field_combobox,
            app.anki_existing_notes_combobox,
            app.install_note_type_button,
            app.apply_deck_settings_button,
        ],
    )
    if sync_enabled:
        app.start_anki_connection_polling()
        if app._last_loaded_anki_url is not None:
            app.set_anki_connection_status("connected")
        app.refresh_anki_catalog_if_needed()
    else:
        app.cancel_anki_connection_refresh()
        app.stop_anki_connection_polling()
        app.set_anki_connection_status("off")


def refresh_anki_catalog_if_needed(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
) -> None:
    if not app.sync_to_anki_var.get():
        return
    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except Exception:
        return
    if normalized_url == app._last_loaded_anki_url:
        app.refresh_anki_fields_if_needed()
        return
    app.refresh_anki_catalog(show_error_dialog=False)


def refresh_anki_fields_if_needed(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
) -> None:
    if not app.sync_to_anki_var.get():
        return
    note_type_name = app.anki_note_type_var.get().strip()
    if not note_type_name:
        return
    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except Exception:
        return
    if (
        normalized_url == app._last_loaded_anki_url
        and note_type_name == app._last_loaded_anki_note_type
    ):
        return
    app.refresh_anki_fields(note_type_name=note_type_name, show_error_dialog=False)


def refresh_anki_catalog(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
    start_anki_catalog_refresh: Callable[..., None],
    messagebox_module: object,
    *,
    show_error_dialog: bool = True,
    quiet: bool = False,
) -> None:
    if app.is_busy or app._anki_catalog_loading:
        return

    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except Exception as exc:
        app._last_loaded_anki_url = None
        app._last_loaded_anki_note_type = None
        app.set_anki_connection_status("error")
        if not quiet:
            app.status_var.set(str(exc))
            app.log(f"Error: {exc}")
        if show_error_dialog and not quiet:
            messagebox_module.showerror("Anki refresh failed", str(exc))
        return
    app._anki_catalog_loading = True
    app._pending_anki_catalog_url = normalized_url
    if not quiet:
        app.set_anki_connection_status("loading")
    if not quiet:
        app.status_var.set("Loading Anki decks and note types…")
        app.log("Loading deck and note type lists from AnkiConnect.")
    start_anki_catalog_refresh(
        app.root,
        normalized_url,
        lambda catalog: app.finish_anki_catalog_refresh_success(catalog, quiet=quiet),
        lambda error_message, details=None: app.finish_anki_catalog_refresh_error(
            error_message,
            details,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
        ),
    )


def refresh_anki_connection(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
    start_anki_connection_check: Callable[..., None],
    messagebox_module: object,
    *,
    show_error_dialog: bool = True,
    quiet: bool = False,
) -> None:
    if app.is_busy or app._anki_catalog_loading or getattr(app, "_anki_connection_check_loading", False):
        return

    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except Exception as exc:
        app._last_loaded_anki_url = None
        app._last_loaded_anki_note_type = None
        app.set_anki_connection_status("error")
        if not quiet:
            app.status_var.set(str(exc))
            app.log(f"Error: {exc}")
        if show_error_dialog and not quiet:
            messagebox_module.showerror("Anki refresh failed", str(exc))
        return

    app._anki_connection_check_loading = True
    if not quiet:
        app.set_anki_connection_status("loading")
        app.status_var.set("Checking Anki availability…")
        app.log("Checking whether AnkiConnect is available.")
    start_anki_connection_check(
        app.root,
        normalized_url,
        lambda: app.finish_anki_connection_check_success(normalized_url, quiet=quiet),
        lambda error_message, details=None: app.finish_anki_connection_check_error(
            error_message,
            details,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
        ),
    )


def refresh_anki_fields(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
    start_anki_field_catalog_refresh: Callable[..., None],
    messagebox_module: object,
    *,
    note_type_name: str | None = None,
    show_error_dialog: bool = True,
) -> None:
    if app.is_busy or app._anki_field_loading or not app.sync_to_anki_var.get():
        return

    resolved_note_type = (note_type_name or app.anki_note_type_var.get()).strip()
    if not resolved_note_type:
        return
    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except Exception as exc:
        app.status_var.set(str(exc))
        app.log(f"Error: {exc}")
        if show_error_dialog:
            messagebox_module.showerror("Anki field refresh failed", str(exc))
        return
    app._anki_field_loading = True
    app._pending_anki_field_key = (normalized_url, resolved_note_type)
    app.status_var.set(f"Loading fields for note type '{resolved_note_type}'…")
    app.log(f"Loading Anki field names for note type '{resolved_note_type}'.")
    start_anki_field_catalog_refresh(
        app.root,
        normalized_url,
        resolved_note_type,
        app.finish_anki_field_refresh_success,
        lambda error_message, details=None: app.finish_anki_field_refresh_error(
            error_message,
            details,
            show_error_dialog=show_error_dialog,
        ),
    )


def finish_anki_catalog_refresh_success(
    app: object,
    catalog: object,
    set_combobox_choices: Callable[[object, object, str], str],
    *,
    quiet: bool = False,
) -> None:
    app._anki_catalog_loading = False
    app._last_loaded_anki_url = app._pending_anki_catalog_url
    app._pending_anki_catalog_url = None
    set_combobox_choices(app.anki_deck_combobox, catalog.deck_names, app.anki_deck_var.get())
    set_combobox_choices(
        app.anki_note_type_combobox,
        catalog.note_type_names,
        app.anki_note_type_var.get(),
    )
    app.set_anki_connection_status("connected")
    loaded_message = (
        f"Loaded {len(catalog.deck_names)} decks and {len(catalog.note_type_names)} note types from AnkiConnect."
    )
    if not quiet:
        app.status_var.set(loaded_message)
        app.log(loaded_message)
    app.refresh_anki_fields_if_needed()


def finish_anki_catalog_refresh_error(
    app: object,
    error_message: str,
    details: str | None,
    messagebox_module: object,
    *,
    show_error_dialog: bool = True,
    quiet: bool = False,
) -> None:
    app._anki_catalog_loading = False
    app._pending_anki_catalog_url = None
    app._last_loaded_anki_url = None
    app._last_loaded_anki_note_type = None
    app.set_anki_connection_status("error")
    if not quiet:
        app.status_var.set(error_message)
        if details is None:
            app.log(f"Error: {error_message}")
        else:
            app.log(error_message)
            app.log(details.rstrip())
    if show_error_dialog and not quiet:
        messagebox_module.showerror("Anki refresh failed", error_message)


def finish_anki_connection_check_success(
    app: object,
    normalized_url: str,
    *,
    quiet: bool = False,
) -> None:
    app._anki_connection_check_loading = False
    app.set_anki_connection_status("connected")
    if app._last_loaded_anki_url != normalized_url:
        app.refresh_anki_catalog(show_error_dialog=False, quiet=True)
        return
    if not quiet:
        app.status_var.set("Connected to AnkiConnect.")
        app.log("Connected to AnkiConnect.")


def finish_anki_connection_check_error(
    app: object,
    error_message: str,
    details: str | None,
    messagebox_module: object,
    *,
    show_error_dialog: bool = True,
    quiet: bool = False,
) -> None:
    app._anki_connection_check_loading = False
    app._last_loaded_anki_url = None
    app._last_loaded_anki_note_type = None
    app.set_anki_connection_status("error")
    if not quiet:
        app.status_var.set(error_message)
        if details is None:
            app.log(f"Error: {error_message}")
        else:
            app.log(error_message)
            app.log(details.rstrip())
    if show_error_dialog and not quiet:
        messagebox_module.showerror("Anki refresh failed", error_message)


def finish_anki_field_refresh_success(
    app: object,
    field_catalog: object,
    set_anki_field_choices: Callable[[object, object, object, str, str], tuple[str, str]],
) -> None:
    app._anki_field_loading = False
    if app._pending_anki_field_key is not None:
        app._last_loaded_anki_url, app._last_loaded_anki_note_type = app._pending_anki_field_key
    app._pending_anki_field_key = None
    set_anki_field_choices(
        app.anki_front_field_combobox,
        app.anki_back_field_combobox,
        field_catalog.field_names,
        app.anki_front_field_var.get(),
        app.anki_back_field_var.get(),
    )
    loaded_message = (
        f"Loaded {len(field_catalog.field_names)} fields for note type '{field_catalog.note_type_name}'."
    )
    app.status_var.set(loaded_message)
    app.log(loaded_message)


def finish_anki_field_refresh_error(
    app: object,
    error_message: str,
    details: str | None,
    messagebox_module: object,
    *,
    show_error_dialog: bool = True,
) -> None:
    app._anki_field_loading = False
    app._pending_anki_field_key = None
    app.status_var.set(error_message)
    if details is None:
        app.log(f"Error: {error_message}")
    else:
        app.log(error_message)
        app.log(details.rstrip())
    if show_error_dialog:
        messagebox_module.showerror("Anki field refresh failed", error_message)
