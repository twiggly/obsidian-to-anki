import tempfile
import unittest
from pathlib import Path

from obsidian_to_anki.exporting import run_export
from obsidian_to_anki.models import ExportError, ExportOptions
from obsidian_to_anki.rendering import clean_body
from obsidian_to_anki.scanner import extract_frontmatter_tags, extract_tags, iter_markdown_note_paths, scan_cards, scan_vault_tags


class TagExtractionTests(unittest.TestCase):
    def test_extract_tags_ignores_html_comments(self) -> None:
        tags = extract_tags("", "<!-- #definition -->\nBody text")

        self.assertEqual(tags, set())

    def test_extract_tags_ignores_markdown_link_fragments(self) -> None:
        tags = extract_tags("", "[link](#definition)\nBody text")

        self.assertEqual(tags, set())

    def test_extract_tags_ignores_obsidian_wikilink_heading_fragments(self) -> None:
        tags = extract_tags("", "[[#definition|label]]\nBody text")

        self.assertEqual(tags, set())

    def test_extract_frontmatter_tags_splits_unquoted_comma_separated_values(self) -> None:
        tags = extract_frontmatter_tags("tags: definition, biology")

        self.assertEqual(tags, {"definition", "biology"})

    def test_extract_frontmatter_tags_keeps_quoted_commas_as_single_tag(self) -> None:
        tags = extract_frontmatter_tags('tags: "definition, biology"')

        self.assertEqual(tags, {"definition, biology"})

    def test_extract_frontmatter_tags_ignores_inline_comments_on_scalar_values(self) -> None:
        tags = extract_frontmatter_tags("tags: definition # note")

        self.assertEqual(tags, {"definition"})

    def test_extract_frontmatter_tags_ignores_inline_comments_on_list_items(self) -> None:
        tags = extract_frontmatter_tags("tags:\n  - definition # note\n  - biology")

        self.assertEqual(tags, {"definition", "biology"})

    def test_extract_frontmatter_tags_preserves_hashes_inside_quoted_values(self) -> None:
        tags = extract_frontmatter_tags('tags: "definition # note"')

        self.assertEqual(tags, {"definition # note"})

    def test_clean_body_preserves_markdown_link_fragments_while_removing_actual_tags(self) -> None:
        cleaned = clean_body("[link](#definition)\n\n#definition")

        self.assertEqual(cleaned, "[link](#definition)")

    def test_clean_body_preserves_obsidian_wikilink_heading_fragments_while_removing_actual_tags(self) -> None:
        cleaned = clean_body("[[#definition|label]]\n\n#definition")

        self.assertEqual(cleaned, "[[#definition|label]]")


class ValidationTests(unittest.TestCase):
    def test_scan_vault_tags_collects_and_sorts_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "A.md").write_text("#definition\n#Biology", encoding="utf-8")
            (vault_path / "B.md").write_text("---\ntags: lexicon, study\n---\nBody", encoding="utf-8")

            tags = scan_vault_tags(vault_path)

            self.assertEqual(tags, ("biology", "definition", "lexicon", "study"))

    def test_scan_vault_tags_respects_folder_filters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "Included").mkdir()
            (vault_path / "Excluded").mkdir()
            (vault_path / "Included" / "A.md").write_text("#definition\n#biology", encoding="utf-8")
            (vault_path / "Excluded" / "B.md").write_text("#ignored", encoding="utf-8")

            tags = scan_vault_tags(vault_path, ("Included",))

            self.assertEqual(tags, ("biology", "definition"))

    def test_scan_vault_tags_ignores_hidden_obsidian_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / ".trash").mkdir()
            (vault_path / ".trash" / "Deleted.md").write_text("#ignored", encoding="utf-8")
            (vault_path / "Kept.md").write_text("#definition", encoding="utf-8")

            tags = scan_vault_tags(vault_path)

            self.assertEqual(tags, ("definition",))

    def test_scan_cards_rejects_missing_vault(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/obsidian-to-anki-missing-vault"),
            output_path=Path("/tmp/out.tsv"),
        )

        with self.assertRaises(ExportError):
            scan_cards(options, preview_limit=0)

    def test_scan_cards_accepts_existing_vault(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "Definition.md").write_text("#definition\nA body", encoding="utf-8")
            options = ExportOptions(vault_path=vault_path, output_path=vault_path / "out.tsv")

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 1)
            self.assertEqual(len(result.cards), 1)
            self.assertEqual(result.preview_cards[0].front, "Definition")

    def test_scan_cards_matches_any_selected_target_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "Definition.md").write_text("#biology\nA body", encoding="utf-8")
            options = ExportOptions(
                vault_path=vault_path,
                output_path=vault_path / "out.tsv",
                target_tag="definition",
                additional_target_tags=("biology",),
            )

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 1)
            self.assertEqual(result.preview_cards[0].front, "Definition")

    def test_iter_markdown_note_paths_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "Definition.MD").write_text("#definition\nA body", encoding="utf-8")
            (vault_path / "Ignore.txt").write_text("not markdown", encoding="utf-8")

            paths = list(iter_markdown_note_paths(vault_path))

            self.assertEqual(paths, [vault_path / "Definition.MD"])

    def test_iter_markdown_note_paths_ignores_hidden_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / ".trash").mkdir()
            (vault_path / ".trash" / "Deleted.md").write_text("#definition\nOld body", encoding="utf-8")
            (vault_path / ".Hidden.md").write_text("#definition\nHidden body", encoding="utf-8")
            (vault_path / "Visible.md").write_text("#definition\nVisible body", encoding="utf-8")

            paths = list(iter_markdown_note_paths(vault_path))

            self.assertEqual(paths, [vault_path / "Visible.md"])

    def test_scan_cards_accepts_utf8_bom_frontmatter_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "Definition.md").write_text(
                "---\ntags:\n  - definition\n---\nA body",
                encoding="utf-8-sig",
            )
            options = ExportOptions(vault_path=vault_path, output_path=vault_path / "out.tsv")

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 1)
            self.assertEqual(result.preview_cards[0].back, "A body")

    def test_scan_cards_accepts_uppercase_markdown_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "Definition.MD").write_text("#definition\nA body", encoding="utf-8")
            options = ExportOptions(vault_path=vault_path, output_path=vault_path / "out.tsv")

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 1)
            self.assertEqual(result.preview_cards[0].front, "Definition")

    def test_scan_cards_ignores_hidden_obsidian_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / ".trash").mkdir()
            (vault_path / ".trash" / "Deleted.md").write_text("#definition\nOld body", encoding="utf-8")
            (vault_path / "Definition.md").write_text("#definition\nA body", encoding="utf-8")
            options = ExportOptions(vault_path=vault_path, output_path=vault_path / "out.tsv")

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 1)
            self.assertEqual([card.front for card in result.cards], ["Definition"])

    def test_scan_cards_can_skip_duplicate_fronts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "A").mkdir(parents=True)
            (vault_path / "B").mkdir(parents=True)
            (vault_path / "A" / "Term.md").write_text("#definition\nFirst", encoding="utf-8")
            (vault_path / "B" / "Term.md").write_text("#definition\nSecond", encoding="utf-8")
            options = ExportOptions(
                vault_path=vault_path,
                output_path=vault_path / "out.tsv",
                duplicate_handling="skip",
            )

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 1)
            self.assertEqual(len(result.cards), 1)
            self.assertEqual(len(result.duplicate_fronts), 1)
            self.assertEqual(result.duplicate_resolutions, {"Term": ("Term",)})

    def test_scan_cards_can_suffix_duplicate_fronts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "A").mkdir(parents=True)
            (vault_path / "B").mkdir(parents=True)
            (vault_path / "A" / "Term.md").write_text("#definition\nFirst", encoding="utf-8")
            (vault_path / "B" / "Term.md").write_text("#definition\nSecond", encoding="utf-8")
            options = ExportOptions(
                vault_path=vault_path,
                output_path=vault_path / "out.tsv",
                duplicate_handling="suffix",
            )

            result = scan_cards(options, preview_limit=10)

            self.assertEqual(result.total_matches, 2)
            self.assertEqual(
                [card.front for card in result.cards],
                ["Term (A)", "Term (B)"],
            )
            self.assertEqual(
                result.duplicate_resolutions,
                {"Term": ("Term (A)", "Term (B)")},
            )

    def test_scan_cards_can_error_on_duplicate_fronts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / "A").mkdir(parents=True)
            (vault_path / "B").mkdir(parents=True)
            (vault_path / "A" / "Term.md").write_text("#definition\nFirst", encoding="utf-8")
            (vault_path / "B" / "Term.md").write_text("#definition\nSecond", encoding="utf-8")
            options = ExportOptions(
                vault_path=vault_path,
                output_path=vault_path / "out.tsv",
                duplicate_handling="error",
            )

            with self.assertRaises(ExportError) as context:
                scan_cards(options, preview_limit=10)

        self.assertIn("Detected 1 duplicate card fronts", str(context.exception))

    def test_run_export_uses_pre_scanned_cards_without_vault_still_existing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as output_dir:
            vault_path = Path(temp_dir)
            note_path = vault_path / "Definition.md"
            note_path.write_text("#definition\nOriginal body", encoding="utf-8")
            output_path = Path(output_dir) / "out.tsv"
            options = ExportOptions(vault_path=vault_path, output_path=output_path)

            result = scan_cards(options, preview_limit=10)
            note_path.unlink()
            vault_path.rmdir()

            count = run_export(options, result.cards)

            self.assertEqual(count, 1)
            content = output_path.read_text(encoding="utf-8-sig")
            self.assertIn("Definition\tOriginal body\tdefinition", content)
