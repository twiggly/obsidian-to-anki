from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ..common import duplicate_handling_display_label, format_target_tags
from ..models import AnkiPreflightSummary, ExportOptions, ScanResult
from ..rendering import populate_preview_text_widget

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import ttk
else:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        tk = None
        ttk = None


def build_anki_preflight_text(
    summary: AnkiPreflightSummary | None,
    error_message: str | None = None,
) -> str | None:
    if summary is not None:
        parts: list[str] = [f"{summary.new_count} new"]
        if summary.update_count:
            noun = "update" if summary.update_count == 1 else "updates"
            parts.append(f"{summary.update_count} {noun}")
        if summary.skip_count:
            noun = "skip" if summary.skip_count == 1 else "skips"
            parts.append(f"{summary.skip_count} {noun}")
        return "Anki preflight: " + ", ".join(parts) + "."
    if error_message:
        return f"Anki preflight unavailable: {error_message}."
    return None


def build_preview_info_text(
    options: ExportOptions,
    scan_result: ScanResult,
    anki_preflight_summary: AnkiPreflightSummary | None = None,
    anki_preflight_error: str | None = None,
) -> str:
    lines = [
        (
            f"Showing the first {len(scan_result.preview_cards)} of {scan_result.total_matches} "
            f"matching cards for {format_target_tags(options.target_tag, options.additional_target_tags)}."
        )
    ]
    if options.include_folders:
        lines.append("Included folders: " + ", ".join(options.include_folders) + ".")
    if options.sync_to_anki:
        lines.append(f"Anki target: {options.anki_deck} / {options.anki_note_type}.")
        lines.append(
            f"Duplicate handling: {duplicate_handling_display_label(options.duplicate_handling)}."
        )
        preflight_text = build_anki_preflight_text(anki_preflight_summary, anki_preflight_error)
        if preflight_text is not None:
            lines.append(preflight_text)
    if scan_result.duplicate_fronts:
        lines.append(f"Duplicate fronts: {len(scan_result.duplicate_fronts)}.")
    return "\n".join(lines)


def close_dialog_and_run_action(dialog: object, on_confirm: Callable[[], None]) -> None:
    dialog.destroy()
    on_confirm()


def show_preview_dialog(
    root: tk.Tk,
    options: ExportOptions,
    scan_result: ScanResult,
    on_confirm: Callable[[], None],
    action_label: str = "Export",
    anki_preflight_summary: AnkiPreflightSummary | None = None,
    anki_preflight_error: str | None = None,
) -> None:
    if tk is None or ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    cards = scan_result.preview_cards

    dialog = tk.Toplevel(root)
    dialog.title("Preview cards")
    dialog.geometry("960x620")
    dialog.minsize(820, 480)
    dialog.transient(root)
    dialog.grab_set()

    container = ttk.Frame(dialog, padding=16)
    container.grid(row=0, column=0, sticky="nsew")
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    container.columnconfigure(1, weight=1)
    container.rowconfigure(1, weight=1)

    info = ttk.Label(
        container,
        text=build_preview_info_text(
            options,
            scan_result,
            anki_preflight_summary=anki_preflight_summary,
            anki_preflight_error=anki_preflight_error,
        ),
        justify="left",
    )
    info.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

    list_frame = ttk.Frame(container)
    list_frame.grid(row=1, column=0, sticky="nsw", padx=(0, 12))
    list_frame.rowconfigure(0, weight=1)

    listbox = tk.Listbox(list_frame, exportselection=False, width=32)
    listbox.grid(row=0, column=0, sticky="nsw")
    list_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    list_scroll.grid(row=0, column=1, sticky="ns")
    listbox.configure(yscrollcommand=list_scroll.set)

    preview_frame = ttk.Frame(container)
    preview_frame.grid(row=1, column=1, sticky="nsew")
    preview_frame.columnconfigure(0, weight=1)
    preview_frame.rowconfigure(0, weight=1)

    preview_text = tk.Text(preview_frame, wrap="word", state="disabled")
    preview_text.grid(row=0, column=0, sticky="nsew")
    preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_text.yview)
    preview_scroll.grid(row=0, column=1, sticky="ns")
    preview_text.configure(yscrollcommand=preview_scroll.set)

    button_row = ttk.Frame(container)
    button_row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))

    def show_selected_card(index: int) -> None:
        card = cards[index]
        populate_preview_text_widget(preview_text, card, html_output=options.html_output)

    def on_select(_: object) -> None:
        selection = listbox.curselection()
        if selection:
            show_selected_card(selection[0])

    def confirm_from_preview() -> None:
        close_dialog_and_run_action(dialog, on_confirm)

    for card in cards:
        listbox.insert("end", card.front)

    listbox.bind("<<ListboxSelect>>", on_select)
    ttk.Button(button_row, text="Cancel", command=dialog.destroy).grid(row=0, column=0, padx=(0, 8))
    action_button = ttk.Button(
        button_row,
        text=action_label,
        command=confirm_from_preview,
        default="active",
    )
    action_button.grid(row=0, column=1)

    listbox.selection_set(0)
    show_selected_card(0)
    dialog.focus_set()
