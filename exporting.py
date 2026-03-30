from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Iterable, Sequence, TextIO

from models import ExportError, ExportOptions, NoteCard


def write_tsv_to_handle(file_handle: TextIO, cards: Iterable[NoteCard]) -> int:
    count = 0
    writer = csv.writer(file_handle, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    for card in cards:
        writer.writerow([card.front, card.back, " ".join(card.tags)])
        count += 1
    return count


def run_export(options: ExportOptions, cards: Sequence[NoteCard]) -> int:
    if options.output_path is None:
        raise ExportError("Output path is required for TSV export.")

    options.output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            suffix=options.output_path.suffix or ".tsv",
            prefix=f".{options.output_path.stem}_",
            dir=options.output_path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            count = write_tsv_to_handle(temp_file, cards)

        if count == 0:
            if temp_path.exists():
                temp_path.unlink()
            return 0

        os.replace(temp_path, options.output_path)
        return count
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        raise
