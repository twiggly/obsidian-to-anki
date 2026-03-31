from __future__ import annotations

from dataclasses import replace

from .models import DeliveryResult, ExportOptions, ScanResult


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
