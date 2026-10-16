import unittest
from types import SimpleNamespace
from unittest import mock

from obsidian_to_anki.gui import app as gui
from obsidian_to_anki.gui import bootstrap, settings, state
from obsidian_to_anki.models import ExportOptions
from tests.test_gui_controller import FakeVar, build_controller


class FakeStringVar(FakeVar):
    pass


class FakeBooleanVar(FakeVar):
    pass


def build_settings_controller():
    app = build_controller()
    bootstrap.initialize_form_variables(
        app, SimpleNamespace(StringVar=FakeStringVar, BooleanVar=FakeBooleanVar)
    )
    bootstrap.initialize_runtime_state(app)
    del app.get_selected_tags_from_listbox
    del app.get_folder_filters_from_listbox
    app.sync_output_option_state = mock.Mock()
    app.sync_html_option_state = mock.Mock()
    app.sync_anki_option_state = mock.Mock()
    return app


class GuiStateTests(unittest.TestCase):
    def test_initial_values_and_reset_share_the_original_gui_defaults(self) -> None:
        app = build_settings_controller()
        expected = {
            "vault": "",
            "output": str(settings.DEFAULT_OUTPUT_PATH),
            "write_tsv": False,
            "tag": "",
            "tags": [],
            "html_output": False,
            "skip_empty": True,
            "italicize_quoted_text": False,
            "flatten_note_links": False,
            "duplicate_handling": "error",
            "include_folders": [],
            "sync_to_anki": False,
            "anki_connect_url": "http://127.0.0.1:8765",
            "anki_deck": "Default",
            "anki_note_type": "Basic",
            "anki_front_field": "Front",
            "anki_back_field": "Back",
            "anki_existing_notes": "update",
        }
        self.assertEqual(app.collect_settings(), expected)
        self.assertEqual(set(settings.GUI_SETTINGS_KEYS), set(expected))
        for value in vars(app).values():
            if isinstance(value, FakeStringVar):
                value.set("changed")
            elif isinstance(value, FakeBooleanVar):
                value.set(not value.get())
        app.set_selected_tags_in_listbox(["tag"])
        app.set_folder_filters_in_listbox(["folder"])

        app.apply_default_settings()

        self.assertEqual(app.collect_settings(), expected)
        self.assertEqual(app.duplicate_handling_display_var.get(), "Stop")
        self.assertEqual(app.status_var.get(), bootstrap.DEFAULT_STATUS_MESSAGE)
        app.sync_output_option_state.assert_called_once_with()
        app.sync_html_option_state.assert_called_once_with()
        app.sync_anki_option_state.assert_called_once_with()
        for key, (name, default) in settings._SCALAR_SETTINGS.items():
            with self.subTest(key=key):
                expected_type = FakeBooleanVar if isinstance(default, bool) else FakeStringVar
                self.assertIsInstance(getattr(app, name), expected_type)

    def test_gui_defaults_remain_distinct_from_cli_defaults(self) -> None:
        from pathlib import Path

        options = ExportOptions(vault_path=Path("/tmp/vault"))
        app = build_settings_controller()
        self.assertEqual(options.target_tag, "definition")
        self.assertEqual(app.tag_var.get(), "")
        self.assertTrue(options.flatten_note_links)
        self.assertFalse(app.flatten_note_links_var.get())
        self.assertEqual(options.anki_existing_notes, "skip")
        self.assertEqual(app.anki_existing_notes_var.get(), "update")

    def test_default_constants_remain_available_through_bootstrap_and_app(self) -> None:
        for name in (
            "DEFAULT_OUTPUT_PATH",
            "DEFAULT_TARGET_TAG",
            "DEFAULT_ANKI_CONNECT_URL",
            "DEFAULT_ANKI_DECK",
            "DEFAULT_ANKI_NOTE_TYPE",
            "DEFAULT_ANKI_FRONT_FIELD",
            "DEFAULT_ANKI_BACK_FIELD",
            "DEFAULT_ANKI_EXISTING_NOTES",
            "DEFAULT_DUPLICATE_HANDLING",
            "DEFAULT_FLATTEN_NOTE_LINKS",
        ):
            with self.subTest(name=name):
                self.assertEqual(getattr(settings, name), getattr(bootstrap, name))
                self.assertEqual(getattr(settings, name), getattr(gui, name))

    def test_reset_helper_preserves_custom_default_arguments(self) -> None:
        app = build_settings_controller()
        state.apply_default_settings(
            app,
            default_output_path="/tmp/custom.tsv",
            default_target_tag="custom",
            default_duplicate_handling="suffix",
            default_flatten_note_links=True,
            default_anki_connect_url="http://localhost:8766",
            default_anki_deck="Study",
            default_anki_note_type="Custom",
            default_anki_front_field="Term",
            default_anki_back_field="Definition",
            default_anki_existing_notes="skip",
            default_status_message="Custom status",
        )
        saved = app.collect_settings()
        self.assertEqual(saved["output"], "/tmp/custom.tsv")
        self.assertEqual(saved["tag"], "custom")
        self.assertEqual(saved["duplicate_handling"], "suffix")
        self.assertEqual(app.duplicate_handling_display_var.get(), "Rename")
        self.assertTrue(saved["flatten_note_links"])
        self.assertEqual(saved["anki_connect_url"], "http://localhost:8766")
        self.assertEqual(saved["anki_deck"], "Study")
        self.assertEqual(saved["anki_note_type"], "Custom")
        self.assertEqual(saved["anki_front_field"], "Term")
        self.assertEqual(saved["anki_back_field"], "Definition")
        self.assertEqual(saved["anki_existing_notes"], "skip")
        self.assertEqual(app.status_var.get(), "Custom status")

    def test_saved_settings_round_trip_all_bindings(self) -> None:
        app = build_settings_controller()
        saved = {
            key: (not default if isinstance(default, bool) else f"saved-{key}")
            for key, (_, default) in settings._SCALAR_SETTINGS.items()
        }
        saved.update(
            skip_empty=True,
            duplicate_handling="skip",
            tags=["definition", "lexicon"],
            include_folders=["Study", "Drafts"],
        )
        state.apply_saved_settings(app, saved, default_duplicate_handling="error")
        self.assertEqual(app.collect_settings(), saved)
        self.assertEqual(app.duplicate_handling_display_var.get(), "Keep first")

    def test_saved_special_values_keep_the_existing_normalization_rules(self) -> None:
        app = build_settings_controller()
        state.apply_saved_settings(
            app,
            {
                "tag": "pending",
                "tags": [" lexicon ", "lexicon", "", "definition"],
                "include_folders": [" Study ", "Study", ""],
                "duplicate_handling": " SUFFIX ",
                "skip_empty": False,
            },
            default_duplicate_handling="error",
        )
        self.assertEqual(app.selected_tags, ["lexicon", "definition"])
        self.assertEqual(app.folder_filters, ["Study"])
        self.assertEqual(app.tag_var.get(), "pending")
        self.assertEqual(app.duplicate_handling_var.get(), "suffix")
        self.assertTrue(app.skip_empty_var.get())
        state.apply_saved_settings(
            app,
            {"tags": [" "], "duplicate_handling": "invalid"},
            default_duplicate_handling="error",
        )
        self.assertEqual(app.selected_tags, [])
        self.assertEqual(app.tag_var.get(), "")
        self.assertEqual(app.duplicate_handling_var.get(), "error")

    def test_invalid_persisted_values_are_ignored_before_application(self) -> None:
        app = build_settings_controller()
        saved = settings.sanitize_gui_settings(
            {"vault": 3, "html_output": "yes", "tags": [2], "anki_deck": "Study"}
        )
        state.apply_saved_settings(app, saved, default_duplicate_handling="error")
        self.assertEqual(app.vault_var.get(), "")
        self.assertFalse(app.html_var.get())
        self.assertEqual(app.selected_tags, [])
        self.assertEqual(app.anki_deck_var.get(), "Study")

    def test_unexpected_settings_validation_errors_are_not_silenced(self) -> None:
        app = build_settings_controller()
        with mock.patch.object(
            state, "normalize_duplicate_handling", side_effect=RuntimeError("bug")
        ):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                state.apply_saved_settings(app, {}, default_duplicate_handling="error")

    def test_error_presentation_preserves_messages_and_tracebacks(self) -> None:
        for details in (None, "traceback\n\n", ""):
            for show_dialog in (False, True):
                for quiet in (False, True):
                    with self.subTest(details=details, show_dialog=show_dialog, quiet=quiet):
                        app = build_settings_controller()
                        app.status_var.set("Previous status")
                        app.is_busy = True
                        dialogs = mock.Mock()
                        state.report_gui_error(
                            app,
                            "Failure",
                            details,
                            title="Test failed",
                            messagebox_module=dialogs,
                            show_error_dialog=show_dialog,
                            quiet=quiet,
                        )
                        self.assertTrue(app.is_busy)
                        if quiet:
                            self.assertEqual(app.status_var.get(), "Previous status")
                            app.log.assert_not_called()
                        else:
                            self.assertEqual(app.status_var.get(), "Failure")
                            expected = (
                                [mock.call("Error: Failure")]
                                if details is None
                                else [mock.call("Failure"), mock.call(details.rstrip())]
                            )
                            self.assertEqual(app.log.call_args_list, expected)
                        if show_dialog and not quiet:
                            dialogs.showerror.assert_called_once_with("Test failed", "Failure")
                        else:
                            dialogs.showerror.assert_not_called()

    def test_unexpected_tag_validation_failure_propagates(self) -> None:
        app = build_settings_controller()
        with (
            mock.patch.object(gui, "build_tag_scan_request", side_effect=RuntimeError("bug")),
            mock.patch.object(gui, "messagebox") as dialogs,
        ):
            with self.assertRaisesRegex(RuntimeError, "bug"):
                app.scan_vault_tags()
        self.assertFalse(app.is_busy)
        dialogs.showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
