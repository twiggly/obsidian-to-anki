import unittest
from pathlib import Path

from obsidian_to_anki.models import AnkiSyncResult, DeliveryResult, ExportOptions, NoteCard, ScanResult
from obsidian_to_anki.reporting import attach_delivery_report, build_delivery_report


def build_scan_result(vault_path: Path) -> ScanResult:
    card = NoteCard(
        front="Term",
        back="Body",
        tags=["definition"],
        source_path=vault_path / "A" / "Term.md",
    )
    return ScanResult(
        cards=[card],
        preview_cards=[card],
        total_matches=1,
        duplicate_fronts={"Term": (vault_path / "A" / "Term.md", vault_path / "B" / "Term.md")},
        duplicate_resolutions={"Term": ("Term (A)", "Term (B)")},
    )


class ReportingTests(unittest.TestCase):
    def test_build_delivery_report_includes_duplicates_and_sync_changes(self) -> None:
        scan_result = build_scan_result(Path("/tmp/vault"))
        delivery_result = DeliveryResult(
            sync_result=AnkiSyncResult(
                added_count=1,
                skipped_count=1,
                updated_count=1,
                deck_name="Lexicon",
                note_type="Basic",
                skipped_fronts=("Term",),
                updated_fronts=("Word",),
            )
        )

        report = build_delivery_report(
            ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv")),
            scan_result,
            delivery_result,
        )

        self.assertIsNotNone(report)
        self.assertIn("Duplicate fronts detected:", report or "")
        self.assertIn("resolved as: Term (A), Term (B)", report or "")
        self.assertIn("Existing Anki notes skipped:", report or "")
        self.assertIn("Existing Anki notes updated:", report or "")

    def test_attach_delivery_report_attaches_report_text(self) -> None:
        vault_path = Path("/tmp/vault")
        scan_result = build_scan_result(vault_path)
        options = ExportOptions(vault_path=vault_path, output_path=Path("/tmp/out.tsv"))

        delivery_result = attach_delivery_report(options, scan_result, DeliveryResult())

        self.assertIsNotNone(delivery_result.report_text)
        self.assertIn("Duplicate fronts detected:", delivery_result.report_text or "")
