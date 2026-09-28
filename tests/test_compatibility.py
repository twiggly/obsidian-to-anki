import importlib
import unittest


class CompatibilityTests(unittest.TestCase):
    def test_legacy_subpackage_facades_reexport_current_implementations(self) -> None:
        modules = {
            "anki_catalog": "anki.catalog",
            "anki_connect_client": "anki.connect_client",
            "anki_existing_notes": "anki.existing_notes",
            "anki_sync": "anki.sync",
            "anki_sync_engine": "anki.sync_engine",
            "gui_anki_controller": "gui.anki_controller",
            "gui_delivery_controller": "gui.delivery_controller",
            "gui_logic": "gui.logic",
            "gui_preview": "gui.preview",
            "gui_sections": "gui.sections",
            "gui_selection_controller": "gui.selection_controller",
            "gui_settings": "gui.settings",
            "gui_state": "gui.state",
            "gui_tasks": "gui.tasks",
            "gui_view": "gui.view",
            "gui_widgets": "gui.widgets",
        }
        for legacy_name, current_name in modules.items():
            legacy = importlib.import_module(f"obsidian_to_anki.{legacy_name}")
            current = importlib.import_module(f"obsidian_to_anki.{current_name}")
            exports = getattr(
                current, "__all__", [name for name in vars(current) if not name.startswith("_")]
            )
            for name in exports:
                with self.subTest(module=legacy_name, name=name):
                    self.assertIs(getattr(legacy, name), getattr(current, name))

    def test_shared_reporting_keeps_gui_import_paths(self) -> None:
        from obsidian_to_anki import reporting
        from obsidian_to_anki.gui import logic

        for name in ("delivery_complete_message", "format_seconds", "timing_breakdown_lines"):
            with self.subTest(name=name):
                self.assertIs(getattr(logic, name), getattr(reporting, name))

    def test_entrypoint_and_scanning_rendering_facades_remain_available(self) -> None:
        from obsidian_to_anki import cli, rendering, scanner
        from obsidian_to_anki.body_cleanup import clean_body
        from obsidian_to_anki.gui import ExporterApp, append_folder_filter
        from obsidian_to_anki.scanner_engine import scan_cards

        self.assertIs(importlib.import_module("main").main, cli.main)
        self.assertIs(scanner.scan_cards, scan_cards)
        self.assertIs(rendering.clean_body, clean_body)
        self.assertIs(importlib.import_module("obsidian_to_anki.main").ExporterApp, ExporterApp)
        self.assertEqual(append_folder_filter([], "Study"), ["Study"])
