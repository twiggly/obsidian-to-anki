import unittest
from pathlib import Path
from unittest import mock
from urllib import error

import anki_sync
from anki_sync import AnkiConnectError, fetch_note_type_fields, invoke_anki_connect, sync_cards_to_anki
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
    def test_invoke_anki_connect_wraps_connection_errors(self) -> None:
        with mock.patch.object(anki_sync.request, "urlopen", side_effect=error.URLError("refused")):
            with self.assertRaises(AnkiConnectError) as context:
                invoke_anki_connect("http://127.0.0.1:8765", "deckNames")

        self.assertIn("Could not reach AnkiConnect", str(context.exception))

    def test_sync_cards_to_anki_skips_existing_notes(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_connect_url="http://127.0.0.1:8765",
            anki_deck="Lexicon",
            anki_note_type="Basic",
            anki_front_field="Front",
            anki_back_field="Back",
        )
        cards = build_cards()

        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            side_effect=[
                5,
                ["Default", "Lexicon"],
                ["Basic"],
                ["Front", "Back"],
                [True, False],
                [123456789],
            ],
        ) as invoke:
            result = sync_cards_to_anki(options, cards)

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.deck_name, "Lexicon")
        self.assertEqual(result.note_type, "Basic")

        can_add_call = invoke.call_args_list[4]
        notes = can_add_call.args[2]["notes"]
        self.assertEqual(notes[0]["fields"]["Front"], "confab")
        self.assertEqual(notes[0]["fields"]["Back"], "noun\nan informal private conversation")
        self.assertEqual(notes[1]["tags"], ["definition", "lexicon"])

        add_notes_call = invoke.call_args_list[5]
        self.assertEqual(add_notes_call.args[1], "addNotes")
        self.assertEqual(add_notes_call.args[2]["notes"][0]["fields"]["Front"], "confab")

    def test_sync_cards_to_anki_returns_zero_when_every_note_already_exists(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_connect_url="http://127.0.0.1:8765",
            anki_deck="Lexicon",
            anki_note_type="Basic",
            anki_front_field="Front",
            anki_back_field="Back",
        )

        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            side_effect=[
                5,
                ["Lexicon"],
                ["Basic"],
                ["Front", "Back"],
                [False, False],
            ],
        ) as invoke:
            result = sync_cards_to_anki(options, build_cards())

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.skipped_count, 2)
        self.assertEqual(invoke.call_count, 5)

    def test_sync_cards_to_anki_treats_add_note_duplicate_errors_as_skips(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_connect_url="http://127.0.0.1:8765",
            anki_deck="Lexicon",
            anki_note_type="Basic",
            anki_front_field="Front",
            anki_back_field="Back",
        )

        duplicate_error = AnkiConnectError(
            "cannot create note because it is a duplicate",
            raw_error="cannot create note because it is a duplicate",
        )

        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            side_effect=[
                5,
                ["Lexicon"],
                ["Basic"],
                ["Front", "Back"],
                [True, True],
                [111, None],
                duplicate_error,
            ],
        ):
            result = sync_cards_to_anki(options, build_cards())

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.skipped_count, 1)

    def test_sync_cards_to_anki_treats_batch_duplicate_error_lists_as_skips(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_connect_url="http://127.0.0.1:8765",
            anki_deck="Lexicon",
            anki_note_type="Basic",
            anki_front_field="Front",
            anki_back_field="Back",
        )

        batch_duplicate_error = AnkiConnectError(
            "cannot create note because it is a duplicate; cannot create note because it is a duplicate",
            raw_error=[
                "cannot create note because it is a duplicate",
                "cannot create note because it is a duplicate",
            ],
        )
        single_duplicate_error = AnkiConnectError(
            "cannot create note because it is a duplicate",
            raw_error="cannot create note because it is a duplicate",
        )

        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            side_effect=[
                5,
                ["Lexicon"],
                ["Basic"],
                ["Front", "Back"],
                [True, True],
                batch_duplicate_error,
                single_duplicate_error,
                single_duplicate_error,
            ],
        ):
            result = sync_cards_to_anki(options, build_cards())

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.skipped_count, 2)

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

    def test_sync_cards_to_anki_can_update_existing_notes(self) -> None:
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

    def test_sync_cards_to_anki_batches_addable_notes(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_connect_url="http://127.0.0.1:8765",
            anki_deck="Lexicon",
            anki_note_type="Basic",
            anki_front_field="Front",
            anki_back_field="Back",
        )

        with mock.patch.object(
            anki_sync,
            "invoke_anki_connect",
            side_effect=[
                5,
                ["Lexicon"],
                ["Basic"],
                ["Front", "Back"],
                [True, True],
                [111, 222],
            ],
        ) as invoke:
            result = sync_cards_to_anki(options, build_cards())

        self.assertEqual(result.added_count, 2)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(invoke.call_args_list[5].args[1], "addNotes")
        self.assertEqual(len(invoke.call_args_list[5].args[2]["notes"]), 2)

    def test_sync_cards_to_anki_skips_noop_updates_for_unchanged_notes(self) -> None:
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
                [101, 102],
                [
                    {
                        "noteId": 101,
                        "modelName": "Basic",
                        "tags": ["definition"],
                        "fields": {
                            "Front": {"value": "confab"},
                            "Back": {"value": "noun\nan informal private conversation"},
                        },
                    },
                    {
                        "noteId": 102,
                        "modelName": "Basic",
                        "tags": ["definition", "lexicon"],
                        "fields": {
                            "Front": {"value": "colloquy"},
                            "Back": {"value": "noun\na conversation"},
                        },
                    },
                ],
                [False, False],
            ],
        ) as invoke:
            result = sync_cards_to_anki(options, build_cards())

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.updated_count, 2)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.updated_fronts, ("confab", "colloquy"))
        self.assertEqual(invoke.call_count, 7)
