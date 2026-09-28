from __future__ import annotations

from dataclasses import replace

from .common import duplicate_handling_warning_message
from .models import DeliveryResult, ExportOptions, ScanResult


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


def delivery_complete_message(
    options: ExportOptions,
    delivery_result: DeliveryResult,
    duplicate_count: int,
) -> str:
    message_parts: list[str] = []
    if delivery_result.export_count and delivery_result.output_path is not None:
        message_parts.append(
            f"Exported {delivery_result.export_count} cards to: {delivery_result.output_path}"
        )

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
        message += (
            f" {duplicate_handling_warning_message(options.duplicate_handling, duplicate_count)}"
        )
    return message


def build_delivery_report(
    options: ExportOptions,
    scan_result: ScanResult,
    delivery_result: DeliveryResult,
) -> str | None:
    lines: list[str] = []

    if scan_result.duplicate_fronts:
        lines.append("Duplicate fronts detected:")
        for front, paths in scan_result.duplicate_fronts.items():
            lines.append(f"- {front}")
            for path in paths:
                lines.append(f"  - {path}")
            resolved_fronts = scan_result.duplicate_resolutions.get(front, ())
            if resolved_fronts:
                lines.append(f"  - resolved as: {', '.join(resolved_fronts)}")
        lines.append("")

    sync_result = delivery_result.sync_result
    if sync_result is not None and sync_result.skipped_fronts:
        lines.append("Existing Anki notes skipped:")
        for front in sync_result.skipped_fronts:
            lines.append(f"- {front}")
        lines.append("")

    if sync_result is not None and sync_result.updated_fronts:
        lines.append("Existing Anki notes updated:")
        for front in sync_result.updated_fronts:
            lines.append(f"- {front}")
        lines.append("")

    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return None
    return "\n".join(lines) + "\n"


def attach_delivery_report(
    options: ExportOptions,
    scan_result: ScanResult,
    delivery_result: DeliveryResult,
) -> DeliveryResult:
    report_text = build_delivery_report(options, scan_result, delivery_result)
    if report_text is None:
        return delivery_result

    return replace(delivery_result, report_text=report_text)
