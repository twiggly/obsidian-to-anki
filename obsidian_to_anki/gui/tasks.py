from __future__ import annotations

import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Callable

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
    AnkiNoteTypeInstallResult,
    AnkiPreflightResult,
    AnkiPreflightSummary,
    AnkiFieldCatalog,
    DeliveryResult,
    ExportError,
    ExportOptions,
    ScanResult,
)
from ..reporting import attach_delivery_report
from ..scanner import scan_cards, scan_vault_tags

if TYPE_CHECKING:
    import tkinter as tk


def run_preview_scan_callbacks(
    options: ExportOptions,
    on_success: Callable[
        [ExportOptions, ScanResult, AnkiPreflightSummary | None, str | None, AnkiPreflightResult | None],
        None,
    ],
    on_error: Callable[[str, str | None], None],
    scan_fn: Callable[[ExportOptions, int], ScanResult] = scan_cards,
    preflight_fn: Callable[[ExportOptions, list], AnkiPreflightResult] = build_anki_preflight_result,
) -> None:
    try:
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
        on_success(options, scan_result, preflight_summary, preflight_error, preflight_result)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("preview"),
            traceback.format_exc(),
        )


def start_preview_scan(
    root: tk.Misc,
    options: ExportOptions,
    on_success: Callable[
        [ExportOptions, ScanResult, AnkiPreflightSummary | None, str | None, AnkiPreflightResult | None],
        None,
    ],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_preview_scan_callbacks(
            options,
            lambda completed_options, scan_result, preflight_summary, preflight_error, preflight_result: root.after(
                0,
                on_success,
                completed_options,
                scan_result,
                preflight_summary,
                preflight_error,
                preflight_result,
            ),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def run_tag_catalog_callbacks(
    vault_path: Path,
    include_folders: tuple[str, ...],
    on_success: Callable[[tuple[str, ...]], None],
    on_error: Callable[[str, str | None], None],
    scan_fn: Callable[[Path, tuple[str, ...]], tuple[str, ...]] = scan_vault_tags,
) -> None:
    try:
        tag_names = scan_fn(vault_path, include_folders)
        on_success(tag_names)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("tag scan"),
            traceback.format_exc(),
        )


def start_tag_catalog_scan(
    root: tk.Misc,
    vault_path: Path,
    include_folders: tuple[str, ...],
    on_success: Callable[[tuple[str, ...]], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_tag_catalog_callbacks(
            vault_path,
            include_folders,
            lambda tag_names: root.after(0, on_success, tag_names),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def run_anki_catalog_callbacks(
    anki_connect_url: str,
    on_success: Callable[[AnkiCatalog], None],
    on_error: Callable[[str, str | None], None],
    fetch_fn: Callable[[str], AnkiCatalog] = fetch_anki_catalog,
) -> None:
    try:
        catalog = fetch_fn(anki_connect_url)
        on_success(catalog)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("Anki refresh"),
            traceback.format_exc(),
        )


def run_anki_connection_check_callbacks(
    anki_connect_url: str,
    on_success: Callable[[], None],
    on_error: Callable[[str, str | None], None],
    check_fn: Callable[[str], None] = check_anki_connection,
) -> None:
    try:
        check_fn(anki_connect_url)
        on_success()
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("Anki connection check"),
            traceback.format_exc(),
        )


def start_anki_connection_check(
    root: tk.Misc,
    anki_connect_url: str,
    on_success: Callable[[], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_anki_connection_check_callbacks(
            anki_connect_url,
            lambda: root.after(0, on_success),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def start_anki_catalog_refresh(
    root: tk.Misc,
    anki_connect_url: str,
    on_success: Callable[[AnkiCatalog], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_anki_catalog_callbacks(
            anki_connect_url,
            lambda catalog: root.after(0, on_success, catalog),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def run_anki_field_catalog_callbacks(
    anki_connect_url: str,
    note_type_name: str,
    on_success: Callable[[AnkiFieldCatalog], None],
    on_error: Callable[[str, str | None], None],
    fetch_fn: Callable[[str, str], AnkiFieldCatalog] = fetch_note_type_fields,
) -> None:
    try:
        field_catalog = fetch_fn(anki_connect_url, note_type_name)
        on_success(field_catalog)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("Anki field refresh"),
            traceback.format_exc(),
        )


def start_anki_field_catalog_refresh(
    root: tk.Misc,
    anki_connect_url: str,
    note_type_name: str,
    on_success: Callable[[AnkiFieldCatalog], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_anki_field_catalog_callbacks(
            anki_connect_url,
            note_type_name,
            lambda field_catalog: root.after(0, on_success, field_catalog),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def run_anki_note_type_install_callbacks(
    anki_connect_url: str,
    on_success: Callable[[AnkiNoteTypeInstallResult], None],
    on_error: Callable[[str, str | None], None],
    install_fn: Callable[[str], AnkiNoteTypeInstallResult] = install_obsidian_definitions_note_type,
) -> None:
    try:
        result = install_fn(anki_connect_url)
        on_success(result)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("note type install"),
            traceback.format_exc(),
        )


def run_anki_deck_settings_callbacks(
    anki_connect_url: str,
    deck_name: str,
    on_success: Callable[[AnkiDeckSettingsResult], None],
    on_error: Callable[[str, str | None], None],
    apply_fn: Callable[[str, str], AnkiDeckSettingsResult] = apply_recommended_deck_settings,
) -> None:
    try:
        result = apply_fn(anki_connect_url, deck_name)
        on_success(result)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("deck settings update"),
            traceback.format_exc(),
        )


def start_anki_note_type_install(
    root: tk.Misc,
    anki_connect_url: str,
    on_success: Callable[[AnkiNoteTypeInstallResult], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_anki_note_type_install_callbacks(
            anki_connect_url,
            lambda result: root.after(0, on_success, result),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def start_anki_deck_settings_update(
    root: tk.Misc,
    anki_connect_url: str,
    deck_name: str,
    on_success: Callable[[AnkiDeckSettingsResult], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_anki_deck_settings_callbacks(
            anki_connect_url,
            deck_name,
            lambda result: root.after(0, on_success, result),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
        )

    threading.Thread(target=worker, daemon=True).start()


def run_delivery_callbacks(
    options: ExportOptions,
    scan_result: ScanResult,
    on_success: Callable[[ExportOptions, ScanResult, DeliveryResult], None],
    on_error: Callable[[str, str | None], None],
    deliver_fn: Callable[[ExportOptions, list, AnkiPreflightResult | None], DeliveryResult] = deliver_cards,
    anki_preflight_result: AnkiPreflightResult | None = None,
) -> None:
    try:
        delivery_result = deliver_fn(options, scan_result.cards, anki_preflight_result)
        delivery_result = attach_delivery_report(options, scan_result, delivery_result)
        on_success(options, scan_result, delivery_result)
    except (ExportError, OSError) as exc:
        on_error(str(exc), None)
    except Exception:
        on_error(
            unexpected_error_message("delivery"),
            traceback.format_exc(),
        )


def start_delivery(
    root: tk.Misc,
    options: ExportOptions,
    scan_result: ScanResult,
    on_success: Callable[[ExportOptions, ScanResult, DeliveryResult], None],
    on_error: Callable[[str, str | None], None],
    anki_preflight_result: AnkiPreflightResult | None = None,
) -> None:
    def worker() -> None:
        run_delivery_callbacks(
            options,
            scan_result,
            lambda completed_options, completed_scan_result, delivery_result: root.after(
                0,
                on_success,
                completed_options,
                completed_scan_result,
                delivery_result,
            ),
            lambda error_message, details=None: root.after(0, on_error, error_message, details),
            anki_preflight_result=anki_preflight_result,
        )

    threading.Thread(target=worker, daemon=True).start()
