import unittest
from unittest import mock

from obsidian_to_anki.anki.connect_client import AnkiConnectError
from obsidian_to_anki.anki.deck_settings import apply_recommended_deck_settings


class AnkiDeckSettingsTests(unittest.TestCase):
    def test_apply_recommended_deck_settings_creates_and_assigns_preset(self) -> None:
        invoke = mock.Mock(
            side_effect=[
                {
                    "id": 1,
                    "name": "Default",
                    "newGatherPriority": 0,
                    "newSortOrder": 0,
                    "reviewOrder": 0,
                    "new": {"perDay": 20, "delays": [1, 10], "bury": False, "ints": [1, 4, 7]},
                    "rev": {"perDay": 100, "bury": False},
                    "lapse": {"delays": [10]},
                },
                99,
                True,
                True,
            ]
        )

        result = apply_recommended_deck_settings(
            "http://127.0.0.1:8765",
            "Obsidian",
            invoke_anki_connect_fn=invoke,
        )

        self.assertTrue(result.created)
        self.assertEqual(result.deck_name, "Obsidian")
        self.assertEqual(result.preset_name, "Term & Definition (Obsidian) - Obsidian")
        self.assertEqual(invoke.call_args_list[1].args[1], "cloneDeckConfigId")
        saved_config = invoke.call_args_list[2].args[2]["config"]
        self.assertEqual(saved_config["id"], 99)
        self.assertEqual(saved_config["name"], "Term & Definition (Obsidian) - Obsidian")
        self.assertEqual(saved_config["newGatherPriority"], 4)
        self.assertEqual(saved_config["newSortOrder"], 2)
        self.assertEqual(saved_config["reviewOrder"], 0)
        self.assertEqual(saved_config["new"]["perDay"], 10)
        self.assertEqual(saved_config["new"]["delays"], [1, 10])
        self.assertTrue(saved_config["new"]["bury"])
        self.assertEqual(saved_config["new"]["ints"][:2], [1, 4])
        self.assertEqual(saved_config["rev"]["perDay"], 200)
        self.assertTrue(saved_config["rev"]["bury"])
        self.assertEqual(saved_config["lapse"]["delays"], [10])
        self.assertEqual(invoke.call_args_list[3].args[1], "setDeckConfigId")

    def test_apply_recommended_deck_settings_updates_existing_recommended_preset(self) -> None:
        invoke = mock.Mock(
            side_effect=[
                {
                    "id": 99,
                    "name": "Term & Definition (Obsidian) - Obsidian",
                    "newGatherPriority": 0,
                    "newSortOrder": 0,
                    "reviewOrder": 0,
                    "new": {"perDay": 20, "delays": [1, 10], "bury": False, "ints": [1, 4, 7]},
                    "rev": {"perDay": 100, "bury": False},
                    "lapse": {"delays": [10]},
                },
                True,
                True,
            ]
        )

        result = apply_recommended_deck_settings(
            "http://127.0.0.1:8765",
            "Obsidian",
            invoke_anki_connect_fn=invoke,
        )

        self.assertFalse(result.created)
        self.assertEqual(invoke.call_args_list[1].args[1], "saveDeckConfig")
        self.assertEqual(invoke.call_args_list[2].args[1], "setDeckConfigId")

    def test_apply_recommended_deck_settings_requires_deck_name(self) -> None:
        with self.assertRaises(AnkiConnectError) as context:
            apply_recommended_deck_settings(
                "http://127.0.0.1:8765",
                "   ",
                invoke_anki_connect_fn=mock.Mock(),
            )

        self.assertEqual(
            str(context.exception),
            "Choose an Anki deck before applying the recommended deck settings.",
        )

    def test_apply_recommended_deck_settings_rejects_missing_deck(self) -> None:
        invoke = mock.Mock(side_effect=[False])

        with self.assertRaises(AnkiConnectError) as context:
            apply_recommended_deck_settings(
                "http://127.0.0.1:8765",
                "Obsidian",
                invoke_anki_connect_fn=invoke,
            )

        self.assertEqual(
            str(context.exception),
            "Anki couldn't load the current deck settings for 'Obsidian'. Try again in Anki and make sure the deck still exists.",
        )


if __name__ == "__main__":
    unittest.main()
