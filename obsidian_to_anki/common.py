from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Sequence

from .models import ExportError, MaskedText


INLINE_TAG_PATTERN = re.compile(r"(?<![\w/])#([A-Za-z0-9_\-/]+)")
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_BLOCK_PATTERN = re.compile(r"(^|\n)(```|~~~)[^\n]*\n(.*?)(?:\n\2)(?=\n|\Z)", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]*`")
MARKDOWN_LINK_DESTINATION_PATTERN = re.compile(r"(!?\[[^\]\n]*\]\()([^\n)]*)(\))")
OBSIDIAN_WIKILINK_TARGET_PATTERN = re.compile(r"(\[\[)([^\]\n]*)(\]\])")
LIST_ITEM_PATTERN = re.compile(r"^\s*[-*]\s+(.*)$")
BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
ITALIC_PATTERN = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
QUOTED_ITALIC_PATTERN = re.compile(r'&quot;(.+?)&quot;|“(.+?)”')
TRAILING_PART_OF_SPEECH_QUALIFIER_PATTERN = re.compile(r"\s+\([^()]+\)\s*$")
PREVIEW_CARD_LIMIT = 30
DUPLICATE_SUMMARY_LIMIT = 8
DUPLICATE_PATH_LIMIT = 3
DUPLICATE_HANDLING_CHOICES = ("skip", "suffix", "error")
DUPLICATE_HANDLING_LABELS = {
    "skip": "Keep first",
    "suffix": "Rename duplicates",
    "error": "Stop",
}
DUPLICATE_HANDLING_DISPLAY_CHOICES = tuple(
    DUPLICATE_HANDLING_LABELS[choice] for choice in DUPLICATE_HANDLING_CHOICES
)
ANKI_EXISTING_NOTE_CHOICES = ("skip", "update")
PART_OF_SPEECH_LABELS = {
    "abbreviation",
    "adjective",
    "adverb",
    "article",
    "attributive adjective",
    "auxiliary verb",
    "cardinal number",
    "combining form",
    "conjunction",
    "count noun",
    "determiner",
    "exclamation",
    "idiom",
    "intransitive verb",
    "interjection",
    "linking verb",
    "mass noun",
    "modal verb",
    "noun",
    "ordinal number",
    "phrase",
    "phrasal verb",
    "plural noun",
    "possessive determiner",
    "predeterminer",
    "predicative adjective",
    "prefix",
    "preposition",
    "proper noun",
    "pronoun",
    "suffix",
    "symbol",
    "transitive verb",
    "verb",
}


def validate_vault_path(vault_path: Path) -> Path:
    resolved = vault_path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ExportError(f"Vault path does not exist or is not a directory: {resolved}")
    return resolved


def unexpected_error_message(action: str) -> str:
    return f"{action.capitalize()} failed due to an unexpected error. See the log for details."


def effective_italicize_quoted_text(html_output: bool, italicize_quoted_text: bool) -> bool:
    return html_output and italicize_quoted_text


def normalize_duplicate_handling(strategy: str) -> str:
    normalized = strategy.strip().lower()
    if normalized not in DUPLICATE_HANDLING_CHOICES:
        raise ExportError(
            "Duplicate handling must be one of: " + ", ".join(DUPLICATE_HANDLING_CHOICES)
        )
    return normalized


def duplicate_handling_display_label(strategy: str) -> str:
    return DUPLICATE_HANDLING_LABELS[normalize_duplicate_handling(strategy)]


def duplicate_handling_from_display(label: str) -> str:
    normalized_label = label.strip()
    for strategy, display_label in DUPLICATE_HANDLING_LABELS.items():
        if normalized_label == display_label:
            return strategy
    return normalize_duplicate_handling(normalized_label)


def normalize_anki_existing_notes(strategy: str) -> str:
    normalized = strategy.strip().lower()
    if normalized not in ANKI_EXISTING_NOTE_CHOICES:
        raise ExportError(
            "Anki existing-note handling must be one of: "
            + ", ".join(ANKI_EXISTING_NOTE_CHOICES)
        )
    return normalized


def duplicate_handling_warning_message(strategy: str, duplicate_count: int) -> str:
    if strategy == "skip":
        return (
            f"Detected {duplicate_count} duplicate card fronts. "
            "Keeping the first matching note for each front."
        )
    if strategy == "suffix":
        return (
            f"Detected {duplicate_count} duplicate card fronts. "
            "Appending folder-based suffixes so each front stays unique."
        )
    if strategy == "error":
        return (
            f"Detected {duplicate_count} duplicate card fronts. "
            "Stopping before export or sync."
        )
    return f"Detected {duplicate_count} duplicate card fronts."


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def normalize_target_tags(raw_tags: str | Sequence[str]) -> tuple[str, ...]:
    values = [raw_tags] if isinstance(raw_tags, str) else list(raw_tags)
    normalized_tags: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = normalize_tag(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_tags.append(normalized)

    if not normalized_tags:
        return ("definition",)
    return tuple(normalized_tags)


def effective_target_tags(target_tag: str, additional_target_tags: Sequence[str] = ()) -> tuple[str, ...]:
    return normalize_target_tags((target_tag, *additional_target_tags))


def format_target_tags(target_tag: str, additional_target_tags: Sequence[str] = ()) -> str:
    tags = [f"#{tag}" for tag in effective_target_tags(target_tag, additional_target_tags)]
    if len(tags) == 1:
        return tags[0]
    if len(tags) == 2:
        return f"{tags[0]} or {tags[1]}"
    return ", ".join(tags[:-1]) + f", or {tags[-1]}"


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_csv_like(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote_char: str | None = None

    for char in text:
        if quote_char is not None:
            current.append(char)
            if char == quote_char:
                quote_char = None
            continue

        if char in {"'", '"'}:
            quote_char = char
            current.append(char)
            continue

        if char == ",":
            parts.append("".join(current))
            current = []
            continue

        current.append(char)

    parts.append("".join(current))
    return parts


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def strip_yaml_inline_comment(value: str) -> str:
    quote_char: str | None = None
    previous_char = ""

    for index, char in enumerate(value):
        if quote_char is not None:
            if char == quote_char and previous_char != "\\":
                quote_char = None
            previous_char = char
            continue

        if char in {"'", '"'}:
            quote_char = char
            previous_char = char
            continue

        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()

        previous_char = char

    return value


def make_placeholder(prefix: str, token: str, index: int) -> str:
    return f"@@{prefix}_{token}_{index}@@"


def mask_code_regions(text: str) -> MaskedText:
    placeholders: list[str] = []
    token = uuid.uuid4().hex

    def replace_fenced(match: re.Match[str]) -> str:
        placeholder = make_placeholder("CODE", token, len(placeholders))
        placeholders.append(match.group(0))
        return f"{match.group(1)}{placeholder}"

    masked = FENCED_BLOCK_PATTERN.sub(replace_fenced, text)

    def replace_inline(match: re.Match[str]) -> str:
        placeholder = make_placeholder("CODE", token, len(placeholders))
        placeholders.append(match.group(0))
        return placeholder

    masked = INLINE_CODE_PATTERN.sub(replace_inline, masked)
    return MaskedText(text=masked, placeholders=placeholders, token=token)


def mask_markdown_link_destinations(text: str) -> MaskedText:
    placeholders: list[str] = []
    token = uuid.uuid4().hex

    def replace_destination(match: re.Match[str]) -> str:
        placeholder = make_placeholder("LINK", token, len(placeholders))
        placeholders.append(match.group(2))
        return f"{match.group(1)}{placeholder}{match.group(3)}"

    masked = MARKDOWN_LINK_DESTINATION_PATTERN.sub(replace_destination, text)
    return MaskedText(text=masked, placeholders=placeholders, token=token)


def mask_obsidian_wikilink_targets(text: str) -> MaskedText:
    placeholders: list[str] = []
    token = uuid.uuid4().hex

    def replace_target(match: re.Match[str]) -> str:
        placeholder = make_placeholder("WIKI", token, len(placeholders))
        placeholders.append(match.group(2))
        return f"{match.group(1)}{placeholder}{match.group(3)}"

    masked = OBSIDIAN_WIKILINK_TARGET_PATTERN.sub(replace_target, text)
    return MaskedText(text=masked, placeholders=placeholders, token=token)


def unmask_placeholders(
    masked: MaskedText | str,
    prefix: str,
    placeholders: list[str] | None = None,
    token: str | None = None,
) -> str:
    if isinstance(masked, MaskedText):
        text = masked.text
        placeholders = masked.placeholders
        token = masked.token
    else:
        if placeholders is None or token is None:
            raise ValueError("placeholders and token are required when unmasking a string")
        text = masked

    if placeholders is None or token is None:
        raise ValueError("masked placeholders and token are required for unmasking")
    for index, original in enumerate(placeholders):
        text = text.replace(make_placeholder(prefix, token, index), original)
    return text


def unmask_code_regions(masked: MaskedText | str, placeholders: list[str] | None = None, token: str | None = None) -> str:
    return unmask_placeholders(masked, "CODE", placeholders, token)


def unmask_markdown_link_destinations(
    masked: MaskedText | str,
    placeholders: list[str] | None = None,
    token: str | None = None,
) -> str:
    return unmask_placeholders(masked, "LINK", placeholders, token)


def unmask_obsidian_wikilink_targets(
    masked: MaskedText | str,
    placeholders: list[str] | None = None,
    token: str | None = None,
) -> str:
    return unmask_placeholders(masked, "WIKI", placeholders, token)
