import unittest
from pathlib import Path

from obsidian_to_anki.delivery import deliver_cards
from obsidian_to_anki.models import AnkiSyncResult, ExportOptions, NoteCard


class DeliveryTests(unittest.TestCase):
    def test_deliver_cards_runs_export_and_sync_when_both_are_enabled(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            sync_to_anki=True,
            anki_deck="Lexicon",
            anki_note_type="Basic",
        )
        cards = [
            NoteCard(
                front="confab",
                back="Body",
                tags=["definition"],
                source_path=Path("/tmp/confab.md"),
            )
        ]
        calls: list[str] = []

        result = deliver_cards(
            options,
            cards,
            export_fn=lambda received_options, received_cards: calls.append("export") or 1,
            sync_fn=lambda received_options, received_cards: calls.append("sync")
            or AnkiSyncResult(
                added_count=1,
                skipped_count=0,
                deck_name="Lexicon",
                note_type="Basic",
            ),
        )

        self.assertEqual(calls, ["export", "sync"])
        self.assertEqual(result.export_count, 1)
        self.assertIsNotNone(result.sync_result)
        self.assertGreaterEqual(result.export_seconds, 0.0)
        self.assertGreaterEqual(result.sync_seconds, 0.0)
        self.assertGreaterEqual(result.total_seconds, 0.0)
