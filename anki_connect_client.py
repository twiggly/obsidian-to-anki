from __future__ import annotations

import json
from typing import Any, Sequence
from urllib import error, request

from models import ExportError


ANKI_CONNECT_API_VERSION = 5


class AnkiConnectError(ExportError):
    def __init__(self, message: str, raw_error: object | None = None) -> None:
        super().__init__(message)
        self.raw_error = raw_error


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


def invoke_anki_connect_multi(url: str, actions: Sequence[dict[str, object]]) -> list[object]:
    if not actions:
        return []
    results = invoke_anki_connect(url, "multi", {"actions": list(actions)})
    if not isinstance(results, list) or len(results) != len(actions):
        raise AnkiConnectError("Received an unexpected response from multi.")
    return results
