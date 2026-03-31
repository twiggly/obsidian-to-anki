import unittest
from pathlib import Path

from obsidian_to_anki.common import unexpected_error_message
from obsidian_to_anki.gui.tasks import (
    run_anki_catalog_callbacks,
    run_anki_field_catalog_callbacks,
    run_delivery_callbacks,
    run_preview_scan_callbacks,
    run_tag_catalog_callbacks,
)
from obsidian_to_anki.models import (
    AnkiCatalog,
    AnkiFieldCatalog,
    DeliveryResult,
    ExportError,
    ExportOptions,
    NoteCard,
    ScanResult,
)


def build_scan_result() -> ScanResult:
    card = NoteCard(
        front="Definition",
        back="Body",
        tags=["definition"],
        source_path=Path("/tmp/Definition.md"),
    )
    return ScanResult(
        cards=[card],
        preview_cards=[card],
        total_matches=1,
        duplicate_fronts={"Definition": (Path("/tmp/A.md"), Path("/tmp/B.md"))},
    )


class GuiTaskTests(unittest.TestCase):
    def test_run_tag_catalog_callbacks_routes_success(self) -> None:
        calls: list[tuple[str, object, object | None]] = []

        run_tag_catalog_callbacks(
            Path("/tmp/vault"),
            ("Study",),
            lambda tag_names: calls.append(("success", tag_names, None)),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            scan_fn=lambda vault_path, include_folders: ("biology", "definition"),
        )

        self.assertEqual(calls, [("success", ("biology", "definition"), None)])

    def test_run_tag_catalog_callbacks_routes_export_errors(self) -> None:
        calls: list[tuple[str, str, str | None]] = []

        def fail_scan(_: Path, __: tuple[str, ...]) -> tuple[str, ...]:
            raise ExportError("Invalid vault")

        run_tag_catalog_callbacks(
            Path("/tmp/vault"),
            (),
            lambda tag_names: calls.append(("success", str(tag_names), None)),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            scan_fn=fail_scan,
        )

        self.assertEqual(calls, [("error", "Invalid vault", None)])

    def test_run_anki_catalog_callbacks_routes_success(self) -> None:
        expected_catalog = AnkiCatalog(deck_names=("Default", "Obsidian"), note_type_names=("Basic", "Cloze"))
        calls: list[tuple[str, object, object | None]] = []

        run_anki_catalog_callbacks(
            "http://127.0.0.1:8765",
            lambda catalog: calls.append(("success", catalog, None)),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            fetch_fn=lambda url: expected_catalog,
        )

        self.assertEqual(calls, [("success", expected_catalog, None)])

    def test_run_anki_catalog_callbacks_routes_export_errors(self) -> None:
        calls: list[tuple[str, str, str | None]] = []

        def fail_fetch(_: str) -> AnkiCatalog:
            raise ExportError("Anki unavailable")

        run_anki_catalog_callbacks(
            "http://127.0.0.1:8765",
            lambda catalog: calls.append(("success", str(catalog), None)),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            fetch_fn=fail_fetch,
        )

        self.assertEqual(calls, [("error", "Anki unavailable", None)])

    def test_run_anki_field_catalog_callbacks_routes_success(self) -> None:
        expected_catalog = AnkiFieldCatalog(note_type_name="Basic", field_names=("Front", "Back"))
        calls: list[tuple[str, object, object | None]] = []

        run_anki_field_catalog_callbacks(
            "http://127.0.0.1:8765",
            "Basic",
            lambda catalog: calls.append(("success", catalog, None)),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            fetch_fn=lambda url, note_type: expected_catalog,
        )

        self.assertEqual(calls, [("success", expected_catalog, None)])

    def test_run_preview_scan_callbacks_routes_success(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        expected_result = build_scan_result()
        calls: list[tuple[str, object, object | None]] = []

        run_preview_scan_callbacks(
            options,
            lambda completed_options, scan_result: calls.append(("success", completed_options, scan_result)),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            scan_fn=lambda received_options, preview_limit: expected_result,
        )

        self.assertEqual(calls, [("success", options, expected_result)])

    def test_run_preview_scan_callbacks_routes_export_errors(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        calls: list[tuple[str, str, str | None]] = []

        def fail_scan(_: ExportOptions, __: int) -> ScanResult:
            raise ExportError("Invalid vault")

        run_preview_scan_callbacks(
            options,
            lambda completed_options, scan_result: calls.append(("success", str(completed_options), str(scan_result))),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            scan_fn=fail_scan,
        )

        self.assertEqual(calls, [("error", "Invalid vault", None)])

    def test_run_preview_scan_callbacks_routes_unexpected_errors_with_traceback(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        calls: list[tuple[str, str, str | None]] = []

        def fail_scan(_: ExportOptions, __: int) -> ScanResult:
            raise RuntimeError("boom")

        run_preview_scan_callbacks(
            options,
            lambda completed_options, scan_result: calls.append(("success", str(completed_options), str(scan_result))),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            scan_fn=fail_scan,
        )

        self.assertEqual(calls[0][0], "error")
        self.assertEqual(calls[0][1], unexpected_error_message("preview"))
        details = calls[0][2]
        self.assertIsNotNone(details)
        self.assertIn("RuntimeError: boom", details or "")

    def test_run_delivery_callbacks_routes_success(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        scan_result = build_scan_result()
        expected_result = DeliveryResult(export_count=3, output_path=options.output_path)
        calls: list[tuple[str, object, object, object]] = []

        run_delivery_callbacks(
            options,
            scan_result,
            lambda completed_options, completed_scan_result, delivery_result: calls.append(
                ("success", completed_options, completed_scan_result, delivery_result)
            ),
            lambda error_message, details=None: calls.append(("error", error_message, details, "")),
            deliver_fn=lambda received_options, cards: expected_result,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "success")
        self.assertEqual(calls[0][1], options)
        self.assertEqual(calls[0][2], scan_result)
        returned_result = calls[0][3]
        self.assertEqual(returned_result.export_count, expected_result.export_count)
        self.assertEqual(returned_result.output_path, expected_result.output_path)
        self.assertIsNotNone(returned_result.report_text)

    def test_run_delivery_callbacks_routes_export_errors(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        scan_result = build_scan_result()
        calls: list[tuple[str, str, str | None]] = []

        def fail_delivery(_: ExportOptions, __: list[NoteCard]) -> DeliveryResult:
            raise ExportError("Disk full")

        run_delivery_callbacks(
            options,
            scan_result,
            lambda completed_options, completed_scan_result, delivery_result: calls.append(
                ("success", str(completed_options), str(completed_scan_result))
            ),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            deliver_fn=fail_delivery,
        )

        self.assertEqual(calls, [("error", "Disk full", None)])

    def test_run_delivery_callbacks_routes_unexpected_errors_with_traceback(self) -> None:
        options = ExportOptions(vault_path=Path("/tmp/vault"), output_path=Path("/tmp/out.tsv"))
        scan_result = build_scan_result()
        calls: list[tuple[str, str, str | None]] = []

        def fail_delivery(_: ExportOptions, __: list[NoteCard]) -> DeliveryResult:
            raise RuntimeError("write failed")

        run_delivery_callbacks(
            options,
            scan_result,
            lambda completed_options, completed_scan_result, delivery_result: calls.append(
                ("success", str(completed_options), str(completed_scan_result))
            ),
            lambda error_message, details=None: calls.append(("error", error_message, details)),
            deliver_fn=fail_delivery,
        )

        self.assertEqual(calls[0][0], "error")
        self.assertEqual(calls[0][1], unexpected_error_message("delivery"))
        details = calls[0][2]
        self.assertIsNotNone(details)
        self.assertIn("RuntimeError: write failed", details or "")
