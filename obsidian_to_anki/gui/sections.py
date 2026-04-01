from __future__ import annotations

from typing import TYPE_CHECKING

from ..anki.sync import OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME
from ..common import ANKI_EXISTING_NOTE_CHOICES, DUPLICATE_HANDLING_DISPLAY_CHOICES
from .widgets import attach_tooltip, chip_tray_frame_kwargs

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


def build_source_section(app: object, parent: object) -> object:
    if tk is None or ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    source = ttk.LabelFrame(parent, text="Source", padding=8)
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
    app.selected_tags_container = tk.Frame(source, **chip_tray_frame_kwargs(source))
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
    app.folder_filters_container = tk.Frame(source, **chip_tray_frame_kwargs(source))
    app.folder_filters_container.grid(row=4, column=1, sticky="ew", padx=(10, 10), pady=(4, 0))

    app.add_folder_button = ttk.Button(source, text="Add Folder…", command=app.add_folder_filter)
    app.add_folder_button.grid(row=4, column=2, sticky="ew", pady=(4, 0))
    return source


def build_formatting_section(app: object, parent: object) -> object:
    if ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    formatting = ttk.LabelFrame(parent, text="Card Formatting", padding=8)
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
        text="Italicize quotes",
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
    skip_empty_checkbutton.grid(row=1, column=0, sticky="w", pady=(4, 0))
    attach_tooltip(
        skip_empty_checkbutton,
        "Skip notes whose cleaned definition is empty after tags and formatting markers are removed. "
        "This helps avoid blank or nearly blank cards.",
    )
    duplicate_frame = ttk.Frame(formatting)
    duplicate_frame.grid(row=1, column=1, sticky="w", pady=(4, 0))
    duplicate_label = ttk.Label(duplicate_frame, text="Duplicates", style="FieldLabel.TLabel")
    duplicate_label.grid(row=0, column=0, sticky="w")
    duplicate_tooltip = (
        "Choose what to do when multiple Obsidian notes would produce the same card front. "
        "Stop pauses before export or sync so you can review the duplicates. "
        "Keep first uses the first matching note and ignores the rest. "
        "Rename duplicates keeps them all and adds folder labels to make each front unique."
    )
    attach_tooltip(duplicate_label, duplicate_tooltip)
    app.duplicate_handling_combobox = ttk.Combobox(
        duplicate_frame,
        textvariable=app.duplicate_handling_display_var,
        values=DUPLICATE_HANDLING_DISPLAY_CHOICES,
        state="readonly",
        width=18,
    )
    app.duplicate_handling_combobox.grid(row=0, column=1, sticky="w", padx=(8, 0))
    app.duplicate_handling_combobox.bind("<<ComboboxSelected>>", app.on_duplicate_handling_change)
    attach_tooltip(app.duplicate_handling_combobox, duplicate_tooltip)
    return formatting


def build_anki_section(app: object, parent: object) -> object:
    if ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    anki_options = ttk.LabelFrame(parent, text="Anki Sync", padding=8)
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

    app.install_note_type_button = ttk.Button(
        anki_options,
        text=f"Install {OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME}",
        command=app.install_obsidian_definitions_note_type,
    )
    app.install_note_type_button.grid(row=2, column=2, columnspan=2, sticky="e", pady=(4, 0))
    attach_tooltip(
        app.install_note_type_button,
        f"Install or update the bundled '{OBSIDIAN_DEFINITIONS_NOTE_TYPE_NAME}' note type in Anki. "
        "It uses the standard Front and Back fields, includes your custom styling, "
        "and creates both forward and reverse definition cards.",
    )

    app.apply_deck_settings_button = ttk.Button(
        anki_options,
        text="Use Recommended Deck Settings",
        command=app.apply_recommended_deck_settings,
    )
    app.apply_deck_settings_button.grid(row=3, column=2, columnspan=2, sticky="e", pady=(4, 0))
    attach_tooltip(
        app.apply_deck_settings_button,
        "Create or update a dedicated Anki deck preset for the selected deck. "
        "It applies the recommended learning steps, daily limits, and sibling burying settings for these cards.",
    )

    app.anki_connect_url_entry = ttk.Entry(anki_options, textvariable=app.anki_connect_url_var)
    app.anki_connect_url_entry.bind("<FocusOut>", app.on_anki_connect_url_change)
    app.anki_connect_url_entry.bind("<Return>", app.on_anki_connect_url_change)
    return anki_options


def build_actions_section(app: object, parent: object) -> object:
    if ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    actions = ttk.Frame(parent)
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
    return actions
