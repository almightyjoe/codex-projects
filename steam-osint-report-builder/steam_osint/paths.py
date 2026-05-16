from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._")[:80] or "steam_target"


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def make_output_dir(base_output: Path, target: str, batch: bool = False) -> Path:
    if batch:
        out = base_output / f"{safe_name(target)}_{timestamp_slug()}"
    else:
        out = base_output
    for child in ("raw", "media", "exports", "graphs"):
        (out / child).mkdir(parents=True, exist_ok=True)
    return out
