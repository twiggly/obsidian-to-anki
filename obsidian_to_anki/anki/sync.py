from __future__ import annotations

from typing import Sequence

from .catalog import (
    fetch_anki_catalog as fetch_anki_catalog_impl,
    fetch_note_type_fields as fetch_note_type_fields_impl,
    validate_anki_target as validate_anki_target_impl,
)
from .connect_client import (
    ANKI_CONNECT_API_VERSION,
    AnkiConnectError,
    format_anki_error,
    invoke_anki_connect as invoke_anki_connect_impl,
    is_duplicate_note_error,
    normalize_anki_connect_url,
    request,
    unexpected_anki_response_message,
)
from .deck_settings import apply_recommended_deck_settings as apply_recommended_deck_settings_impl
from .existing_notes import (
    ExistingAnkiNote,
    PendingExistingNoteUpdate,
    apply_existing_note_updates as apply_existing_note_updates_impl,
    build_existing_note_snapshot as build_existing_note_snapshot_impl,
    build_existing_note_update_plan as build_existing_note_update_plan_impl,
    fetch_existing_notes_by_front as fetch_existing_notes_by_front_impl,
    note_front_value as note_front_value_impl,
)
from .note_types import (
    OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
    install_obsidian_definitions_note_type as install_obsidian_definitions_note_type_impl,
)
from .sync_engine import (
    add_notes_batch as add_notes_batch_impl,
    add_single_note as add_single_note_impl,
    build_anki_preflight_summary as build_anki_preflight_summary_impl,
    build_anki_notes as build_anki_notes_impl,
    sync_cards_to_anki as sync_cards_to_anki_impl,
)
from ..models import (
    AnkiCatalog,
    AnkiDeckSettingsResult,
    AnkiPreflightSummary,
    AnkiFieldCatalog,
    AnkiNoteTypeInstallResult,
    AnkiSyncResult,
    ExportOptions,
    NoteCard,
)


ANKI_MULTI_ACTION_BATCH_SIZE = 250

__all__ = [
    "ANKI_CONNECT_API_VERSION",
    "AnkiCatalog",
    "AnkiConnectError",
    "AnkiDeckSettingsResult",
    "AnkiFieldCatalog",
    "AnkiNoteTypeInstallResult",
    "AnkiPreflightSummary",
    "AnkiSyncResult",
    "OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME",
    "ExportOptions",
    "NoteCard",
    "build_anki_notes",
    "build_anki_preflight_summary",
    "apply_recommended_deck_settings",
    "fetch_anki_catalog",
    "fetch_note_type_fields",
    "format_anki_error",
    "install_obsidian_definitions_note_type",
    "invoke_anki_connect",
    "normalize_anki_connect_url",
    "sync_cards_to_anki",
]

def invoke_anki_connect(url: str, action: str, params: dict[str, object] | None = None) -> object:
    return invoke_anki_connect_impl(url, action, params)


def _invoke_anki_connect_multi(url: str, actions: Sequence[dict[str, object]]) -> list[object]:
    results = invoke_anki_connect(url, "multi", {"actions": list(actions)})
    if not isinstance(results, list):
        raise AnkiConnectError(unexpected_anki_response_message("multi"))
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


def _validate_anki_target(options: ExportOptions) -> None:
    validate_anki_target_impl(
        options,
        invoke_anki_connect_fn=invoke_anki_connect,
        fetch_note_type_fields_fn=fetch_note_type_fields_impl,
    )


def _fetch_existing_notes_by_front(options: ExportOptions) -> dict[str, list[ExistingAnkiNote]]:
    return fetch_existing_notes_by_front_impl(
        options,
        invoke_anki_connect_fn=invoke_anki_connect,
    )


def build_anki_notes(options: ExportOptions, cards: Sequence[NoteCard]) -> list[dict[str, object]]:
    return build_anki_notes_impl(options, cards)


def _note_front_value(note: dict[str, object], front_field_name: str) -> str:
    return note_front_value_impl(note, front_field_name)


def _add_notes_batch(url: str, notes: Sequence[dict[str, object]]) -> list[int | None]:
    return add_notes_batch_impl(url, notes, invoke_anki_connect_fn=invoke_anki_connect)


def _add_single_note(url: str, note: dict[str, object]) -> int:
    return add_single_note_impl(url, note, invoke_anki_connect_fn=invoke_anki_connect)


def _build_existing_note_snapshot(note_id: int, note: dict[str, object]) -> ExistingAnkiNote:
    return build_existing_note_snapshot_impl(note_id, note)


def _build_existing_note_update_plan(
    options: ExportOptions,
    note: dict[str, object],
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]],
) -> PendingExistingNoteUpdate | None:
    return build_existing_note_update_plan_impl(options, note, existing_notes_by_front)


def _apply_existing_note_updates(
    url: str,
    update_plans: Sequence[PendingExistingNoteUpdate],
) -> None:
    apply_existing_note_updates_impl(
        url,
        update_plans,
        batch_size=ANKI_MULTI_ACTION_BATCH_SIZE,
        invoke_anki_connect_multi_fn=_invoke_anki_connect_multi,
    )


def sync_cards_to_anki(options: ExportOptions, cards: Sequence[NoteCard]) -> AnkiSyncResult:
    return sync_cards_to_anki_impl(
        options,
        cards,
        validate_anki_target_fn=_validate_anki_target,
        build_anki_notes_fn=build_anki_notes,
        fetch_existing_notes_by_front_fn=_fetch_existing_notes_by_front,
        invoke_anki_connect_fn=invoke_anki_connect,
        note_front_value_fn=_note_front_value,
        build_existing_note_update_plan_fn=_build_existing_note_update_plan,
        apply_existing_note_updates_fn=_apply_existing_note_updates,
        add_notes_batch_fn=_add_notes_batch,
        add_single_note_fn=_add_single_note,
        is_duplicate_note_error_fn=is_duplicate_note_error,
        build_existing_note_snapshot_fn=_build_existing_note_snapshot,
    )


def build_anki_preflight_summary(
    options: ExportOptions,
    cards: Sequence[NoteCard],
) -> AnkiPreflightSummary:
    return build_anki_preflight_summary_impl(
        options,
        cards,
        validate_anki_target_fn=_validate_anki_target,
        build_anki_notes_fn=build_anki_notes,
        fetch_existing_notes_by_front_fn=_fetch_existing_notes_by_front,
        invoke_anki_connect_fn=invoke_anki_connect,
        build_existing_note_update_plan_fn=_build_existing_note_update_plan,
    )


def install_obsidian_definitions_note_type(anki_connect_url: str) -> AnkiNoteTypeInstallResult:
    return install_obsidian_definitions_note_type_impl(
        anki_connect_url,
        invoke_anki_connect_fn=invoke_anki_connect,
    )


def apply_recommended_deck_settings(
    anki_connect_url: str,
    deck_name: str,
) -> AnkiDeckSettingsResult:
    return apply_recommended_deck_settings_impl(
        anki_connect_url,
        deck_name,
        invoke_anki_connect_fn=invoke_anki_connect,
    )
