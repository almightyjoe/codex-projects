from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SteamReportError(Exception):
    """Base application error shown safely in the GUI."""


class SteamInputError(SteamReportError):
    """Raised for malformed or unsupported target input."""


class SteamAPIError(SteamReportError):
    """Raised for Steam HTTP/API failures."""


@dataclass(slots=True)
class EvidenceRecord:
    label: str
    kind: str
    path: Path
    url: str = ""
    sha256: str = ""
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


@dataclass(slots=True)
class CollectionResult:
    target: str
    profile_url: str
    steamid64: str = ""
    mode: str = "Public Profile Mode"
    output_dir: Path = Path("output")
    profile: dict[str, Any] = field(default_factory=dict)
    games: list[dict[str, Any]] = field(default_factory=list)
    recent_games: list[dict[str, Any]] = field(default_factory=list)
    friends: list[dict[str, Any]] = field(default_factory=list)
    aliases: list[dict[str, Any]] = field(default_factory=list)
    screenshots: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    workshop_items: list[dict[str, Any]] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    badges: list[dict[str, Any]] = field(default_factory=list)
    media: dict[str, str] = field(default_factory=dict)
    timeline: list[dict[str, str]] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        if message and message not in self.warnings:
            self.warnings.append(message)
