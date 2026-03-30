from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

from gui_sections import (
    build_actions_section,
    build_anki_section,
    build_formatting_section,
    build_source_section,
)
from gui_widgets import attach_tooltip, build_status_section

if TYPE_CHECKING:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, messagebox, ttk
else:
    try:
        import tkinter as tk
        import tkinter.font as tkfont
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        tk = None
        tkfont = None
        filedialog = None
        messagebox = None
        ttk = None


def append_unique_value(existing_values: Sequence[str], new_value: str) -> list[str]:
    normalized_new_filter = new_value.strip()
    if not normalized_new_filter:
        return list(existing_values)
    if normalized_new_filter in existing_values:
        return list(existing_values)
    return [*existing_values, normalized_new_filter]


def remove_selected_values(existing_values: Sequence[str], selected_indexes: Sequence[int]) -> list[str]:
    selected = {index for index in selected_indexes if 0 <= index < len(existing_values)}
    return [value for index, value in enumerate(existing_values) if index not in selected]


def append_folder_filter(existing_filters: Sequence[str], new_filter: str) -> list[str]:
    return append_unique_value(existing_filters, new_filter)


def remove_folder_filters(existing_filters: Sequence[str], selected_indexes: Sequence[int]) -> list[str]:
    return remove_selected_values(existing_filters, selected_indexes)

def build_main_window(app: object) -> None:
    if tk is None or ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    root = app.root
    style = ttk.Style(root)
    if tkfont is not None:
        section_font = tkfont.nametofont("TkDefaultFont").copy()
        section_font.configure(weight="bold")
        field_font = tkfont.nametofont("TkDefaultFont").copy()
        field_font.configure(weight="normal")
        log_font = tkfont.nametofont("TkTextFont").copy()
        log_font.configure(size=max(log_font.cget("size") - 1, 9))
        style.configure("TLabelframe.Label", font=section_font)
        style.configure("FieldLabel.TLabel", font=field_font)
    else:
        log_font = None
    style.configure("AnkiOff.TLabel", foreground="#9a9a9a")
    style.configure("AnkiPending.TLabel", foreground="#d4b25f")
    style.configure("AnkiConnected.TLabel", foreground="#8ccf7e")
    style.configure("AnkiError.TLabel", foreground="#d97a7a")

    main = ttk.Frame(root, padding=10)
    main.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    main.columnconfigure(0, weight=1)

    build_source_section(app, main)
    build_formatting_section(app, main)
    app.sync_output_option_state()
    app.sync_html_option_state()
    build_anki_section(app, main)
    app.sync_anki_option_state()
    build_actions_section(app, main)

    build_status_section(app, main, row=4, log_font=log_font)


def choose_vault(vault_var: tk.StringVar, log: Callable[[str], None]) -> None:
    if filedialog is None:
        raise RuntimeError("Tkinter file dialog is not available.")

    folder = filedialog.askdirectory(title="Select Obsidian vault")
    if folder:
        vault_var.set(folder)
        log(f"Vault selected: {folder}")


def choose_output(output_var: tk.StringVar, log: Callable[[str], None]) -> None:
    if filedialog is None:
        raise RuntimeError("Tkinter file dialog is not available.")

    path = filedialog.asksaveasfilename(
        title="Choose output TSV file",
        defaultextension=".tsv",
        filetypes=[("Tab-separated values", "*.tsv"), ("All files", "*.*")],
        initialfile="obsidian-to-anki.tsv",
    )
    if path:
        output_var.set(path)
        log(f"Output selected: {path}")


def sync_html_option_state(html_enabled: bool, quoted_italic_checkbutton: object) -> None:
    if html_enabled:
        quoted_italic_checkbutton.state(["!disabled"])
    else:
        quoted_italic_checkbutton.state(["disabled"])


def sync_output_option_state(write_tsv_enabled: bool, widgets: Sequence[object]) -> None:
    state = ["!disabled"] if write_tsv_enabled else ["disabled"]
    for widget in widgets:
        widget.state(state)


def sync_anki_option_state(sync_enabled: bool, widgets: Sequence[object]) -> None:
    state = ["!disabled"] if sync_enabled else ["disabled"]
    for widget in widgets:
        widget.state(state)


def set_combobox_choices(combobox: object, choices: Sequence[str], selected_value: str) -> str:
    normalized_choices = tuple(choices)
    combobox.configure(values=normalized_choices)

    if selected_value in normalized_choices:
        resolved_value = selected_value
    elif normalized_choices:
        resolved_value = normalized_choices[0]
    else:
        resolved_value = selected_value

    combobox.set(resolved_value)
    return resolved_value


def set_anki_field_choices(
    front_combobox: object,
    back_combobox: object,
    choices: Sequence[str],
    selected_front: str,
    selected_back: str,
) -> tuple[str, str]:
    front_value = set_combobox_choices(front_combobox, choices, selected_front)

    if selected_back in choices:
        back_value = selected_back
    elif len(choices) > 1:
        back_value = next((choice for choice in choices if choice != front_value), choices[1])
    elif choices:
        back_value = choices[0]
    else:
        back_value = selected_back

    back_combobox.configure(values=tuple(choices))
    back_combobox.set(back_value)
    return front_value, back_value


def get_folder_filters(listbox: object) -> list[str]:
    return list(listbox.get(0, "end"))


def get_listbox_values(listbox: object) -> list[str]:
    return list(listbox.get(0, "end"))


def set_folder_filters(listbox: object, folder_filters: Sequence[str]) -> None:
    listbox.delete(0, "end")
    for folder_filter in folder_filters:
        listbox.insert("end", folder_filter)


def set_listbox_values(listbox: object, values: Sequence[str]) -> None:
    listbox.delete(0, "end")
    for value in values:
        listbox.insert("end", value)


def add_folder_filter_from_dialog(
    vault: str,
    existing_filters: Sequence[str],
    log: Callable[[str], None],
) -> list[str] | None:
    if messagebox is None or filedialog is None:
        raise RuntimeError("Tkinter dialogs are not available.")

    vault_value = vault.strip()
    if not vault_value:
        messagebox.showerror("Missing vault", "Choose an Obsidian vault folder first.")
        return None

    vault_path = Path(vault_value).expanduser().resolve()
    if not vault_path.exists() or not vault_path.is_dir():
        messagebox.showerror("Invalid vault", "The selected vault folder does not exist.")
        return None

    selected_folder = filedialog.askdirectory(title="Select folder to include", initialdir=str(vault_path))
    if not selected_folder:
        return None

    selected_path = Path(selected_folder).expanduser().resolve()
    try:
        relative = selected_path.relative_to(vault_path).as_posix()
    except ValueError:
        messagebox.showerror("Invalid folder", "Choose a folder inside the selected vault.")
        return None

    updated_values = append_folder_filter(existing_filters, relative)
    if updated_values != list(existing_filters):
        log(f"Added folder filter: {relative}")
    return updated_values


def remove_selected_folder_filters(
    existing_filters: Sequence[str],
    selection: Sequence[int],
    log: Callable[[str], None],
) -> list[str]:
    updated_values = remove_folder_filters(existing_filters, selection)
    if updated_values != list(existing_filters):
        log("Removed selected folder filters.")
    return updated_values
