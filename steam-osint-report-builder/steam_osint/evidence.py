from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import EvidenceRecord


class EvidenceStore:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.raw_dir = output_dir / "raw"
        self.media_dir = output_dir / "media"
        self.records: list[EvidenceRecord] = []
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def save_text(self, filename: str, text: str, label: str, url: str = "") -> EvidenceRecord:
        path = self.raw_dir / filename
        path.write_text(text, encoding="utf-8", errors="replace")
        return self._record(label, "html", path, url)

    def save_json(self, filename: str, data: Any, label: str, url: str = "") -> EvidenceRecord:
        path = self.raw_dir / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return self._record(label, "json", path, url)

    def save_bytes(self, filename: str, data: bytes, label: str, url: str = "") -> EvidenceRecord:
        path = self.media_dir / filename
        path.write_bytes(data)
        return self._record(label, "media", path, url)

    def write_manifest(self) -> Path:
        path = self.output_dir / "evidence_manifest.json"
        payload = [
            {
                "label": r.label,
                "kind": r.kind,
                "path": str(r.path),
                "url": r.url,
                "sha256": r.sha256,
                "collected_at": r.collected_at,
            }
            for r in self.records
        ]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _record(self, label: str, kind: str, path: Path, url: str) -> EvidenceRecord:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        record = EvidenceRecord(label=label, kind=kind, path=path, url=url, sha256=digest)
        self.records.append(record)
        return record
