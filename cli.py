from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from common import (
    ANKI_EXISTING_NOTE_CHOICES,
    DUPLICATE_HANDLING_CHOICES,
    duplicate_handling_warning_message,
    effective_italicize_quoted_text,
    format_target_tags,
    normalize_anki_existing_notes,
    normalize_duplicate_handling,
    normalize_tag,
    validate_vault_path,
)
from delivery import deliver_cards
from gui import launch_gui
from gui_logic import delivery_complete_message, timing_breakdown_lines
from models import ExportError, ExportOptions
from reporting import attach_delivery_report
from scanner import build_duplicate_summary, normalize_folder_filters, scan_cards


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Obsidian #definition notes into an Anki-importable TSV file or sync them directly to Anki."
    )
    parser.add_argument("--vault", type=Path, help="Path to the root of the Obsidian vault.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output TSV file path. Optional when syncing directly to Anki.",
    )
    parser.add_argument(
        "--tag",
        default="definition",
        help="Tag to match, without the leading #. Default: definition",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Export card backs as simple HTML for nicer formatting in Anki.",
    )
    parser.add_argument(
        "--skip-empty",
        action="store_true",
        help="Skip notes whose cleaned body is empty.",
    )
    parser.add_argument(
        "--italicize-quoted-text",
        action="store_true",
        help="Italicize text inside double quotation marks when using HTML export.",
    )
    parser.add_argument(
        "--include-folder",
        action="append",
        default=[],
        help="Filter to one or more folders inside the vault. Repeat the option to include multiple folders.",
    )
    parser.add_argument(
        "--duplicate-handling",
        default="error",
        choices=DUPLICATE_HANDLING_CHOICES,
        help=(
            "How to handle duplicate card fronts. "
            "skip: keep the first, suffix: append folder-based suffixes, error: stop. "
            "Default: error"
        ),
    )
    parser.add_argument(
        "--anki",
        action="store_true",
        help="Sync matching notes directly to Anki via AnkiConnect.",
    )
    parser.add_argument(
        "--anki-connect-url",
        default="http://127.0.0.1:8765",
        help="AnkiConnect URL. Default: http://127.0.0.1:8765",
    )
    parser.add_argument(
        "--anki-deck",
        default="Default",
        help="Anki deck name for direct sync. Default: Default",
    )
    parser.add_argument(
        "--anki-note-type",
        default="Basic",
        help="Anki note type for direct sync. Default: Basic",
    )
    parser.add_argument(
        "--anki-front-field",
        default="Front",
        help="Field name for the card front when syncing to Anki. Default: Front",
    )
    parser.add_argument(
        "--anki-back-field",
        default="Back",
        help="Field name for the card back when syncing to Anki. Default: Back",
    )
    parser.add_argument(
        "--anki-existing-notes",
        default="skip",
        choices=ANKI_EXISTING_NOTE_CHOICES,
        help="How direct Anki sync should handle existing notes. Default: skip",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open the desktop UI.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    cli_args = list(argv) if argv is not None else sys.argv[1:]
    args = parse_args(cli_args)

    if args.gui or not cli_args:
        return launch_gui()

    if args.vault is None or (args.output is None and not args.anki):
        print(
            "Error: --vault and at least one of --output or --anki are required in command line mode.",
            file=sys.stderr,
        )
        return 2

    try:
        vault_path = validate_vault_path(args.vault)
        include_folders = normalize_folder_filters(args.include_folder, vault_path)
        duplicate_handling = normalize_duplicate_handling(args.duplicate_handling)
        anki_existing_notes = normalize_anki_existing_notes(args.anki_existing_notes)
    except ExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    options = ExportOptions(
        vault_path=vault_path,
        output_path=args.output.expanduser().resolve() if args.output is not None else None,
        target_tag=normalize_tag(args.tag),
        html_output=args.html,
        skip_empty=args.skip_empty,
        italicize_quoted_text=effective_italicize_quoted_text(
            args.html,
            args.italicize_quoted_text,
        ),
        include_folders=include_folders,
        duplicate_handling=duplicate_handling,
        sync_to_anki=args.anki,
        anki_connect_url=args.anki_connect_url,
        anki_deck=args.anki_deck,
        anki_note_type=args.anki_note_type,
        anki_front_field=args.anki_front_field,
        anki_back_field=args.anki_back_field,
        anki_existing_notes=anki_existing_notes,
    )

    try:
        scan_result = scan_cards(options, preview_limit=0)
        if scan_result.duplicate_fronts:
            print(
                "Warning: "
                + duplicate_handling_warning_message(
                    options.duplicate_handling,
                    len(scan_result.duplicate_fronts),
                ),
                file=sys.stderr,
            )
            print(build_duplicate_summary(scan_result.duplicate_fronts), file=sys.stderr)
        delivery_result = deliver_cards(options, scan_result.cards)
        delivery_result = attach_delivery_report(options, scan_result, delivery_result)
    except (ExportError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if scan_result.total_matches == 0:
        print(
            f"No notes tagged with {format_target_tags(options.target_tag, options.additional_target_tags)} were found."
        )
        return 0

    print(
        delivery_complete_message(
            options,
            delivery_result,
            len(scan_result.duplicate_fronts),
        )
    )
    for line in timing_breakdown_lines(scan_result, delivery_result):
        print(line)
    if delivery_result.report_text is not None:
        print(delivery_result.report_text, end="")
    return 0
