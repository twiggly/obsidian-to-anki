from __future__ import annotations

from typing import Any, Callable

from .connect_client import (
    ANKI_CONNECT_API_VERSION,
    AnkiConnectError,
    invoke_anki_connect,
    unexpected_anki_response_message,
)
from ..models import AnkiCatalog, AnkiFieldCatalog, ExportOptions


def fetch_anki_catalog(
    anki_connect_url: str,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
) -> AnkiCatalog:
    version = invoke_anki_connect_fn(anki_connect_url, "version", None)
    if not isinstance(version, int) or version < ANKI_CONNECT_API_VERSION:
        raise AnkiConnectError(
            f"Update the AnkiConnect add-on to version {ANKI_CONNECT_API_VERSION} or newer."
        )

    deck_names = invoke_anki_connect_fn(anki_connect_url, "deckNames", None)
    note_type_names = invoke_anki_connect_fn(anki_connect_url, "modelNames", None)
    if not isinstance(deck_names, list) or not all(isinstance(name, str) for name in deck_names):
        raise AnkiConnectError(unexpected_anki_response_message("deckNames"))
    if not isinstance(note_type_names, list) or not all(isinstance(name, str) for name in note_type_names):
        raise AnkiConnectError(unexpected_anki_response_message("modelNames"))

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
        raise AnkiConnectError(unexpected_anki_response_message("modelFieldNames"))

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
            f"Update the AnkiConnect add-on to version {ANKI_CONNECT_API_VERSION} or newer."
        )

    deck_names = invoke_anki_connect_fn(options.anki_connect_url, "deckNames", None)
    if options.anki_deck not in deck_names:
        raise AnkiConnectError(
            f"The Anki deck '{options.anki_deck}' wasn't found. Create it in Anki or choose a different deck."
        )

    model_names = invoke_anki_connect_fn(options.anki_connect_url, "modelNames", None)
    if options.anki_note_type not in model_names:
        raise AnkiConnectError(
            f"The Anki note type '{options.anki_note_type}' wasn't found. Choose another note type in the app or create it in Anki."
        )

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
            f"The Anki note type '{options.anki_note_type}' is missing these fields: {', '.join(missing_fields)}. "
            "Choose another note type or change the selected fields."
        )
