import unittest
from pathlib import Path
from unittest import mock

from obsidian_to_anki.gui import app as gui
from obsidian_to_anki.gui import ExporterApp
from obsidian_to_anki.gui.logic import FormValidationError
from obsidian_to_anki.models import (
    AnkiCatalog,
    AnkiPreflightSummary,
    AnkiFieldCatalog,
    AnkiSyncResult,
    DeliveryResult,
    ExportOptions,
    NoteCard,
    ScanResult,
)


class FakeVar:
    def __init__(self, value: object = "") -> None:
        self.value = value

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.value = value


class FakeButton:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.configured: dict[str, object] = {}

    def state(self, value: list[str]) -> None:
        self.calls.append(value)

    def configure(self, **kwargs: object) -> None:
        self.configured.update(kwargs)


class FakeCombobox(FakeButton):
    def __init__(self, value: str = "") -> None:
        super().__init__()
        self.values: tuple[str, ...] = ()
        self.value = value

    def configure(self, *, values: tuple[str, ...]) -> None:
        self.values = values

    def set(self, value: str) -> None:
        self.value = value


class FakeGridWidget:
    def __init__(self) -> None:
        self.visible = True
        self.grid_calls = 0
        self.grid_remove_calls = 0

    def grid(self) -> None:
        self.visible = True
        self.grid_calls += 1

    def grid_remove(self) -> None:
        self.visible = False
        self.grid_remove_calls += 1


class FakeRoot:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object, str]] = []
        self.after_cancel_calls: list[object] = []
        self.bindings: list[tuple[str, object, str]] = []
        self.destroyed = False

    def after(self, delay_ms: int, callback: object) -> str:
        token = f"after-{len(self.after_calls) + 1}"
        self.after_calls.append((delay_ms, callback, token))
        return token

    def after_cancel(self, after_id: object) -> None:
        self.after_cancel_calls.append(after_id)

    def bind(self, event_name: str, callback: object, add: str | None = None) -> None:
        self.bindings.append((event_name, callback, add or ""))

    def destroy(self) -> None:
        self.destroyed = True


def build_scan_result() -> ScanResult:
    card = NoteCard(
        front="Definition",
        back="Body",
        tags=["definition"],
        source_path=Path("/tmp/Definition.md"),
    )
    return ScanResult(
        cards=[card],
        preview_cards=[card],
        total_matches=1,
        duplicate_fronts={"Definition": (Path("/tmp/A.md"), Path("/tmp/B.md"))},
        scan_seconds=1.5,
    )


def build_controller() -> ExporterApp:
    app = ExporterApp.__new__(ExporterApp)
    app.root = FakeRoot()
    app.vault_var = FakeVar("/tmp/vault")
    app.output_var = FakeVar("/tmp/out.tsv")
    app.write_tsv_var = FakeVar(True)
    app.tag_var = FakeVar("definition")
    app.html_var = FakeVar(False)
    app.skip_empty_var = FakeVar(False)
    app.quoted_italic_var = FakeVar(False)
    app.duplicate_handling_var = FakeVar("error")
    app.duplicate_handling_display_var = FakeVar("Stop")
    app.sync_to_anki_var = FakeVar(False)
    app.anki_connect_url_var = FakeVar("http://127.0.0.1:8765")
    app.anki_deck_var = FakeVar("Default")
    app.anki_note_type_var = FakeVar("Basic")
    app.anki_front_field_var = FakeVar("Front")
    app.anki_back_field_var = FakeVar("Back")
    app.anki_existing_notes_var = FakeVar("skip")
    app.anki_connection_var = FakeVar("Sync off")
    app.status_var = FakeVar("")
    app.status_details_var = FakeVar("Show Details")
    app.status_details_visible = False
    app.preview_button = FakeButton()
    app.reset_button = FakeButton()
    app.output_entry = FakeButton()
    app.output_button = FakeButton()
    app.tag_scan_button = FakeButton()
    app.add_folder_button = FakeButton()
    app.anki_connection_indicator = FakeButton()
    app.tag_combobox = FakeCombobox("definition")
    app.selected_tags_container = mock.Mock()
    app.selected_tag_remove_buttons = []
    app.selected_tags = ["definition"]
    app.anki_deck_combobox = FakeCombobox("Default")
    app.anki_note_type_combobox = FakeCombobox("Basic")
    app.anki_front_field_combobox = FakeCombobox("Front")
    app.anki_back_field_combobox = FakeCombobox("Back")
    app.anki_existing_notes_combobox = FakeCombobox("skip")
    app.anki_connect_url_entry = FakeButton()
    app.folder_filters_container = mock.Mock()
    app.folder_filter_remove_buttons = []
    app.folder_filters = []
    app.get_folder_filters_from_listbox = mock.Mock(return_value=[])
    app.get_selected_tags_from_listbox = mock.Mock(return_value=["definition"])
    app.log = mock.Mock()
    app.begin_delivery = mock.Mock()
    app.is_busy = False
    app._anki_catalog_loading = False
    app._anki_field_loading = False
    app._last_loaded_anki_url = None
    app._last_loaded_anki_note_type = None
    app._pending_anki_catalog_url = None
    app._pending_anki_field_key = None
    app._anki_refresh_after_id = None
    app._anki_poll_after_id = None
    return app


class GuiControllerTests(unittest.TestCase):
    def test_scan_vault_tags_kicks_off_background_tag_scan(self) -> None:
        app = build_controller()

        with (
            mock.patch.object(
                gui,
                "build_tag_scan_request",
                return_value=(Path("/tmp/vault"), ()),
            ),
            mock.patch.object(gui, "start_tag_catalog_scan") as start_tag_catalog_scan,
        ):
            ExporterApp.scan_vault_tags(app)

        self.assertTrue(app.is_busy)
        self.assertEqual(app.status_var.get(), "Scanning vault for tags…")
        self.assertEqual(app.log.call_args_list[0].args[0], "Scanning vault to find available tags.")
        args = start_tag_catalog_scan.call_args.args
        self.assertEqual(args[1], Path("/tmp/vault"))
        self.assertEqual(args[2], ())
        self.assertIs(args[3].__func__, ExporterApp.finish_tag_scan_success)
        self.assertIs(args[4].__func__, ExporterApp.finish_tag_scan_error)

    def test_finish_tag_scan_success_updates_tag_choices(self) -> None:
        app = build_controller()
        app.is_busy = True

        ExporterApp.finish_tag_scan_success(app, ("biology", "definition", "study"))

        self.assertFalse(app.is_busy)
        self.assertEqual(app.tag_combobox.values, ("biology", "definition", "study"))
        self.assertEqual(app.tag_var.get(), "definition")
        self.assertEqual(app.status_var.get(), "Found 3 tags in the scanned vault.")
        self.assertEqual(app.log.call_args_list[0].args[0], "Found 3 tags in the scanned vault.")

    def test_finish_tag_scan_success_keeps_blank_input_blank(self) -> None:
        app = build_controller()
        app.is_busy = True
        app.tag_var = FakeVar("")
        app.tag_combobox = FakeCombobox("")

        ExporterApp.finish_tag_scan_success(app, ("biology", "definition", "study"))

        self.assertEqual(app.tag_var.get(), "")
        self.assertEqual(app.tag_combobox.value, "")

    def test_add_selected_tag_appends_and_clears_input(self) -> None:
        app = build_controller()
        app.get_selected_tags_from_listbox = mock.Mock(return_value=["definition"])
        app.set_selected_tags_in_listbox = mock.Mock()
        app.tag_var.set("fallacy")

        ExporterApp.add_selected_tag(app)

        app.set_selected_tags_in_listbox.assert_called_once_with(["definition", "fallacy"])
        self.assertEqual(app.tag_var.get(), "")
        self.assertEqual(app.tag_combobox.value, "")

    def test_set_selected_tags_in_listbox_sanitizes_and_renders_chips(self) -> None:
        app = build_controller()

        with mock.patch.object(gui, "render_tag_chips", return_value=[]) as render_tag_chips:
            ExporterApp.set_selected_tags_in_listbox(app, ["definition", " definition ", "fallacy"])

        self.assertEqual(app.selected_tags, ["definition", "fallacy"])
        render_tag_chips.assert_called_once_with(
            app.selected_tags_container,
            ["definition", "fallacy"],
            app.remove_tag,
            disabled=False,
        )

    def test_apply_saved_settings_ignores_blank_saved_tags(self) -> None:
        app = build_controller()
        app.sync_output_option_state = mock.Mock()
        app.sync_html_option_state = mock.Mock()
        app.sync_anki_option_state = mock.Mock()
        app.set_selected_tags_in_listbox = mock.Mock()

        with mock.patch.object(
            gui,
            "load_gui_settings",
            return_value={"tag": "", "tags": ["", "  "]},
        ):
            ExporterApp.apply_saved_settings(app)

        self.assertEqual(app.tag_var.get(), "")
        app.set_selected_tags_in_listbox.assert_called_once_with([])
        app.sync_output_option_state.assert_called_once_with()

    def test_build_options_from_form_passes_write_tsv_toggle(self) -> None:
        app = build_controller()
        app.write_tsv_var = FakeVar(False)

        with mock.patch.object(gui, "build_export_options_from_values", return_value=mock.Mock()) as builder:
            ExporterApp.build_options_from_form(app)

        self.assertEqual(builder.call_args.kwargs["write_tsv"], False)

    def test_sync_status_details_visibility_hides_log_by_default(self) -> None:
        app = build_controller()
        app.log_widget = FakeGridWidget()

        ExporterApp.sync_status_details_visibility(app)

        self.assertEqual(app.status_details_var.get(), "Show Details")
        self.assertFalse(app.log_widget.visible)

    def test_toggle_status_details_shows_log(self) -> None:
        app = build_controller()
        app.log_widget = FakeGridWidget()

        ExporterApp.toggle_status_details(app)

        self.assertEqual(app.status_details_var.get(), "Hide Details")
        self.assertTrue(app.log_widget.visible)

    def test_reset_settings_restores_defaults_and_deletes_saved_settings(self) -> None:
        app = build_controller()
        app.apply_default_settings = mock.Mock()

        with (
            mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock,
            mock.patch.object(gui, "delete_gui_settings") as delete_gui_settings,
        ):
            messagebox_mock.askyesno.return_value = True

            ExporterApp.reset_settings(app)

        messagebox_mock.askyesno.assert_called_once_with(
            "Reset settings",
            "Reset the app back to its default settings?",
        )
        delete_gui_settings.assert_called_once_with()
        app.apply_default_settings.assert_called_once_with()
        app.log.assert_called_with("Settings reset to defaults.")

    def test_reset_settings_does_nothing_when_cancelled(self) -> None:
        app = build_controller()
        app.apply_default_settings = mock.Mock()

        with (
            mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock,
            mock.patch.object(gui, "delete_gui_settings") as delete_gui_settings,
        ):
            messagebox_mock.askyesno.return_value = False

            ExporterApp.reset_settings(app)

        delete_gui_settings.assert_not_called()
        app.apply_default_settings.assert_not_called()

    def test_start_preview_kicks_off_background_scan(self) -> None:
        app = build_controller()
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            duplicate_handling="skip",
        )
        app.build_options_from_form = mock.Mock(return_value=options)

        with mock.patch.object(gui, "start_preview_scan") as start_preview_scan:
            ExporterApp.start_preview(app)

        self.assertTrue(app.is_busy)
        self.assertEqual(app.status_var.get(), "Generating preview…")
        app.log.assert_called_with("Generating preview for #definition")
        start_preview_scan.assert_called_once()
        args = start_preview_scan.call_args.args
        self.assertIs(args[0], app.root)
        self.assertEqual(args[1], options)
        self.assertTrue(callable(args[2]))
        self.assertIs(args[3].__self__, app)
        self.assertIs(args[3].__func__, ExporterApp.finish_preview_error)

    def test_build_options_from_form_shows_validation_error(self) -> None:
        app = build_controller()

        with (
            mock.patch.object(
                gui,
                "build_export_options_from_values",
                side_effect=FormValidationError("Missing vault", "Choose an Obsidian vault folder."),
            ),
            mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock,
        ):
            result = ExporterApp.build_options_from_form(app)

        self.assertIsNone(result)
        messagebox_mock.showerror.assert_called_once_with(
            "Missing vault",
            "Choose an Obsidian vault folder.",
        )

    def test_finish_preview_success_shows_warning_and_wires_export_callback(self) -> None:
        app = build_controller()
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            duplicate_handling="skip",
        )
        scan_result = build_scan_result()

        with (
            mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock,
            mock.patch.object(gui, "show_preview_dialog") as show_preview_dialog,
        ):
            ExporterApp.finish_preview_success(app, options, scan_result)

        self.assertFalse(app.is_busy)
        self.assertEqual(
            app.status_var.get(),
            "Preview ready. Showing the first 1 of 1 matching cards.",
        )
        self.assertEqual(
            app.log.call_args_list[0].args[0],
            "Preview ready. Showing the first 1 of 1 matching cards.",
        )
        self.assertEqual(app.log.call_args_list[1].args[0], "Timing: scan 1.50s")
        self.assertEqual(app.log.call_args_list[2].args[0], "Detected 1 duplicate fronts.")
        messagebox_mock.showwarning.assert_called_once()
        show_preview_dialog.assert_called_once()
        self.assertEqual(show_preview_dialog.call_args.kwargs["action_label"], "Export")
        callback = show_preview_dialog.call_args.kwargs["on_confirm"]
        callback()
        app.begin_delivery.assert_called_once_with(options, scan_result)

    def test_finish_preview_success_passes_anki_preflight_summary_to_dialog(self) -> None:
        app = build_controller()
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            sync_to_anki=True,
            anki_deck="Lexicon",
            anki_note_type="Basic",
            duplicate_handling="skip",
        )
        scan_result = build_scan_result()
        preflight_summary = AnkiPreflightSummary(
            new_count=3,
            update_count=1,
            skip_count=0,
            deck_name="Lexicon",
            note_type="Basic",
        )

        with (
            mock.patch.object(gui, "messagebox", mock.Mock()),
            mock.patch.object(gui, "show_preview_dialog") as show_preview_dialog,
        ):
            ExporterApp.finish_preview_success(app, options, scan_result, preflight_summary, None)

        self.assertEqual(show_preview_dialog.call_args.kwargs["anki_preflight_summary"], preflight_summary)

    def test_finish_preview_success_logs_anki_preflight_error(self) -> None:
        app = build_controller()
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            sync_to_anki=True,
            duplicate_handling="skip",
        )
        scan_result = build_scan_result()

        with (
            mock.patch.object(gui, "messagebox", mock.Mock()),
            mock.patch.object(gui, "show_preview_dialog"),
        ):
            ExporterApp.finish_preview_success(app, options, scan_result, None, "Anki unavailable")

        self.assertEqual(
            app.log.call_args_list[-1].args[0],
            "Anki preflight unavailable: Anki unavailable",
        )

    def test_finish_preview_success_stops_after_warning_in_error_mode(self) -> None:
        app = build_controller()
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            duplicate_handling="error",
        )
        scan_result = build_scan_result()

        with (
            mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock,
            mock.patch.object(gui, "show_preview_dialog") as show_preview_dialog,
        ):
            ExporterApp.finish_preview_success(app, options, scan_result)

        messagebox_mock.showwarning.assert_called_once()
        show_preview_dialog.assert_not_called()
        self.assertEqual(
            app.status_var.get(),
            "Duplicate fronts detected. Resolve them or choose skip or suffix to continue.",
        )

    def test_refresh_anki_catalog_kicks_off_background_refresh(self) -> None:
        app = build_controller()

        with mock.patch.object(gui, "start_anki_catalog_refresh") as start_anki_catalog_refresh:
            ExporterApp.refresh_anki_catalog(app)

        self.assertEqual(app.status_var.get(), "Loading Anki decks and note types…")
        self.assertEqual(app.anki_connection_var.get(), "Checking…")
        app.log.assert_called_with("Loading deck and note type lists from AnkiConnect.")
        start_anki_catalog_refresh.assert_called_once()
        args = start_anki_catalog_refresh.call_args.args
        self.assertIs(args[0], app.root)
        self.assertEqual(args[1], "http://127.0.0.1:8765")

    def test_refresh_anki_catalog_quietly_keeps_visible_connection_state(self) -> None:
        app = build_controller()
        app.anki_connection_var = FakeVar("Connected")
        app.status_var = FakeVar("Existing status")

        with mock.patch.object(gui, "start_anki_catalog_refresh") as start_anki_catalog_refresh:
            ExporterApp.refresh_anki_catalog(app, show_error_dialog=False, quiet=True)

        self.assertEqual(app.anki_connection_var.get(), "Connected")
        self.assertEqual(app.status_var.get(), "Existing status")
        app.log.assert_not_called()
        start_anki_catalog_refresh.assert_called_once()

    def test_on_root_focus_refreshes_anki_catalog(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)
        app.schedule_anki_connection_refresh = mock.Mock()

        ExporterApp.on_root_focus(app)

        app.schedule_anki_connection_refresh.assert_called_once_with()

    def test_on_root_focus_does_not_refresh_anki_catalog_when_sync_is_off(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(False)
        app.schedule_anki_connection_refresh = mock.Mock()

        ExporterApp.on_root_focus(app)

        app.schedule_anki_connection_refresh.assert_not_called()

    def test_schedule_anki_connection_refresh_debounces_prior_request(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)

        ExporterApp.schedule_anki_connection_refresh(app)
        first_after_id = app._anki_refresh_after_id
        ExporterApp.schedule_anki_connection_refresh(app)

        self.assertEqual(app.root.after_calls[0][0], gui.ANKI_FOCUS_REFRESH_DELAY_MS)
        self.assertEqual(app.root.after_calls[1][0], gui.ANKI_FOCUS_REFRESH_DELAY_MS)
        self.assertEqual(app.root.after_cancel_calls, [first_after_id])

    def test_run_anki_connection_refresh_uses_quiet_refresh(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)
        app.refresh_anki_catalog = mock.Mock()

        ExporterApp.run_anki_connection_refresh(app)

        app.refresh_anki_catalog.assert_called_once_with(show_error_dialog=False, quiet=True)

    def test_start_anki_connection_polling_schedules_periodic_refresh(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)

        ExporterApp.start_anki_connection_polling(app)

        self.assertEqual(app.root.after_calls[0][0], gui.ANKI_POLL_REFRESH_INTERVAL_MS)
        self.assertEqual(app._anki_poll_after_id, "after-1")

    def test_sync_anki_option_state_starts_polling_when_enabled(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)
        app.start_anki_connection_polling = mock.Mock()
        app.refresh_anki_catalog_if_needed = mock.Mock()

        ExporterApp.sync_anki_option_state(app)

        app.start_anki_connection_polling.assert_called_once_with()
        app.refresh_anki_catalog_if_needed.assert_called_once_with()

    def test_sync_anki_option_state_stops_polling_when_disabled(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(False)
        app.cancel_anki_connection_refresh = mock.Mock()
        app.stop_anki_connection_polling = mock.Mock()

        ExporterApp.sync_anki_option_state(app)

        app.cancel_anki_connection_refresh.assert_called_once_with()
        app.stop_anki_connection_polling.assert_called_once_with()

    def test_finish_anki_catalog_refresh_success_populates_comboboxes(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)
        app._pending_anki_catalog_url = "http://127.0.0.1:8765"
        catalog = AnkiCatalog(
            deck_names=("Default", "Obsidian"),
            note_type_names=("Basic", "Cloze"),
        )

        with mock.patch.object(gui.ExporterApp, "refresh_anki_fields_if_needed") as refresh_anki_fields_if_needed:
            ExporterApp.finish_anki_catalog_refresh_success(app, catalog)

        self.assertEqual(app.anki_deck_combobox.values, ("Default", "Obsidian"))
        self.assertEqual(app.anki_note_type_combobox.values, ("Basic", "Cloze"))
        self.assertEqual(app.anki_connection_var.get(), "Connected")
        self.assertEqual(app.status_var.get(), "Loaded 2 decks and 2 note types from AnkiConnect.")
        self.assertEqual(app.anki_connection_indicator.configured["style"], "AnkiConnected.TLabel")
        refresh_anki_fields_if_needed.assert_called_once()

    def test_finish_anki_catalog_refresh_success_is_quiet_when_requested(self) -> None:
        app = build_controller()
        app.sync_to_anki_var = FakeVar(True)
        app._pending_anki_catalog_url = "http://127.0.0.1:8765"
        app.status_var = FakeVar("Existing status")
        catalog = AnkiCatalog(
            deck_names=("Default", "Obsidian"),
            note_type_names=("Basic", "Cloze"),
        )

        with mock.patch.object(gui.ExporterApp, "refresh_anki_fields_if_needed") as refresh_anki_fields_if_needed:
            ExporterApp.finish_anki_catalog_refresh_success(app, catalog, quiet=True)

        self.assertEqual(app.status_var.get(), "Existing status")
        app.log.assert_not_called()
        self.assertEqual(app.anki_connection_var.get(), "Connected")
        refresh_anki_fields_if_needed.assert_called_once()

    def test_finish_anki_catalog_refresh_error_is_quiet_when_requested(self) -> None:
        app = build_controller()
        app._last_loaded_anki_url = "http://127.0.0.1:8765"
        app._last_loaded_anki_note_type = "Basic"
        app.status_var = FakeVar("Existing status")

        with mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock:
            ExporterApp.finish_anki_catalog_refresh_error(app, "Could not reach Anki", quiet=True)

        self.assertEqual(app.status_var.get(), "Existing status")
        app.log.assert_not_called()
        self.assertEqual(app.anki_connection_var.get(), "Connection failed")
        self.assertIsNone(app._last_loaded_anki_url)
        self.assertIsNone(app._last_loaded_anki_note_type)
        messagebox_mock.showerror.assert_not_called()

    def test_finish_anki_field_refresh_success_populates_field_comboboxes(self) -> None:
        app = build_controller()
        app._pending_anki_field_key = ("http://127.0.0.1:8765", "Basic")
        field_catalog = AnkiFieldCatalog(note_type_name="Basic", field_names=("Front", "Back", "Tags"))

        ExporterApp.finish_anki_field_refresh_success(app, field_catalog)

        self.assertEqual(app.anki_front_field_combobox.values, ("Front", "Back", "Tags"))
        self.assertEqual(app.anki_back_field_combobox.values, ("Front", "Back", "Tags"))
        self.assertEqual(app.status_var.get(), "Loaded 3 fields for note type 'Basic'.")

    def test_finish_delivery_success_updates_status_and_shows_completion(self) -> None:
        app = build_controller()
        options = ExportOptions(
            vault_path=Path("/tmp/vault"),
            output_path=Path("/tmp/out.tsv"),
            duplicate_handling="suffix",
        )
        scan_result = build_scan_result()
        delivery_result = DeliveryResult(
            export_count=2,
            output_path=Path("/tmp/out.tsv"),
            sync_result=AnkiSyncResult(
                added_count=1,
                skipped_count=0,
                deck_name="Default",
                note_type="Basic",
            ),
            report_text="Duplicate fronts detected:\n- Term\n",
            export_seconds=0.25,
            sync_seconds=1.5,
            total_seconds=1.75,
        )

        with mock.patch.object(gui, "messagebox", mock.Mock()) as messagebox_mock:
            ExporterApp.finish_delivery_success(app, options, scan_result, delivery_result)

        self.assertFalse(app.is_busy)
        self.assertEqual(
            app.status_var.get(),
            "Exported 2 cards to: /tmp/out.tsv Synced 1 cards to Anki deck 'Default' using note type 'Basic'. Detected 1 duplicate card fronts. Appending folder-based suffixes so each front stays unique.",
        )
        self.assertEqual(
            app.log.call_args_list[0],
            mock.call(
                "Exported 2 cards to: /tmp/out.tsv Synced 1 cards to Anki deck 'Default' using note type 'Basic'. Detected 1 duplicate card fronts. Appending folder-based suffixes so each front stays unique."
            ),
        )
        self.assertEqual(
            app.log.call_args_list[1],
            mock.call("Timing: scan 1.50s, export 0.25s, sync 0.00s, total 1.75s"),
        )
        self.assertEqual(
            app.log.call_args_list[2],
            mock.call("Anki sync: validate 0.00s, check duplicates 0.00s, write changes 0.00s"),
        )
        self.assertEqual(app.log.call_args_list[3], mock.call("Duplicate fronts detected:"))
        self.assertEqual(app.log.call_args_list[4], mock.call("- Term"))
        messagebox_mock.showinfo.assert_called_once_with(
            "Export complete",
            "Exported 2 cards to: /tmp/out.tsv Synced 1 cards to Anki deck 'Default' using note type 'Basic'. Detected 1 duplicate card fronts. Appending folder-based suffixes so each front stays unique.",
        )
