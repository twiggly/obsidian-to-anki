from __future__ import annotations

import re

from common import (
    FRONTMATTER_PATTERN,
    HTML_COMMENT_PATTERN,
    INLINE_TAG_PATTERN,
    mask_code_regions,
    mask_markdown_link_destinations,
    mask_obsidian_wikilink_targets,
    normalize_newlines,
    normalize_tag,
    split_csv_like,
    strip_quotes,
    strip_yaml_inline_comment,
)


def split_frontmatter(text: str) -> tuple[str, str]:
    normalized = normalize_newlines(text)
    match = FRONTMATTER_PATTERN.match(normalized)
    if not match:
        return "", normalized
    return match.group(1), normalized[match.end():]


def extract_tags(frontmatter: str, body: str) -> set[str]:
    tags = set(extract_frontmatter_tags(frontmatter))
    body_without_comments = HTML_COMMENT_PATTERN.sub("", body)
    masked_code = mask_code_regions(body_without_comments)
    masked_links = mask_markdown_link_destinations(masked_code.text)
    masked_wikilinks = mask_obsidian_wikilink_targets(masked_links.text)
    tags.update(normalize_tag(tag) for tag in INLINE_TAG_PATTERN.findall(masked_wikilinks.text))
    return {tag for tag in tags if tag}


def extract_frontmatter_tags(frontmatter: str) -> set[str]:
    if not frontmatter.strip():
        return set()

    tags: set[str] = set()
    lines = frontmatter.splitlines()
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        key_match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", stripped)
        if not key_match:
            index += 1
            continue

        key = key_match.group(1).lower()
        value = key_match.group(2).strip()

        if key != "tags":
            index += 1
            continue

        if value:
            tags.update(parse_frontmatter_tag_value(value))
            index += 1
            continue

        index += 1
        while index < len(lines):
            item_line = lines[index]
            if not item_line.strip():
                index += 1
                continue
            if not re.match(r"^\s*-\s+", item_line):
                break
            item_value = re.sub(r"^\s*-\s+", "", item_line).strip()
            tags.update(parse_frontmatter_tag_value(item_value))
            index += 1

    return {normalize_tag(tag) for tag in tags if tag}


def parse_frontmatter_tag_value(value: str) -> set[str]:
    value = strip_yaml_inline_comment(value.strip())
    if not value:
        return set()

    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return set()
        parts = split_csv_like(inner)
        cleaned_parts = {strip_quotes(part.strip()) for part in parts}
        return {part for part in cleaned_parts if part}

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        cleaned = strip_quotes(value)
        return {cleaned} if cleaned else set()

    parts = split_csv_like(value) if "," in value else [value]
    cleaned_parts = {strip_quotes(part.strip()) for part in parts}
    return {part for part in cleaned_parts if part}
