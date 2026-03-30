from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from models import NoteCard

if TYPE_CHECKING:
    import tkinter as tk


def html_to_preview_text(text: str) -> str:
    preview = text
    preview = preview.replace("<br>", "\n")
    preview = preview.replace("</li>", "\n")
    preview = preview.replace("<li>", "• ")
    preview = preview.replace("<ul>", "")
    preview = preview.replace("</ul>", "")
    preview = re.sub(r"<div(?:\s+[^>]*)?>", "", preview)
    preview = preview.replace("</div>", "\n\n")
    preview = preview.replace("<pre><code>", "")
    preview = preview.replace("</code></pre>", "")
    preview = re.sub(r"</?(?:em|strong|code)>", "", preview)
    preview = re.sub(r"<[^>]+>", "", preview)
    preview = html.unescape(preview)
    preview = re.sub(r"\n{3,}", "\n\n", preview)
    return preview.strip()


def preview_sections_for_card(card: NoteCard, html_output: bool = False) -> list[tuple[str, str]]:
    back = html_to_preview_text(card.back) if html_output else card.back
    tags = " ".join(card.tags)
    sections = [("Front:", card.front), ("Back:", back)]
    if tags:
        sections.append(("Tags:", tags))
    sections.append(("Source:", str(card.source_path)))
    return sections


def populate_preview_text_widget(widget: tk.Text, card: NoteCard, html_output: bool = False) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.tag_configure("label", font=("TkDefaultFont", 10, "bold"))

    sections = preview_sections_for_card(card, html_output=html_output)
    for index, (label, content) in enumerate(sections):
        widget.insert("end", label + "\n", "label")
        widget.insert("end", content)
        if index < len(sections) - 1:
            widget.insert("end", "\n\n")

    widget.configure(state="disabled")
