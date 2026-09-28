from __future__ import annotations

from collections.abc import Sequence

from ..models import (
    AnkiCatalog,
    AnkiDeckSettingsResult,
    AnkiFieldCatalog,
    AnkiNoteTypeInstallResult,
    AnkiPreflightResult,
    AnkiPreflightSummary,
    AnkiSyncResult,
    ExportOptions,
    NoteCard,
)
from .catalog import (
    check_anki_connection as check_anki_connection_impl,
)
from .catalog import (
    fetch_anki_catalog as fetch_anki_catalog_impl,
)
from .catalog import (
    fetch_note_type_fields as fetch_note_type_fields_impl,
)
from .catalog import (
    validate_anki_target as validate_anki_target_impl,
)
from .connect_client import (
    ANKI_CONNECT_API_VERSION,
    AnkiConnectError,
    format_anki_error,
    is_duplicate_note_error,
    normalize_anki_connect_url,
)
from .connect_client import (
    invoke_anki_connect as invoke_anki_connect_impl,
)
from .connect_client import (
    invoke_anki_connect_multi as invoke_anki_connect_multi_impl,
)
from .connect_client import (
    request as request,
)
from .connect_client import (
    unexpected_anki_response_message as unexpected_anki_response_message,
)
from .deck_settings import apply_recommended_deck_settings as apply_recommended_deck_settings_impl
from .existing_notes import (
    ExistingAnkiNote,
    PendingExistingNoteUpdate,
)
from .existing_notes import (
    apply_existing_note_updates as apply_existing_note_updates_impl,
)
from .existing_notes import (
    build_existing_note_snapshot as build_existing_note_snapshot_impl,
)
from .existing_notes import (
    build_existing_note_update_plan as build_existing_note_update_plan_impl,
)
from .existing_notes import (
    fetch_existing_notes_by_front as fetch_existing_notes_by_front_impl,
)
from .existing_notes import (
    note_front_value as note_front_value_impl,
)
from .note_types import (
    OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
)
from .note_types import (
    install_obsidian_definitions_note_type as install_obsidian_definitions_note_type_impl,
)
from .sync_engine import (
    add_notes_batch as add_notes_batch_impl,
)
from .sync_engine import (
    add_single_note as add_single_note_impl,
)
from .sync_engine import (
    build_anki_notes as build_anki_notes_impl,
)
from .sync_engine import (
    build_anki_preflight_result as build_anki_preflight_result_impl,
)
from .sync_engine import (
    build_anki_preflight_summary as build_anki_preflight_summary_impl,
)
from .sync_engine import (
    sync_cards_to_anki as sync_cards_to_anki_impl,
)

ANKI_MULTI_ACTION_BATCH_SIZE = 250

__all__ = [
    "ANKI_CONNECT_API_VERSION",
    "AnkiCatalog",
    "AnkiConnectError",
    "AnkiDeckSettingsResult",
    "AnkiFieldCatalog",
    "AnkiNoteTypeInstallResult",
    "AnkiPreflightResult",
    "AnkiPreflightSummary",
    "AnkiSyncResult",
    "OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME",
    "ExportOptions",
    "NoteCard",
    "build_anki_notes",
    "build_anki_preflight_result",
    "build_anki_preflight_summary",
    "apply_recommended_deck_settings",
    "check_anki_connection",
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
    return invoke_anki_connect_multi_impl(url, actions, invoke_anki_connect_fn=invoke_anki_connect)


def fetch_anki_catalog(anki_connect_url: str) -> AnkiCatalog:
    return fetch_anki_catalog_impl(
        anki_connect_url,
        invoke_anki_connect_fn=invoke_anki_connect,
    )


def check_anki_connection(anki_connect_url: str) -> None:
    check_anki_connection_impl(
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


def sync_cards_to_anki(
    options: ExportOptions,
    cards: Sequence[NoteCard],
    preflight_result: AnkiPreflightResult | None = None,
) -> AnkiSyncResult:
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
        preflight_result=preflight_result,
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


def build_anki_preflight_result(
    options: ExportOptions,
    cards: Sequence[NoteCard],
) -> AnkiPreflightResult:
    return build_anki_preflight_result_impl(
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
