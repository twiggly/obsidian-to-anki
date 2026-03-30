from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

from common import ANKI_EXISTING_NOTE_CHOICES, DUPLICATE_HANDLING_DISPLAY_CHOICES

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


def measure_container_width(container: object) -> int:
    try:
        container.update_idletasks()
    except Exception:
        pass

    for method_name in ("winfo_width", "winfo_reqwidth"):
        try:
            width = int(getattr(container, method_name)())
        except Exception:
            continue
        if width > 1:
            return width

    return 0


def bind_chip_container_resize(container: object) -> None:
    if getattr(container, "_chip_resize_bound", False):
        return

    def rerender(event: object) -> None:
        state = getattr(container, "_chip_render_state", None)
        if state is None or getattr(container, "_chip_render_in_progress", False):
            return

        event_width = getattr(event, "width", 0)
        if not isinstance(event_width, int) or event_width <= 1:
            return

        if event_width == getattr(container, "_chip_last_width", None):
            return

        setattr(container, "_chip_last_width", event_width)
        render_tag_chips(
            container,
            state["values"],
            state["on_remove"],
            disabled=state["disabled"],
            empty_text=state["empty_text"],
        )

    try:
        container.bind("<Configure>", rerender, add="+")
        setattr(container, "_chip_resize_bound", True)
    except Exception:
        pass


def render_tag_chips(
    container: object,
    values: Sequence[str],
    on_remove: Callable[[str], None],
    *,
    disabled: bool = False,
    empty_text: str = "No tags selected",
) -> list[object]:
    if tk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    bind_chip_container_resize(container)
    setattr(
        container,
        "_chip_render_state",
        {
            "values": tuple(values),
            "on_remove": on_remove,
            "disabled": disabled,
            "empty_text": empty_text,
        },
    )
    setattr(container, "_chip_render_in_progress", True)
    existing_children = container.winfo_children()
    if not isinstance(existing_children, (list, tuple)):
        setattr(container, "_chip_render_in_progress", False)
        return []

    try:
        for child in existing_children:
            child.destroy()

        tray_background = "#2a2a2a"
        chip_background = "#343434"
        chip_border = "#4a4a4a"
        remove_buttons: list[object] = []
        if not values:
            placeholder = tk.Label(
                container,
                text=empty_text,
                background=tray_background,
                foreground="#a4a4a4",
                padx=2,
                pady=2,
            )
            placeholder.grid(row=0, column=0, sticky="w")
            return remove_buttons

        available_width = max(measure_container_width(container) - 12, 0)
        row = 0
        column = 0
        row_width = 0
        chip_font = None
        remove_font = None
        if tkfont is not None:
            chip_font = tkfont.nametofont("TkDefaultFont").copy()
            chip_font.configure(size=max(chip_font.cget("size") - 1, 9))
            remove_font = tkfont.nametofont("TkDefaultFont").copy()
            remove_font.configure(size=max(remove_font.cget("size") - 2, 8))
        for value in values:
            chip = tk.Frame(
                container,
                background=chip_background,
                borderwidth=1,
                relief="solid",
                highlightthickness=0,
                highlightbackground=chip_border,
            )
            chip.grid(row=row, column=column, sticky="w", padx=(0, 6), pady=2)

            label = tk.Label(
                chip,
                text=value,
                background=chip_background,
                foreground="#ededed",
                padx=8,
                pady=2,
                font=chip_font,
            )
            label.pack(side="left")

            remove_button = tk.Label(
                chip,
                text="×",
                background=chip_background,
                foreground="#939393",
                cursor="" if disabled else "hand2",
                padx=3,
                pady=2,
                font=remove_font,
            )
            if not disabled:
                remove_button.bind("<Button-1>", lambda _event, selected=value: on_remove(selected))
                remove_button.bind(
                    "<Enter>",
                    lambda _event, widget=remove_button: widget.configure(foreground="#bebebe"),
                )
                remove_button.bind(
                    "<Leave>",
                    lambda _event, widget=remove_button: widget.configure(foreground="#939393"),
                )
            remove_button.pack(side="left")
            remove_buttons.append(remove_button)

            try:
                chip.update_idletasks()
                chip_width = chip.winfo_reqwidth() + 6
            except Exception:
                chip_width = 0

            if column > 0 and available_width > 0 and row_width + chip_width > available_width:
                row += 1
                column = 0
                row_width = 0

            chip.grid(row=row, column=column, sticky="w", padx=(0, 6), pady=2)

            row_width += chip_width
            column += 1

        return remove_buttons
    finally:
        setattr(container, "_chip_last_width", measure_container_width(container))
        setattr(container, "_chip_render_in_progress", False)


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

    source = ttk.LabelFrame(main, text="Source", padding=8)
    source.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    source.columnconfigure(0, minsize=72)
    source.columnconfigure(1, weight=1)

    vault_label = ttk.Label(source, text="Vault", style="FieldLabel.TLabel")
    vault_label.grid(row=0, column=0, sticky="w")
    attach_tooltip(
        vault_label,
        "Choose the root folder of the Obsidian vault you want to scan. "
        "The app will search this vault recursively for Markdown notes, then apply any tag and folder filters you selected.",
    )
    ttk.Entry(source, textvariable=app.vault_var).grid(row=0, column=1, sticky="ew", padx=(10, 10))
    ttk.Button(source, text="Browse…", command=app.choose_vault).grid(row=0, column=2, sticky="ew")

    output_label_frame = ttk.Frame(source)
    output_label_frame.grid(row=1, column=0, sticky="w", pady=(4, 0))
    app.output_tsv_checkbutton = ttk.Checkbutton(
        output_label_frame,
        text="",
        variable=app.write_tsv_var,
        command=app.sync_output_option_state,
        width=0,
    )
    app.output_tsv_checkbutton.grid(row=0, column=0, sticky="w")
    output_label = ttk.Label(output_label_frame, text="Output TSV", style="FieldLabel.TLabel")
    output_label.grid(row=0, column=1, sticky="w", padx=(4, 0))
    attach_tooltip(
        output_label,
        "Save a TSV export as a backup or import it into Anki manually. "
        "This is optional when direct sync is enabled, and it is often the faster option for very large first-time loads.",
    )
    attach_tooltip(
        app.output_tsv_checkbutton,
        "Turn TSV export on or off for this run.",
    )
    app.output_entry = ttk.Entry(source, textvariable=app.output_var)
    app.output_entry.grid(row=1, column=1, sticky="ew", padx=(10, 10), pady=(4, 0))
    app.output_button = ttk.Button(source, text="Save As…", command=app.choose_output)
    app.output_button.grid(row=1, column=2, sticky="ew", pady=(4, 0))

    tag_label = ttk.Label(source, text="Tags", style="FieldLabel.TLabel")
    tag_label.grid(row=2, column=0, sticky="w", pady=(4, 0))
    attach_tooltip(
        tag_label,
        "Select one or more tags to scan for. "
        "A note is included if it matches any selected tag.",
    )
    tag_picker_frame = ttk.Frame(source)
    tag_picker_frame.grid(row=2, column=1, sticky="ew", padx=(10, 10), pady=(4, 0))
    tag_picker_frame.columnconfigure(0, weight=1)
    app.tag_combobox = ttk.Combobox(
        tag_picker_frame,
        textvariable=app.tag_var,
        values=((app.tag_var.get(),) if app.tag_var.get() else ()),
    )
    app.tag_combobox.grid(row=0, column=0, sticky="ew")
    app.tag_combobox.bind("<<ComboboxSelected>>", app.add_selected_tag)
    app.tag_combobox.bind("<Return>", app.add_selected_tag)
    app.tag_combobox.bind("<FocusOut>", app.add_selected_tag)
    app.selected_tags_container = tk.Frame(
        source,
        background="#2a2a2a",
        borderwidth=1,
        relief="solid",
        highlightthickness=0,
        highlightbackground="#404040",
        padx=6,
        pady=4,
    )
    app.selected_tags_container.grid(row=3, column=1, sticky="ew", padx=(10, 10), pady=(4, 0))
    app.tag_scan_button = ttk.Button(source, text="Find Tags…", command=app.scan_vault_tags)
    app.tag_scan_button.grid(row=2, column=2, sticky="ew", pady=(4, 0))

    folder_label = ttk.Label(source, text="Folders", style="FieldLabel.TLabel")
    folder_label.grid(row=4, column=0, sticky="nw", pady=(12, 0))
    attach_tooltip(
        folder_label,
        "Optionally limit the scan to specific folders inside the vault. "
        "Leave this empty to scan the whole vault.",
    )
    app.folder_filters_container = tk.Frame(
        source,
        background="#2a2a2a",
        borderwidth=1,
        relief="solid",
        highlightthickness=0,
        highlightbackground="#404040",
        padx=6,
        pady=4,
    )
    app.folder_filters_container.grid(row=4, column=1, sticky="ew", padx=(10, 10), pady=(4, 0))

    app.add_folder_button = ttk.Button(source, text="Add Folder…", command=app.add_folder_filter)
    app.add_folder_button.grid(row=4, column=2, sticky="ew", pady=(4, 0))

    formatting = ttk.LabelFrame(main, text="Card Formatting", padding=8)
    formatting.grid(row=1, column=0, sticky="ew", pady=(0, 8))
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
        pady=(4, 0),
    )
    attach_tooltip(
        skip_empty_checkbutton,
        "Skip notes whose cleaned definition is empty after tags and formatting markers are removed. "
        "This helps avoid blank or nearly blank cards.",
    )
    duplicate_frame = ttk.Frame(formatting)
    duplicate_frame.grid(row=1, column=1, sticky="w", pady=(4, 0))
    duplicate_label = ttk.Label(duplicate_frame, text="Duplicates", style="FieldLabel.TLabel")
    duplicate_label.grid(row=0, column=0, sticky="w")
    attach_tooltip(
        duplicate_label,
        "Choose what to do when multiple Obsidian notes would produce the same card front. "
        "Stop pauses before export or sync so you can review the duplicates. "
        "Keep first uses the first matching note and ignores the rest. "
        "Rename duplicates keeps them all and adds folder labels to make each front unique.",
    )
    app.duplicate_handling_combobox = ttk.Combobox(
        duplicate_frame,
        textvariable=app.duplicate_handling_display_var,
        values=DUPLICATE_HANDLING_DISPLAY_CHOICES,
        state="readonly",
        width=18,
    )
    app.duplicate_handling_combobox.grid(row=0, column=1, sticky="w", padx=(8, 0))
    app.duplicate_handling_combobox.bind("<<ComboboxSelected>>", app.on_duplicate_handling_change)
    attach_tooltip(
        app.duplicate_handling_combobox,
        "Choose what to do when multiple Obsidian notes would produce the same card front. "
        "Stop pauses before export or sync so you can review the duplicates. "
        "Keep first uses the first matching note and ignores the rest. "
        "Rename duplicates keeps them all and adds folder labels to make each front unique.",
    )
    app.sync_output_option_state()
    app.sync_html_option_state()

    anki_options = ttk.LabelFrame(main, text="Anki Sync", padding=8)
    anki_options.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    anki_options.columnconfigure(0, minsize=88)
    anki_options.columnconfigure(1, weight=1)
    anki_options.columnconfigure(2, minsize=88)
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

    deck_label = ttk.Label(anki_options, text="Deck", style="FieldLabel.TLabel")
    deck_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
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
    app.anki_deck_combobox.grid(row=1, column=1, sticky="ew", padx=(10, 10), pady=(4, 0))

    note_type_label = ttk.Label(anki_options, text="Note type", style="FieldLabel.TLabel")
    note_type_label.grid(row=1, column=2, sticky="w", pady=(4, 0))
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
    app.anki_note_type_combobox.grid(row=1, column=3, sticky="ew", pady=(4, 0))
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

    existing_notes_label = ttk.Label(anki_options, text="Existing notes", style="FieldLabel.TLabel")
    existing_notes_label.grid(row=2, column=0, sticky="w", pady=(4, 0))
    attach_tooltip(
        existing_notes_label,
        "Choose what happens when Anki already has a note with the same front. "
        "Update refreshes the existing Anki note with the latest Obsidian content. "
        "Skip leaves the existing Anki note unchanged.",
    )
    app.anki_existing_notes_combobox = ttk.Combobox(
        anki_options,
        textvariable=app.anki_existing_notes_var,
        values=ANKI_EXISTING_NOTE_CHOICES,
        state="readonly",
        width=10,
    )
    app.anki_existing_notes_combobox.grid(row=2, column=1, sticky="w", padx=(10, 10), pady=(4, 0))

    app.anki_connect_url_entry = ttk.Entry(anki_options, textvariable=app.anki_connect_url_var)
    app.anki_connect_url_entry.bind("<FocusOut>", app.on_anki_connect_url_change)
    app.anki_connect_url_entry.bind("<Return>", app.on_anki_connect_url_change)
    app.sync_anki_option_state()

    actions = ttk.Frame(main)
    actions.grid(row=3, column=0, sticky="ew", pady=(0, 8))
    actions.columnconfigure(0, weight=1)

    app.reset_button = ttk.Button(actions, text="Reset Settings", command=app.reset_settings)
    app.reset_button.grid(row=0, column=0, sticky="w")

    app.preview_button = ttk.Button(
        actions,
        text="Preview & Continue",
        command=app.start_preview,
        default="active",
        width=18,
    )
    app.preview_button.grid(row=0, column=1, sticky="e")

    status_frame = ttk.Frame(main)
    status_frame.grid(row=4, column=0, sticky="ew")
    status_frame.columnconfigure(0, weight=1)

    ttk.Separator(status_frame, orient="horizontal").grid(row=0, column=0, sticky="ew", pady=(0, 6))

    status_header = ttk.Frame(status_frame)
    status_header.grid(row=1, column=0, sticky="ew")
    status_header.columnconfigure(0, weight=1)
    ttk.Label(status_header, textvariable=app.status_var).grid(row=0, column=0, sticky="w")
    app.status_toggle_button = ttk.Button(
        status_header,
        textvariable=app.status_details_var,
        command=app.toggle_status_details,
    )
    app.status_toggle_button.grid(row=0, column=1, sticky="e")
    log_widget_kwargs = {
        "height": 8,
        "wrap": "word",
        "state": "disabled",
        "foreground": "#b9b9b9",
        "insertbackground": "#b9b9b9",
    }
    if log_font is not None:
        log_widget_kwargs["font"] = log_font
    log_widget_kwargs["height"] = 6
    app.log_widget = tk.Text(status_frame, **log_widget_kwargs)
    app.log_widget.grid(row=2, column=0, sticky="ew", pady=(6, 0))


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
