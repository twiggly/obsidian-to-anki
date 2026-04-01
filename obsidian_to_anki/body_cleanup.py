from __future__ import annotations

import re

from .common import (
    HTML_COMMENT_PATTERN,
    INLINE_TAG_PATTERN,
    mask_code_regions,
    mask_markdown_link_destinations,
    mask_obsidian_wikilink_targets,
    normalize_newlines,
    unmask_code_regions,
    unmask_markdown_link_destinations,
    unmask_obsidian_wikilink_targets,
)

MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]\n]*)\]\([^\n)]*\)")
OBSIDIAN_EMBED_LINE_PATTERN = re.compile(r"(?m)^[ \t]*!\[\[([^\]\n]*)\]\][ \t]*(?:\n|$)")
OBSIDIAN_EMBED_PATTERN = re.compile(r"!\[\[([^\]\n]*)\]\]")
OBSIDIAN_WIKILINK_PATTERN = re.compile(r"(?<!!)\[\[([^\]\n]*)\]\]")


def _flatten_markdown_links(text: str) -> str:
    return MARKDOWN_LINK_PATTERN.sub(lambda match: match.group(1).strip(), text)


def _remove_obsidian_embeds(text: str) -> str:
    text = OBSIDIAN_EMBED_LINE_PATTERN.sub("", text)
    return OBSIDIAN_EMBED_PATTERN.sub("", text)


def _flatten_obsidian_wikilinks(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_target = match.group(1).strip()
        if not raw_target:
            return ""

        target, separator, alias = raw_target.partition("|")
        if separator:
            return alias.strip()

        note_name, heading_separator, heading = target.partition("#")
        if heading_separator:
            cleaned_heading = heading.strip().lstrip("^").strip()
            if cleaned_heading:
                return cleaned_heading

        return note_name.strip()

    return OBSIDIAN_WIKILINK_PATTERN.sub(replace, text)


def clean_body(body: str, *, flatten_note_links: bool = True) -> str:
    cleaned = normalize_newlines(body)
    cleaned = HTML_COMMENT_PATTERN.sub("", cleaned)

    masked_code = mask_code_regions(cleaned)
    if flatten_note_links:
        text = _remove_obsidian_embeds(masked_code.text)
        text = _flatten_obsidian_wikilinks(text)
        text = _flatten_markdown_links(text)
        text = INLINE_TAG_PATTERN.sub("", text)
    else:
        masked_links = mask_markdown_link_destinations(masked_code.text)
        masked_wikilinks = mask_obsidian_wikilink_targets(masked_links.text)
        text = INLINE_TAG_PATTERN.sub("", masked_wikilinks.text)
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not flatten_note_links:
        text = unmask_obsidian_wikilink_targets(text, masked_wikilinks.placeholders, masked_wikilinks.token)
        text = unmask_markdown_link_destinations(text, masked_links.placeholders, masked_links.token)
    return unmask_code_regions(text, masked_code.placeholders, masked_code.token).strip()
