from __future__ import annotations

import html
import re
import uuid
from typing import Sequence

from .common import (
    BOLD_PATTERN,
    FENCED_BLOCK_PATTERN,
    INLINE_CODE_PATTERN,
    ITALIC_PATTERN,
    LIST_ITEM_PATTERN,
    PART_OF_SPEECH_LABELS,
    QUOTED_ITALIC_PATTERN,
    TRAILING_PART_OF_SPEECH_QUALIFIER_PATTERN,
    make_placeholder,
)


def markdownish_to_html(text: str, italicize_quoted_text: bool = False) -> str:
    text = text.strip()
    if not text:
        return ""

    block_token = uuid.uuid4().hex
    code_blocks: list[str] = []

    def block_placeholder(index: int) -> str:
        return make_placeholder("BLOCK", block_token, index)

    def stash_code_block(match: re.Match[str]) -> str:
        placeholder = block_placeholder(len(code_blocks))
        code_content = match.group(3)
        code_blocks.append(f"<pre><code>{html.escape(code_content)}</code></pre>")
        return f"{match.group(1)}{placeholder}"

    text = FENCED_BLOCK_PATTERN.sub(stash_code_block, text)

    paragraphs: list[str] = []
    block_placeholders = {block_placeholder(index) for index in range(len(code_blocks))}
    current_dictionary_entry: tuple[str, list[list[str]]] | None = None

    def flush_current_dictionary_entry() -> None:
        nonlocal current_dictionary_entry
        if current_dictionary_entry is None:
            return

        part_of_speech, body_blocks = current_dictionary_entry
        entry_html = render_dictionary_entry_blocks(
            part_of_speech,
            body_blocks,
            italicize_quoted_text=italicize_quoted_text,
        )
        if entry_html is not None:
            paragraphs.append(entry_html)
        current_dictionary_entry = None

    for block in re.split(r"\n\s*\n", text):
        stripped_block = block.strip()
        if not stripped_block:
            continue

        if stripped_block in block_placeholders:
            flush_current_dictionary_entry()
            paragraphs.append(stripped_block)
            continue

        lines = [line.rstrip() for line in stripped_block.splitlines() if line.strip()]
        if not lines:
            continue

        if is_part_of_speech_label(lines[0]):
            flush_current_dictionary_entry()
            entry_ranges = dictionary_entry_ranges(lines)
            if entry_ranges is None:
                continue

            for start, end in entry_ranges[:-1]:
                entry_html = render_dictionary_entry(
                    lines[start:end],
                    italicize_quoted_text=italicize_quoted_text,
                )
                if entry_html is not None:
                    paragraphs.append(entry_html)

            last_start, last_end = entry_ranges[-1]
            last_entry_lines = lines[last_start:last_end]
            current_dictionary_entry = (
                last_entry_lines[0].strip(),
                [list(last_entry_lines[1:])],
            )
            continue

        if current_dictionary_entry is not None:
            current_dictionary_entry[1].append(lines)
            continue

        paragraphs.extend(render_block_segments(lines, italicize_quoted_text=italicize_quoted_text))

    flush_current_dictionary_entry()

    output = "\n".join(paragraphs)
    for index, code_html in enumerate(code_blocks):
        output = output.replace(block_placeholder(index), code_html)

    return output


def render_inline_text(text: str, italicize_quoted_text: bool = False) -> str:
    return inline_formatting(html.escape(text), italicize_quoted_text=italicize_quoted_text)


def render_block_segments(
    lines: Sequence[str],
    italicize_quoted_text: bool = False,
    text_class: str | None = None,
) -> list[str]:
    segment_parts: list[str] = []
    text_lines: list[str] = []
    list_items: list[str] = []
    text_wrapper = f'<div class="{text_class}">{{}}</div>' if text_class else "<div>{}</div>"

    def flush_text_lines() -> None:
        nonlocal text_lines
        if not text_lines:
            return
        joined = "<br>".join(
            render_inline_text(line.strip(), italicize_quoted_text=italicize_quoted_text)
            for line in text_lines
        )
        segment_parts.append(text_wrapper.format(joined))
        text_lines = []

    def flush_list_items() -> None:
        nonlocal list_items
        if not list_items:
            return
        items = "".join(f"<li>{item}</li>" for item in list_items)
        segment_parts.append(f"<ul>{items}</ul>")
        list_items = []

    for line in lines:
        match = LIST_ITEM_PATTERN.match(line)
        if match:
            flush_text_lines()
            list_items.append(
                render_inline_text(match.group(1).strip(), italicize_quoted_text=italicize_quoted_text)
            )
        else:
            flush_list_items()
            text_lines.append(line)

    flush_text_lines()
    flush_list_items()
    return segment_parts


def dictionary_entry_ranges(lines: Sequence[str]) -> list[tuple[int, int]] | None:
    if not lines or not is_part_of_speech_label(lines[0]):
        return None

    entry_boundaries = [0]
    for index in range(1, len(lines)):
        if not is_part_of_speech_label(lines[index]):
            continue
        if index + 1 >= len(lines):
            continue
        if LIST_ITEM_PATTERN.match(lines[index + 1]):
            continue
        entry_boundaries.append(index)

    entry_boundaries.append(len(lines))
    return list(zip(entry_boundaries, entry_boundaries[1:]))


def render_dictionary_entries(lines: Sequence[str], italicize_quoted_text: bool = False) -> list[str] | None:
    entry_ranges = dictionary_entry_ranges(lines)
    if entry_ranges is None:
        return None

    entries: list[str] = []
    for start, end in entry_ranges:
        entry_html = render_dictionary_entry(lines[start:end], italicize_quoted_text=italicize_quoted_text)
        if entry_html is None:
            return None
        entries.append(entry_html)

    return entries


def render_dictionary_entry(lines: Sequence[str], italicize_quoted_text: bool = False) -> str | None:
    if len(lines) < 2:
        return None

    part_of_speech = lines[0].strip()
    return render_dictionary_entry_blocks(
        part_of_speech,
        [list(lines[1:])],
        italicize_quoted_text=italicize_quoted_text,
    )


def render_dictionary_entry_blocks(
    part_of_speech: str,
    body_blocks: Sequence[Sequence[str]],
    italicize_quoted_text: bool = False,
) -> str | None:
    if not is_part_of_speech_label(part_of_speech):
        return None

    entry_parts: list[str] = []
    for block_lines in body_blocks:
        body_segments = render_block_segments(
            block_lines,
            italicize_quoted_text=italicize_quoted_text,
            text_class="gloss",
        )
        if not body_segments:
            continue
        entry_parts.extend(body_segments)

    if not entry_parts:
        return None

    pos_html = render_inline_text(part_of_speech, italicize_quoted_text=italicize_quoted_text)
    return f'<div class="dictionary-entry"><div class="pos">{pos_html}</div>{"".join(entry_parts)}</div>'


def is_part_of_speech_label(label: str) -> bool:
    return normalize_part_of_speech_label(label) in PART_OF_SPEECH_LABELS


def normalize_part_of_speech_label(label: str) -> str:
    normalized = label.strip()
    while True:
        without_qualifier = TRAILING_PART_OF_SPEECH_QUALIFIER_PATTERN.sub("", normalized)
        if without_qualifier == normalized:
            break
        normalized = without_qualifier

    return re.sub(r"\s+", " ", normalized).casefold()


def inline_formatting(text: str, italicize_quoted_text: bool = False) -> str:
    span_token = uuid.uuid4().hex
    code_spans: list[str] = []

    def span_placeholder(index: int) -> str:
        return make_placeholder("SPAN", span_token, index)

    def stash_code_span(match: re.Match[str]) -> str:
        placeholder = span_placeholder(len(code_spans))
        content = match.group(0)[1:-1]
        code_spans.append(f"<code>{content}</code>")
        return placeholder

    def italicize_quotes(match: re.Match[str]) -> str:
        straight = match.group(1)
        curly = match.group(2)
        if straight is not None:
            return f"<em>&quot;{straight}&quot;</em>"
        if curly is None:
            raise ValueError("quoted italic pattern did not capture expected text")
        return f"<em>“{curly}”</em>"

    text = INLINE_CODE_PATTERN.sub(stash_code_span, text)
    if italicize_quoted_text:
        text = QUOTED_ITALIC_PATTERN.sub(italicize_quotes, text)
    text = BOLD_PATTERN.sub(r"<strong>\1</strong>", text)
    text = ITALIC_PATTERN.sub(r"<em>\1</em>", text)

    for index, code_html in enumerate(code_spans):
        text = text.replace(span_placeholder(index), code_html)

    return text
