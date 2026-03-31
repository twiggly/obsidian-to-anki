from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NoteCard:
    front: str
    back: str
    tags: list[str]
    source_path: Path


@dataclass(frozen=True)
class ExportOptions:
    vault_path: Path
    output_path: Path | None = None
    target_tag: str = "definition"
    additional_target_tags: tuple[str, ...] = ()
    html_output: bool = False
    skip_empty: bool = False
    italicize_quoted_text: bool = False
    include_folders: tuple[str, ...] = ()
    duplicate_handling: str = "error"
    sync_to_anki: bool = False
    anki_connect_url: str = "http://127.0.0.1:8765"
    anki_deck: str = "Default"
    anki_note_type: str = "Basic"
    anki_front_field: str = "Front"
    anki_back_field: str = "Back"
    anki_existing_notes: str = "skip"


@dataclass(frozen=True)
class MaskedText:
    text: str
    placeholders: list[str]
    token: str


@dataclass(frozen=True)
class ScanResult:
    cards: list[NoteCard]
    preview_cards: list[NoteCard]
    total_matches: int
    duplicate_fronts: dict[str, tuple[Path, ...]]
    duplicate_resolutions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    scan_seconds: float = 0.0


@dataclass(frozen=True)
class AnkiSyncTiming:
    validation_seconds: float = 0.0
    existing_lookup_seconds: float = 0.0
    can_add_seconds: float = 0.0
    write_seconds: float = 0.0
    total_seconds: float = 0.0


@dataclass(frozen=True)
class AnkiPreflightSummary:
    new_count: int
    update_count: int
    skip_count: int
    deck_name: str
    note_type: str


@dataclass(frozen=True)
class AnkiSyncResult:
    added_count: int
    skipped_count: int
    deck_name: str
    note_type: str
    updated_count: int = 0
    skipped_fronts: tuple[str, ...] = ()
    updated_fronts: tuple[str, ...] = ()
    timing: AnkiSyncTiming = field(default_factory=AnkiSyncTiming)


@dataclass(frozen=True)
class AnkiCatalog:
    deck_names: tuple[str, ...]
    note_type_names: tuple[str, ...]


@dataclass(frozen=True)
class AnkiFieldCatalog:
    note_type_name: str
    field_names: tuple[str, ...]


@dataclass(frozen=True)
class DeliveryResult:
    export_count: int = 0
    output_path: Path | None = None
    sync_result: AnkiSyncResult | None = None
    report_text: str | None = None
    export_seconds: float = 0.0
    sync_seconds: float = 0.0
    total_seconds: float = 0.0


class ExportError(Exception):
    pass
