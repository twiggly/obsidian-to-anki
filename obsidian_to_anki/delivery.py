from __future__ import annotations

from time import perf_counter
from typing import Callable, Sequence

from .anki.sync import sync_cards_to_anki
from .exporting import run_export
from .models import AnkiPreflightResult, AnkiSyncResult, DeliveryResult, ExportOptions, NoteCard


def deliver_cards(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    export_fn: Callable[[ExportOptions, Sequence[NoteCard]], int] = run_export,
    sync_fn: Callable[[ExportOptions, Sequence[NoteCard], AnkiPreflightResult | None], AnkiSyncResult] = sync_cards_to_anki,
    anki_preflight_result: AnkiPreflightResult | None = None,
) -> DeliveryResult:
    if not cards:
        return DeliveryResult(output_path=options.output_path)

    delivery_started_at = perf_counter()
    export_count = 0
    export_seconds = 0.0
    if options.output_path is not None:
        export_started_at = perf_counter()
        export_count = export_fn(options, cards)
        export_seconds = perf_counter() - export_started_at

    sync_result = None
    sync_seconds = 0.0
    if options.sync_to_anki:
        sync_started_at = perf_counter()
        sync_result = sync_fn(options, cards, anki_preflight_result)
        sync_seconds = perf_counter() - sync_started_at

    return DeliveryResult(
        export_count=export_count,
        output_path=options.output_path,
        sync_result=sync_result,
        export_seconds=export_seconds,
        sync_seconds=sync_seconds,
        total_seconds=perf_counter() - delivery_started_at,
    )
