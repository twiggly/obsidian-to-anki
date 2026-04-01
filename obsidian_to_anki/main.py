#!/usr/bin/env python3
"""
Convert Obsidian notes matching selected tags into Anki import cards.

You can use it in two ways:
- Command line mode
- Desktop UI mode

If you run the script without arguments, it opens the UI.
"""

from __future__ import annotations

from .anki.sync import AnkiConnectError, build_anki_notes, invoke_anki_connect, sync_cards_to_anki
from .body_cleanup import clean_body
from .cli import main, parse_args
from .common import (
    BOLD_PATTERN,
    DUPLICATE_HANDLING_CHOICES,
    DUPLICATE_PATH_LIMIT,
    DUPLICATE_SUMMARY_LIMIT,
    FENCED_BLOCK_PATTERN,
    FRONTMATTER_PATTERN,
    HTML_COMMENT_PATTERN,
    INLINE_CODE_PATTERN,
    INLINE_TAG_PATTERN,
    ITALIC_PATTERN,
    LIST_ITEM_PATTERN,
    MARKDOWN_LINK_DESTINATION_PATTERN,
    OBSIDIAN_WIKILINK_TARGET_PATTERN,
    PART_OF_SPEECH_LABELS,
    PREVIEW_CARD_LIMIT,
    QUOTED_ITALIC_PATTERN,
    TRAILING_PART_OF_SPEECH_QUALIFIER_PATTERN,
    duplicate_handling_warning_message,
    effective_italicize_quoted_text,
    make_placeholder,
    mask_code_regions,
    mask_markdown_link_destinations,
    mask_obsidian_wikilink_targets,
    normalize_duplicate_handling,
    normalize_newlines,
    normalize_tag,
    split_csv_like,
    strip_quotes,
    strip_yaml_inline_comment,
    unexpected_error_message,
    unmask_code_regions,
    unmask_markdown_link_destinations,
    unmask_obsidian_wikilink_targets,
    unmask_placeholders,
    validate_vault_path,
)
from .delivery import deliver_cards
from .exporting import run_export, write_tsv_to_handle
from .gui import ExporterApp, append_folder_filter, launch_gui, remove_folder_filters
from .html_render import (
    inline_formatting,
    is_part_of_speech_label,
    markdownish_to_html,
    normalize_part_of_speech_label,
    render_block_segments,
    render_dictionary_entries,
    render_dictionary_entry,
    render_inline_text,
)
from .models import ExportError, ExportOptions, MaskedText, NoteCard, ScanResult
from .note_parser import extract_frontmatter_tags, extract_tags, parse_frontmatter_tag_value, split_frontmatter
from .preview_render import html_to_preview_text, populate_preview_text_widget, preview_sections_for_card
from .scan_filters import iter_markdown_note_paths, normalize_folder_filters, note_matches_folder_filters
from .scanner_engine import build_duplicate_summary, iter_cards, scan_cards

__all__ = [
    "AnkiConnectError",
    "BOLD_PATTERN",
    "DUPLICATE_HANDLING_CHOICES",
    "DUPLICATE_PATH_LIMIT",
    "DUPLICATE_SUMMARY_LIMIT",
    "ExporterApp",
    "ExportError",
    "ExportOptions",
    "FENCED_BLOCK_PATTERN",
    "FRONTMATTER_PATTERN",
    "HTML_COMMENT_PATTERN",
    "INLINE_CODE_PATTERN",
    "INLINE_TAG_PATTERN",
    "ITALIC_PATTERN",
    "LIST_ITEM_PATTERN",
    "MARKDOWN_LINK_DESTINATION_PATTERN",
    "MaskedText",
    "NoteCard",
    "OBSIDIAN_WIKILINK_TARGET_PATTERN",
    "PART_OF_SPEECH_LABELS",
    "PREVIEW_CARD_LIMIT",
    "QUOTED_ITALIC_PATTERN",
    "ScanResult",
    "TRAILING_PART_OF_SPEECH_QUALIFIER_PATTERN",
    "append_folder_filter",
    "build_anki_notes",
    "build_duplicate_summary",
    "clean_body",
    "duplicate_handling_warning_message",
    "deliver_cards",
    "effective_italicize_quoted_text",
    "extract_frontmatter_tags",
    "extract_tags",
    "html_to_preview_text",
    "inline_formatting",
    "is_part_of_speech_label",
    "iter_cards",
    "iter_markdown_note_paths",
    "invoke_anki_connect",
    "launch_gui",
    "main",
    "make_placeholder",
    "markdownish_to_html",
    "mask_code_regions",
    "mask_markdown_link_destinations",
    "mask_obsidian_wikilink_targets",
    "normalize_duplicate_handling",
    "normalize_folder_filters",
    "normalize_newlines",
    "normalize_part_of_speech_label",
    "normalize_tag",
    "note_matches_folder_filters",
    "parse_args",
    "parse_frontmatter_tag_value",
    "populate_preview_text_widget",
    "preview_sections_for_card",
    "remove_folder_filters",
    "render_block_segments",
    "render_dictionary_entries",
    "render_dictionary_entry",
    "render_inline_text",
    "run_export",
    "scan_cards",
    "split_csv_like",
    "split_frontmatter",
    "strip_quotes",
    "strip_yaml_inline_comment",
    "sync_cards_to_anki",
    "unexpected_error_message",
    "unmask_code_regions",
    "unmask_markdown_link_destinations",
    "unmask_obsidian_wikilink_targets",
    "unmask_placeholders",
    "validate_vault_path",
    "write_tsv_to_handle",
]


if __name__ == "__main__":
    raise SystemExit(main())
