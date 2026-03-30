import unittest
from pathlib import Path

from gui_preview import build_preview_info_text, close_dialog_and_run_action
from models import ExportOptions, NoteCard, ScanResult


def build_scan_result(
    *,
    total_matches: int = 1,
    duplicate_fronts: dict[str, tuple[Path, ...]] | None = None,
) -> ScanResult:
    card = NoteCard(
        front="Definition",
        back="Body",
        tags=["definition"],
        source_path=Path("/tmp/Definition.md"),
    )
    return ScanResult(
        cards=[card],
        preview_cards=[card],
        total_matches=total_matches,
        duplicate_fronts=duplicate_fronts or {},
    )


class FakeDialog:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class GuiPreviewTests(unittest.TestCase):
    def test_build_preview_info_text_includes_folders_and_duplicate_count(self) -> None:
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            include_folders=("Lexicon", "Study"),
            sync_to_anki=True,
            anki_deck="Lexicon",
            anki_note_type="Basic",
        )
        scan_result = build_scan_result(
            total_matches=3,
            duplicate_fronts={"Definition": (Path("/tmp/A.md"), Path("/tmp/B.md"))},
        )

        info_text = build_preview_info_text(options, scan_result)

        self.assertIn("Showing the first 1 of 3 matching cards", info_text)
        self.assertIn("Included folders: Lexicon, Study", info_text)
        self.assertIn("Anki target: Lexicon / Basic.", info_text)
        self.assertIn("Duplicate fronts: 1.", info_text)

    def test_build_preview_info_text_omits_optional_sections_when_unused(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        scan_result = build_scan_result(total_matches=1)

        info_text = build_preview_info_text(options, scan_result)

        self.assertEqual(
            info_text,
            "Showing the first 1 of 1 matching cards for #definition.",
        )

    def test_close_dialog_and_run_action_destroys_dialog_and_calls_action(self) -> None:
        dialog = FakeDialog()
        calls: list[str] = []

        close_dialog_and_run_action(dialog, lambda: calls.append("run"))

        self.assertTrue(dialog.destroyed)
        self.assertEqual(calls, ["run"])
