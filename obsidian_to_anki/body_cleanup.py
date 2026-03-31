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


def clean_body(body: str) -> str:
    cleaned = normalize_newlines(body)
    cleaned = HTML_COMMENT_PATTERN.sub("", cleaned)

    masked_code = mask_code_regions(cleaned)
    masked_links = mask_markdown_link_destinations(masked_code.text)
    masked_wikilinks = mask_obsidian_wikilink_targets(masked_links.text)
    text = INLINE_TAG_PATTERN.sub("", masked_wikilinks.text)
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = unmask_obsidian_wikilink_targets(text, masked_wikilinks.placeholders, masked_wikilinks.token)
    text = unmask_markdown_link_destinations(text, masked_links.placeholders, masked_links.token)
    return unmask_code_regions(text, masked_code.placeholders, masked_code.token).strip()
