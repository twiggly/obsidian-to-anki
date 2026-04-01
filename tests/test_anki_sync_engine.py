import unittest
from pathlib import Path
from unittest import mock

from obsidian_to_anki.anki.connect_client import AnkiConnectError
from obsidian_to_anki.anki.existing_notes import ExistingAnkiNote, build_existing_note_snapshot, build_existing_note_update_plan
from obsidian_to_anki.anki.sync_engine import (
    build_anki_notes,
    build_anki_preflight_result,
    build_anki_preflight_summary,
    sync_cards_to_anki,
)
from obsidian_to_anki.models import AnkiPreflightResult, ExportOptions, NoteCard


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


def build_options(existing_notes: str = "skip") -> ExportOptions:
    return ExportOptions(
        vault_path=Path("/tmp/vault"),
        sync_to_anki=True,
        anki_connect_url="http://127.0.0.1:8765",
        anki_deck="Lexicon",
        anki_note_type="Basic",
        anki_front_field="Front",
        anki_back_field="Back",
        anki_existing_notes=existing_notes,
    )


class AnkiSyncEngineTests(unittest.TestCase):
    def test_build_anki_preflight_summary_counts_new_and_skipped_notes(self) -> None:
        summary = build_anki_preflight_summary(
            build_options(),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: {},
            invoke_anki_connect_fn=lambda url, action, params=None: [True, False],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
        )

        self.assertEqual(summary.new_count, 1)
        self.assertEqual(summary.update_count, 0)
        self.assertEqual(summary.skip_count, 1)
        self.assertEqual(summary.deck_name, "Lexicon")

    def test_build_anki_preflight_summary_counts_updates_when_enabled(self) -> None:
        existing_notes_by_front = {
            "colloquy": [
                ExistingAnkiNote(
                    note_id=101,
                    fields={"Front": "colloquy", "Back": "old"},
                    tags=frozenset(),
                )
            ]
        }

        summary = build_anki_preflight_summary(
            build_options(existing_notes="update"),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: existing_notes_by_front,
            invoke_anki_connect_fn=lambda url, action, params=None: [True, False],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
        )

        self.assertEqual(summary.new_count, 1)
        self.assertEqual(summary.update_count, 1)
        self.assertEqual(summary.skip_count, 0)

    def test_build_anki_preflight_result_captures_notes_and_can_add_results(self) -> None:
        result = build_anki_preflight_result(
            build_options(),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: {},
            invoke_anki_connect_fn=lambda url, action, params=None: [True, False],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
        )

        self.assertEqual(result.summary.new_count, 1)
        self.assertEqual(result.summary.skip_count, 1)
        self.assertEqual(result.can_add, (True, False))
        self.assertEqual(result.notes[0]["fields"]["Front"], "confab")

    def test_sync_cards_to_anki_skips_existing_notes(self) -> None:
        invoke = mock.Mock(return_value=[True, False])
        add_notes_batch = mock.Mock(return_value=[123456789])
        add_single = mock.Mock()

        result = sync_cards_to_anki(
            build_options(),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: {},
            invoke_anki_connect_fn=invoke,
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=mock.Mock(),
            add_notes_batch_fn=add_notes_batch,
            add_single_note_fn=add_single,
            is_duplicate_note_error_fn=lambda error_value: False,
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
        )

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.deck_name, "Lexicon")
        self.assertEqual(result.note_type, "Basic")
        can_add_notes = invoke.call_args.args[2]["notes"]
        self.assertEqual(can_add_notes[0]["fields"]["Front"], "confab")
        self.assertEqual(can_add_notes[1]["tags"], ["definition", "lexicon"])
        notes = add_notes_batch.call_args.args[1]
        self.assertEqual(notes[0]["fields"]["Front"], "confab")
        add_single.assert_not_called()

    def test_sync_cards_to_anki_returns_zero_when_every_note_already_exists(self) -> None:
        result = sync_cards_to_anki(
            build_options(),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: {},
            invoke_anki_connect_fn=lambda url, action, params=None: [False, False],
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=mock.Mock(),
            add_notes_batch_fn=mock.Mock(),
            add_single_note_fn=mock.Mock(),
            is_duplicate_note_error_fn=lambda error_value: False,
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
        )

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.skipped_count, 2)

    def test_sync_cards_to_anki_treats_add_note_duplicate_errors_as_skips(self) -> None:
        duplicate_error = AnkiConnectError(
            "cannot create note because it is a duplicate",
            raw_error="cannot create note because it is a duplicate",
        )

        result = sync_cards_to_anki(
            build_options(),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: {},
            invoke_anki_connect_fn=lambda url, action, params=None: [True, True],
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=mock.Mock(),
            add_notes_batch_fn=mock.Mock(return_value=[111, None]),
            add_single_note_fn=mock.Mock(side_effect=duplicate_error),
            is_duplicate_note_error_fn=lambda error_value: "cannot create note because it is a duplicate"
            in str(error_value).casefold(),
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
        )

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.skipped_count, 1)

    def test_sync_cards_to_anki_treats_batch_duplicate_error_lists_as_skips(self) -> None:
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

        result = sync_cards_to_anki(
            build_options(),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: {},
            invoke_anki_connect_fn=lambda url, action, params=None: [True, True],
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=mock.Mock(),
            add_notes_batch_fn=mock.Mock(side_effect=batch_duplicate_error),
            add_single_note_fn=mock.Mock(side_effect=[single_duplicate_error, single_duplicate_error]),
            is_duplicate_note_error_fn=lambda error_value: (
                isinstance(error_value, list)
                and error_value
                and all("cannot create note because it is a duplicate" in str(item).casefold() for item in error_value)
            )
            or "cannot create note because it is a duplicate" in str(error_value).casefold(),
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
        )

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.skipped_count, 2)

    def test_sync_cards_to_anki_can_update_existing_notes(self) -> None:
        existing_notes_by_front = {
            "colloquy": [
                ExistingAnkiNote(
                    note_id=101,
                    fields={"Front": "colloquy", "Back": "old"},
                    tags=frozenset(),
                )
            ]
        }
        apply_updates = mock.Mock()

        result = sync_cards_to_anki(
            build_options(existing_notes="update"),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: existing_notes_by_front,
            invoke_anki_connect_fn=lambda url, action, params=None: [True, False],
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=apply_updates,
            add_notes_batch_fn=mock.Mock(return_value=[222]),
            add_single_note_fn=mock.Mock(),
            is_duplicate_note_error_fn=lambda error_value: False,
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
        )

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.updated_fronts, ("colloquy",))
        applied_updates = apply_updates.call_args.args[1]
        self.assertEqual(applied_updates[0].note_id, 101)
        self.assertEqual(applied_updates[0].front_value, "colloquy")

    def test_sync_cards_to_anki_reuses_preflight_result(self) -> None:
        options = build_options(existing_notes="update")
        existing_notes_by_front = {
            "colloquy": (
                ExistingAnkiNote(
                    note_id=101,
                    fields={"Front": "colloquy", "Back": "old"},
                    tags=frozenset(),
                ),
            )
        }
        preflight_result = AnkiPreflightResult(
            summary=build_anki_preflight_summary(
                options,
                build_cards(),
                validate_anki_target_fn=lambda options: None,
                build_anki_notes_fn=build_anki_notes,
                fetch_existing_notes_by_front_fn=lambda options: {
                    front: list(notes)
                    for front, notes in existing_notes_by_front.items()
                },
                invoke_anki_connect_fn=lambda url, action, params=None: [True, False],
                build_existing_note_update_plan_fn=build_existing_note_update_plan,
            ),
            notes=tuple(build_anki_notes(options, build_cards())),
            can_add=(True, False),
            existing_notes_by_front=existing_notes_by_front,
        )

        validate_target = mock.Mock()
        fetch_existing_notes = mock.Mock()
        invoke = mock.Mock()
        apply_updates = mock.Mock()

        result = sync_cards_to_anki(
            options,
            build_cards(),
            validate_anki_target_fn=validate_target,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=fetch_existing_notes,
            invoke_anki_connect_fn=invoke,
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=apply_updates,
            add_notes_batch_fn=mock.Mock(return_value=[222]),
            add_single_note_fn=mock.Mock(),
            is_duplicate_note_error_fn=lambda error_value: False,
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
            preflight_result=preflight_result,
        )

        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.updated_count, 1)
        self.assertEqual(result.timing.validation_seconds, 0.0)
        self.assertEqual(result.timing.existing_lookup_seconds, 0.0)
        self.assertEqual(result.timing.can_add_seconds, 0.0)
        validate_target.assert_not_called()
        fetch_existing_notes.assert_not_called()
        invoke.assert_not_called()

    def test_sync_cards_to_anki_skips_noop_updates_for_unchanged_notes(self) -> None:
        existing_notes_by_front = {
            "confab": [
                ExistingAnkiNote(
                    note_id=101,
                    fields={
                        "Front": "confab",
                        "Back": "noun\nan informal private conversation",
                    },
                    tags=frozenset({"definition"}),
                )
            ],
            "colloquy": [
                ExistingAnkiNote(
                    note_id=102,
                    fields={"Front": "colloquy", "Back": "noun\na conversation"},
                    tags=frozenset({"definition", "lexicon"}),
                )
            ],
        }
        apply_updates = mock.Mock()

        result = sync_cards_to_anki(
            build_options(existing_notes="update"),
            build_cards(),
            validate_anki_target_fn=lambda options: None,
            build_anki_notes_fn=build_anki_notes,
            fetch_existing_notes_by_front_fn=lambda options: existing_notes_by_front,
            invoke_anki_connect_fn=lambda url, action, params=None: [False, False],
            note_front_value_fn=lambda note, front_field_name: note["fields"][front_field_name],
            build_existing_note_update_plan_fn=build_existing_note_update_plan,
            apply_existing_note_updates_fn=apply_updates,
            add_notes_batch_fn=mock.Mock(),
            add_single_note_fn=mock.Mock(),
            is_duplicate_note_error_fn=lambda error_value: False,
            build_existing_note_snapshot_fn=build_existing_note_snapshot,
        )

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.updated_count, 2)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(len(apply_updates.call_args.args[1]), 2)


if __name__ == "__main__":
    unittest.main()
