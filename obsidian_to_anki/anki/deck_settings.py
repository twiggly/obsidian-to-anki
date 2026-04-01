from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .connect_client import AnkiConnectError, invoke_anki_connect, unexpected_anki_response_message
from .note_types import OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME
from ..models import AnkiDeckSettingsResult


RECOMMENDED_DECK_NEW_CARDS_PER_DAY = 10
RECOMMENDED_DECK_MAX_REVIEWS_PER_DAY = 200
RECOMMENDED_DECK_LEARNING_STEPS = (1, 10)
RECOMMENDED_DECK_RELEARNING_STEPS = (10,)
RECOMMENDED_DECK_NEW_GATHER_PRIORITY = 4
RECOMMENDED_DECK_NEW_SORT_ORDER = 2
RECOMMENDED_DECK_REVIEW_ORDER = 0


def _validate_deck_name(deck_name: str) -> str:
    normalized = deck_name.strip()
    if not normalized:
        raise AnkiConnectError("Choose an Anki deck before applying the recommended deck settings.")
    return normalized


def _validate_mapping(value: object, action: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnkiConnectError(unexpected_anki_response_message(action))
    return value


def _validate_config_id(value: object, action: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise AnkiConnectError(unexpected_anki_response_message(action))
    return value


def _recommended_deck_preset_name(deck_name: str) -> str:
    return f"{OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME} - {deck_name}"


def _apply_recommended_settings(config: dict[str, Any]) -> None:
    new_config = _validate_mapping(config.setdefault("new", {}), "getDeckConfig")
    rev_config = _validate_mapping(config.setdefault("rev", {}), "getDeckConfig")
    lapse_config = _validate_mapping(config.setdefault("lapse", {}), "getDeckConfig")

    config["newGatherPriority"] = RECOMMENDED_DECK_NEW_GATHER_PRIORITY
    config["newSortOrder"] = RECOMMENDED_DECK_NEW_SORT_ORDER
    config["reviewOrder"] = RECOMMENDED_DECK_REVIEW_ORDER

    new_config["bury"] = True
    new_config["perDay"] = RECOMMENDED_DECK_NEW_CARDS_PER_DAY
    new_config["delays"] = list(RECOMMENDED_DECK_LEARNING_STEPS)

    existing_intervals = new_config.get("ints")
    if isinstance(existing_intervals, list) and all(isinstance(item, int) for item in existing_intervals):
        updated_intervals = list(existing_intervals)
        if not updated_intervals:
            updated_intervals = [1, 4]
        elif len(updated_intervals) == 1:
            updated_intervals = [1, 4]
        else:
            updated_intervals[0] = 1
            updated_intervals[1] = 4
        new_config["ints"] = updated_intervals
    else:
        new_config["ints"] = [1, 4]

    rev_config["bury"] = True
    rev_config["perDay"] = RECOMMENDED_DECK_MAX_REVIEWS_PER_DAY

    lapse_config["delays"] = list(RECOMMENDED_DECK_RELEARNING_STEPS)

def apply_recommended_deck_settings(
    anki_connect_url: str,
    deck_name: str,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
) -> AnkiDeckSettingsResult:
    normalized_deck_name = _validate_deck_name(deck_name)
    config_result = invoke_anki_connect_fn(
        anki_connect_url,
        "getDeckConfig",
        {"deck": normalized_deck_name},
    )
    if config_result is False:
        raise AnkiConnectError(
            f"Anki couldn't load the current deck settings for '{normalized_deck_name}'. Try again in Anki and make sure the deck still exists."
        )
    config = _validate_mapping(config_result, "getDeckConfig")

    current_config_id = _validate_config_id(config.get("id"), "getDeckConfig")
    target_preset_name = _recommended_deck_preset_name(normalized_deck_name)
    config_name = config.get("name")
    created = False

    if config_name == target_preset_name:
        updated_config = deepcopy(config)
    else:
        cloned_config_id = invoke_anki_connect_fn(
            anki_connect_url,
            "cloneDeckConfigId",
            {
                "name": target_preset_name,
                "cloneFrom": current_config_id,
            },
        )
        if cloned_config_id is False:
            raise AnkiConnectError(
                f"Anki couldn't create the recommended deck settings preset for '{normalized_deck_name}'. Try again in Anki and make sure the deck still exists."
            )
        updated_config = deepcopy(config)
        updated_config["id"] = _validate_config_id(cloned_config_id, "cloneDeckConfigId")
        updated_config["name"] = target_preset_name
        created = True

    _apply_recommended_settings(updated_config)

    saved = invoke_anki_connect_fn(
        anki_connect_url,
        "saveDeckConfig",
        {"config": updated_config},
    )
    if saved is not True:
        raise AnkiConnectError(
            f"Anki couldn't save the recommended deck settings for '{normalized_deck_name}'. Try again in Anki and make sure the deck still exists."
        )

    assigned = invoke_anki_connect_fn(
        anki_connect_url,
        "setDeckConfigId",
        {
            "decks": [normalized_deck_name],
            "configId": updated_config["id"],
        },
    )
    if assigned is not True:
        raise AnkiConnectError(
            f"Anki couldn't assign the recommended deck settings to '{normalized_deck_name}'. Try again in Anki and make sure the deck still exists."
        )

    return AnkiDeckSettingsResult(
        deck_name=normalized_deck_name,
        preset_name=target_preset_name,
        created=created,
    )
