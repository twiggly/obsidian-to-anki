import tempfile
import unittest
from pathlib import Path

from obsidian_to_anki.gui.logic import (
    FormValidationError,
    build_export_options_from_values,
    delivery_action_label,
    duplicate_front_warning_message,
    delivery_complete_message,
    delivery_complete_title,
    delivery_progress_message,
    export_no_cards_message,
    preview_no_matches_message,
    preview_ready_message,
    timing_breakdown_lines,
)
from obsidian_to_anki.models import AnkiSyncResult, DeliveryResult, ExportOptions, NoteCard, ScanResult


def build_scan_result(
    *,
    preview_count: int = 1,
    total_matches: int = 1,
    duplicate_fronts: dict[str, tuple[Path, ...]] | None = None,
) -> ScanResult:
    cards = [
        NoteCard(
            front=f"Definition {index}",
            back="Body",
            tags=["definition"],
            source_path=Path(f"/tmp/Definition-{index}.md"),
        )
        for index in range(preview_count)
    ]
    return ScanResult(
        cards=cards,
        preview_cards=cards,
        total_matches=total_matches,
        duplicate_fronts=duplicate_fronts or {},
    )


class GuiLogicTests(unittest.TestCase):
    def test_build_export_options_from_values_returns_normalized_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            included_path = vault_path / "Study"
            included_path.mkdir(parents=True)
            output_path = Path(temp_dir) / "definitions.tsv"

            options = build_export_options_from_values(
                str(vault_path),
                str(output_path),
                "  #Definition  ",
                html_output=False,
                skip_empty=True,
                italicize_quoted_text=True,
                raw_folder_filters=["Study"],
                duplicate_handling="error",
                sync_to_anki=False,
                anki_connect_url="http://127.0.0.1:8765",
                anki_deck="Default",
                anki_note_type="Basic",
                anki_front_field="Front",
                anki_back_field="Back",
            )

            self.assertEqual(options.vault_path, vault_path.resolve())
            self.assertEqual(options.output_path, output_path.resolve())
            self.assertEqual(options.target_tag, "definition")
            self.assertFalse(options.html_output)
            self.assertTrue(options.skip_empty)
            self.assertFalse(options.italicize_quoted_text)
            self.assertEqual(options.include_folders, ("Study",))
            self.assertEqual(options.anki_existing_notes, "skip")

    def test_build_export_options_from_values_accepts_multiple_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            options = build_export_options_from_values(
                str(vault_path),
                "",
                [" #Definition ", "biology", "definition"],
                html_output=False,
                skip_empty=False,
                italicize_quoted_text=False,
                raw_folder_filters=[],
                duplicate_handling="error",
                sync_to_anki=True,
                anki_connect_url="http://127.0.0.1:8765",
                anki_deck="Lexicon",
                anki_note_type="Basic",
                anki_front_field="Front",
                anki_back_field="Back",
                write_tsv=False,
            )

            self.assertEqual(options.target_tag, "definition")
            self.assertEqual(options.additional_target_tags, ("biology",))

    def test_build_export_options_from_values_raises_missing_vault(self) -> None:
        with self.assertRaises(FormValidationError) as context:
            build_export_options_from_values(
                "",
                "/tmp/out.tsv",
                "definition",
                html_output=False,
                skip_empty=False,
                italicize_quoted_text=False,
                raw_folder_filters=[],
                duplicate_handling="error",
                sync_to_anki=False,
                anki_connect_url="http://127.0.0.1:8765",
                anki_deck="Default",
                anki_note_type="Basic",
                anki_front_field="Front",
                anki_back_field="Back",
            )

        self.assertEqual(context.exception.title, "Missing vault")
        self.assertEqual(str(context.exception), "Choose an Obsidian vault folder.")

    def test_build_export_options_from_values_requires_at_least_one_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            with self.assertRaises(FormValidationError) as context:
                build_export_options_from_values(
                    str(vault_path),
                    str(Path(temp_dir) / "out.tsv"),
                    [],
                    html_output=False,
                    skip_empty=False,
                    italicize_quoted_text=False,
                    raw_folder_filters=[],
                    duplicate_handling="error",
                    sync_to_anki=False,
                    anki_connect_url="http://127.0.0.1:8765",
                    anki_deck="Default",
                    anki_note_type="Basic",
                    anki_front_field="Front",
                    anki_back_field="Back",
                )

        self.assertEqual(context.exception.title, "Missing tags")
        self.assertEqual(str(context.exception), "Choose at least one tag to match.")

    def test_build_export_options_from_values_allows_sync_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            options = build_export_options_from_values(
                str(vault_path),
                "",
                "definition",
                html_output=False,
                skip_empty=False,
                italicize_quoted_text=False,
                raw_folder_filters=[],
                duplicate_handling="error",
                sync_to_anki=True,
                anki_connect_url=" http://127.0.0.1:8765/ ",
                anki_deck="Lexicon",
                anki_note_type="Basic",
                anki_front_field="Front",
                anki_back_field="Back",
                write_tsv=False,
            )

        self.assertIsNone(options.output_path)
        self.assertTrue(options.sync_to_anki)
        self.assertEqual(options.anki_connect_url, "http://127.0.0.1:8765")
        self.assertEqual(options.anki_deck, "Lexicon")

    def test_build_export_options_from_values_raises_invalid_folder_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            with self.assertRaises(FormValidationError) as context:
                build_export_options_from_values(
                    str(vault_path),
                    str(Path(temp_dir) / "out.tsv"),
                    "definition",
                    html_output=True,
                    skip_empty=False,
                    italicize_quoted_text=True,
                    raw_folder_filters=["Missing"],
                    duplicate_handling="error",
                    sync_to_anki=False,
                    anki_connect_url="http://127.0.0.1:8765",
                    anki_deck="Default",
                    anki_note_type="Basic",
                    anki_front_field="Front",
                    anki_back_field="Back",
                )

        self.assertEqual(context.exception.title, "Invalid folder filter")
        self.assertIn("Folder filter does not exist in the vault", str(context.exception))

    def test_preview_message_helpers_format_expected_text(self) -> None:
        scan_result = build_scan_result(preview_count=2, total_matches=5)
        scan_result = ScanResult(
            cards=scan_result.cards,
            preview_cards=scan_result.preview_cards,
            total_matches=scan_result.total_matches,
            duplicate_fronts=scan_result.duplicate_fronts,
            scan_seconds=1.25,
        )

        self.assertEqual(
            preview_ready_message(scan_result),
            "Preview ready. Showing the first 2 of 5 matching cards.",
        )
        self.assertEqual(
            preview_no_matches_message("definition"),
            "No notes tagged with #definition were found.",
        )
        self.assertEqual(
            preview_no_matches_message("definition", ("fallacy",), ("Logic",)),
            "No notes tagged with #definition or #fallacy were found in Logic.",
        )
        self.assertEqual(
            timing_breakdown_lines(scan_result),
            ["Timing: scan 1.25s"],
        )

    def test_timing_breakdown_lines_include_delivery_timings(self) -> None:
        scan_result = build_scan_result()
        scan_result = ScanResult(
            cards=scan_result.cards,
            preview_cards=scan_result.preview_cards,
            total_matches=scan_result.total_matches,
            duplicate_fronts=scan_result.duplicate_fronts,
            scan_seconds=2.5,
        )

        lines = timing_breakdown_lines(
            scan_result,
            DeliveryResult(
                export_count=1,
                output_path=Path("/tmp/out.tsv"),
                sync_result=AnkiSyncResult(
                    added_count=1,
                    skipped_count=0,
                    deck_name="Lexicon",
                    note_type="Basic",
                ),
                export_seconds=0.2,
                sync_seconds=3.4,
                total_seconds=3.6,
            ),
        )

        self.assertEqual(
            lines,
            [
                "Timing: scan 2.50s, export 0.20s, sync 0.00s, total 3.60s",
                "Anki sync: validate 0.00s, check duplicates 0.00s, write changes 0.00s",
            ],
        )

    def test_duplicate_front_warning_message_returns_none_without_duplicates(self) -> None:
        scan_result = build_scan_result()

        self.assertIsNone(duplicate_front_warning_message(scan_result.duplicate_fronts, "error"))

    def test_duplicate_front_warning_message_includes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            duplicate_fronts = {
                "Definition": (
                    Path(temp_dir) / "Lexicon" / "Definition.md",
                    Path(temp_dir) / "Study" / "Definition.md",
                )
            }

            message = duplicate_front_warning_message(duplicate_fronts, "skip")

        self.assertIsNotNone(message)
        self.assertIn("1 duplicate word found.", message or "")
        self.assertIn("Current handling: keep the first matching note for each word.", message or "")
        self.assertIn("• Definition (2 matches)\n  Lexicon, Study", message or "")
        self.assertNotIn(str(Path(temp_dir)), message or "")

    def test_duplicate_front_warning_message_changes_wording_for_suffix_mode(self) -> None:
        duplicate_fronts = {
            "Definition": (
                Path("/tmp/Lexicon/Definition.md"),
                Path("/tmp/Study/Definition.md"),
            )
        }

        message = duplicate_front_warning_message(duplicate_fronts, "suffix")

        self.assertEqual(
            message,
            "1 duplicate word found.\n"
            "Current handling: rename duplicate fronts with folder suffixes.\n\n"
            "• Definition (2 matches)\n"
            "  Lexicon, Study",
        )

    def test_delivery_message_helpers_format_expected_text(self) -> None:
        export_options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            duplicate_handling="suffix",
        )
        sync_options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            sync_to_anki=True,
            anki_deck="Lexicon",
            anki_note_type="Basic",
        )
        both_options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            sync_to_anki=True,
            anki_deck="Lexicon",
            anki_note_type="Basic",
            duplicate_handling="suffix",
        )

        self.assertEqual(
            export_no_cards_message("definition"),
            "No notes tagged with #definition were found.",
        )
        self.assertEqual(
            export_no_cards_message("definition", ("fallacy",), ("Logic", "Study")),
            "No notes tagged with #definition or #fallacy were found in Logic, and Study.",
        )
        self.assertEqual(
            delivery_action_label(export_options),
            "Export",
        )
        self.assertEqual(
            delivery_action_label(sync_options),
            "Sync to Anki",
        )
        self.assertEqual(
            delivery_progress_message(both_options),
            "Exporting and syncing cards…",
        )
        self.assertEqual(
            delivery_complete_title(sync_options),
            "Sync complete",
        )
        self.assertEqual(
            delivery_complete_message(
                export_options,
                DeliveryResult(export_count=3, output_path=Path("/tmp/out.tsv")),
                0,
            ),
            "Exported 3 cards to: /tmp/out.tsv",
        )
        self.assertEqual(
            delivery_complete_message(
                both_options,
                DeliveryResult(
                    export_count=3,
                    output_path=Path("/tmp/out.tsv"),
                    sync_result=AnkiSyncResult(
                        added_count=2,
                        skipped_count=1,
                        deck_name="Lexicon",
                        note_type="Basic",
                    ),
                ),
                2,
            ),
            "Exported 3 cards to: /tmp/out.tsv Synced 2 cards to Anki deck 'Lexicon' using note type 'Basic'. Skipped 1 existing notes. Detected 2 duplicate card fronts. Appending folder-based suffixes so each front stays unique.",
        )
        self.assertEqual(
            delivery_complete_message(
                sync_options,
                DeliveryResult(
                    sync_result=AnkiSyncResult(
                        added_count=0,
                        skipped_count=0,
                        updated_count=2,
                        deck_name="Lexicon",
                        note_type="Basic",
                    )
                ),
                0,
            ),
            "Updated 2 existing Anki notes in deck 'Lexicon' using note type 'Basic'.",
        )
        self.assertEqual(
            delivery_complete_message(
                sync_options,
                DeliveryResult(
                    sync_result=AnkiSyncResult(
                        added_count=0,
                        skipped_count=4,
                        deck_name="Lexicon",
                        note_type="Basic",
                    )
                ),
                0,
            ),
            "No new Anki notes were added to deck 'Lexicon'. Skipped 4 existing notes.",
        )
        self.assertEqual(
            delivery_complete_message(
                ExportOptions(
                    vault_path=Path("/tmp/vault"),
                    output_path=Path("/tmp/out.tsv"),
                    duplicate_handling="skip",
                ),
                DeliveryResult(export_count=2, output_path=Path("/tmp/out.tsv")),
                1,
            ),
            "Exported 2 cards to: /tmp/out.tsv Detected 1 duplicate card fronts. Keeping the first matching note for each front.",
        )
        self.assertEqual(
            delivery_complete_message(
                export_options,
                DeliveryResult(
                    export_count=3,
                    output_path=Path("/tmp/out.tsv"),
                    report_text="Duplicate fronts detected:\n- Term\n",
                ),
                0,
            ),
            "Exported 3 cards to: /tmp/out.tsv",
        )

    def test_build_export_options_from_values_requires_output_path_when_tsv_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            with self.assertRaises(FormValidationError) as context:
                build_export_options_from_values(
                    str(vault_path),
                    "",
                    "definition",
                    html_output=False,
                    skip_empty=False,
                    italicize_quoted_text=False,
                    raw_folder_filters=[],
                    duplicate_handling="error",
                    sync_to_anki=True,
                    anki_connect_url="http://127.0.0.1:8765",
                    anki_deck="Default",
                    anki_note_type="Basic",
                    anki_front_field="Front",
                    anki_back_field="Back",
                )

        self.assertEqual(context.exception.title, "Missing destination")
        self.assertIn("turn off TSV export", str(context.exception))

    def test_build_export_options_from_values_requires_destination_when_sync_is_off(self) -> None:
        with self.assertRaises(FormValidationError) as context:
            build_export_options_from_values(
                "/tmp/vault",
                "",
                "definition",
                html_output=False,
                skip_empty=False,
                italicize_quoted_text=False,
                raw_folder_filters=[],
                duplicate_handling="error",
                sync_to_anki=False,
                anki_connect_url="http://127.0.0.1:8765",
                anki_deck="Default",
                anki_note_type="Basic",
                anki_front_field="Front",
                anki_back_field="Back",
                write_tsv=False,
            )

        self.assertEqual(context.exception.title, "Missing destination")
        self.assertIn("Turn on TSV export or enable direct Anki sync", str(context.exception))

    def test_build_export_options_from_values_requires_anki_deck_when_syncing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            with self.assertRaises(FormValidationError) as context:
                build_export_options_from_values(
                    str(vault_path),
                    "",
                    "definition",
                    html_output=False,
                    skip_empty=False,
                    italicize_quoted_text=False,
                    raw_folder_filters=[],
                    duplicate_handling="error",
                    sync_to_anki=True,
                    anki_connect_url="http://127.0.0.1:8765",
                anki_deck="",
                anki_note_type="Basic",
                anki_front_field="Front",
                anki_back_field="Back",
                write_tsv=False,
                )

        self.assertEqual(context.exception.title, "Missing Anki deck")
        self.assertEqual(str(context.exception), "Enter an Anki deck name.")

    def test_build_export_options_from_values_rejects_invalid_duplicate_handling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            with self.assertRaises(FormValidationError) as context:
                build_export_options_from_values(
                    str(vault_path),
                    str(Path(temp_dir) / "out.tsv"),
                    "definition",
                    html_output=False,
                    skip_empty=False,
                    italicize_quoted_text=False,
                    raw_folder_filters=[],
                    duplicate_handling="merge",
                    sync_to_anki=False,
                    anki_connect_url="http://127.0.0.1:8765",
                    anki_deck="Default",
                    anki_note_type="Basic",
                    anki_front_field="Front",
                    anki_back_field="Back",
                )

        self.assertEqual(context.exception.title, "Invalid duplicate handling")
