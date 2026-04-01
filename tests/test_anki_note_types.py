import unittest
from unittest import mock

from obsidian_to_anki.anki.connect_client import AnkiConnectError
from obsidian_to_anki.anki.note_types import (
    OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME,
    install_obsidian_definitions_note_type,
)


class AnkiNoteTypeInstallerTests(unittest.TestCase):
    def test_install_obsidian_definitions_note_type_creates_model_when_missing(self) -> None:
        invoke = mock.Mock(side_effect=[6, [], None])

        result = install_obsidian_definitions_note_type(
            "http://127.0.0.1:8765",
            invoke_anki_connect_fn=invoke,
        )

        self.assertTrue(result.created)
        self.assertEqual(result.note_type_name, OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME)
        self.assertEqual(invoke.call_args_list[2].args[1], "createModel")
        params = invoke.call_args_list[2].args[2]
        self.assertEqual(params["modelName"], OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME)
        self.assertEqual(params["inOrderFields"], ["Front", "Back"])
        self.assertEqual(len(params["cardTemplates"]), 2)

    def test_install_obsidian_definitions_note_type_updates_existing_model(self) -> None:
        invoke = mock.Mock(
            side_effect=[
                6,
                [OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME],
                ["Front", "Back"],
                {"Word to Definition": {"Front": "old", "Back": "old"}},
                None,
                None,
                None,
            ]
        )

        result = install_obsidian_definitions_note_type(
            "http://127.0.0.1:8765",
            invoke_anki_connect_fn=invoke,
        )

        self.assertFalse(result.created)
        self.assertEqual(invoke.call_args_list[4].args[1], "modelTemplateAdd")
        self.assertEqual(invoke.call_args_list[5].args[1], "updateModelTemplates")
        self.assertEqual(invoke.call_args_list[6].args[1], "updateModelStyling")

    def test_install_obsidian_definitions_note_type_rejects_conflicting_existing_fields(self) -> None:
        invoke = mock.Mock(
            side_effect=[
                6,
                [OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME],
                ["Word", "Meaning"],
            ]
        )

        with self.assertRaises(AnkiConnectError) as context:
            install_obsidian_definitions_note_type(
                "http://127.0.0.1:8765",
                invoke_anki_connect_fn=invoke,
            )

        self.assertEqual(
            str(context.exception),
            "The existing Anki note type 'Term & Definition (Obsidian)' doesn't use the required Front and Back fields. Rename or remove it in Anki, then try the installer again.",
        )


if __name__ == "__main__":
    unittest.main()
