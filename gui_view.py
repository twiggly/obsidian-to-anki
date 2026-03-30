from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

from common import ANKI_EXISTING_NOTE_CHOICES, DUPLICATE_HANDLING_CHOICES

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
else:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        tk = None
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


def resolve_relative_tooltip_position(
    label_left: int,
    label_top: int,
    label_height: int,
    window_width: int,
    tooltip_width: int,
    *,
    margin: int = 12,
    vertical_offset: int = 8,
) -> tuple[int, int]:
    min_x = margin
    max_x = max(min_x, window_width - tooltip_width - margin)
    x_position = min(max(label_left, min_x), max_x)
    y_position = label_top + label_height + vertical_offset
    return x_position, y_position


class HoverTooltip:
    def __init__(self, widget: object, text: str) -> None:
        self.widget = widget
        self.text = text.strip()
        self.tip_label: tk.Label | None = None
        self.after_id: str | None = None
        self.root_window = widget.winfo_toplevel()
        widget.bind("<Enter>", self.schedule_show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")
        self.root_window.bind("<FocusOut>", self.hide, add="+")
        self.root_window.bind("<Unmap>", self.hide, add="+")

    def schedule_show(self, _: object | None = None) -> None:
        self.cancel_scheduled_show()
        self.after_id = self.widget.after(0, self.show)

    def cancel_scheduled_show(self) -> None:
        if self.after_id is None:
            return
        self.widget.after_cancel(self.after_id)
        self.after_id = None

    def show(self) -> None:
        if tk is None or self.tip_label is not None or not self.text:
            return

        self.after_id = None
        self.tip_label = tk.Label(
            self.root_window,
            text=self.text,
            justify="left",
            wraplength=190,
            background="#cfcfcf",
            foreground="#1f1f1f",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=12,
            pady=6,
        )
        self.tip_label.update_idletasks()

        root_left = self.root_window.winfo_rootx()
        root_top = self.root_window.winfo_rooty()
        label_left = self.widget.winfo_rootx() - root_left
        label_top = self.widget.winfo_rooty() - root_top

        x_position, y_position = resolve_relative_tooltip_position(
            label_left,
            label_top,
            self.widget.winfo_height(),
            self.root_window.winfo_width(),
            self.tip_label.winfo_reqwidth(),
            margin=12,
        )
        self.tip_label.place(x=x_position, y=y_position)
        self.tip_label.lift()

    def hide(self, _: object | None = None) -> None:
        self.cancel_scheduled_show()
        if self.tip_label is None:
            return
        tip_label = self.tip_label
        self.tip_label = None
        tip_label.place_forget()
        try:
            tip_label.destroy()
        except Exception:
            pass


def attach_tooltip(widget: object, text: str) -> HoverTooltip:
    tooltip = HoverTooltip(widget, text)
    setattr(widget, "_hover_tooltip", tooltip)
    return tooltip


def build_main_window(app: object) -> None:
    if tk is None or ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    root = app.root
    style = ttk.Style(root)
    style.configure("AnkiOff.TLabel", foreground="#9a9a9a")
    style.configure("AnkiPending.TLabel", foreground="#d4b25f")
    style.configure("AnkiConnected.TLabel", foreground="#8ccf7e")
    style.configure("AnkiError.TLabel", foreground="#d97a7a")

    main = ttk.Frame(root, padding=16)
    main.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    main.columnconfigure(0, weight=1)
    main.rowconfigure(4, weight=1)

    source = ttk.LabelFrame(main, text="Source", padding=12)
    source.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    source.columnconfigure(1, weight=1)

    vault_label = ttk.Label(source, text="Vault")
    vault_label.grid(row=0, column=0, sticky="w")
    attach_tooltip(
        vault_label,
        "Choose the root folder of the Obsidian vault you want to scan. "
        "The app will search this vault recursively for Markdown notes, then apply any tag and folder filters you selected.",
    )
    ttk.Entry(source, textvariable=app.vault_var).grid(row=0, column=1, sticky="ew", padx=(12, 12))
    ttk.Button(source, text="Browse…", command=app.choose_vault).grid(row=0, column=2, sticky="ew")

    app.output_tsv_checkbutton = ttk.Checkbutton(
        source,
        text="Output TSV",
        variable=app.write_tsv_var,
        command=app.sync_output_option_state,
    )
    app.output_tsv_checkbutton.grid(row=1, column=0, sticky="w", pady=(8, 0))
    attach_tooltip(
        app.output_tsv_checkbutton,
        "Save a tab-separated export file that can be imported into Anki manually. "
        "This is optional if you only want direct sync, but it is useful as a backup and is often the faster option for very large first-time loads.",
    )
    app.output_entry = ttk.Entry(source, textvariable=app.output_var)
    app.output_entry.grid(row=1, column=1, sticky="ew", padx=(12, 12), pady=(8, 0))
    app.output_button = ttk.Button(source, text="Save As…", command=app.choose_output)
    app.output_button.grid(row=1, column=2, sticky="ew", pady=(8, 0))

    tag_label = ttk.Label(source, text="Tags")
    tag_label.grid(row=2, column=0, sticky="nw", pady=(8, 0))
    attach_tooltip(
        tag_label,
        "Include notes that match any selected tag. "
        "You can choose more than one tag, and a note will be included if it has at least one of them.",
    )
    tag_frame = ttk.Frame(source)
    tag_frame.grid(row=2, column=1, sticky="ew", padx=(12, 12), pady=(8, 0))
    tag_frame.columnconfigure(0, weight=1)
    app.tag_combobox = ttk.Combobox(
        tag_frame,
        textvariable=app.tag_var,
        values=((app.tag_var.get(),) if app.tag_var.get() else ()),
    )
    app.tag_combobox.grid(row=0, column=0, sticky="ew")
    app.tag_combobox.bind("<<ComboboxSelected>>", app.add_selected_tag)
    app.tag_combobox.bind("<Return>", app.add_selected_tag)
    app.tag_combobox.bind("<FocusOut>", app.add_selected_tag)
    tag_list_frame = ttk.Frame(tag_frame)
    tag_list_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    tag_list_frame.columnconfigure(0, weight=1)
    app.selected_tags_listbox = tk.Listbox(
        tag_list_frame,
        exportselection=False,
        height=3,
        selectmode="extended",
    )
    app.selected_tags_listbox.grid(row=0, column=0, sticky="ew")
    tag_scroll = ttk.Scrollbar(
        tag_list_frame,
        orient="vertical",
        command=app.selected_tags_listbox.yview,
    )
    tag_scroll.grid(row=0, column=1, sticky="ns")
    app.selected_tags_listbox.configure(yscrollcommand=tag_scroll.set)
    tag_button_frame = ttk.Frame(source)
    tag_button_frame.grid(row=2, column=2, sticky="new", pady=(8, 0))
    tag_button_frame.columnconfigure(0, weight=1)
    app.tag_scan_button = ttk.Button(tag_button_frame, text="Find Tags…", command=app.scan_vault_tags)
    app.tag_scan_button.grid(row=0, column=0, sticky="ew")
    app.tag_remove_button = ttk.Button(tag_button_frame, text="Remove", command=app.remove_selected_tags)
    app.tag_remove_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))

    folder_label = ttk.Label(source, text="Folders")
    folder_label.grid(row=3, column=0, sticky="nw", pady=(8, 0))
    attach_tooltip(
        folder_label,
        "Limit the scan to specific folders inside the vault. "
        "Leave this empty to scan the whole vault.",
    )
    folder_filter_frame = ttk.Frame(source)
    folder_filter_frame.grid(row=3, column=1, sticky="ew", padx=(12, 12), pady=(8, 0))
    folder_filter_frame.columnconfigure(0, weight=1)

    app.folder_filters_listbox = tk.Listbox(folder_filter_frame, exportselection=False, height=4)
    app.folder_filters_listbox.grid(row=0, column=0, sticky="ew")
    folder_filter_scroll = ttk.Scrollbar(
        folder_filter_frame,
        orient="vertical",
        command=app.folder_filters_listbox.yview,
    )
    folder_filter_scroll.grid(row=0, column=1, sticky="ns")
    app.folder_filters_listbox.configure(yscrollcommand=folder_filter_scroll.set)

    folder_filter_buttons = ttk.Frame(source)
    folder_filter_buttons.grid(row=3, column=2, sticky="ew", pady=(8, 0))
    folder_filter_buttons.columnconfigure(0, weight=1)
    ttk.Button(folder_filter_buttons, text="Add Folder…", command=app.add_folder_filter).grid(row=0, column=0, sticky="ew")
    ttk.Button(folder_filter_buttons, text="Remove", command=app.remove_selected_folder_filters).grid(
        row=1,
        column=0,
        sticky="ew",
        pady=(8, 0),
    )

    formatting = ttk.LabelFrame(main, text="Card Formatting", padding=12)
    formatting.grid(row=1, column=0, sticky="ew", pady=(0, 12))
    formatting.columnconfigure(0, weight=1)
    formatting.columnconfigure(1, weight=1)

    app.html_checkbutton = ttk.Checkbutton(
        formatting,
        text="Use HTML",
        variable=app.html_var,
        command=app.sync_html_option_state,
    )
    app.html_checkbutton.grid(row=0, column=0, sticky="w")
    attach_tooltip(
        app.html_checkbutton,
        "Render the card back as lightweight HTML instead of plain text. "
        "This gives nicer spacing, lists, inline formatting, and dictionary-style part-of-speech sections in Anki.",
    )
    app.quoted_italic_checkbutton = ttk.Checkbutton(
        formatting,
        text='Italicize quotes',
        variable=app.quoted_italic_var,
    )
    app.quoted_italic_checkbutton.grid(row=0, column=1, sticky="w")
    attach_tooltip(
        app.quoted_italic_checkbutton,
        "When HTML is enabled, text inside double quotes will be italicized automatically. "
        "This is helpful for examples or quoted usage, but it has no effect when HTML is off.",
    )
    skip_empty_checkbutton = ttk.Checkbutton(
        formatting,
        text="Skip empty notes",
        variable=app.skip_empty_var,
    )
    skip_empty_checkbutton.grid(
        row=1,
        column=0,
        sticky="w",
        pady=(8, 0),
    )
    attach_tooltip(
        skip_empty_checkbutton,
        "Skip notes whose cleaned definition is empty after tags and formatting markers are removed. "
        "This helps avoid blank or nearly blank cards.",
    )
    duplicate_frame = ttk.Frame(formatting)
    duplicate_frame.grid(row=1, column=1, sticky="w", pady=(8, 0))
    duplicate_label = ttk.Label(duplicate_frame, text="Duplicates")
    duplicate_label.grid(row=0, column=0, sticky="w")
    attach_tooltip(
        duplicate_label,
        "Choose what to do when multiple Obsidian notes would produce the same card front. "
        "Skip keeps only the first matching note. "
        "Suffix keeps all duplicates and renames them with folder labels. "
        "Error stops before export or sync until the duplicates are resolved.",
    )
    app.duplicate_handling_combobox = ttk.Combobox(
        duplicate_frame,
        textvariable=app.duplicate_handling_var,
        values=DUPLICATE_HANDLING_CHOICES,
        state="readonly",
        width=10,
    )
    app.duplicate_handling_combobox.grid(row=0, column=1, sticky="w", padx=(8, 0))
    app.sync_output_option_state()
    app.sync_html_option_state()

    anki_options = ttk.LabelFrame(main, text="Anki Sync", padding=12)
    anki_options.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    anki_options.columnconfigure(1, weight=1)
    anki_options.columnconfigure(3, weight=1)

    app.sync_to_anki_checkbutton = ttk.Checkbutton(
        anki_options,
        text="Sync directly to Anki with AnkiConnect",
        variable=app.sync_to_anki_var,
        command=app.sync_anki_option_state,
    )
    app.sync_to_anki_checkbutton.grid(row=0, column=0, columnspan=3, sticky="w")
    attach_tooltip(
        app.sync_to_anki_checkbutton,
        "Send cards straight to Anki without a manual import step. "
        "Best for regular syncs and updates. For very large first-time loads, exporting TSV and importing it in Anki may be faster.",
    )
    app.anki_connection_indicator = ttk.Label(
        anki_options,
        textvariable=app.anki_connection_var,
        style="AnkiOff.TLabel",
    )
    app.anki_connection_indicator.grid(row=0, column=3, sticky="e")
    attach_tooltip(
        app.anki_connection_indicator,
        "Shows whether the app can currently reach AnkiConnect. "
        "If this says the connection failed, make sure Anki is open and the AnkiConnect add-on is installed.",
    )

    deck_label = ttk.Label(anki_options, text="Deck")
    deck_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
    attach_tooltip(
        deck_label,
        "The Anki deck where cards will be added or updated. "
        "This deck must already exist in Anki.",
    )
    app.anki_deck_combobox = ttk.Combobox(
        anki_options,
        textvariable=app.anki_deck_var,
        values=(app.anki_deck_var.get(),),
    )
    app.anki_deck_combobox.grid(row=1, column=1, sticky="ew", padx=(12, 12), pady=(8, 0))

    note_type_label = ttk.Label(anki_options, text="Note type")
    note_type_label.grid(row=1, column=2, sticky="w", pady=(8, 0))
    attach_tooltip(
        note_type_label,
        "The Anki note type to use for synced cards. "
        "Styling and card templates come from this note type, not from the deck.",
    )
    app.anki_note_type_combobox = ttk.Combobox(
        anki_options,
        textvariable=app.anki_note_type_var,
        values=(app.anki_note_type_var.get(),),
    )
    app.anki_note_type_combobox.grid(row=1, column=3, sticky="ew", pady=(8, 0))
    app.anki_note_type_combobox.bind("<<ComboboxSelected>>", app.on_anki_note_type_change)
    app.anki_note_type_combobox.bind("<FocusOut>", app.on_anki_note_type_change)
    app.anki_note_type_combobox.bind("<Return>", app.on_anki_note_type_change)

    app.anki_front_field_combobox = ttk.Combobox(
        anki_options,
        textvariable=app.anki_front_field_var,
        values=(app.anki_front_field_var.get(),),
    )

    app.anki_back_field_combobox = ttk.Combobox(
        anki_options,
        textvariable=app.anki_back_field_var,
        values=(app.anki_back_field_var.get(),),
    )

    existing_notes_label = ttk.Label(anki_options, text="Existing notes")
    existing_notes_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
    attach_tooltip(
        existing_notes_label,
        "Choose what happens when Anki already has a note with the same front. "
        "You can skip it or update the existing note with the latest Obsidian content.",
    )
    app.anki_existing_notes_combobox = ttk.Combobox(
        anki_options,
        textvariable=app.anki_existing_notes_var,
        values=ANKI_EXISTING_NOTE_CHOICES,
        state="readonly",
        width=10,
    )
    app.anki_existing_notes_combobox.grid(row=2, column=1, sticky="w", padx=(12, 12), pady=(8, 0))

    app.anki_connect_url_entry = ttk.Entry(anki_options, textvariable=app.anki_connect_url_var)
    app.anki_connect_url_entry.bind("<FocusOut>", app.on_anki_connect_url_change)
    app.anki_connect_url_entry.bind("<Return>", app.on_anki_connect_url_change)
    app.sync_anki_option_state()

    actions = ttk.Frame(main)
    actions.grid(row=3, column=0, sticky="ew", pady=(0, 12))
    actions.columnconfigure(0, weight=1)

    app.reset_button = ttk.Button(actions, text="Reset Settings", command=app.reset_settings)
    app.reset_button.grid(row=0, column=0, sticky="w")

    app.preview_button = ttk.Button(
        actions,
        text="Preview & Continue",
        command=app.start_preview,
        default="active",
    )
    app.preview_button.grid(row=0, column=1, sticky="e")

    output_frame = ttk.LabelFrame(main, text="Status", padding=12)
    output_frame.grid(row=4, column=0, sticky="nsew")
    output_frame.columnconfigure(0, weight=1)
    output_frame.rowconfigure(1, weight=1)

    ttk.Label(output_frame, textvariable=app.status_var).grid(row=0, column=0, sticky="w", pady=(0, 8))
    app.log_widget = tk.Text(output_frame, height=10, wrap="word", state="disabled")
    app.log_widget.grid(row=1, column=0, sticky="nsew")


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
