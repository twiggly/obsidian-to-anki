from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..models import ExportError
from .state import report_gui_error


@dataclass(frozen=True)
class _RefreshRequest:
    token: int
    url: str
    note_type: str | None = None


_REQUEST_LOADING_FLAGS = {
    "connection": "_anki_connection_check_loading",
    "catalog": "_anki_catalog_loading",
    "fields": "_anki_field_loading",
}


def _discard_request(app: object, kind: str) -> None:
    app._anki_refresh_requests.pop(kind, None)
    setattr(app, _REQUEST_LOADING_FLAGS[kind], False)
    if kind == "catalog":
        app._pending_anki_catalog_url = None
    elif kind == "fields":
        app._pending_anki_field_key = None


def invalidate_anki_refreshes(app: object, *, fields_only: bool = False) -> None:
    for kind in ("fields",) if fields_only else _REQUEST_LOADING_FLAGS:
        _discard_request(app, kind)
    app._last_loaded_anki_note_type = None
    if not fields_only:
        app._last_loaded_anki_url = None


def _observe_url(app: object, url: str) -> None:
    if app._anki_refresh_url is not None and app._anki_refresh_url != url:
        invalidate_anki_refreshes(app)
    app._anki_refresh_url = url


def _observe_note_type(app: object, note_type: str) -> None:
    if app._anki_refresh_note_type is not None and app._anki_refresh_note_type != note_type:
        invalidate_anki_refreshes(app, fields_only=True)
    app._anki_refresh_note_type = note_type


def _begin_request(
    app: object, kind: str, url: str, note_type: str | None = None
) -> _RefreshRequest:
    app._anki_refresh_sequence += 1
    request = _RefreshRequest(app._anki_refresh_sequence, url, note_type)
    app._anki_refresh_requests[kind] = request
    setattr(app, _REQUEST_LOADING_FLAGS[kind], True)
    return request


def _guard_refresh_callback(
    app: object,
    kind: str,
    request: _RefreshRequest,
    normalize_url: Callable[[str], str],
    callback: Callable[..., None],
) -> Callable[..., None]:
    def complete(*args: object, **kwargs: object) -> None:
        # An obsolete completion must never release a newer request's loading flag.
        if app._closing or app._anki_refresh_requests.get(kind) != request:
            return
        try:
            current_url = normalize_url(app.anki_connect_url_var.get())
        except ExportError:
            current_url = None
        if (
            not app.sync_to_anki_var.get()
            or current_url != request.url
            or (
                request.note_type is not None
                and app.anki_note_type_var.get().strip() != request.note_type
            )
        ):
            _discard_request(app, kind)
            return
        del app._anki_refresh_requests[kind]
        callback(*args, **kwargs)

    return complete


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
        invalidate_anki_refreshes(app)
        app.cancel_anki_connection_refresh()
        app.stop_anki_connection_polling()
        app.set_anki_connection_status("off")


def refresh_anki_catalog_if_needed(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
) -> None:
    if app._closing or not app.sync_to_anki_var.get():
        return
    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except ExportError:
        invalidate_anki_refreshes(app)
        return
    _observe_url(app, normalized_url)
    if normalized_url == app._last_loaded_anki_url:
        app.refresh_anki_fields_if_needed()
        return
    app.refresh_anki_catalog(show_error_dialog=False)


def refresh_anki_fields_if_needed(
    app: object,
    normalize_anki_connect_url: Callable[[str], str],
) -> None:
    if app._closing or not app.sync_to_anki_var.get():
        return
    note_type_name = app.anki_note_type_var.get().strip()
    _observe_note_type(app, note_type_name)
    if not note_type_name:
        return
    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except ExportError:
        invalidate_anki_refreshes(app)
        return
    _observe_url(app, normalized_url)
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
    if app._closing or app.is_busy or not app.sync_to_anki_var.get():
        return

    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except ExportError as exc:
        invalidate_anki_refreshes(app)
        app.set_anki_connection_status("error")
        report_gui_error(
            app,
            str(exc),
            title="Anki refresh failed",
            messagebox_module=messagebox_module,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
        )
        return
    _observe_url(app, normalized_url)
    if app._anki_catalog_loading:
        return
    _discard_request(app, "connection")
    request = _begin_request(app, "catalog", normalized_url)
    app._pending_anki_catalog_url = normalized_url
    if not quiet:
        app.set_anki_connection_status("loading")
        app.status_var.set("Loading Anki decks and note types…")
        app.log("Loading deck and note type lists from AnkiConnect.")
    start_anki_catalog_refresh(
        app.root,
        normalized_url,
        _guard_refresh_callback(
            app,
            "catalog",
            request,
            normalize_anki_connect_url,
            lambda catalog: app.finish_anki_catalog_refresh_success(catalog, quiet=quiet),
        ),
        _guard_refresh_callback(
            app,
            "catalog",
            request,
            normalize_anki_connect_url,
            lambda error_message, details=None: app.finish_anki_catalog_refresh_error(
                error_message,
                details,
                show_error_dialog=show_error_dialog,
                quiet=quiet,
            ),
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
    if app._closing or app.is_busy or not app.sync_to_anki_var.get():
        return

    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except ExportError as exc:
        invalidate_anki_refreshes(app)
        app.set_anki_connection_status("error")
        report_gui_error(
            app,
            str(exc),
            title="Anki refresh failed",
            messagebox_module=messagebox_module,
            show_error_dialog=show_error_dialog,
            quiet=quiet,
        )
        return
    _observe_url(app, normalized_url)
    if app._anki_catalog_loading or app._anki_connection_check_loading:
        return
    request = _begin_request(app, "connection", normalized_url)
    if not quiet:
        app.set_anki_connection_status("loading")
        app.status_var.set("Checking Anki availability…")
        app.log("Checking whether AnkiConnect is available.")
    start_anki_connection_check(
        app.root,
        normalized_url,
        _guard_refresh_callback(
            app,
            "connection",
            request,
            normalize_anki_connect_url,
            lambda: app.finish_anki_connection_check_success(normalized_url, quiet=quiet),
        ),
        _guard_refresh_callback(
            app,
            "connection",
            request,
            normalize_anki_connect_url,
            lambda error_message, details=None: app.finish_anki_connection_check_error(
                error_message,
                details,
                show_error_dialog=show_error_dialog,
                quiet=quiet,
            ),
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
    if app._closing or app.is_busy or not app.sync_to_anki_var.get():
        return

    resolved_note_type = (note_type_name or app.anki_note_type_var.get()).strip()
    _observe_note_type(app, resolved_note_type)
    if not resolved_note_type:
        return
    try:
        normalized_url = normalize_anki_connect_url(app.anki_connect_url_var.get())
    except ExportError as exc:
        invalidate_anki_refreshes(app)
        report_gui_error(
            app,
            str(exc),
            title="Anki field refresh failed",
            messagebox_module=messagebox_module,
            show_error_dialog=show_error_dialog,
        )
        return
    _observe_url(app, normalized_url)
    if app._anki_field_loading:
        return
    request = _begin_request(app, "fields", normalized_url, resolved_note_type)
    app._pending_anki_field_key = (normalized_url, resolved_note_type)
    app.status_var.set(f"Loading fields for note type '{resolved_note_type}'…")
    app.log(f"Loading Anki field names for note type '{resolved_note_type}'.")
    start_anki_field_catalog_refresh(
        app.root,
        normalized_url,
        resolved_note_type,
        _guard_refresh_callback(
            app,
            "fields",
            request,
            normalize_anki_connect_url,
            app.finish_anki_field_refresh_success,
        ),
        _guard_refresh_callback(
            app,
            "fields",
            request,
            normalize_anki_connect_url,
            lambda error_message, details=None: app.finish_anki_field_refresh_error(
                error_message,
                details,
                show_error_dialog=show_error_dialog,
            ),
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
    loaded_message = f"Loaded {len(catalog.deck_names)} decks and {len(catalog.note_type_names)} note types from AnkiConnect."
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
    invalidate_anki_refreshes(app)
    app.set_anki_connection_status("error")
    report_gui_error(
        app,
        error_message,
        details,
        title="Anki refresh failed",
        messagebox_module=messagebox_module,
        show_error_dialog=show_error_dialog,
        quiet=quiet,
    )


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
    invalidate_anki_refreshes(app)
    app.set_anki_connection_status("error")
    report_gui_error(
        app,
        error_message,
        details,
        title="Anki refresh failed",
        messagebox_module=messagebox_module,
        show_error_dialog=show_error_dialog,
        quiet=quiet,
    )


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
    loaded_message = f"Loaded {len(field_catalog.field_names)} fields for note type '{field_catalog.note_type_name}'."
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
    report_gui_error(
        app,
        error_message,
        details,
        title="Anki field refresh failed",
        messagebox_module=messagebox_module,
        show_error_dialog=show_error_dialog,
    )
