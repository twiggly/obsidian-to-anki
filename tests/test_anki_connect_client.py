import unittest
from unittest import mock
from urllib import error

from obsidian_to_anki.anki import connect_client as anki_connect_client
from obsidian_to_anki.anki.connect_client import (
    AnkiConnectError,
    format_anki_error,
    invoke_anki_connect,
    invoke_anki_connect_multi,
    is_duplicate_note_error,
    normalize_anki_connect_url,
)


class AnkiConnectClientTests(unittest.TestCase):
    def test_invoke_anki_connect_wraps_connection_errors(self) -> None:
        with mock.patch.object(anki_connect_client.request, "urlopen", side_effect=error.URLError("refused")):
            with self.assertRaises(AnkiConnectError) as context:
                invoke_anki_connect("http://127.0.0.1:8765", "deckNames")

        self.assertIn("Couldn't reach AnkiConnect", str(context.exception))
        self.assertIn("Open Anki", str(context.exception))

    def test_invoke_anki_connect_multi_returns_empty_list_for_no_actions(self) -> None:
        self.assertEqual(invoke_anki_connect_multi("http://127.0.0.1:8765", []), [])

    def test_invoke_anki_connect_multi_validates_result_length(self) -> None:
        with mock.patch.object(anki_connect_client, "invoke_anki_connect", return_value=[1]):
            with self.assertRaises(AnkiConnectError) as context:
                invoke_anki_connect_multi(
                    "http://127.0.0.1:8765",
                    [{"action": "deckNames"}, {"action": "modelNames"}],
                )

        self.assertEqual(
            str(context.exception),
            "AnkiConnect returned an unexpected response while running 'multi'.",
        )

    def test_duplicate_note_error_helper_handles_lists(self) -> None:
        self.assertTrue(
            is_duplicate_note_error(
                [
                    "cannot create note because it is a duplicate",
                    "Cannot create note because it is a duplicate",
                ]
            )
        )
        self.assertFalse(is_duplicate_note_error(["cannot create note because it is a duplicate", "other"]))

    def test_format_and_normalize_helpers(self) -> None:
        self.assertEqual(format_anki_error(["one", "two"]), "one; two")
        self.assertEqual(normalize_anki_connect_url(" http://127.0.0.1:8765/ "), "http://127.0.0.1:8765")


if __name__ == "__main__":
    unittest.main()
