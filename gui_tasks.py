from __future__ import annotations

import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from anki_sync import fetch_anki_catalog, fetch_note_type_fields
from common import PREVIEW_CARD_LIMIT, unexpected_error_message
from delivery import deliver_cards
from models import (
    AnkiCatalog,
    AnkiFieldCatalog,
    DeliveryResult,
    ExportError,
    ExportOptions,
    ScanResult,
)
from reporting import attach_delivery_report
from scanner import scan_cards, scan_vault_tags

if TYPE_CHECKING:
    import tkinter as tk


def run_preview_scan_callbacks(
    options: ExportOptions,
    on_success: Callable[[ExportOptions, ScanResult], None],
    on_error: Callable[[str, str | None], None],
    scan_fn: Callable[[ExportOptions, int], ScanResult] = scan_cards,
) -> None:
    try:
        scan_result = scan_fn(options, PREVIEW_CARD_LIMIT)
        on_success(options, scan_result)
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
    on_success: Callable[[ExportOptions, ScanResult], None],
    on_error: Callable[[str, str | None], None],
) -> None:
    def worker() -> None:
        run_preview_scan_callbacks(
            options,
            lambda completed_options, scan_result: root.after(0, on_success, completed_options, scan_result),
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


def run_delivery_callbacks(
    options: ExportOptions,
    scan_result: ScanResult,
    on_success: Callable[[ExportOptions, ScanResult, DeliveryResult], None],
    on_error: Callable[[str, str | None], None],
    deliver_fn: Callable[[ExportOptions, list], DeliveryResult] = deliver_cards,
) -> None:
    try:
        delivery_result = deliver_fn(options, scan_result.cards)
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
        )

    threading.Thread(target=worker, daemon=True).start()
