import unittest
from pathlib import Path
from unittest import mock

from obsidian_to_anki.anki.existing_notes import (
    ExistingAnkiNote,
    PendingExistingNoteUpdate,
    apply_existing_note_updates,
    build_existing_note_update_plan,
    fetch_existing_notes_by_front,
)
from obsidian_to_anki.models import ExportOptions


def build_options() -> ExportOptions:
    return ExportOptions(
        vault_path=Path("/tmp/vault"),
        sync_to_anki=True,
        anki_connect_url="http://127.0.0.1:8765",
        anki_deck="Lexicon",
        anki_note_type="Basic",
        anki_front_field="Front",
        anki_back_field="Back",
        anki_existing_notes="update",
    )


class AnkiExistingNotesTests(unittest.TestCase):
    def test_fetch_existing_notes_by_front_normalizes_note_info(self) -> None:
        invoke = mock.Mock(
            side_effect=[
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
            ]
        )

        existing = fetch_existing_notes_by_front(build_options(), invoke_anki_connect_fn=invoke)

        self.assertEqual(sorted(existing.keys()), ["colloquy", "confab"])
        self.assertEqual(existing["confab"][0].note_id, 101)
        self.assertEqual(existing["confab"][0].fields["Back"], "noun\nan informal private conversation")
        self.assertEqual(existing["colloquy"][0].tags, frozenset({"definition", "lexicon"}))

    def test_build_existing_note_update_plan_detects_field_and_tag_changes(self) -> None:
        existing_notes = {
            "colloquy": [
                ExistingAnkiNote(
                    note_id=101,
                    fields={"Front": "colloquy", "Back": "old"},
                    tags=frozenset(),
                )
            ]
        }
        note = {
            "fields": {"Front": "colloquy", "Back": "noun\na conversation"},
            "tags": ["definition", "lexicon"],
        }

        plan = build_existing_note_update_plan(build_options(), note, existing_notes)

        self.assertEqual(
            plan,
            PendingExistingNoteUpdate(
                note_id=101,
                front_value="colloquy",
                fields_to_update={"Front": "colloquy", "Back": "noun\na conversation"},
                tags_to_add="definition lexicon",
            ),
        )

    def test_build_existing_note_update_plan_returns_none_when_front_missing(self) -> None:
        note = {
            "fields": {"Front": "confab", "Back": "noun\nan informal private conversation"},
            "tags": ["definition"],
        }

        self.assertIsNone(build_existing_note_update_plan(build_options(), note, {}))

    def test_apply_existing_note_updates_batches_multi_actions(self) -> None:
        invoke_multi = mock.Mock()
        updates = [
            PendingExistingNoteUpdate(
                note_id=101,
                front_value="colloquy",
                fields_to_update={"Front": "colloquy", "Back": "noun\na conversation"},
                tags_to_add="definition lexicon",
            ),
            PendingExistingNoteUpdate(
                note_id=102,
                front_value="confab",
                fields_to_update={"Front": "confab", "Back": "noun\nan informal private conversation"},
                tags_to_add=None,
            ),
        ]

        apply_existing_note_updates(
            "http://127.0.0.1:8765",
            updates,
            batch_size=2,
            invoke_anki_connect_multi_fn=invoke_multi,
        )

        self.assertEqual(invoke_multi.call_count, 2)
        self.assertEqual(len(invoke_multi.call_args_list[0].args[1]), 2)
        self.assertEqual(len(invoke_multi.call_args_list[1].args[1]), 1)
        self.assertEqual(invoke_multi.call_args_list[0].args[1][0]["action"], "updateNoteFields")
        self.assertEqual(invoke_multi.call_args_list[0].args[1][1]["action"], "addTags")


if __name__ == "__main__":
    unittest.main()
