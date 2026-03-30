from __future__ import annotations

from time import perf_counter
from typing import Callable, Sequence

from anki_connect_client import AnkiConnectError
from anki_existing_notes import ExistingAnkiNote, PendingExistingNoteUpdate
from models import AnkiSyncResult, AnkiSyncTiming, ExportOptions, NoteCard


def build_anki_notes(options: ExportOptions, cards: Sequence[NoteCard]) -> list[dict[str, object]]:
    return [
        {
            "deckName": options.anki_deck,
            "modelName": options.anki_note_type,
            "fields": {
                options.anki_front_field: card.front,
                options.anki_back_field: card.back,
            },
            "options": {"allowDuplicate": False},
            "tags": card.tags,
        }
        for card in cards
    ]


def add_notes_batch(
    url: str,
    notes: Sequence[dict[str, object]],
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
) -> list[int | None]:
    if not notes:
        return []

    note_ids = invoke_anki_connect_fn(url, "addNotes", {"notes": list(notes)})
    if not isinstance(note_ids, list) or len(note_ids) != len(notes):
        raise AnkiConnectError("Received an unexpected response from addNotes.")
    if not all(
        note_id is None or (isinstance(note_id, int) and not isinstance(note_id, bool))
        for note_id in note_ids
    ):
        raise AnkiConnectError("Received an unexpected response from addNotes.")
    return note_ids


def add_single_note(
    url: str,
    note: dict[str, object],
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
) -> int:
    note_id = invoke_anki_connect_fn(url, "addNote", {"note": note})
    if isinstance(note_id, bool) or not isinstance(note_id, int):
        raise AnkiConnectError("AnkiConnect did not add a note successfully.")
    return note_id


def sync_cards_to_anki(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    *,
    validate_anki_target_fn: Callable[[ExportOptions], None],
    build_anki_notes_fn: Callable[[ExportOptions, Sequence[NoteCard]], list[dict[str, object]]],
    fetch_existing_notes_by_front_fn: Callable[[ExportOptions], dict[str, list[ExistingAnkiNote]]],
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
    note_front_value_fn: Callable[[dict[str, object], str], str],
    build_existing_note_update_plan_fn: Callable[
        [ExportOptions, dict[str, object], dict[str, list[ExistingAnkiNote]]],
        PendingExistingNoteUpdate | None,
    ],
    apply_existing_note_updates_fn: Callable[[str, Sequence[PendingExistingNoteUpdate]], None],
    add_notes_batch_fn: Callable[[str, Sequence[dict[str, object]]], list[int | None]],
    add_single_note_fn: Callable[[str, dict[str, object]], int],
    is_duplicate_note_error_fn: Callable[[object], bool],
    build_existing_note_snapshot_fn: Callable[[int, dict[str, object]], ExistingAnkiNote],
) -> AnkiSyncResult:
    if not cards:
        return AnkiSyncResult(
            added_count=0,
            skipped_count=0,
            deck_name=options.anki_deck,
            note_type=options.anki_note_type,
        )

    sync_started_at = perf_counter()
    validation_started_at = perf_counter()
    validate_anki_target_fn(options)
    validation_seconds = perf_counter() - validation_started_at
    notes = build_anki_notes_fn(options, cards)
    existing_lookup_seconds = 0.0
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]] = {}
    if options.anki_existing_notes == "update":
        existing_lookup_started_at = perf_counter()
        existing_notes_by_front = fetch_existing_notes_by_front_fn(options)
        existing_lookup_seconds = perf_counter() - existing_lookup_started_at
    can_add_started_at = perf_counter()
    can_add = invoke_anki_connect_fn(options.anki_connect_url, "canAddNotes", {"notes": notes})
    can_add_seconds = perf_counter() - can_add_started_at
    if not isinstance(can_add, list) or len(can_add) != len(notes):
        raise AnkiConnectError("Received an unexpected response from canAddNotes.")
    added_count = 0
    skipped_count = 0
    updated_count = 0
    skipped_fronts: list[str] = []
    updated_fronts: list[str] = []

    write_started_at = perf_counter()
    pending_existing_updates: list[PendingExistingNoteUpdate] = []
    pending_batch_notes: list[dict[str, object]] = []
    pending_batch_fronts: list[str] = []

    for note, allowed in zip(notes, can_add):
        front_value = note_front_value_fn(note, options.anki_front_field)
        if not allowed:
            if options.anki_existing_notes == "update":
                update_plan = build_existing_note_update_plan_fn(
                    options,
                    note,
                    existing_notes_by_front,
                )
                if update_plan is not None:
                    pending_existing_updates.append(update_plan)
                    updated_count += 1
                    updated_fronts.append(front_value)
                    continue
            skipped_count += 1
            skipped_fronts.append(front_value)
            continue

        pending_batch_notes.append(note)
        pending_batch_fronts.append(front_value)

    apply_existing_note_updates_fn(options.anki_connect_url, pending_existing_updates)

    if pending_batch_notes:
        try:
            added_note_ids = add_notes_batch_fn(options.anki_connect_url, pending_batch_notes)
        except AnkiConnectError as exc:
            if not is_duplicate_note_error_fn(exc.raw_error if exc.raw_error is not None else str(exc)):
                raise
            added_note_ids = [None] * len(pending_batch_notes)
        for note, front_value, note_id in zip(pending_batch_notes, pending_batch_fronts, added_note_ids):
            if note_id is not None:
                added_count += 1
                if options.anki_existing_notes == "update":
                    existing_notes_by_front.setdefault(front_value, []).append(
                        build_existing_note_snapshot_fn(note_id, note)
                    )
                continue

            try:
                resolved_note_id = add_single_note_fn(options.anki_connect_url, note)
            except AnkiConnectError as exc:
                if not is_duplicate_note_error_fn(exc.raw_error if exc.raw_error is not None else str(exc)):
                    raise
                if options.anki_existing_notes == "update":
                    update_plan = build_existing_note_update_plan_fn(
                        options,
                        note,
                        existing_notes_by_front,
                    )
                    if update_plan is not None:
                        apply_existing_note_updates_fn(options.anki_connect_url, [update_plan])
                        updated_count += 1
                        updated_fronts.append(front_value)
                        continue
                skipped_count += 1
                skipped_fronts.append(front_value)
                continue

            added_count += 1
            if options.anki_existing_notes == "update":
                existing_notes_by_front.setdefault(front_value, []).append(
                    build_existing_note_snapshot_fn(resolved_note_id, note)
                )

    write_seconds = perf_counter() - write_started_at
    return AnkiSyncResult(
        added_count=added_count,
        skipped_count=skipped_count,
        deck_name=options.anki_deck,
        note_type=options.anki_note_type,
        updated_count=updated_count,
        skipped_fronts=tuple(skipped_fronts),
        updated_fronts=tuple(updated_fronts),
        timing=AnkiSyncTiming(
            validation_seconds=validation_seconds,
            existing_lookup_seconds=existing_lookup_seconds,
            can_add_seconds=can_add_seconds,
            write_seconds=write_seconds,
            total_seconds=perf_counter() - sync_started_at,
        ),
    )
