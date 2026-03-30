from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

if TYPE_CHECKING:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import ttk
else:
    try:
        import tkinter as tk
        import tkinter.font as tkfont
        from tkinter import ttk
    except ImportError:
        tk = None
        tkfont = None
        ttk = None


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


def build_status_section(app: object, parent: object, *, row: int, log_font: object | None) -> object:
    if tk is None or ttk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    status_frame = ttk.Frame(parent)
    status_frame.grid(row=row, column=0, sticky="ew")
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
        "height": 6,
        "wrap": "word",
        "state": "disabled",
        "foreground": "#b9b9b9",
        "insertbackground": "#b9b9b9",
    }
    if log_font is not None:
        log_widget_kwargs["font"] = log_font
    app.log_widget = tk.Text(status_frame, **log_widget_kwargs)
    app.log_widget.grid(row=2, column=0, sticky="ew", pady=(6, 0))
    return status_frame
