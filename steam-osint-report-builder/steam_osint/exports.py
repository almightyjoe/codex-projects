from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .models import CollectionResult


def export_csvs(result: CollectionResult) -> list[Path]:
    export_dir = result.output_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    exports = [
        ("games.csv", result.games),
        ("friends.csv", result.friends),
        ("workshop_items.csv", result.workshop_items),
        ("screenshots.csv", result.screenshots),
        ("reviews.csv", result.reviews),
    ]
    paths: list[Path] = []
    for filename, rows in exports:
        path = export_dir / filename
        write_csv(path, rows)
        paths.append(path)
    return paths


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    if not keys:
        keys = ["notice"]
        rows = [{"notice": "No public records collected for this category."}]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
