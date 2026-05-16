from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil

from .models import CollectionResult


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._")[:80] or "steam_target"


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def make_output_dir(base_output: Path, target: str, batch: bool = False) -> Path:
    out = base_output / "_collecting" / f"{safe_name(target)}_{timestamp_slug()}"
    ensure_output_tree(out)
    return out


def finalize_output_dir(base_output: Path, result: CollectionResult) -> Path:
    old_dir = result.output_dir.resolve()
    final_dir = resolved_user_output_dir(base_output, result)
    if old_dir == final_dir.resolve():
        ensure_output_tree(final_dir)
        return final_dir

    ensure_output_tree(final_dir)
    if old_dir.exists():
        for item in old_dir.iterdir():
            destination = final_dir / item.name
            if destination.exists() and destination.is_dir() and item.is_dir():
                for child in item.iterdir():
                    shutil.move(str(child), str(destination / child.name))
                item.rmdir()
            else:
                shutil.move(str(item), str(destination))
        _prune_empty_parents(old_dir, stop_at=base_output.resolve())

    _rewrite_result_paths(result, old_dir, final_dir.resolve())
    result.output_dir = final_dir
    return final_dir


def resolved_user_output_dir(base_output: Path, result: CollectionResult) -> Path:
    persona = result.profile.get("personaname") or result.profile.get("persona_name") or ""
    identity = persona or result.steamid64 or result.target
    user_folder = safe_name(f"{identity}_{result.steamid64}" if result.steamid64 and result.steamid64 not in identity else identity)
    return base_output / user_folder / timestamp_slug()


def ensure_output_tree(out: Path) -> None:
    for child in ("raw", "media", "exports", "graphs"):
        (out / child).mkdir(parents=True, exist_ok=True)


def _rewrite_result_paths(result: CollectionResult, old_dir: Path, new_dir: Path) -> None:
    for record in result.evidence:
        try:
            record.path = new_dir / record.path.resolve().relative_to(old_dir)
        except ValueError:
            pass
    for key, value in list(result.media.items()):
        try:
            path = Path(value)
            if path.is_absolute():
                result.media[key] = str(new_dir / path.resolve().relative_to(old_dir))
        except (OSError, ValueError):
            pass


def _prune_empty_parents(path: Path, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
