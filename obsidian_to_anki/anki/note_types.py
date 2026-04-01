from __future__ import annotations

from typing import Any, Callable

from .connect_client import AnkiConnectError, invoke_anki_connect, unexpected_anki_response_message
from ..models import AnkiNoteTypeInstallResult


OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME = "Term & Definition (Obsidian)"
OBSIDIAN_DEFINITIONS_MIN_VERSION = 6
OBSIDIAN_DEFINITIONS_FIELD_NAMES = ("Front", "Back")
OBSIDIAN_DEFINITIONS_CARD_TEMPLATES = (
    {
        "Name": "Word to Definition",
        "Front": '<div class="front">{{Front}}</div>',
        "Back": '<div class="front">{{Front}}</div>\n\n<hr id="answer">\n\n<div class="back">\n  {{Back}}\n</div>',
    },
    {
        "Name": "Definition to Word",
        "Front": '<div class="back reverse-definition">\n  {{Back}}\n</div>',
        "Back": '<div class="back reverse-definition">\n  {{Back}}\n</div>\n\n<hr id="answer">\n\n<div class="front">{{Front}}</div>',
    },
)
OBSIDIAN_DEFINITIONS_STYLING = """.card {
  font-family: Arial, sans-serif;
  font-size: 22px;
  color: #f2f2f2;
  background: #2f2f2f;
  text-align: center;
  padding: 28px 20px;
}

.front {
  font-size: 1.35em;
  font-weight: bold;
}

.back {
  text-align: left;
  max-width: 720px;
  margin: 0 auto;
  line-height: 1.35;
}

.reverse-definition {
  text-align: left;
  max-width: 720px;
  margin: 0 auto;
  line-height: 1.35;
}

/* Only style top-level content blocks */
.back > div {
  margin: 0 0 0.45em 0;
}

.back .dictionary-entry {
  margin: 0 0 0.9em 0;
  padding: 0.1em 0 0.15em 0.8em;
  border-left: 3px solid #b8b1a6;
}

.back .pos {
  margin: 0 0 0.2em 0;
  font-size: 0.68em;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #d8c792;
}

.back .gloss {
  margin: 0 0 0.28em 0;
}

.back ul {
  margin: 0.2em 0 0.55em 1.2em;
  padding-left: 0.4em;
}

.back .dictionary-entry ul {
  margin-top: 0.15em;
  margin-bottom: 0.35em;
}

.back li {
  margin: 0.12em 0;
}

#answer {
  border: none;
  border-top: 1px solid #b8b1a6;
  margin: 18px auto 20px;
  max-width: 720px;
}
"""


def _validate_string_list(value: object, action: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AnkiConnectError(unexpected_anki_response_message(action))
    return value


def _validate_template_mapping(value: object, action: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise AnkiConnectError(unexpected_anki_response_message(action))
    normalized: dict[str, dict[str, str]] = {}
    for template_name, template in value.items():
        if not isinstance(template_name, str) or not isinstance(template, dict):
            raise AnkiConnectError(unexpected_anki_response_message(action))
        front = template.get("Front")
        back = template.get("Back")
        if not isinstance(front, str) or not isinstance(back, str):
            raise AnkiConnectError(unexpected_anki_response_message(action))
        normalized[template_name] = {"Front": front, "Back": back}
    return normalized


def _obsidian_definitions_template_mapping() -> dict[str, dict[str, str]]:
    return {
        template["Name"]: {
            "Front": template["Front"],
            "Back": template["Back"],
        }
        for template in OBSIDIAN_DEFINITIONS_CARD_TEMPLATES
    }


def install_obsidian_definitions_note_type(
    anki_connect_url: str,
    *,
    invoke_anki_connect_fn: Callable[[str, str, dict[str, Any] | None], Any] = invoke_anki_connect,
) -> AnkiNoteTypeInstallResult:
    version = invoke_anki_connect_fn(anki_connect_url, "version", None)
    if not isinstance(version, int) or version < OBSIDIAN_DEFINITIONS_MIN_VERSION:
        raise AnkiConnectError(
            f"Installing the {OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME} note type requires AnkiConnect 6 or newer. Update the add-on and try again."
        )

    model_names = _validate_string_list(
        invoke_anki_connect_fn(anki_connect_url, "modelNames", None),
        "modelNames",
    )

    if OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME not in model_names:
        invoke_anki_connect_fn(
            anki_connect_url,
            "createModel",
            {
                "modelName": OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
                "inOrderFields": list(OBSIDIAN_DEFINITIONS_FIELD_NAMES),
                "css": OBSIDIAN_DEFINITIONS_STYLING,
                "isCloze": False,
                "cardTemplates": list(OBSIDIAN_DEFINITIONS_CARD_TEMPLATES),
            },
        )
        return AnkiNoteTypeInstallResult(
            note_type_name=OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
            created=True,
        )

    field_names = _validate_string_list(
        invoke_anki_connect_fn(
            anki_connect_url,
            "modelFieldNames",
            {"modelName": OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME},
        ),
        "modelFieldNames",
    )
    missing_fields = [field for field in OBSIDIAN_DEFINITIONS_FIELD_NAMES if field not in field_names]
    if missing_fields:
        raise AnkiConnectError(
            f"The existing Anki note type '{OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME}' doesn't use the required Front and Back fields. Rename or remove it in Anki, then try the installer again."
        )

    existing_templates = _validate_template_mapping(
        invoke_anki_connect_fn(
            anki_connect_url,
            "modelTemplates",
            {"modelName": OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME},
        ),
        "modelTemplates",
    )
    desired_templates = _obsidian_definitions_template_mapping()

    for template in OBSIDIAN_DEFINITIONS_CARD_TEMPLATES:
        if template["Name"] in existing_templates:
            continue
        invoke_anki_connect_fn(
            anki_connect_url,
            "modelTemplateAdd",
            {
                "modelName": OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
                "template": template,
            },
        )

    invoke_anki_connect_fn(
        anki_connect_url,
        "updateModelTemplates",
        {
            "model": {
                "name": OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
                "templates": desired_templates,
            }
        },
    )
    invoke_anki_connect_fn(
        anki_connect_url,
        "updateModelStyling",
        {
            "model": {
                "name": OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
                "css": OBSIDIAN_DEFINITIONS_STYLING,
            }
        },
    )
    return AnkiNoteTypeInstallResult(
        note_type_name=OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
        created=False,
    )
