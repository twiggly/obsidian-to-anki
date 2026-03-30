import unittest

from common import effective_italicize_quoted_text, unexpected_error_message
from gui_view import (
    attach_tooltip,
    append_folder_filter,
    remove_folder_filters,
    resolve_relative_tooltip_position,
    set_anki_field_choices,
    set_combobox_choices,
    sync_anki_option_state,
    sync_html_option_state,
    sync_output_option_state,
)


class FakeCheckbutton:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def state(self, value: list[str]) -> None:
        self.calls.append(value)


class FakeCombobox:
    def __init__(self) -> None:
        self.values: tuple[str, ...] = ()
        self.current_value = ""

    def configure(self, *, values: tuple[str, ...]) -> None:
        self.values = values

    def set(self, value: str) -> None:
        self.current_value = value


class FakeWidget:
    def __init__(self) -> None:
        self.bindings: list[tuple[str, object, str]] = []
        self.root = FakeRoot()

    def bind(self, event_name: str, callback: object, add: str | None = None) -> None:
        self.bindings.append((event_name, callback, add or ""))

    def winfo_toplevel(self) -> object:
        return self.root


class FakeRoot:
    def __init__(self) -> None:
        self.bindings: list[tuple[str, object, str]] = []

    def bind(self, event_name: str, callback: object, add: str | None = None) -> None:
        self.bindings.append((event_name, callback, add or ""))


class OptionBehaviorTests(unittest.TestCase):
    def test_effective_italicize_quoted_text_requires_html_output(self) -> None:
        self.assertFalse(effective_italicize_quoted_text(False, False))
        self.assertFalse(effective_italicize_quoted_text(False, True))
        self.assertFalse(effective_italicize_quoted_text(True, False))
        self.assertTrue(effective_italicize_quoted_text(True, True))

    def test_append_folder_filter_preserves_commas_in_folder_names(self) -> None:
        updated = append_folder_filter(["Reference, Notes"], "Lexicon")

        self.assertEqual(updated, ["Reference, Notes", "Lexicon"])

    def test_append_folder_filter_deduplicates_exact_matches(self) -> None:
        updated = append_folder_filter(["Lexicon"], "Lexicon")

        self.assertEqual(updated, ["Lexicon"])

    def test_remove_folder_filters_removes_selected_indexes(self) -> None:
        updated = remove_folder_filters(
            ["Reference, Notes", "Lexicon", "Study"],
            [0, 2],
        )

        self.assertEqual(updated, ["Lexicon"])

    def test_sync_html_option_state_disables_when_html_is_off(self) -> None:
        checkbutton = FakeCheckbutton()

        sync_html_option_state(False, checkbutton)

        self.assertEqual(checkbutton.calls, [["disabled"]])

    def test_sync_output_option_state_disables_output_widgets_when_export_is_off(self) -> None:
        widgets = [FakeCheckbutton(), FakeCheckbutton()]

        sync_output_option_state(False, widgets)

        self.assertEqual(widgets[0].calls, [["disabled"]])
        self.assertEqual(widgets[1].calls, [["disabled"]])

    def test_sync_anki_option_state_disables_all_anki_fields_when_sync_is_off(self) -> None:
        widgets = [FakeCheckbutton(), FakeCheckbutton()]

        sync_anki_option_state(False, widgets)

        self.assertEqual(widgets[0].calls, [["disabled"]])
        self.assertEqual(widgets[1].calls, [["disabled"]])

    def test_set_combobox_choices_preserves_existing_selection_when_available(self) -> None:
        combobox = FakeCombobox()

        resolved = set_combobox_choices(combobox, ["Default", "Obsidian"], "Obsidian")

        self.assertEqual(combobox.values, ("Default", "Obsidian"))
        self.assertEqual(combobox.current_value, "Obsidian")
        self.assertEqual(resolved, "Obsidian")

    def test_set_combobox_choices_falls_back_to_first_choice(self) -> None:
        combobox = FakeCombobox()

        resolved = set_combobox_choices(combobox, ["Basic", "Cloze"], "Missing")

        self.assertEqual(combobox.current_value, "Basic")
        self.assertEqual(resolved, "Basic")

    def test_set_anki_field_choices_prefers_second_field_for_back(self) -> None:
        front_combobox = FakeCombobox()
        back_combobox = FakeCombobox()

        front_value, back_value = set_anki_field_choices(
            front_combobox,
            back_combobox,
            ["Front", "Back", "Extra"],
            "Missing",
            "Missing",
        )

        self.assertEqual(front_value, "Front")
        self.assertEqual(back_value, "Back")
        self.assertEqual(front_combobox.values, ("Front", "Back", "Extra"))
        self.assertEqual(back_combobox.values, ("Front", "Back", "Extra"))

    def test_attach_tooltip_registers_hover_bindings(self) -> None:
        widget = FakeWidget()

        tooltip = attach_tooltip(widget, "Helpful text")

        self.assertEqual(tooltip.text, "Helpful text")
        self.assertEqual(
            [binding[0] for binding in widget.bindings],
            ["<Enter>", "<Leave>", "<ButtonPress>", "<Destroy>"],
        )
        self.assertEqual(
            [binding[0] for binding in widget.root.bindings],
            ["<FocusOut>", "<Unmap>"],
        )

    def test_resolve_relative_tooltip_position_anchors_below_label(self) -> None:
        position = resolve_relative_tooltip_position(
            180,
            120,
            24,
            800,
            180,
        )

        self.assertEqual(position, (180, 152))

    def test_resolve_relative_tooltip_position_clamps_to_window_bounds(self) -> None:
        position = resolve_relative_tooltip_position(
            760,
            120,
            24,
            800,
            180,
        )

        self.assertEqual(position, (608, 152))

    def test_unexpected_error_message_points_users_to_the_log(self) -> None:
        self.assertEqual(
            unexpected_error_message("preview"),
            "Preview failed due to an unexpected error. See the log for details.",
        )
