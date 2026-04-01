from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from typing import Iterator, Sequence

from .common import (
    DUPLICATE_PATH_LIMIT,
    DUPLICATE_SUMMARY_LIMIT,
    PREVIEW_CARD_LIMIT,
    effective_target_tags,
    validate_vault_path,
)
from .models import ExportError, ExportOptions, NoteCard, ScanResult
from .note_parser import extract_tags, split_frontmatter
from .rendering import clean_body, markdownish_to_html
from .scan_filters import iter_markdown_note_paths, note_matches_folder_filters


def scan_cards(options: ExportOptions, preview_limit: int = PREVIEW_CARD_LIMIT) -> ScanResult:
    scan_started_at = perf_counter()
    validate_vault_path(options.vault_path)
    cards = list(
        iter_cards(
            vault_path=options.vault_path,
            target_tags=effective_target_tags(
                options.target_tag,
                options.additional_target_tags,
            ),
            html_output=options.html_output,
            italicize_quoted_text=options.italicize_quoted_text,
            flatten_note_links=options.flatten_note_links,
            include_folders=options.include_folders,
        )
    )
    front_groups = group_cards_by_front(cards)
    duplicate_fronts = build_duplicate_front_map(front_groups)
    resolved_cards, duplicate_resolutions = resolve_duplicate_fronts(
        cards,
        front_groups,
        options.duplicate_handling,
        options.vault_path,
    )
    preview_cards = resolved_cards[:preview_limit] if preview_limit > 0 else []

    return ScanResult(
        cards=resolved_cards,
        preview_cards=preview_cards,
        total_matches=len(resolved_cards),
        duplicate_fronts=duplicate_fronts,
        duplicate_resolutions=duplicate_resolutions,
        scan_seconds=perf_counter() - scan_started_at,
    )


def scan_vault_tags(
    vault_path: Path,
    include_folders: tuple[str, ...] = (),
) -> tuple[str, ...]:
    validate_vault_path(vault_path)
    tags: set[str] = set()

    for path in iter_markdown_note_paths(vault_path):
        if not note_matches_folder_filters(path, vault_path, include_folders):
            continue

        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            print(f"Skipping unreadable file (not UTF-8): {path}", file=sys.stderr)
            continue
        except OSError as exc:
            print(f"Skipping unreadable file {path}: {exc}", file=sys.stderr)
            continue

        frontmatter, body = split_frontmatter(raw_text)
        tags.update(extract_tags(frontmatter, body))

    return tuple(sorted(tags, key=str.casefold))


def build_duplicate_summary(duplicate_fronts: dict[str, tuple[Path, ...]]) -> str:
    lines: list[str] = []
    items = list(duplicate_fronts.items())

    for front, paths in items[:DUPLICATE_SUMMARY_LIMIT]:
        lines.append(f"- {front} ({len(paths)} matches)")
        for path in paths[:DUPLICATE_PATH_LIMIT]:
            lines.append(f"    {path}")
        if len(paths) > DUPLICATE_PATH_LIMIT:
            lines.append(f"    ... {len(paths) - DUPLICATE_PATH_LIMIT} more")

    remaining = len(items) - DUPLICATE_SUMMARY_LIMIT
    if remaining > 0:
        lines.append(f"... {remaining} more duplicate fronts")

    return "\n".join(lines)


def group_cards_by_front(cards: Sequence[NoteCard]) -> dict[str, list[NoteCard]]:
    groups: dict[str, list[NoteCard]] = defaultdict(list)
    for card in cards:
        groups[card.front.casefold()].append(card)
    return groups


def build_duplicate_front_map(front_groups: dict[str, list[NoteCard]]) -> dict[str, tuple[Path, ...]]:
    duplicate_fronts: dict[str, tuple[Path, ...]] = {}
    for entries in front_groups.values():
        if len(entries) > 1:
            display_front = entries[0].front
            duplicate_fronts[display_front] = tuple(card.source_path for card in entries)
    return dict(sorted(duplicate_fronts.items(), key=lambda item: item[0].casefold()))


def resolve_duplicate_fronts(
    cards: Sequence[NoteCard],
    front_groups: dict[str, list[NoteCard]],
    strategy: str,
    vault_path: Path,
) -> tuple[list[NoteCard], dict[str, tuple[str, ...]]]:
    if strategy == "warn":
        return list(cards), {}

    duplicate_groups = {key: entries for key, entries in front_groups.items() if len(entries) > 1}
    if not duplicate_groups:
        return list(cards), {}

    if strategy == "error":
        raise ExportError(
            f"Detected {len(duplicate_groups)} duplicate card fronts. Change the duplicate handling option to continue."
        )

    if strategy == "skip":
        seen_fronts: set[str] = set()
        resolved_cards: list[NoteCard] = []
        duplicate_resolutions = {
            entries[0].front: (entries[0].front,)
            for entries in duplicate_groups.values()
        }
        for card in cards:
            front_key = card.front.casefold()
            if front_key in seen_fronts:
                continue
            seen_fronts.add(front_key)
            resolved_cards.append(card)
        return resolved_cards, dict(
            sorted(duplicate_resolutions.items(), key=lambda item: item[0].casefold())
        )

    if strategy == "suffix":
        replacements: dict[tuple[str, Path], NoteCard] = {}
        duplicate_resolutions: dict[str, tuple[str, ...]] = {}
        for entries in duplicate_groups.values():
            updated_cards: list[NoteCard] = []
            for original_card, label in zip(entries, build_duplicate_suffix_labels(entries, vault_path)):
                updated_card = replace(
                    original_card,
                    front=f"{original_card.front} ({label})",
                )
                replacements[(original_card.front.casefold(), original_card.source_path)] = updated_card
                updated_cards.append(updated_card)
            duplicate_resolutions[entries[0].front] = tuple(card.front for card in updated_cards)
        return [
            replacements.get((card.front.casefold(), card.source_path), card)
            for card in cards
        ], dict(sorted(duplicate_resolutions.items(), key=lambda item: item[0].casefold()))

    raise ExportError(f"Unsupported duplicate handling strategy: {strategy}")


def build_duplicate_suffix_labels(cards: Sequence[NoteCard], vault_path: Path) -> list[str]:
    parent_labels = [duplicate_parent_label(card, vault_path) for card in cards]
    if len({label.casefold() for label in parent_labels}) == len(parent_labels):
        return parent_labels

    full_labels = [duplicate_full_label(card, vault_path) for card in cards]
    seen_labels: dict[str, int] = defaultdict(int)
    resolved_labels: list[str] = []
    for full_label in full_labels:
        key = full_label.casefold()
        seen_labels[key] += 1
        if seen_labels[key] == 1:
            resolved_labels.append(full_label)
        else:
            resolved_labels.append(f"{full_label} #{seen_labels[key]}")
    return resolved_labels


def duplicate_parent_label(card: NoteCard, vault_path: Path) -> str:
    relative_path = card.source_path.relative_to(vault_path)
    parent_label = relative_path.parent.as_posix()
    if parent_label != ".":
        return parent_label
    return duplicate_full_label(card, vault_path)


def duplicate_full_label(card: NoteCard, vault_path: Path) -> str:
    return card.source_path.relative_to(vault_path).with_suffix("").as_posix()


def iter_cards(
    vault_path: Path,
    target_tags: tuple[str, ...],
    html_output: bool,
    italicize_quoted_text: bool,
    flatten_note_links: bool,
    include_folders: tuple[str, ...],
) -> Iterator[NoteCard]:
    for path in iter_markdown_note_paths(vault_path):
        if not note_matches_folder_filters(path, vault_path, include_folders):
            continue

        try:
            raw_text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            print(f"Skipping unreadable file (not UTF-8): {path}", file=sys.stderr)
            continue
        except OSError as exc:
            print(f"Skipping unreadable file {path}: {exc}", file=sys.stderr)
            continue

        frontmatter, body = split_frontmatter(raw_text)
        tags = extract_tags(frontmatter, body)

        if not any(target_tag in tags for target_tag in target_tags):
            continue

        front = path.stem.strip()
        back = clean_body(body, flatten_note_links=flatten_note_links)

        if not back.strip():
            continue

        if html_output:
            back = markdownish_to_html(back, italicize_quoted_text=italicize_quoted_text)

        yield NoteCard(front=front, back=back, tags=sorted(tags), source_path=path)
