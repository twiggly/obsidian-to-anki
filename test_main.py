import unittest

import cli
import main
import rendering
import scanner


class MainCompatibilityTests(unittest.TestCase):
    def test_main_reexports_cli_entrypoints(self) -> None:
        self.assertIs(main.main, cli.main)
        self.assertIs(main.parse_args, cli.parse_args)

    def test_main_reexports_core_helpers(self) -> None:
        self.assertIs(main.markdownish_to_html, rendering.markdownish_to_html)
        self.assertIs(main.extract_tags, scanner.extract_tags)
        self.assertIs(main.scan_cards, scanner.scan_cards)
