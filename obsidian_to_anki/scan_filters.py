from __future__ import annotations

from pathlib import Path
from typing import Iterator, Sequence

from .common import validate_vault_path
from .models import ExportError


def normalize_folder_filters(raw_filters: Sequence[str], vault_path: Path) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_filter in raw_filters:
        value = raw_filter.strip()
        if not value:
            continue

        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
            try:
                relative = resolved.relative_to(vault_path)
            except ValueError as exc:
                raise ExportError(f"Folder filter is outside the vault: {value}") from exc
            normalized_value = relative.as_posix().strip("/")
        else:
            normalized_value = value.replace("\\", "/").strip().strip("/")

        if not normalized_value or normalized_value == ".":
            continue

        parts = [part for part in normalized_value.split("/") if part]
        if any(part == ".." for part in parts):
            raise ExportError(f"Folder filter cannot contain '..': {value}")

        normalized_value = "/".join(parts)
        folder_path = (vault_path / normalized_value).resolve()
        if not folder_path.exists() or not folder_path.is_dir():
            raise ExportError(f"Folder filter does not exist in the vault: {normalized_value}")

        if normalized_value not in seen:
            seen.add(normalized_value)
            normalized.append(normalized_value)

    return tuple(normalized)


def note_matches_folder_filters(note_path: Path, vault_path: Path, include_folders: tuple[str, ...]) -> bool:
    if not include_folders:
        return True

    relative_path = note_path.relative_to(vault_path).as_posix()
    return any(relative_path.startswith(folder + "/") for folder in include_folders)


def iter_markdown_note_paths(vault_path: Path) -> Iterator[Path]:
    validate_vault_path(vault_path)
    for path in sorted(vault_path.rglob("*")):
        if path.is_file() and path.suffix.casefold() == ".md":
            yield path
