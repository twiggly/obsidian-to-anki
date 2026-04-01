import unittest

from obsidian_to_anki import cli
from obsidian_to_anki.html_render import markdownish_to_html
from obsidian_to_anki.note_parser import extract_tags
from obsidian_to_anki.scanner_engine import scan_cards
import main


class MainCompatibilityTests(unittest.TestCase):
    def test_main_reexports_cli_entrypoints(self) -> None:
        self.assertIs(main.main, cli.main)
        self.assertIs(main.parse_args, cli.parse_args)

    def test_main_reexports_core_helpers(self) -> None:
        self.assertIs(main.markdownish_to_html, markdownish_to_html)
        self.assertIs(main.extract_tags, extract_tags)
        self.assertIs(main.scan_cards, scan_cards)
