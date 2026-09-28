from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from ..anki.sync import (
    apply_recommended_deck_settings,
    build_anki_preflight_result,
    check_anki_connection,
    fetch_anki_catalog,
    fetch_note_type_fields,
    install_obsidian_definitions_note_type,
)
from ..common import PREVIEW_CARD_LIMIT, unexpected_error_message
from ..delivery import deliver_cards
from ..models import (
    AnkiCatalog,
    AnkiDeckSettingsResult,
    AnkiFieldCatalog,
    AnkiNoteTypeInstallResult,
    AnkiPreflightResult,
    AnkiPreflightSummary,
    DeliveryResult,
    ExportError,
    ExportOptions,
    NoteCard,
    ScanResult,
)
from ..reporting import attach_delivery_report
from ..scanner import scan_cards, scan_vault_tags

if TYPE_CHECKING:
    import tkinter as tk


_Result = TypeVar("_Result")
_Args = ParamSpec("_Args")
_ErrorCallback = Callable[[str, str | None], None]


def _run_task(
    operation: Callable[[], _Result],
    action: str,
    on_success: Callable[[_Result], None],
    on_error: _ErrorCallback,
) -> None:
    try:
        result = operation()
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(unexpected_error_message(action), traceback.format_exc())
    else:
        # Completion failures must not be reported as failed exports or Anki writes.
        on_success(result)


def _on_main_thread(
    root: tk.Misc,
    callback: Callable[_Args, None],
) -> Callable[_Args, None]:
    def schedule(*args: _Args.args, **kwargs: _Args.kwargs) -> None:
        root.after(0, partial(callback, *args, **kwargs))

    return schedule


def _start_task(
    root: tk.Misc,
    run_callbacks: Callable[[Callable[_Args, None], _ErrorCallback], None],
    on_success: Callable[_Args, None],
    on_error: _ErrorCallback,
) -> None:
    worker = partial(
        run_callbacks,
        _on_main_thread(root, on_success),
        _on_main_thread(root, on_error),
    )
    threading.Thread(target=worker, daemon=True).start()


def run_preview_scan_callbacks(
    options: ExportOptions,
    on_success: Callable[
        [
            ExportOptions,
            ScanResult,
            AnkiPreflightSummary | None,
            str | None,
            AnkiPreflightResult | None,
        ],
        None,
    ],
    on_error: Callable[[str, str | None], None],
    scan_fn: Callable[[ExportOptions, int], ScanResult] = scan_cards,
    preflight_fn: Callable[
        [ExportOptions, list], AnkiPreflightResult
    ] = build_anki_preflight_result,
) -> None:
    def operation() -> tuple[
        ScanResult, AnkiPreflightSummary | None, str | None, AnkiPreflightResult | None
    ]:
        scan_result = scan_fn(options, PREVIEW_CARD_LIMIT)
        preflight_summary: AnkiPreflightSummary | None = None
        preflight_error: str | None = None
        preflight_result: AnkiPreflightResult | None = None
        if options.sync_to_anki:
            try:
                preflight_result = preflight_fn(options, scan_result.cards)
                preflight_summary = preflight_result.summary
            except (ExportError, OSError) as exc:
                preflight_error = str(exc)
            except Exception:
                preflight_error = unexpected_error_message("Anki preflight")
        return scan_result, preflight_summary, preflight_error, preflight_result

    _run_task(operation, "preview", lambda result: on_success(options, *result), on_error)


def start_preview_scan(
    root: tk.Misc,
    options: ExportOptions,
    on_success: Callable[
        [
            ExportOptions,
            ScanResult,
            AnkiPreflightSummary | None,
            str | None,
            AnkiPreflightResult | None,
        ],
        None,
    ],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_preview_scan_callbacks(options, success, error),
        on_success,
        on_error,
    )


def run_tag_catalog_callbacks(
    vault_path: Path,
    include_folders: tuple[str, ...],
    on_success: Callable[[tuple[str, ...]], None],
    on_error: Callable[[str, str | None], None],
    scan_fn: Callable[[Path, tuple[str, ...]], tuple[str, ...]] = scan_vault_tags,
) -> None:
    _run_task(lambda: scan_fn(vault_path, include_folders), "tag scan", on_success, on_error)


def start_tag_catalog_scan(
    root: tk.Misc,
    vault_path: Path,
    include_folders: tuple[str, ...],
    on_success: Callable[[tuple[str, ...]], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_tag_catalog_callbacks(
            vault_path, include_folders, success, error
        ),
        on_success,
        on_error,
    )


def run_anki_catalog_callbacks(
    anki_connect_url: str,
    on_success: Callable[[AnkiCatalog], None],
    on_error: Callable[[str, str | None], None],
    fetch_fn: Callable[[str], AnkiCatalog] = fetch_anki_catalog,
) -> None:
    _run_task(lambda: fetch_fn(anki_connect_url), "Anki refresh", on_success, on_error)


def run_anki_connection_check_callbacks(
    anki_connect_url: str,
    on_success: Callable[[], None],
    on_error: Callable[[str, str | None], None],
    check_fn: Callable[[str], None] = check_anki_connection,
) -> None:
    _run_task(
        lambda: check_fn(anki_connect_url),
        "Anki connection check",
        lambda _: on_success(),
        on_error,
    )


def start_anki_connection_check(
    root: tk.Misc,
    anki_connect_url: str,
    on_success: Callable[[], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_anki_connection_check_callbacks(
            anki_connect_url, success, error
        ),
        on_success,
        on_error,
    )


def start_anki_catalog_refresh(
    root: tk.Misc,
    anki_connect_url: str,
    on_success: Callable[[AnkiCatalog], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_anki_catalog_callbacks(anki_connect_url, success, error),
        on_success,
        on_error,
    )


def run_anki_field_catalog_callbacks(
    anki_connect_url: str,
    note_type_name: str,
    on_success: Callable[[AnkiFieldCatalog], None],
    on_error: Callable[[str, str | None], None],
    fetch_fn: Callable[[str, str], AnkiFieldCatalog] = fetch_note_type_fields,
) -> None:
    _run_task(
        lambda: fetch_fn(anki_connect_url, note_type_name),
        "Anki field refresh",
        on_success,
        on_error,
    )


def start_anki_field_catalog_refresh(
    root: tk.Misc,
    anki_connect_url: str,
    note_type_name: str,
    on_success: Callable[[AnkiFieldCatalog], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_anki_field_catalog_callbacks(
            anki_connect_url, note_type_name, success, error
        ),
        on_success,
        on_error,
    )


def run_anki_note_type_install_callbacks(
    anki_connect_url: str,
    on_success: Callable[[AnkiNoteTypeInstallResult], None],
    on_error: Callable[[str, str | None], None],
    install_fn: Callable[[str], AnkiNoteTypeInstallResult] = install_obsidian_definitions_note_type,
) -> None:
    _run_task(lambda: install_fn(anki_connect_url), "note type install", on_success, on_error)


def run_anki_deck_settings_callbacks(
    anki_connect_url: str,
    deck_name: str,
    on_success: Callable[[AnkiDeckSettingsResult], None],
    on_error: Callable[[str, str | None], None],
    apply_fn: Callable[[str, str], AnkiDeckSettingsResult] = apply_recommended_deck_settings,
) -> None:
    _run_task(
        lambda: apply_fn(anki_connect_url, deck_name),
        "deck settings update",
        on_success,
        on_error,
    )


def start_anki_note_type_install(
    root: tk.Misc,
    anki_connect_url: str,
    on_success: Callable[[AnkiNoteTypeInstallResult], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_anki_note_type_install_callbacks(
            anki_connect_url, success, error
        ),
        on_success,
        on_error,
    )


def start_anki_deck_settings_update(
    root: tk.Misc,
    anki_connect_url: str,
    deck_name: str,
    on_success: Callable[[AnkiDeckSettingsResult], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    _start_task(
        root,
        lambda success, error: run_anki_deck_settings_callbacks(
            anki_connect_url, deck_name, success, error
        ),
        on_success,
        on_error,
    )


def _deliver_with_preflight(
    options: ExportOptions,
    cards: list[NoteCard],
    anki_preflight_result: AnkiPreflightResult | None,
) -> DeliveryResult:
    return deliver_cards(options, cards, anki_preflight_result=anki_preflight_result)


def run_delivery_callbacks(
    options: ExportOptions,
    scan_result: ScanResult,
    on_success: Callable[[ExportOptions, ScanResult, DeliveryResult], None],
    on_error: Callable[[str, str | None], None],
    deliver_fn: Callable[
        [ExportOptions, list, AnkiPreflightResult | None], DeliveryResult
    ] = _deliver_with_preflight,
    anki_preflight_result: AnkiPreflightResult | None = None,
) -> None:
    def operation() -> DeliveryResult:
        delivery_result = deliver_fn(options, scan_result.cards, anki_preflight_result)
        return attach_delivery_report(options, scan_result, delivery_result)

    _run_task(
        operation, "delivery", lambda result: on_success(options, scan_result, result), on_error
    )


def start_delivery(
    root: tk.Misc,
    options: ExportOptions,
    scan_result: ScanResult,
    on_success: Callable[[ExportOptions, ScanResult, DeliveryResult], None],
    on_error: Callable[[str, str | None], None],
    anki_preflight_result: AnkiPreflightResult | None = None,
) -> None:
    _start_task(
        root,
        lambda success, error: run_delivery_callbacks(
            options,
            scan_result,
            success,
            error,
            anki_preflight_result=anki_preflight_result,
        ),
        on_success,
        on_error,
    )
