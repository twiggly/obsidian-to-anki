from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from time import perf_counter

from ..models import (
    AnkiPreflightResult,
    AnkiPreflightSummary,
    AnkiSyncResult,
    AnkiSyncTiming,
    ExportOptions,
    NoteCard,
)
from .connect_client import AnkiConnectError, unexpected_anki_response_message
from .existing_notes import ExistingAnkiNote, PendingExistingNoteUpdate


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
        raise AnkiConnectError(unexpected_anki_response_message("addNotes"))
    if not all(
        note_id is None or (isinstance(note_id, int) and not isinstance(note_id, bool))
        for note_id in note_ids
    ):
        raise AnkiConnectError(unexpected_anki_response_message("addNotes"))
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


def _validate_can_add_results(can_add: object, expected_count: int) -> tuple[bool, ...]:
    if (
        not isinstance(can_add, list)
        or len(can_add) != expected_count
        or not all(isinstance(item, bool) for item in can_add)
    ):
        raise AnkiConnectError(unexpected_anki_response_message("canAddNotes"))
    return tuple(can_add)


@dataclass
class _PreparedSync:
    notes: list[dict[str, object]]
    can_add: tuple[bool, ...]
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]]
    timing: AnkiSyncTiming = field(default_factory=AnkiSyncTiming)


@dataclass
class _SyncChanges:
    notes_to_add: list[tuple[dict[str, object], str]] = field(default_factory=list)
    existing_updates: list[PendingExistingNoteUpdate] = field(default_factory=list)
    skipped_fronts: list[str] = field(default_factory=list)
    updated_fronts: list[str] = field(default_factory=list)
    added_count: int = 0


def _prepare_sync(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    *,
    validate_anki_target_fn: Callable[[ExportOptions], None],
    build_anki_notes_fn: Callable[[ExportOptions, Sequence[NoteCard]], list[dict[str, object]]],
    fetch_existing_notes_by_front_fn: Callable[[ExportOptions], dict[str, list[ExistingAnkiNote]]],
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
    preflight_result: AnkiPreflightResult | None = None,
) -> _PreparedSync:
    if preflight_result is not None:
        return _PreparedSync(
            notes=list(preflight_result.notes),
            can_add=preflight_result.can_add,
            existing_notes_by_front={
                front: list(notes_for_front)
                for front, notes_for_front in preflight_result.existing_notes_by_front.items()
            }
            if options.anki_existing_notes == "update"
            else {},
        )

    validation_started_at = perf_counter()
    validate_anki_target_fn(options)
    validation_seconds = perf_counter() - validation_started_at
    notes = build_anki_notes_fn(options, cards)
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]] = {}
    existing_lookup_seconds = 0.0
    if options.anki_existing_notes == "update":
        existing_lookup_started_at = perf_counter()
        existing_notes_by_front = fetch_existing_notes_by_front_fn(options)
        existing_lookup_seconds = perf_counter() - existing_lookup_started_at
    can_add_started_at = perf_counter()
    can_add = _validate_can_add_results(
        invoke_anki_connect_fn(options.anki_connect_url, "canAddNotes", {"notes": notes}),
        len(notes),
    )
    return _PreparedSync(
        notes=notes,
        can_add=can_add,
        existing_notes_by_front=existing_notes_by_front,
        timing=AnkiSyncTiming(
            validation_seconds=validation_seconds,
            existing_lookup_seconds=existing_lookup_seconds,
            can_add_seconds=perf_counter() - can_add_started_at,
        ),
    )


def _plan_sync_changes(
    options: ExportOptions,
    prepared: _PreparedSync,
    *,
    note_front_value_fn: Callable[[dict[str, object], str], str],
    build_existing_note_update_plan_fn: Callable[
        [ExportOptions, dict[str, object], dict[str, list[ExistingAnkiNote]]],
        PendingExistingNoteUpdate | None,
    ],
) -> _SyncChanges:
    changes = _SyncChanges()
    for note, allowed in zip(prepared.notes, prepared.can_add, strict=True):
        front_value = note_front_value_fn(note, options.anki_front_field)
        if allowed:
            changes.notes_to_add.append((note, front_value))
            continue
        if options.anki_existing_notes == "update":
            update_plan = build_existing_note_update_plan_fn(
                options, note, prepared.existing_notes_by_front
            )
            if update_plan is not None:
                changes.existing_updates.append(update_plan)
                changes.updated_fronts.append(front_value)
                continue
        changes.skipped_fronts.append(front_value)
    return changes


def _add_new_notes(
    options: ExportOptions,
    changes: _SyncChanges,
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]],
    *,
    add_notes_batch_fn: Callable[[str, Sequence[dict[str, object]]], list[int | None]],
    add_single_note_fn: Callable[[str, dict[str, object]], int],
    is_duplicate_note_error_fn: Callable[[object], bool],
    build_existing_note_snapshot_fn: Callable[[int, dict[str, object]], ExistingAnkiNote],
    build_existing_note_update_plan_fn: Callable[
        [ExportOptions, dict[str, object], dict[str, list[ExistingAnkiNote]]],
        PendingExistingNoteUpdate | None,
    ],
    apply_existing_note_updates_fn: Callable[[str, Sequence[PendingExistingNoteUpdate]], None],
) -> None:
    if not changes.notes_to_add:
        return

    pending_notes = [note for note, _ in changes.notes_to_add]
    try:
        added_note_ids = add_notes_batch_fn(options.anki_connect_url, pending_notes)
    except AnkiConnectError as exc:
        if not is_duplicate_note_error_fn(exc.raw_error if exc.raw_error is not None else str(exc)):
            raise
        added_note_ids = [None] * len(pending_notes)

    for (note, front_value), note_id in zip(changes.notes_to_add, added_note_ids, strict=True):
        if note_id is None:
            try:
                note_id = add_single_note_fn(options.anki_connect_url, note)
            except AnkiConnectError as exc:
                if not is_duplicate_note_error_fn(
                    exc.raw_error if exc.raw_error is not None else str(exc)
                ):
                    raise
                if options.anki_existing_notes == "update":
                    update_plan = build_existing_note_update_plan_fn(
                        options, note, existing_notes_by_front
                    )
                    if update_plan is not None:
                        apply_existing_note_updates_fn(options.anki_connect_url, [update_plan])
                        changes.updated_fronts.append(front_value)
                        continue
                changes.skipped_fronts.append(front_value)
                continue

        changes.added_count += 1
        if options.anki_existing_notes == "update":
            existing_notes_by_front.setdefault(front_value, []).append(
                build_existing_note_snapshot_fn(note_id, note)
            )


def _build_anki_preflight_result(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    *,
    validate_anki_target_fn: Callable[[ExportOptions], None],
    build_anki_notes_fn: Callable[[ExportOptions, Sequence[NoteCard]], list[dict[str, object]]],
    fetch_existing_notes_by_front_fn: Callable[[ExportOptions], dict[str, list[ExistingAnkiNote]]],
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
    build_existing_note_update_plan_fn: Callable[
        [ExportOptions, dict[str, object], dict[str, list[ExistingAnkiNote]]],
        PendingExistingNoteUpdate | None,
    ],
) -> AnkiPreflightResult:
    if not cards:
        return AnkiPreflightResult(
            summary=AnkiPreflightSummary(
                new_count=0,
                update_count=0,
                skip_count=0,
                deck_name=options.anki_deck,
                note_type=options.anki_note_type,
            ),
            notes=(),
            can_add=(),
        )

    prepared = _prepare_sync(
        options,
        cards,
        validate_anki_target_fn=validate_anki_target_fn,
        build_anki_notes_fn=build_anki_notes_fn,
        fetch_existing_notes_by_front_fn=fetch_existing_notes_by_front_fn,
        invoke_anki_connect_fn=invoke_anki_connect_fn,
    )

    new_count = 0
    update_count = 0
    skip_count = 0
    for note, allowed in zip(prepared.notes, prepared.can_add, strict=True):
        if allowed:
            new_count += 1
            continue
        if options.anki_existing_notes == "update":
            update_plan = build_existing_note_update_plan_fn(
                options,
                note,
                prepared.existing_notes_by_front,
            )
            if update_plan is not None:
                update_count += 1
                continue
        skip_count += 1

    return AnkiPreflightResult(
        summary=AnkiPreflightSummary(
            new_count=new_count,
            update_count=update_count,
            skip_count=skip_count,
            deck_name=options.anki_deck,
            note_type=options.anki_note_type,
        ),
        notes=tuple(prepared.notes),
        can_add=prepared.can_add,
        existing_notes_by_front={
            front: tuple(notes_for_front)
            for front, notes_for_front in prepared.existing_notes_by_front.items()
        },
    )


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
    preflight_result: AnkiPreflightResult | None = None,
) -> AnkiSyncResult:
    if preflight_result is not None:
        if (
            len(preflight_result.notes) != len(cards)
            or len(preflight_result.can_add) != len(cards)
            or not all(isinstance(allowed, bool) for allowed in preflight_result.can_add)
        ):
            raise AnkiConnectError("Cached Anki preview data is inconsistent. Preview cards again.")
    if not cards:
        return AnkiSyncResult(
            added_count=0,
            skipped_count=0,
            deck_name=options.anki_deck,
            note_type=options.anki_note_type,
        )

    sync_started_at = perf_counter()
    prepared = _prepare_sync(
        options,
        cards,
        validate_anki_target_fn=validate_anki_target_fn,
        build_anki_notes_fn=build_anki_notes_fn,
        fetch_existing_notes_by_front_fn=fetch_existing_notes_by_front_fn,
        invoke_anki_connect_fn=invoke_anki_connect_fn,
        preflight_result=preflight_result,
    )

    write_started_at = perf_counter()
    changes = _plan_sync_changes(
        options,
        prepared,
        note_front_value_fn=note_front_value_fn,
        build_existing_note_update_plan_fn=build_existing_note_update_plan_fn,
    )
    apply_existing_note_updates_fn(options.anki_connect_url, changes.existing_updates)
    _add_new_notes(
        options,
        changes,
        prepared.existing_notes_by_front,
        add_notes_batch_fn=add_notes_batch_fn,
        add_single_note_fn=add_single_note_fn,
        is_duplicate_note_error_fn=is_duplicate_note_error_fn,
        build_existing_note_snapshot_fn=build_existing_note_snapshot_fn,
        build_existing_note_update_plan_fn=build_existing_note_update_plan_fn,
        apply_existing_note_updates_fn=apply_existing_note_updates_fn,
    )

    write_seconds = perf_counter() - write_started_at
    return AnkiSyncResult(
        added_count=changes.added_count,
        skipped_count=len(changes.skipped_fronts),
        deck_name=options.anki_deck,
        note_type=options.anki_note_type,
        updated_count=len(changes.updated_fronts),
        skipped_fronts=tuple(changes.skipped_fronts),
        updated_fronts=tuple(changes.updated_fronts),
        timing=replace(
            prepared.timing,
            write_seconds=write_seconds,
            total_seconds=perf_counter() - sync_started_at,
        ),
    )


def build_anki_preflight_summary(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    *,
    validate_anki_target_fn: Callable[[ExportOptions], None],
    build_anki_notes_fn: Callable[[ExportOptions, Sequence[NoteCard]], list[dict[str, object]]],
    fetch_existing_notes_by_front_fn: Callable[[ExportOptions], dict[str, list[ExistingAnkiNote]]],
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
    build_existing_note_update_plan_fn: Callable[
        [ExportOptions, dict[str, object], dict[str, list[ExistingAnkiNote]]],
        PendingExistingNoteUpdate | None,
    ],
) -> AnkiPreflightSummary:
    return _build_anki_preflight_result(
        options,
        cards,
        validate_anki_target_fn=validate_anki_target_fn,
        build_anki_notes_fn=build_anki_notes_fn,
        fetch_existing_notes_by_front_fn=fetch_existing_notes_by_front_fn,
        invoke_anki_connect_fn=invoke_anki_connect_fn,
        build_existing_note_update_plan_fn=build_existing_note_update_plan_fn,
    ).summary


def build_anki_preflight_result(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    *,
    validate_anki_target_fn: Callable[[ExportOptions], None],
    build_anki_notes_fn: Callable[[ExportOptions, Sequence[NoteCard]], list[dict[str, object]]],
    fetch_existing_notes_by_front_fn: Callable[[ExportOptions], dict[str, list[ExistingAnkiNote]]],
    invoke_anki_connect_fn: Callable[[str, str, dict[str, object] | None], object],
    build_existing_note_update_plan_fn: Callable[
        [ExportOptions, dict[str, object], dict[str, list[ExistingAnkiNote]]],
        PendingExistingNoteUpdate | None,
    ],
) -> AnkiPreflightResult:
    return _build_anki_preflight_result(
        options,
        cards,
        validate_anki_target_fn=validate_anki_target_fn,
        build_anki_notes_fn=build_anki_notes_fn,
        fetch_existing_notes_by_front_fn=fetch_existing_notes_by_front_fn,
        invoke_anki_connect_fn=invoke_anki_connect_fn,
        build_existing_note_update_plan_fn=build_existing_note_update_plan_fn,
    )
