import unittest
from contextlib import ExitStack
from unittest import mock

from obsidian_to_anki.gui import app as gui
from obsidian_to_anki.models import AnkiCatalog, AnkiFieldCatalog
from tests.test_gui_controller import build_controller


class GuiRefreshTests(unittest.TestCase):
    def setUp(self) -> None:
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.app = build_controller()
        self.app.sync_to_anki_var.set(True)
        self.starters = {
            kind: stack.enter_context(mock.patch.object(gui, name))
            for kind, name in (
                ("connection", "start_anki_connection_check"),
                ("catalog", "start_anki_catalog_refresh"),
                ("fields", "start_anki_field_catalog_refresh"),
            )
        }
        self.dialogs = stack.enter_context(mock.patch.object(gui, "messagebox"))
        stack.enter_context(mock.patch.object(gui, "delete_gui_settings"))
        self.app.save_settings = mock.Mock()

    def start_request(self, kind: str) -> tuple:
        {
            "connection": self.app.refresh_anki_connection,
            "catalog": self.app.refresh_anki_catalog,
            "fields": self.app.refresh_anki_fields,
        }[kind]()
        return self.starters[kind].call_args.args[-2:]

    def complete(self, kind: str, callbacks: tuple, outcome: str = "success") -> None:
        if outcome == "error":
            callbacks[1]("Anki unavailable", "traceback\n")
        elif kind == "connection":
            callbacks[0]()
        elif kind == "catalog":
            callbacks[0](AnkiCatalog(("Default", "Latest"), ("Basic", "New type")))
        else:
            callbacks[0](AnkiFieldCatalog("Basic", ("Front", "Back")))

    def snapshot(self) -> tuple:
        app = self.app
        return (
            app.status_var.get(),
            app.anki_connection_var.get(),
            app.anki_deck_var.get(),
            app.anki_note_type_var.get(),
            app.anki_deck_combobox.values,
            app.anki_note_type_combobox.values,
            app.anki_front_field_combobox.values,
            app.anki_back_field_combobox.values,
            app._last_loaded_anki_url,
            app._last_loaded_anki_note_type,
            app._pending_anki_catalog_url,
            app._pending_anki_field_key,
            app._anki_catalog_loading,
            app._anki_connection_check_loading,
            app._anki_field_loading,
            dict(app._anki_refresh_requests),
            list(app.log.mock_calls),
            list(self.dialogs.mock_calls),
            {kind: list(starter.mock_calls) for kind, starter in self.starters.items()},
        )

    def test_disabling_sync_discards_every_success_and_error(self) -> None:
        for kind in self.starters:
            with self.subTest(kind=kind):
                self.app.sync_to_anki_var.set(True)
                callbacks = self.start_request(kind)
                self.app.sync_to_anki_var.set(False)
                self.app.sync_anki_option_state()
                before = self.snapshot()
                self.complete(kind, callbacks)
                self.complete(kind, callbacks, "error")
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.app.anki_connection_var.get(), "Sync off")
                self.assertEqual(self.app._anki_refresh_requests, {})

    def test_reenabling_sync_does_not_revive_old_requests(self) -> None:
        for kind in self.starters:
            with self.subTest(kind=kind):
                self.app.sync_to_anki_var.set(False)
                self.app.sync_anki_option_state()
                self.app.sync_to_anki_var.set(True)
                old = self.start_request(kind)
                self.app.sync_to_anki_var.set(False)
                self.app.sync_anki_option_state()
                self.app.sync_to_anki_var.set(True)
                self.app.sync_anki_option_state()
                catalog = self.starters["catalog"].call_args.args[-2:]
                before = self.snapshot()
                self.complete(kind, old)
                self.complete(kind, old, "error")
                self.assertEqual(self.snapshot(), before)
                self.assertTrue(self.app._anki_catalog_loading)
                self.complete("catalog", catalog)
                self.assertEqual(self.app.anki_connection_var.get(), "Connected")
                self.assertIn("Latest", self.app.anki_deck_combobox.values)

    def test_url_changes_invalidate_all_old_targets_including_a_b_a(self) -> None:
        old_connection = self.start_request("connection")
        old_fields = self.start_request("fields")
        old_catalog = self.start_request("catalog")
        self.app.anki_connect_url_var.set("http://localhost:8766")
        self.app.on_anki_connect_url_change()
        middle_catalog = self.starters["catalog"].call_args.args[-2:]
        self.app.anki_connect_url_var.set("http://127.0.0.1:8765")
        self.app.on_anki_connect_url_change()
        latest_catalog = self.starters["catalog"].call_args.args[-2:]
        before = self.snapshot()
        for kind, callbacks in (
            ("connection", old_connection),
            ("fields", old_fields),
            ("catalog", old_catalog),
            ("catalog", middle_catalog),
        ):
            self.complete(kind, callbacks)
            self.complete(kind, callbacks, "error")
            self.assertEqual(self.snapshot(), before)
        self.complete("catalog", latest_catalog)
        self.assertEqual(self.app._last_loaded_anki_url, "http://127.0.0.1:8765")
        self.assertFalse(self.app._anki_catalog_loading)
        self.assertIn("Latest", self.app.anki_deck_combobox.values)

    def test_note_type_changes_only_replace_field_requests(self) -> None:
        catalog = self.start_request("catalog")
        old = self.start_request("fields")
        self.app.anki_note_type_var.set("New type")
        self.app.on_anki_note_type_change()
        middle = self.starters["fields"].call_args.args[-2:]
        self.app.anki_note_type_var.set("Basic")
        self.app.on_anki_note_type_change()
        latest = self.starters["fields"].call_args.args[-2:]
        before = self.snapshot()
        for callbacks in (old, middle):
            self.complete("fields", callbacks)
            self.complete("fields", callbacks, "error")
            self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.app._anki_catalog_loading)
        self.complete("fields", latest)
        self.assertFalse(self.app._anki_field_loading)
        self.assertEqual(self.app._last_loaded_anki_note_type, "Basic")
        self.assertEqual(self.app.anki_front_field_combobox.values, ("Front", "Back"))
        self.complete("catalog", catalog)
        self.assertEqual(self.app.anki_connection_var.get(), "Connected")

    def test_blank_note_type_discards_old_fields_and_allows_next_selection(self) -> None:
        old = self.start_request("fields")
        self.app.anki_note_type_var.set("")
        self.app.on_anki_note_type_change()
        before = self.snapshot()
        self.complete("fields", old)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.app._anki_field_loading)
        self.app.anki_note_type_var.set("New type")
        self.app.on_anki_note_type_change()
        self.assertTrue(self.app._anki_field_loading)
        self.assertEqual(self.starters["fields"].call_args.args[2], "New type")

    def test_reset_and_close_invalidate_pending_completions(self) -> None:
        for action in ("reset_settings", "close"):
            with self.subTest(action=action):
                self.app._closing = False
                self.app.sync_to_anki_var.set(True)
                callbacks = self.start_request("catalog")
                fields = self.start_request("fields")
                getattr(self.app, action)()
                before = self.snapshot()
                for kind, pending in (("catalog", callbacks), ("fields", fields)):
                    self.complete(kind, pending)
                    self.complete(kind, pending, "error")
                    self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.app._anki_refresh_requests, {})
        self.assertTrue(self.app.root.destroyed)

    def test_catalog_supersedes_connection_probe(self) -> None:
        for outcome in ("success", "error"):
            with self.subTest(outcome=outcome):
                old = self.start_request("connection")
                catalog = self.start_request("catalog")
                self.complete("catalog", catalog, outcome)
                before = self.snapshot()
                self.complete("connection", old)
                self.complete("connection", old, "error")
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(self.app._anki_connection_check_loading)

    def test_current_connection_failure_discards_inflight_fields(self) -> None:
        fields = self.start_request("fields")
        connection = self.start_request("connection")
        self.complete("connection", connection, "error")
        before = self.snapshot()
        self.complete("fields", fields)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.app.anki_connection_var.get(), "Connection failed")
        latest = self.start_request("catalog")
        self.complete("catalog", latest)
        self.assertEqual(self.app.anki_connection_var.get(), "Connected")

    def test_repeated_requests_for_same_target_are_coalesced(self) -> None:
        for kind in self.starters:
            with self.subTest(kind=kind):
                self.app.sync_to_anki_var.set(False)
                self.app.sync_anki_option_state()
                self.app.sync_to_anki_var.set(True)
                self.starters[kind].reset_mock()
                self.start_request(kind)
                self.app.anki_connect_url_var.set(" http://127.0.0.1:8765/ ")
                self.start_request(kind)
                self.start_request(kind)
                self.starters[kind].assert_called_once()

    def test_callbacks_are_consumed_once(self) -> None:
        callbacks = self.start_request("catalog")
        self.complete("catalog", callbacks)
        before = self.snapshot()
        self.complete("catalog", callbacks)
        self.complete("catalog", callbacks, "error")
        self.assertEqual(self.snapshot(), before)

    def test_completion_checks_current_selection_even_without_change_event(self) -> None:
        old = self.start_request("fields")
        self.app.anki_note_type_var.set("New type")
        previous_status = self.app.status_var.get()
        previous_log = list(self.app.log.mock_calls)
        self.complete("fields", old)
        self.assertEqual(self.app.anki_front_field_combobox.values, ())
        self.assertEqual(self.app.status_var.get(), previous_status)
        self.assertEqual(self.app.log.mock_calls, previous_log)
        self.assertFalse(self.app._anki_field_loading)
        self.app.on_anki_note_type_change()
        self.assertTrue(self.app._anki_field_loading)

    def test_busy_disabled_and_closed_apps_do_not_start_requests(self) -> None:
        for attribute in ("is_busy", "_closing", "sync_to_anki_var"):
            with self.subTest(state=attribute):
                self.app.is_busy = attribute == "is_busy"
                self.app._closing = attribute == "_closing"
                self.app.sync_to_anki_var.set(attribute != "sync_to_anki_var")
                self.app.anki_connect_url_var.set("")
                self.app.refresh_anki_catalog()
                self.app.refresh_anki_connection()
                self.app.refresh_anki_fields()
                for starter in self.starters.values():
                    starter.assert_not_called()
                self.dialogs.showerror.assert_not_called()

    def test_quiet_current_failure_still_releases_loading_without_dialogs(self) -> None:
        self.app.status_var.set("Previous status")
        self.app.refresh_anki_catalog(show_error_dialog=True, quiet=True)
        pending = self.starters["catalog"].call_args.args[-2:]
        self.complete("catalog", pending, "error")
        self.assertFalse(self.app._anki_catalog_loading)
        self.assertEqual(self.app.anki_connection_var.get(), "Connection failed")
        self.assertEqual(self.app.status_var.get(), "Previous status")
        self.app.log.assert_not_called()
        self.dialogs.showerror.assert_not_called()

    def test_invalid_url_discards_pending_requests(self) -> None:
        old = self.start_request("catalog")
        self.app.anki_connect_url_var.set("")
        self.app.on_anki_connect_url_change()
        before = self.snapshot()
        self.complete("catalog", old)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.app._anki_catalog_loading)
        self.app.anki_connect_url_var.set("http://localhost:8766")
        self.app.on_anki_connect_url_change()
        self.assertTrue(self.app._anki_catalog_loading)

    def test_unexpected_url_validation_errors_propagate(self) -> None:
        with mock.patch.object(gui, "normalize_anki_connect_url", side_effect=RuntimeError("bug")):
            for method in (
                self.app.refresh_anki_catalog,
                self.app.refresh_anki_connection,
                self.app.refresh_anki_fields,
                self.app.refresh_anki_catalog_if_needed,
                self.app.refresh_anki_fields_if_needed,
            ):
                with (
                    self.subTest(method=method.__name__),
                    self.assertRaisesRegex(RuntimeError, "bug"),
                ):
                    method()
        self.dialogs.showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()
