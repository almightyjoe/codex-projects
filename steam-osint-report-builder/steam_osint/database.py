from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import CollectionResult


SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
  steamid64 TEXT,
  profile_url TEXT,
  persona_name TEXT,
  collected_at TEXT,
  raw_json TEXT
);
CREATE TABLE IF NOT EXISTS aliases (steamid64 TEXT, alias TEXT, source TEXT, collected_at TEXT);
CREATE TABLE IF NOT EXISTS games (steamid64 TEXT, appid TEXT, name TEXT, playtime_forever TEXT, collected_at TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS friends (steamid64 TEXT, friend_steamid TEXT, name TEXT, url TEXT, collected_at TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS screenshots (steamid64 TEXT, title TEXT, url TEXT, collected_at TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS reviews (steamid64 TEXT, title TEXT, url TEXT, collected_at TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS workshop_items (steamid64 TEXT, title TEXT, url TEXT, collected_at TEXT, raw_json TEXT);
CREATE TABLE IF NOT EXISTS collection_events (steamid64 TEXT, event TEXT, event_date TEXT, collected_at TEXT);
CREATE TABLE IF NOT EXISTS evidence (steamid64 TEXT, label TEXT, kind TEXT, path TEXT, url TEXT, sha256 TEXT, collected_at TEXT);
"""


class EvidenceDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_result(self, result: CollectionResult) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)
            collected = result.evidence[0].collected_at if result.evidence else ""
            profile_name = result.profile.get("personaname") or result.profile.get("persona_name") or "Unknown"
            conn.execute(
                "INSERT INTO profiles VALUES (?, ?, ?, ?, ?)",
                (result.steamid64, result.profile_url, profile_name, collected, json.dumps(result.profile)),
            )
            self._insert_many(conn, "aliases", result, result.aliases)
            self._insert_many(conn, "games", result, result.games)
            self._insert_many(conn, "friends", result, result.friends)
            self._insert_many(conn, "screenshots", result, result.screenshots)
            self._insert_many(conn, "reviews", result, result.reviews)
            self._insert_many(conn, "workshop_items", result, result.workshop_items)
            for item in result.timeline:
                conn.execute(
                    "INSERT INTO collection_events VALUES (?, ?, ?, ?)",
                    (result.steamid64, item.get("event", ""), item.get("date", ""), collected),
                )
            for item in result.evidence:
                conn.execute(
                    "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (result.steamid64, item.label, item.kind, str(item.path), item.url, item.sha256, item.collected_at),
                )

    @staticmethod
    def _insert_many(conn: sqlite3.Connection, table: str, result: CollectionResult, rows: list[dict[str, Any]]) -> None:
        collected = result.evidence[0].collected_at if result.evidence else ""
        for row in rows:
            raw = json.dumps(row, ensure_ascii=False)
            if table == "aliases":
                conn.execute("INSERT INTO aliases VALUES (?, ?, ?, ?)", (result.steamid64, row.get("alias", ""), row.get("source", ""), collected))
            elif table == "games":
                conn.execute(
                    "INSERT INTO games VALUES (?, ?, ?, ?, ?, ?)",
                    (result.steamid64, str(row.get("appid", "")), row.get("name", ""), str(row.get("playtime_forever", "")), collected, raw),
                )
            elif table == "friends":
                conn.execute(
                    "INSERT INTO friends VALUES (?, ?, ?, ?, ?, ?)",
                    (result.steamid64, str(row.get("steamid", "")), row.get("name", ""), row.get("url", ""), collected, raw),
                )
            else:
                conn.execute(
                    f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?)",
                    (result.steamid64, row.get("title", ""), row.get("url", ""), collected, raw),
                )
