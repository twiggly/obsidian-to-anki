from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Sequence
from urllib import error, request

from models import (
    AnkiCatalog,
    AnkiFieldCatalog,
    AnkiSyncResult,
    AnkiSyncTiming,
    ExportError,
    ExportOptions,
    NoteCard,
)


ANKI_CONNECT_API_VERSION = 5
ANKI_MULTI_ACTION_BATCH_SIZE = 250


class AnkiConnectError(ExportError):
    def __init__(self, message: str, raw_error: object | None = None) -> None:
        super().__init__(message)
        self.raw_error = raw_error


@dataclass(frozen=True)
class ExistingAnkiNote:
    note_id: int
    fields: dict[str, str]
    tags: frozenset[str]


@dataclass(frozen=True)
class PendingExistingNoteUpdate:
    note_id: int
    front_value: str
    fields_to_update: dict[str, str] | None
    tags_to_add: str | None


def format_anki_error(error_value: object) -> str:
    if isinstance(error_value, list):
        return "; ".join(str(item) for item in error_value)
    return str(error_value)


def is_duplicate_note_error(error_value: object) -> bool:
    if isinstance(error_value, list):
        return bool(error_value) and all(is_duplicate_note_error(item) for item in error_value)
    if not isinstance(error_value, str):
        return False
    return "cannot create note because it is a duplicate" in error_value.casefold()


def normalize_anki_connect_url(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if not normalized:
        raise AnkiConnectError("AnkiConnect URL is required when syncing to Anki.")
    return normalized


def invoke_anki_connect(url: str, action: str, params: dict[str, Any] | None = None) -> Any:
    normalized_url = normalize_anki_connect_url(url)
    payload = json.dumps(
        {
            "action": action,
            "version": ANKI_CONNECT_API_VERSION,
            "params": params or {},
        }
    ).encode("utf-8")
    http_request = request.Request(
        normalized_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=5) as response:
            body = json.load(response)
    except (error.URLError, TimeoutError, OSError) as exc:
        raise AnkiConnectError(
            f"Could not reach AnkiConnect at {normalized_url}. Make sure Anki is running and the AnkiConnect add-on is installed."
        ) from exc
    except json.JSONDecodeError as exc:
        raise AnkiConnectError("Received an invalid response from AnkiConnect.") from exc

    if not isinstance(body, dict) or "result" not in body or "error" not in body:
        raise AnkiConnectError("Received an unexpected response from AnkiConnect.")

    if body["error"] is not None:
        raise AnkiConnectError(format_anki_error(body["error"]), raw_error=body["error"])

    return body["result"]


def validate_anki_target(options: ExportOptions) -> None:
    version = invoke_anki_connect(options.anki_connect_url, "version")
    if not isinstance(version, int) or version < ANKI_CONNECT_API_VERSION:
        raise AnkiConnectError(
            f"AnkiConnect API version {ANKI_CONNECT_API_VERSION} or newer is required."
        )

    deck_names = invoke_anki_connect(options.anki_connect_url, "deckNames")
    if options.anki_deck not in deck_names:
        raise AnkiConnectError(f"Anki deck not found: {options.anki_deck}")

    model_names = invoke_anki_connect(options.anki_connect_url, "modelNames")
    if options.anki_note_type not in model_names:
        raise AnkiConnectError(f"Anki note type not found: {options.anki_note_type}")

    field_names = fetch_note_type_fields(
        options.anki_connect_url,
        options.anki_note_type,
    ).field_names
    missing_fields = [
        field_name
        for field_name in (options.anki_front_field, options.anki_back_field)
        if field_name not in field_names
    ]
    if missing_fields:
        raise AnkiConnectError(
            "Missing Anki field"
            + ("s" if len(missing_fields) > 1 else "")
            + f" on note type '{options.anki_note_type}': {', '.join(missing_fields)}"
        )


def fetch_anki_catalog(anki_connect_url: str) -> AnkiCatalog:
    version = invoke_anki_connect(anki_connect_url, "version")
    if not isinstance(version, int) or version < ANKI_CONNECT_API_VERSION:
        raise AnkiConnectError(
            f"AnkiConnect API version {ANKI_CONNECT_API_VERSION} or newer is required."
        )

    deck_names = invoke_anki_connect(anki_connect_url, "deckNames")
    note_type_names = invoke_anki_connect(anki_connect_url, "modelNames")
    if not isinstance(deck_names, list) or not all(isinstance(name, str) for name in deck_names):
        raise AnkiConnectError("Received an unexpected response from deckNames.")
    if not isinstance(note_type_names, list) or not all(isinstance(name, str) for name in note_type_names):
        raise AnkiConnectError("Received an unexpected response from modelNames.")

    return AnkiCatalog(
        deck_names=tuple(sorted(deck_names, key=str.casefold)),
        note_type_names=tuple(sorted(note_type_names, key=str.casefold)),
    )


def fetch_note_type_fields(anki_connect_url: str, note_type_name: str) -> AnkiFieldCatalog:
    field_names = invoke_anki_connect(
        anki_connect_url,
        "modelFieldNames",
        {"modelName": note_type_name},
    )
    if not isinstance(field_names, list) or not all(isinstance(name, str) for name in field_names):
        raise AnkiConnectError("Received an unexpected response from modelFieldNames.")

    return AnkiFieldCatalog(
        note_type_name=note_type_name,
        field_names=tuple(field_names),
    )


def escape_anki_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def fetch_existing_notes_by_front(options: ExportOptions) -> dict[str, list[ExistingAnkiNote]]:
    query = (
        f'deck:"{escape_anki_query_value(options.anki_deck)}" '
        f'note:"{escape_anki_query_value(options.anki_note_type)}"'
    )
    note_ids = invoke_anki_connect(
        options.anki_connect_url,
        "findNotes",
        {"query": query},
    )
    if not isinstance(note_ids, list) or not all(isinstance(note_id, int) for note_id in note_ids):
        raise AnkiConnectError("Received an unexpected response from findNotes.")
    if not note_ids:
        return {}

    note_infos = invoke_anki_connect(
        options.anki_connect_url,
        "notesInfo",
        {"notes": note_ids},
    )
    if not isinstance(note_infos, list):
        raise AnkiConnectError("Received an unexpected response from notesInfo.")

    existing_notes: dict[str, list[ExistingAnkiNote]] = defaultdict(list)
    for note_info in note_infos:
        if not isinstance(note_info, dict):
            raise AnkiConnectError("Received an unexpected response from notesInfo.")
        note_id = note_info.get("noteId")
        if isinstance(note_id, bool) or not isinstance(note_id, int):
            raise AnkiConnectError("Received an unexpected response from notesInfo.")
        if note_info.get("modelName") != options.anki_note_type:
            continue
        fields = note_info.get("fields")
        if not isinstance(fields, dict):
            raise AnkiConnectError("Received an unexpected response from notesInfo.")
        normalized_fields: dict[str, str] = {}
        for field_name, field_value in fields.items():
            if not isinstance(field_name, str) or not isinstance(field_value, dict):
                raise AnkiConnectError("Received an unexpected response from notesInfo.")
            normalized_value = field_value.get("value")
            if not isinstance(normalized_value, str):
                raise AnkiConnectError("Received an unexpected response from notesInfo.")
            normalized_fields[field_name] = normalized_value
        tags = note_info.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise AnkiConnectError("Received an unexpected response from notesInfo.")
        front_field = fields.get(options.anki_front_field)
        if not isinstance(front_field, dict):
            continue
        front_value = front_field.get("value")
        if isinstance(front_value, str):
            existing_notes[front_value].append(
                ExistingAnkiNote(
                    note_id=note_id,
                    fields=normalized_fields,
                    tags=frozenset(tags),
                )
            )
    return {
        front: sorted(notes, key=lambda note: note.note_id)
        for front, notes in existing_notes.items()
    }


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


def note_front_value(note: dict[str, object], front_field_name: str) -> str:
    fields = note.get("fields")
    if not isinstance(fields, dict):
        raise AnkiConnectError("Anki note fields must be a dictionary.")
    front_value = fields.get(front_field_name)
    if not isinstance(front_value, str):
        raise AnkiConnectError("Anki note front field must be a string.")
    return front_value


def add_notes_batch(url: str, notes: Sequence[dict[str, object]]) -> list[int | None]:
    if not notes:
        return []

    note_ids = invoke_anki_connect(url, "addNotes", {"notes": list(notes)})
    if not isinstance(note_ids, list) or len(note_ids) != len(notes):
        raise AnkiConnectError("Received an unexpected response from addNotes.")
    if not all(note_id is None or (isinstance(note_id, int) and not isinstance(note_id, bool)) for note_id in note_ids):
        raise AnkiConnectError("Received an unexpected response from addNotes.")
    return note_ids


def add_single_note(url: str, note: dict[str, object]) -> int:
    note_id = invoke_anki_connect(url, "addNote", {"note": note})
    if isinstance(note_id, bool) or not isinstance(note_id, int):
        raise AnkiConnectError("AnkiConnect did not add a note successfully.")
    return note_id


def invoke_anki_connect_multi(url: str, actions: Sequence[dict[str, object]]) -> list[object]:
    if not actions:
        return []
    results = invoke_anki_connect(url, "multi", {"actions": list(actions)})
    if not isinstance(results, list) or len(results) != len(actions):
        raise AnkiConnectError("Received an unexpected response from multi.")
    return results


def note_tags(note: dict[str, object]) -> list[str]:
    tags = note.get("tags", [])
    if not isinstance(tags, list):
        raise AnkiConnectError("Anki note tags must be a list.")
    normalized_tags: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            raise AnkiConnectError("Anki note tags must be strings.")
        normalized_tags.append(tag)
    return normalized_tags


def build_existing_note_snapshot(note_id: int, note: dict[str, object]) -> ExistingAnkiNote:
    fields = note.get("fields")
    if not isinstance(fields, dict):
        raise AnkiConnectError("Anki note fields must be a dictionary.")
    normalized_fields: dict[str, str] = {}
    for field_name, field_value in fields.items():
        if not isinstance(field_name, str) or not isinstance(field_value, str):
            raise AnkiConnectError("Anki note fields must be string pairs.")
        normalized_fields[field_name] = field_value
    return ExistingAnkiNote(
        note_id=note_id,
        fields=normalized_fields,
        tags=frozenset(note_tags(note)),
    )


def build_existing_note_update_plan(
    options: ExportOptions,
    note: dict[str, object],
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]],
) -> PendingExistingNoteUpdate | None:
    front_value = note_front_value(note, options.anki_front_field)
    existing_notes = existing_notes_by_front.get(front_value, ())
    if not existing_notes:
        return None

    existing_note = existing_notes[0]
    fields = note.get("fields")
    if not isinstance(fields, dict):
        raise AnkiConnectError("Anki note fields must be a dictionary.")
    desired_fields: dict[str, str] = {}
    for field_name, field_value in fields.items():
        if not isinstance(field_name, str) or not isinstance(field_value, str):
            raise AnkiConnectError("Anki note fields must be string pairs.")
        desired_fields[field_name] = field_value

    fields_to_update = (
        desired_fields
        if any(existing_note.fields.get(field_name) != field_value for field_name, field_value in desired_fields.items())
        else None
    )
    missing_tags = [tag for tag in note_tags(note) if tag not in existing_note.tags]
    tags_to_add = " ".join(missing_tags) if missing_tags else None
    return PendingExistingNoteUpdate(
        note_id=existing_note.note_id,
        front_value=front_value,
        fields_to_update=fields_to_update,
        tags_to_add=tags_to_add,
    )


def apply_existing_note_updates(
    url: str,
    update_plans: Sequence[PendingExistingNoteUpdate],
) -> None:
    actions: list[dict[str, object]] = []
    for plan in update_plans:
        if plan.fields_to_update is not None:
            actions.append(
                {
                    "action": "updateNoteFields",
                    "params": {"note": {"id": plan.note_id, "fields": plan.fields_to_update}},
                }
            )
        if plan.tags_to_add:
            actions.append(
                {
                    "action": "addTags",
                    "params": {"notes": [plan.note_id], "tags": plan.tags_to_add},
                }
            )

    for start in range(0, len(actions), ANKI_MULTI_ACTION_BATCH_SIZE):
        invoke_anki_connect_multi(url, actions[start : start + ANKI_MULTI_ACTION_BATCH_SIZE])


def sync_cards_to_anki(options: ExportOptions, cards: Sequence[NoteCard]) -> AnkiSyncResult:
    if not cards:
        return AnkiSyncResult(
            added_count=0,
            skipped_count=0,
            deck_name=options.anki_deck,
            note_type=options.anki_note_type,
        )

    sync_started_at = perf_counter()
    validation_started_at = perf_counter()
    validate_anki_target(options)
    validation_seconds = perf_counter() - validation_started_at
    notes = build_anki_notes(options, cards)
    existing_lookup_seconds = 0.0
    existing_notes_by_front: dict[str, list[ExistingAnkiNote]] = {}
    if options.anki_existing_notes == "update":
        existing_lookup_started_at = perf_counter()
        existing_notes_by_front = fetch_existing_notes_by_front(options)
        existing_lookup_seconds = perf_counter() - existing_lookup_started_at
    can_add_started_at = perf_counter()
    can_add = invoke_anki_connect(options.anki_connect_url, "canAddNotes", {"notes": notes})
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
        front_value = note_front_value(note, options.anki_front_field)
        if not allowed:
            if options.anki_existing_notes == "update":
                update_plan = build_existing_note_update_plan(
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

    apply_existing_note_updates(options.anki_connect_url, pending_existing_updates)

    if pending_batch_notes:
        try:
            added_note_ids = add_notes_batch(options.anki_connect_url, pending_batch_notes)
        except AnkiConnectError as exc:
            if not is_duplicate_note_error(exc.raw_error if exc.raw_error is not None else str(exc)):
                raise
            added_note_ids = [None] * len(pending_batch_notes)
        for note, front_value, note_id in zip(pending_batch_notes, pending_batch_fronts, added_note_ids):
            if note_id is not None:
                added_count += 1
                if options.anki_existing_notes == "update":
                    existing_notes_by_front.setdefault(front_value, []).append(
                        build_existing_note_snapshot(note_id, note)
                    )
                continue

            try:
                resolved_note_id = add_single_note(options.anki_connect_url, note)
            except AnkiConnectError as exc:
                if not is_duplicate_note_error(exc.raw_error if exc.raw_error is not None else str(exc)):
                    raise
                if options.anki_existing_notes == "update":
                    update_plan = build_existing_note_update_plan(
                        options,
                        note,
                        existing_notes_by_front,
                    )
                    if update_plan is not None:
                        apply_existing_note_updates(options.anki_connect_url, [update_plan])
                        updated_count += 1
                        updated_fronts.append(front_value)
                        continue
                skipped_count += 1
                skipped_fronts.append(front_value)
                continue

            added_count += 1
            if options.anki_existing_notes == "update":
                existing_notes_by_front.setdefault(front_value, []).append(
                    build_existing_note_snapshot(resolved_note_id, note)
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
