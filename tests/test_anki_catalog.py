import unittest
from pathlib import Path
from unittest import mock

from obsidian_to_anki.anki.catalog import fetch_anki_catalog, fetch_note_type_fields, validate_anki_target
from obsidian_to_anki.anki.connect_client import AnkiConnectError
from obsidian_to_anki.models import ExportOptions


def build_options() -> ExportOptions:
    return ExportOptions(
        vault_path=Path("/tmp/vault"),
        sync_to_anki=True,
        anki_connect_url="http://127.0.0.1:8765",
        anki_deck="Lexicon",
        anki_note_type="Basic",
        anki_front_field="Front",
        anki_back_field="Back",
    )


class AnkiCatalogTests(unittest.TestCase):
    def test_fetch_anki_catalog_sorts_results(self) -> None:
        invoke = mock.Mock(side_effect=[5, ["lexicon", "Default"], ["basic", "Cloze"]])

        catalog = fetch_anki_catalog("http://127.0.0.1:8765", invoke_anki_connect_fn=invoke)

        self.assertEqual(catalog.deck_names, ("Default", "lexicon"))
        self.assertEqual(catalog.note_type_names, ("basic", "Cloze"))

    def test_fetch_note_type_fields_returns_field_catalog(self) -> None:
        invoke = mock.Mock(return_value=["Front", "Back", "Extra"])

        field_catalog = fetch_note_type_fields(
            "http://127.0.0.1:8765",
            "Basic",
            invoke_anki_connect_fn=invoke,
        )

        self.assertEqual(field_catalog.note_type_name, "Basic")
        self.assertEqual(field_catalog.field_names, ("Front", "Back", "Extra"))

    def test_validate_anki_target_raises_for_missing_fields(self) -> None:
        invoke = mock.Mock(side_effect=[5, ["Lexicon"], ["Basic"]])
        fetch_fields = mock.Mock(return_value=mock.Mock(field_names=("Front",)))

        with self.assertRaises(AnkiConnectError) as context:
            validate_anki_target(
                build_options(),
                invoke_anki_connect_fn=invoke,
                fetch_note_type_fields_fn=fetch_fields,
            )

        self.assertIn("Missing Anki field", str(context.exception))


if __name__ == "__main__":
    unittest.main()
