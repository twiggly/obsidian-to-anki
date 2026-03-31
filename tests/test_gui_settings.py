import tempfile
import unittest
from pathlib import Path

from obsidian_to_anki.gui.settings import load_gui_settings, save_gui_settings


class GuiSettingsTests(unittest.TestCase):
    def test_save_and_load_gui_settings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            settings = {
                "vault": "/tmp/vault",
                "output": "/tmp/out.tsv",
                "write_tsv": True,
                "tag": "definition",
                "tags": ["definition", "fallacy"],
                "html_output": True,
                "skip_empty": True,
                "italicize_quoted_text": False,
                "duplicate_handling": "suffix",
                "include_folders": ["Lexicon"],
                "sync_to_anki": True,
                "anki_connect_url": "http://127.0.0.1:8765",
                "anki_deck": "Lexicon",
                "anki_note_type": "Basic",
                "anki_front_field": "Front",
                "anki_back_field": "Back",
                "anki_existing_notes": "update",
            }

            save_gui_settings(settings, settings_path)
            loaded_settings = load_gui_settings(settings_path)

            self.assertEqual(loaded_settings, settings)

    def test_load_gui_settings_ignores_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            settings_path.write_text(
                '{"vault": 3, "include_folders": ["Lexicon", 2], "sync_to_anki": true}',
                encoding="utf-8",
            )

            loaded_settings = load_gui_settings(settings_path)

            self.assertEqual(loaded_settings, {"sync_to_anki": True})
