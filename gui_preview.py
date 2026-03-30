from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from common import format_target_tags
from models import ExportOptions, ScanResult
from rendering import populate_preview_text_widget

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


def build_preview_info_text(options: ExportOptions, scan_result: ScanResult) -> str:
    info_text = (
        f"Showing the first {len(scan_result.preview_cards)} of {scan_result.total_matches} "
        f"matching cards for {format_target_tags(options.target_tag, options.additional_target_tags)}."
    )
    if options.include_folders:
        info_text += " Included folders: " + ", ".join(options.include_folders)
    if options.sync_to_anki:
        info_text += f" Anki target: {options.anki_deck} / {options.anki_note_type}."
    if scan_result.duplicate_fronts:
        info_text += f" Duplicate fronts: {len(scan_result.duplicate_fronts)}."
    return info_text


def close_dialog_and_run_action(dialog: object, on_confirm: Callable[[], None]) -> None:
    dialog.destroy()
    on_confirm()


def show_preview_dialog(
    root: tk.Tk,
    options: ExportOptions,
    scan_result: ScanResult,
    on_confirm: Callable[[], None],
    action_label: str = "Export",
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

    info = ttk.Label(container, text=build_preview_info_text(options, scan_result))
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
