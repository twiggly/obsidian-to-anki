from __future__ import annotations

from typing import Sequence

from anki_catalog import (
    fetch_anki_catalog as fetch_anki_catalog_impl,
    fetch_note_type_fields as fetch_note_type_fields_impl,
    validate_anki_target as validate_anki_target_impl,
)
from anki_connect_client import (
    ANKI_CONNECT_API_VERSION,
    AnkiConnectError,
    format_anki_error,
    invoke_anki_connect as invoke_anki_connect_impl,
    is_duplicate_note_error,
    normalize_anki_connect_url,
    request,
)
from anki_existing_notes import (
    ExistingAnkiNote,
    PendingExistingNoteUpdate,
    apply_existing_note_updates as apply_existing_note_updates_impl,
    build_existing_note_snapshot as build_existing_note_snapshot_impl,
    build_existing_note_update_plan as build_existing_note_update_plan_impl,
    fetch_existing_notes_by_front as fetch_existing_notes_by_front_impl,
    note_front_value as note_front_value_impl,
    note_tags as note_tags_impl,
)
from anki_sync_engine import (
    add_notes_batch as add_notes_batch_impl,
    add_single_note as add_single_note_impl,
    build_anki_notes as build_anki_notes_impl,
    sync_cards_to_anki as sync_cards_to_anki_impl,
)
from models import (
    AnkiCatalog,
    AnkiFieldCatalog,
    AnkiSyncResult,
    ExportOptions,
    NoteCard,
)


ANKI_MULTI_ACTION_BATCH_SIZE = 250

def invoke_anki_connect(url: str, action: str, params: dict[str, object] | None = None) -> object:
    return invoke_anki_connect_impl(url, action, params)


def invoke_anki_connect_multi(url: str, actions: Sequence[dict[str, object]]) -> list[object]:
    results = invoke_anki_connect(url, "multi", {"actions": list(actions)})
    if not isinstance(results, list):
        raise AnkiConnectError("Received an unexpected response from AnkiConnect multi.")
    return results


def fetch_anki_catalog(anki_connect_url: str) -> AnkiCatalog:
    return fetch_anki_catalog_impl(
        anki_connect_url,
        invoke_anki_connect_fn=invoke_anki_connect,
    )


def fetch_note_type_fields(anki_connect_url: str, note_type_name: str) -> AnkiFieldCatalog:
    return fetch_note_type_fields_impl(
        anki_connect_url,
        note_type_name,
        invoke_anki_connect_fn=invoke_anki_connect,
    )


def validate_anki_target(options: ExportOptions) -> None:
    validate_anki_target_impl(
        options,
        invoke_anki_connect_fn=invoke_anki_connect,
        fetch_note_type_fields_fn=fetch_note_type_fields_impl,
    )


def fetch_existing_notes_by_front(options: ExportOptions) -> dict[str, list[ExistingAnkiNote]]:
    return fetch_existing_notes_by_front_impl(
        options,
        invoke_anki_connect_fn=invoke_anki_connect,
    )


def build_anki_notes(options: ExportOptions, cards: Sequence[NoteCard]) -> list[dict[str, object]]:
    return build_anki_notes_impl(options, cards)


def note_front_value(note: dict[str, object], front_field_name: str) -> str:
    return note_front_value_impl(note, front_field_name)


def add_notes_batch(url: str, notes: Sequence[dict[str, object]]) -> list[int | None]:
    return add_notes_batch_impl(url, notes, invoke_anki_connect_fn=invoke_anki_connect)


def add_single_note(url: str, note: dict[str, object]) -> int:
    return add_single_note_impl(url, note, invoke_anki_connect_fn=invoke_anki_connect)


def note_tags(note: dict[str, object]) -> list[str]:
    return note_tags_impl(note)


def build_existing_note_snapshot(note_id: int, note: dict[str, object]) -> ExistingAnkiNote:
    return build_existing_note_snapshot_impl(note_id, note)


def build_existing_note_update_plan(
    options: ExportOptions,
    note: dict[str, object],
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]],
) -> PendingExistingNoteUpdate | None:
    return build_existing_note_update_plan_impl(options, note, existing_notes_by_front)


def apply_existing_note_updates(
    url: str,
    update_plans: Sequence[PendingExistingNoteUpdate],
) -> None:
    apply_existing_note_updates_impl(
        url,
        update_plans,
        batch_size=ANKI_MULTI_ACTION_BATCH_SIZE,
        invoke_anki_connect_multi_fn=invoke_anki_connect_multi,
    )


def sync_cards_to_anki(options: ExportOptions, cards: Sequence[NoteCard]) -> AnkiSyncResult:
    return sync_cards_to_anki_impl(
        options,
        cards,
        validate_anki_target_fn=validate_anki_target,
        build_anki_notes_fn=build_anki_notes,
        fetch_existing_notes_by_front_fn=fetch_existing_notes_by_front,
        invoke_anki_connect_fn=invoke_anki_connect,
        note_front_value_fn=note_front_value,
        build_existing_note_update_plan_fn=build_existing_note_update_plan,
        apply_existing_note_updates_fn=apply_existing_note_updates,
        add_notes_batch_fn=add_notes_batch,
        add_single_note_fn=add_single_note,
        is_duplicate_note_error_fn=is_duplicate_note_error,
        build_existing_note_snapshot_fn=build_existing_note_snapshot,
    )
