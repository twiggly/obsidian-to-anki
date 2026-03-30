from __future__ import annotations

from typing import Any, Callable

from anki_connect_client import ANKI_CONNECT_API_VERSION, AnkiConnectError, invoke_anki_connect
from models import AnkiCatalog, AnkiFieldCatalog, ExportOptions


def fetch_anki_catalog(
    anki_connect_url: str,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
) -> AnkiCatalog:
    version = invoke_anki_connect_fn(anki_connect_url, "version", None)
    if not isinstance(version, int) or version < ANKI_CONNECT_API_VERSION:
        raise AnkiConnectError(
            f"AnkiConnect API version {ANKI_CONNECT_API_VERSION} or newer is required."
        )

    deck_names = invoke_anki_connect_fn(anki_connect_url, "deckNames", None)
    note_type_names = invoke_anki_connect_fn(anki_connect_url, "modelNames", None)
    if not isinstance(deck_names, list) or not all(isinstance(name, str) for name in deck_names):
        raise AnkiConnectError("Received an unexpected response from deckNames.")
    if not isinstance(note_type_names, list) or not all(isinstance(name, str) for name in note_type_names):
        raise AnkiConnectError("Received an unexpected response from modelNames.")

    return AnkiCatalog(
        deck_names=tuple(sorted(deck_names, key=str.casefold)),
        note_type_names=tuple(sorted(note_type_names, key=str.casefold)),
    )


def fetch_note_type_fields(
    anki_connect_url: str,
    note_type_name: str,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
) -> AnkiFieldCatalog:
    field_names = invoke_anki_connect_fn(
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


def validate_anki_target(
    options: ExportOptions,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
    fetch_note_type_fields_fn: Callable[..., AnkiFieldCatalog] = fetch_note_type_fields,
) -> None:
    version = invoke_anki_connect_fn(options.anki_connect_url, "version", None)
    if not isinstance(version, int) or version < ANKI_CONNECT_API_VERSION:
        raise AnkiConnectError(
            f"AnkiConnect API version {ANKI_CONNECT_API_VERSION} or newer is required."
        )

    deck_names = invoke_anki_connect_fn(options.anki_connect_url, "deckNames", None)
    if options.anki_deck not in deck_names:
        raise AnkiConnectError(f"Anki deck not found: {options.anki_deck}")

    model_names = invoke_anki_connect_fn(options.anki_connect_url, "modelNames", None)
    if options.anki_note_type not in model_names:
        raise AnkiConnectError(f"Anki note type not found: {options.anki_note_type}")

    field_names = fetch_note_type_fields_fn(
        options.anki_connect_url,
        options.anki_note_type,
        invoke_anki_connect_fn=invoke_anki_connect_fn,
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
