import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from obsidian_to_anki import cli
from obsidian_to_anki.cli import main as cli_main
from obsidian_to_anki.models import AnkiSyncResult, DeliveryResult


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = cli_main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_main_requires_vault_and_output_or_anki_in_command_line_mode(self) -> None:
        exit_code, stdout, stderr = run_cli(["--vault", "/tmp/example-vault"])

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("--vault and at least one of --output or --anki are required", stderr)

    def test_main_creates_output_file_and_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()
            (vault_path / "Definition.md").write_text("#definition\nA body", encoding="utf-8")
            output_path = Path(temp_dir) / "definitions.tsv"

            exit_code, stdout, stderr = run_cli(
                ["--vault", str(vault_path), "--output", str(output_path)]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported 1 cards", stdout)
            self.assertEqual(stderr, "")
            self.assertTrue(output_path.exists())
            self.assertIn("Definition\tA body\tdefinition", output_path.read_text(encoding="utf-8-sig"))

    def test_main_reports_duplicate_fronts_on_stderr_for_suffix_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            (vault_path / "A").mkdir(parents=True)
            (vault_path / "B").mkdir(parents=True)
            (vault_path / "A" / "Term.md").write_text("#definition\nFirst", encoding="utf-8")
            (vault_path / "B" / "Term.md").write_text("#definition\nSecond", encoding="utf-8")
            output_path = Path(temp_dir) / "definitions.tsv"

            exit_code, stdout, stderr = run_cli(
                [
                    "--vault",
                    str(vault_path),
                    "--output",
                    str(output_path),
                    "--duplicate-handling",
                    "suffix",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported 2 cards", stdout)
            self.assertIn("Warning: Detected 1 duplicate card fronts.", stderr)
            self.assertIn("Appending folder-based suffixes so each front stays unique.", stderr)
            self.assertIn("Term (2 matches)", stderr)

    def test_main_errors_on_duplicate_fronts_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            (vault_path / "A").mkdir(parents=True)
            (vault_path / "B").mkdir(parents=True)
            (vault_path / "A" / "Term.md").write_text("#definition\nFirst", encoding="utf-8")
            (vault_path / "B" / "Term.md").write_text("#definition\nSecond", encoding="utf-8")
            output_path = Path(temp_dir) / "definitions.tsv"

            exit_code, stdout, stderr = run_cli(
                ["--vault", str(vault_path), "--output", str(output_path)]
            )

            self.assertEqual(exit_code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("Detected 1 duplicate card fronts", stderr)

    def test_main_can_skip_duplicate_fronts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            (vault_path / "A").mkdir(parents=True)
            (vault_path / "B").mkdir(parents=True)
            (vault_path / "A" / "Term.md").write_text("#definition\nFirst", encoding="utf-8")
            (vault_path / "B" / "Term.md").write_text("#definition\nSecond", encoding="utf-8")
            output_path = Path(temp_dir) / "definitions.tsv"

            exit_code, stdout, stderr = run_cli(
                [
                    "--vault",
                    str(vault_path),
                    "--output",
                    str(output_path),
                    "--duplicate-handling",
                    "skip",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported 1 cards", stdout)
            self.assertIn("Keeping the first matching note for each front", stderr)
            content = output_path.read_text(encoding="utf-8-sig")
            self.assertEqual(content.count("Term\t"), 1)

    def test_main_respects_include_folder_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            (vault_path / "Included").mkdir(parents=True)
            (vault_path / "Excluded").mkdir(parents=True)
            (vault_path / "Included" / "Keep.md").write_text("#definition\nKeep me", encoding="utf-8")
            (vault_path / "Excluded" / "Skip.md").write_text("#definition\nSkip me", encoding="utf-8")
            output_path = Path(temp_dir) / "definitions.tsv"

            exit_code, stdout, _ = run_cli(
                [
                    "--vault",
                    str(vault_path),
                    "--output",
                    str(output_path),
                    "--include-folder",
                    "Included",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported 1 cards", stdout)
            content = output_path.read_text(encoding="utf-8-sig")
            self.assertIn("Keep\tKeep me\tdefinition", content)
            self.assertNotIn("Skip\tSkip me\tdefinition", content)

    def test_main_html_automatically_skips_empty_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()
            (vault_path / "Empty.md").write_text("#definition", encoding="utf-8")
            (vault_path / "Rich.md").write_text(
                'noun\n"an informal private conversation"\n#definition',
                encoding="utf-8",
            )
            output_path = Path(temp_dir) / "definitions.tsv"

            exit_code, stdout, stderr = run_cli(
                [
                    "--vault",
                    str(vault_path),
                    "--output",
                    str(output_path),
                    "--html",
                    "--italicize-quoted-text",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported 1 cards", stdout)
            self.assertEqual(stderr, "")
            content = output_path.read_text(encoding="utf-8-sig")
            self.assertNotIn("Empty\t", content)
            self.assertIn("dictionary-entry", content)
            self.assertIn("&quot;an informal private conversation&quot;", content)
            self.assertIn("<em>", content)

    def test_main_supports_sync_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()
            (vault_path / "Definition.md").write_text("#definition\nA body", encoding="utf-8")

            with mock.patch.object(
                cli,
                "deliver_cards",
                return_value=DeliveryResult(
                    sync_result=AnkiSyncResult(
                        added_count=1,
                        skipped_count=0,
                        deck_name="Lexicon",
                        note_type="Basic",
                    )
                ),
            ) as deliver_cards:
                exit_code, stdout, stderr = run_cli(
                    [
                        "--vault",
                        str(vault_path),
                        "--anki",
                        "--anki-deck",
                        "Lexicon",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Synced 1 cards to Anki deck 'Lexicon' using note type 'Basic'.", stdout)
            self.assertEqual(stderr, "")
            deliver_cards.assert_called_once()

    def test_main_passes_anki_existing_note_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()
            (vault_path / "Definition.md").write_text("#definition\nA body", encoding="utf-8")

            with mock.patch.object(cli, "deliver_cards", return_value=DeliveryResult()) as deliver_cards:
                exit_code, _, _ = run_cli(
                    [
                        "--vault",
                        str(vault_path),
                        "--anki",
                        "--anki-existing-notes",
                        "update",
                    ]
                )

        self.assertEqual(exit_code, 0)
        passed_options = deliver_cards.call_args.args[0]
        self.assertEqual(passed_options.anki_existing_notes, "update")
