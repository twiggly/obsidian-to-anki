from __future__ import annotations

from typing import Callable

from models import DeliveryResult, ExportOptions, ScanResult


def set_busy(app: object, busy: bool) -> None:
    app.is_busy = busy
    if busy:
        app.preview_button.state(["disabled"])
        app.reset_button.state(["disabled"])
        app.tag_scan_button.state(["disabled"])
        app.add_folder_button.state(["disabled"])
    else:
        app.preview_button.state(["!disabled"])
        app.reset_button.state(["!disabled"])
        app.tag_scan_button.state(["!disabled"])
        app.add_folder_button.state(["!disabled"])
    app.set_selected_tags_in_listbox(app.get_selected_tags_from_listbox())
    app.set_folder_filters_in_listbox(app.get_folder_filters_from_listbox())


def log(app: object, message: str) -> None:
    app.log_widget.configure(state="normal")
    app.log_widget.insert("end", message + "\n")
    app.log_widget.see("end")
    app.log_widget.configure(state="disabled")


def start_preview(
    app: object,
    *,
    replace_options: Callable[..., ExportOptions],
    format_target_tags: Callable[[str, tuple[str, ...]], str],
    start_preview_scan: Callable[..., None],
) -> None:
    if app.is_busy:
        return

    options = app.build_options_from_form()
    if options is None:
        return

    app.set_busy(True)
    app.status_var.set("Generating preview…")
    app.log(
        f"Generating preview for {format_target_tags(options.target_tag, options.additional_target_tags)}"
    )
    preview_options = (
        replace_options(options, duplicate_handling="warn")
        if options.duplicate_handling == "error"
        else options
    )
    start_preview_scan(
        app.root,
        preview_options,
        lambda _completed_options, scan_result: app.finish_preview_success(options, scan_result),
        app.finish_preview_error,
    )


def finish_preview_success(
    app: object,
    options: ExportOptions,
    scan_result: ScanResult,
    *,
    preview_no_matches_message: Callable[[str, tuple[str, ...], tuple[str, ...]], str],
    preview_ready_message: Callable[[ScanResult], str],
    timing_breakdown_lines: Callable[[ScanResult, DeliveryResult | None], list[str]],
    duplicate_front_warning_message: Callable[[dict[str, tuple[object, ...]], str], str | None],
    show_preview_dialog: Callable[..., None],
    delivery_action_label: Callable[[ExportOptions], str],
    messagebox_module: object,
) -> None:
    app.set_busy(False)
    if scan_result.total_matches == 0:
        message = preview_no_matches_message(
            options.target_tag,
            options.additional_target_tags,
            options.include_folders,
        )
        app.status_var.set(message)
        app.log(message)
        messagebox_module.showinfo("No matching cards", message)
        return

    message = preview_ready_message(scan_result)
    app.status_var.set(message)
    app.log(message)
    for line in timing_breakdown_lines(scan_result, None):
        app.log(line)

    warning_message = duplicate_front_warning_message(
        scan_result.duplicate_fronts,
        options.duplicate_handling,
    )
    if warning_message is not None:
        duplicate_count = len(scan_result.duplicate_fronts)
        app.log(f"Detected {duplicate_count} duplicate fronts.")
        messagebox_module.showwarning("Duplicate fronts detected", warning_message)
        if options.duplicate_handling == "error":
            stop_message = "Duplicate fronts detected. Resolve them or choose skip or suffix to continue."
            app.status_var.set(stop_message)
            app.log(stop_message)
            return

    show_preview_dialog(
        app.root,
        options,
        scan_result,
        on_confirm=lambda: app.begin_delivery(options, scan_result),
        action_label=delivery_action_label(options),
    )


def finish_preview_error(
    app: object,
    error_message: str,
    details: str | None = None,
    *,
    messagebox_module: object,
) -> None:
    app.set_busy(False)
    app.status_var.set(error_message)
    if details is None:
        app.log(f"Error: {error_message}")
    else:
        app.log(error_message)
        app.log(details.rstrip())
    messagebox_module.showerror("Preview failed", error_message)


def begin_delivery(
    app: object,
    options: ExportOptions,
    scan_result: ScanResult,
    *,
    delivery_action_label: Callable[[ExportOptions], str],
    delivery_progress_message: Callable[[ExportOptions], str],
    format_target_tags: Callable[[str, tuple[str, ...]], str],
    start_delivery: Callable[..., None],
) -> None:
    if app.is_busy:
        return

    app.set_busy(True)
    progress_message = delivery_progress_message(options)
    app.status_var.set(progress_message)
    app.log(
        f"Starting {delivery_action_label(options).lower()} for "
        f"{format_target_tags(options.target_tag, options.additional_target_tags)}"
    )
    start_delivery(
        app.root,
        options,
        scan_result,
        app.finish_delivery_success,
        app.finish_delivery_error,
    )


def finish_delivery_success(
    app: object,
    options: ExportOptions,
    scan_result: ScanResult,
    delivery_result: DeliveryResult,
    *,
    export_no_cards_message: Callable[[str, tuple[str, ...], tuple[str, ...]], str],
    delivery_complete_message: Callable[[ExportOptions, DeliveryResult, int], str],
    delivery_complete_title: Callable[[ExportOptions], str],
    timing_breakdown_lines: Callable[[ScanResult, DeliveryResult | None], list[str]],
    messagebox_module: object,
) -> None:
    app.set_busy(False)
    if scan_result.total_matches == 0:
        message = export_no_cards_message(
            options.target_tag,
            options.additional_target_tags,
            options.include_folders,
        )
        app.status_var.set(message)
        app.log(message)
        messagebox_module.showinfo("No cards exported", message)
        return

    message = delivery_complete_message(
        options,
        delivery_result,
        len(scan_result.duplicate_fronts),
    )
    app.status_var.set(message)
    app.log(message)
    for line in timing_breakdown_lines(scan_result, delivery_result):
        app.log(line)
    if delivery_result.report_text is not None:
        for line in delivery_result.report_text.rstrip().splitlines():
            app.log(line)
    messagebox_module.showinfo(delivery_complete_title(options), message)


def finish_delivery_error(
    app: object,
    error_message: str,
    details: str | None = None,
    *,
    messagebox_module: object,
) -> None:
    app.set_busy(False)
    app.status_var.set(error_message)
    if details is None:
        app.log(f"Error: {error_message}")
    else:
        app.log(error_message)
        app.log(details.rstrip())
    messagebox_module.showerror("Delivery failed", error_message)
