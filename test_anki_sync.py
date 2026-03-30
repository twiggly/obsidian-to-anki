import unittest
from pathlib import Path
from unittest import mock

import anki_sync
from anki_sync import fetch_note_type_fields, sync_cards_to_anki
from models import ExportOptions, NoteCard


def build_cards() -> list[NoteCard]:
    return [
        NoteCard(
            front="confab",
            back="noun\nan informal private conversation",
            tags=["definition"],
            source_path=Path("/tmp/confab.md"),
        ),
        NoteCard(
            front="colloquy",
            back="noun\na conversation",
            tags=["definition", "lexicon"],
            source_path=Path("/tmp/colloquy.md"),
        ),
    ]


class AnkiSyncTests(unittest.TestCase):
    def test_fetch_note_type_fields_returns_field_catalog(self) -> None:
        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            return_value=["Front", "Back", "Extra"],
        ) as invoke:
            field_catalog = fetch_note_type_fields("http://127.0.0.1:8765", "Basic")

        self.assertEqual(field_catalog.note_type_name, "Basic")
        self.assertEqual(field_catalog.field_names, ("Front", "Back", "Extra"))
        invoke.assert_called_once_with(
            "http://127.0.0.1:8765",
            "modelFieldNames",
            {"modelName": "Basic"},
        )

    def test_sync_cards_to_anki_uses_public_invoke_patchpoint_for_updates(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_connect_url="http://127.0.0.1:8765",
            anki_deck="Lexicon",
            anki_note_type="Basic",
            anki_front_field="Front",
            anki_back_field="Back",
            anki_existing_notes="update",
        )

        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            side_effect=[
                5,
                ["Lexicon"],
                ["Basic"],
                ["Front", "Back"],
                [101],
                [
                    {
                        "noteId": 101,
                        "modelName": "Basic",
                        "tags": [],
                        "fields": {"Front": {"value": "colloquy"}, "Back": {"value": "old"}},
                    }
                ],
                [True, False],
                [None, None],
                [222],
            ],
        ) as invoke:
            result = sync_cards_to_anki(options, build_cards())

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.updated_fronts, ("colloquy",))
        self.assertEqual(invoke.call_args_list[7].args[1], "multi")
        actions = invoke.call_args_list[7].args[2]["actions"]
        self.assertEqual(actions[0]["action"], "updateNoteFields")
        self.assertEqual(actions[1]["action"], "addTags")
        self.assertEqual(invoke.call_count, 9)
