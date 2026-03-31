from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .connect_client import AnkiConnectError, invoke_anki_connect, invoke_anki_connect_multi
from ..models import ExportOptions


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


def escape_anki_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def note_front_value(note: dict[str, object], front_field_name: str) -> str:
    fields = note.get("fields")
    if not isinstance(fields, dict):
        raise AnkiConnectError("Anki note fields must be a dictionary.")
    front_value = fields.get(front_field_name)
    if not isinstance(front_value, str):
        raise AnkiConnectError("Anki note front field must be a string.")
    return front_value


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


def fetch_existing_notes_by_front(
    options: ExportOptions,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
) -> dict[str, list[ExistingAnkiNote]]:
    query = (
        f'deck:"{escape_anki_query_value(options.anki_deck)}" '
        f'note:"{escape_anki_query_value(options.anki_note_type)}"'
    )
    note_ids = invoke_anki_connect_fn(
        options.anki_connect_url,
        "findNotes",
        {"query": query},
    )
    if not isinstance(note_ids, list) or not all(isinstance(note_id, int) for note_id in note_ids):
        raise AnkiConnectError("Received an unexpected response from findNotes.")
    if not note_ids:
        return {}

    note_infos = invoke_anki_connect_fn(
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
    *,
    batch_size: int,
    invoke_anki_connect_multi_fn: Callable[[str, Sequence[dict[str, object]]], list[object]] = invoke_anki_connect_multi,
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

    for start in range(0, len(actions), batch_size):
        invoke_anki_connect_multi_fn(url, actions[start : start + batch_size])
