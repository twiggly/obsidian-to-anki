from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from ..anki.sync import normalize_anki_connect_url
from ..common import (
    duplicate_handling_warning_message,
    effective_italicize_quoted_text,
    format_target_tags,
    normalize_anki_existing_notes,
    normalize_duplicate_handling,
    normalize_target_tags,
    validate_vault_path,
)
from ..models import DeliveryResult, ExportError, ExportOptions, ScanResult
from ..scanner import normalize_folder_filters


class FormValidationError(Exception):
    def __init__(self, title: str, message: str) -> None:
        super().__init__(message)
        self.title = title
        self.message = message


def build_tag_scan_request(
    vault: str,
    raw_folder_filters: Sequence[str],
) -> tuple[Path, tuple[str, ...]]:
    vault_value = vault.strip()
    if not vault_value:
        raise FormValidationError("Missing vault", "Choose an Obsidian vault folder.")

    try:
        vault_path = validate_vault_path(Path(vault_value))
    except ExportError as exc:
        raise FormValidationError("Invalid vault", str(exc)) from exc

    try:
        include_folders = normalize_folder_filters(raw_folder_filters, vault_path)
    except ExportError as exc:
        raise FormValidationError("Invalid folder filter", str(exc)) from exc

    return vault_path, include_folders


def build_export_options_from_values(
    vault: str,
    output: str,
    tag: str | Sequence[str],
    html_output: bool,
    skip_empty: bool,
    italicize_quoted_text: bool,
    raw_folder_filters: Sequence[str],
    duplicate_handling: str,
    sync_to_anki: bool,
    anki_connect_url: str,
    anki_deck: str,
    anki_note_type: str,
    anki_front_field: str,
    anki_back_field: str,
    anki_existing_notes: str = "skip",
    write_tsv: bool = True,
    flatten_note_links: bool = True,
) -> ExportOptions:
    vault_value = vault.strip()
    output_value = output.strip()
    raw_tags = [tag] if isinstance(tag, str) else list(tag)

    if not vault_value:
        raise FormValidationError("Missing vault", "Choose an Obsidian vault folder.")

    if not any(str(value).strip() for value in raw_tags):
        raise FormValidationError("Missing tags", "Choose at least one tag to match.")

    target_tags = normalize_target_tags(tag)

    if write_tsv and not output_value:
        raise FormValidationError(
            "Missing destination",
            "Choose where to save the TSV file or turn off TSV export.",
        )

    if not write_tsv and not sync_to_anki:
        raise FormValidationError(
            "Missing destination",
            "Turn on TSV export or enable direct Anki sync.",
        )

    try:
        vault_path = validate_vault_path(Path(vault_value))
    except ExportError as exc:
        raise FormValidationError("Invalid vault", str(exc)) from exc

    try:
        include_folders = normalize_folder_filters(raw_folder_filters, vault_path)
    except ExportError as exc:
        raise FormValidationError("Invalid folder filter", str(exc)) from exc

    try:
        normalized_duplicate_handling = normalize_duplicate_handling(duplicate_handling)
    except ExportError as exc:
        raise FormValidationError("Invalid duplicate handling", str(exc)) from exc

    try:
        normalized_anki_existing_notes = normalize_anki_existing_notes(anki_existing_notes)
    except ExportError as exc:
        raise FormValidationError("Invalid Anki setting", str(exc)) from exc

    output_path = Path(output_value).expanduser().resolve() if write_tsv and output_value else None

    if sync_to_anki:
        try:
            normalized_anki_connect_url = normalize_anki_connect_url(anki_connect_url)
        except ExportError as exc:
            raise FormValidationError("Missing AnkiConnect URL", str(exc)) from exc
        if not anki_deck.strip():
            raise FormValidationError("Missing Anki deck", "Enter an Anki deck name.")
        if not anki_note_type.strip():
            raise FormValidationError("Missing Anki note type", "Enter an Anki note type.")
        if not anki_front_field.strip():
            raise FormValidationError("Missing front field", "Enter the Anki front field name.")
        if not anki_back_field.strip():
            raise FormValidationError("Missing back field", "Enter the Anki back field name.")
    else:
        normalized_anki_connect_url = normalize_anki_connect_url("http://127.0.0.1:8765")

    return ExportOptions(
        vault_path=vault_path,
        output_path=output_path,
        target_tag=target_tags[0],
        additional_target_tags=target_tags[1:],
        html_output=html_output,
        skip_empty=True,
        italicize_quoted_text=effective_italicize_quoted_text(
            html_output,
            italicize_quoted_text,
        ),
        flatten_note_links=flatten_note_links,
        include_folders=include_folders,
        duplicate_handling=normalized_duplicate_handling,
        sync_to_anki=sync_to_anki,
        anki_connect_url=normalized_anki_connect_url,
        anki_deck=anki_deck.strip() or "Default",
        anki_note_type=anki_note_type.strip() or "Basic",
        anki_front_field=anki_front_field.strip() or "Front",
        anki_back_field=anki_back_field.strip() or "Back",
        anki_existing_notes=normalized_anki_existing_notes,
    )


def format_include_folders(include_folders: Sequence[str]) -> str:
    if not include_folders:
        return ""
    if len(include_folders) == 1:
        return f" in {include_folders[0]}"
    return " in " + ", ".join(include_folders[:-1]) + f", and {include_folders[-1]}"


def preview_no_matches_message(
    tag: str,
    additional_tags: Sequence[str] = (),
    include_folders: Sequence[str] = (),
) -> str:
    return (
        f"No notes tagged with {format_target_tags(tag, additional_tags)} were found"
        f"{format_include_folders(include_folders)}."
    )


def preview_ready_message(scan_result: ScanResult) -> str:
    preview_count = len(scan_result.preview_cards)
    return f"Preview ready. Showing the first {preview_count} of {scan_result.total_matches} matching cards."


def format_seconds(seconds: float) -> str:
    return f"{seconds:.2f}s"


def timing_breakdown_lines(
    scan_result: ScanResult,
    delivery_result: DeliveryResult | None = None,
) -> list[str]:
    summary_parts = [f"scan {format_seconds(scan_result.scan_seconds)}"]

    if delivery_result is None:
        return [f"Timing: {', '.join(summary_parts)}"]

    if delivery_result.output_path is not None:
        summary_parts.append(f"export {format_seconds(delivery_result.export_seconds)}")

    detail_parts: list[str] = []
    if delivery_result.sync_result is not None:
        timing = delivery_result.sync_result.timing
        summary_parts.append(f"sync {format_seconds(timing.total_seconds)}")
        detail_parts.append(f"validate {format_seconds(timing.validation_seconds)}")
        if timing.existing_lookup_seconds > 0:
            detail_parts.append(f"lookup {format_seconds(timing.existing_lookup_seconds)}")
        detail_parts.append(f"check duplicates {format_seconds(timing.can_add_seconds)}")
        detail_parts.append(f"write changes {format_seconds(timing.write_seconds)}")

    summary_parts.append(f"total {format_seconds(delivery_result.total_seconds)}")
    lines = [f"Timing: {', '.join(summary_parts)}"]
    if detail_parts:
        lines.append(f"Anki sync: {', '.join(detail_parts)}")
    return lines


def recommended_deck_settings_confirmation_message(deck_name: str, preset_name: str) -> str:
    return (
        f"Apply the recommended deck settings to '{deck_name}'?\n\n"
        f"This will create or update the preset '{preset_name}' and assign it to that deck.\n\n"
        "It will set:\n"
        "• learning steps: 1m 10m\n"
        "• relearning step: 10m\n"
        "• new cards/day: 10\n"
        "• max reviews/day: 200\n"
        "• new gather order: Random notes\n"
        "• new sort order: Card type, then random\n"
        "• review sort order: Due date, then random\n"
        "• bury new siblings: on\n"
        "• bury review siblings: on"
    )


def duplicate_front_warning_message(
    duplicate_fronts: dict[str, tuple[Path, ...]],
    duplicate_handling: str,
) -> str | None:
    if not duplicate_fronts:
        return None

    duplicate_count = len(duplicate_fronts)
    return (
        f"{duplicate_popup_intro_message(duplicate_handling, duplicate_count)}\n\n"
        f"{build_duplicate_folder_summary(duplicate_fronts, duplicate_handling)}"
    )


def duplicate_popup_intro_message(duplicate_handling: str, duplicate_count: int) -> str:
    noun = "front" if duplicate_count == 1 else "fronts"
    summary = f"{duplicate_count} duplicate {noun} found."

    if duplicate_handling == "skip":
        behavior = "Current handling: keep the first matching note and ignore the rest."
    elif duplicate_handling == "suffix":
        behavior = "Current handling: keep all matching notes and add folder suffixes to each front."
    elif duplicate_handling == "error":
        behavior = "Current handling: stop before export or sync until the duplicates are resolved."
    else:
        behavior = "Current handling: keep all duplicate notes."

    return f"{summary}\nThese fronts appear in more than one note.\n{behavior}"


def build_duplicate_folder_summary(
    duplicate_fronts: dict[str, tuple[Path, ...]],
    duplicate_handling: str,
) -> str:
    lines: list[str] = []

    for front, paths in duplicate_fronts.items():
        labels = duplicate_parent_folder_labels(paths)
        lines.append(f"\u2022 {front} ({len(paths)} matches)")
        lines.append(f"  Found in: {', '.join(labels)}")
        if duplicate_handling == "suffix":
            renamed_fronts = ", ".join(f"{front} ({label})" for label in labels)
            if renamed_fronts:
                lines.append(f"  Will become: {renamed_fronts}")

    return "\n".join(lines)


def duplicate_parent_folder_labels(paths: Sequence[Path]) -> list[str]:
    if not paths:
        return []

    parent_paths = [path.parent for path in paths]
    common_parent = Path(os.path.commonpath(parent_paths))
    labels: list[str] = []

    for parent_path in parent_paths:
        try:
            relative_parent = parent_path.relative_to(common_parent).as_posix()
        except ValueError:
            relative_parent = ""

        if relative_parent and relative_parent != ".":
            labels.append(relative_parent)
            continue

        if parent_path.name:
            labels.append(parent_path.name)
            continue

        labels.append(parent_path.as_posix())

    return labels


def export_no_cards_message(
    tag: str,
    additional_tags: Sequence[str] = (),
    include_folders: Sequence[str] = (),
) -> str:
    return (
        f"No notes tagged with {format_target_tags(tag, additional_tags)} were found"
        f"{format_include_folders(include_folders)}."
    )


def delivery_action_label(options: ExportOptions) -> str:
    if options.output_path is not None and options.sync_to_anki:
        return "Export & Sync"
    if options.sync_to_anki:
        return "Sync to Anki"
    return "Export"


def delivery_progress_message(options: ExportOptions) -> str:
    if options.output_path is not None and options.sync_to_anki:
        return "Exporting and syncing cards…"
    if options.sync_to_anki:
        return "Syncing cards to Anki…"
    return "Exporting cards…"


def delivery_complete_title(options: ExportOptions) -> str:
    if options.output_path is not None and options.sync_to_anki:
        return "Export & Sync complete"
    if options.sync_to_anki:
        return "Sync complete"
    return "Export complete"


def delivery_complete_message(
    options: ExportOptions,
    delivery_result: DeliveryResult,
    duplicate_count: int,
) -> str:
    message_parts: list[str] = []
    if delivery_result.export_count and delivery_result.output_path is not None:
        message_parts.append(f"Exported {delivery_result.export_count} cards to: {delivery_result.output_path}")

    if delivery_result.sync_result is not None:
        sync_result = delivery_result.sync_result
        if sync_result.added_count:
            sync_message = (
                f"Synced {sync_result.added_count} cards to Anki deck '{sync_result.deck_name}' "
                f"using note type '{sync_result.note_type}'."
            )
        elif sync_result.updated_count:
            sync_message = (
                f"Updated {sync_result.updated_count} existing Anki notes in deck '{sync_result.deck_name}' "
                f"using note type '{sync_result.note_type}'."
            )
        else:
            sync_message = f"No new Anki notes were added to deck '{sync_result.deck_name}'."
        if sync_result.updated_count and sync_result.added_count:
            sync_message += f" Updated {sync_result.updated_count} existing notes."
        if sync_result.skipped_count:
            sync_message += f" Skipped {sync_result.skipped_count} existing notes."
        message_parts.append(sync_message)

    message = " ".join(message_parts) or "Completed processing cards."
    if duplicate_count:
        message += f" {duplicate_handling_warning_message(options.duplicate_handling, duplicate_count)}"
    return message
