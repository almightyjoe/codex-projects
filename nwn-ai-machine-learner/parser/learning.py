"""Utilities for parser edge-case collection and rule candidate discovery."""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime

from config import COMBAT_DB

_LOG_LINE = re.compile(
    r'^\[CHAT WINDOW TEXT\] \[(?P<stamp>\w{3} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2})\] (?P<content>.+)$'
)


def unwrap_log_line(raw_line: str) -> tuple[str, str]:
    """Return an ISO-ish timestamp and content for a chat-window log line."""
    match = _LOG_LINE.match(raw_line)
    if not match:
        return datetime.now().isoformat(), raw_line.strip()

    stamp = match.group("stamp")
    try:
        ts = datetime.strptime(stamp, "%a %b %d %H:%M:%S").replace(
            year=datetime.now().year
        ).isoformat()
    except ValueError:
        ts = stamp
    return ts, match.group("content").strip()


def bucket_for_content(content: str) -> str:
    """Build a stable bucket key so repeated unknown patterns cluster together."""
    text = re.sub(r"\d+", "#", content.strip())
    text = re.sub(r"\s+", " ", text)

    if text.startswith("* ") and text.endswith(" *"):
        return "* ability banner *"
    if "actions have shifted your alignment" in text:
        return "alignment shift"
    if " uses Potion of " in text:
        return "uses potion"
    if " uses " in text:
        return "uses item or ability"
    if "will be available again" in text or "is now available for use" in text:
        return "cooldown notice"
    if text.startswith("[Server] Armor class:"):
        return "armor class block"
    if text.startswith("**Console**:"):
        return "console output"
    if "Found an unidentified" in text:
        return "unidentified loot"

    return " ".join(text.split()[:6]) or "empty"


def make_unparsed_event(raw_line: str, source_file: str = "", area: str = "") -> dict:
    ts, content = unwrap_log_line(raw_line)
    return {
        "type": "unparsed",
        "ts": ts,
        "raw_line": raw_line,
        "content": content,
        "bucket": bucket_for_content(content),
        "source_file": source_file,
        "area": area,
    }


def analyze_unparsed(limit: int = 100) -> list[dict]:
    """Create lightweight parser rule candidates from repeated unparsed buckets."""
    conn = sqlite3.connect(COMBAT_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT bucket, COUNT(*) AS seen_count, MIN(ts) AS first_seen, MAX(ts) AS last_seen
        FROM unparsed_lines
        GROUP BY bucket
        ORDER BY seen_count DESC, last_seen DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    candidates = []
    for row in rows:
        existing = conn.execute(
            "SELECT id FROM parser_rule_candidates WHERE bucket=? AND status='new'",
            (row["bucket"],),
        ).fetchone()
        samples = [
            r["content"]
            for r in conn.execute(
                """
                SELECT DISTINCT content
                FROM unparsed_lines
                WHERE bucket=?
                ORDER BY id DESC
                LIMIT 5
                """,
                (row["bucket"],),
            )
        ]
        payload = {
            "bucket": row["bucket"],
            "seen_count": row["seen_count"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "samples": samples,
        }
        candidates.append(payload)
        if not existing:
            conn.execute(
                """
                INSERT INTO parser_rule_candidates
                (bucket, seen_count, first_seen, last_seen, samples_json, status)
                VALUES (?, ?, ?, ?, ?, 'new')
                """,
                (
                    row["bucket"],
                    row["seen_count"],
                    row["first_seen"],
                    row["last_seen"],
                    __import__("json").dumps(samples, indent=2),
                ),
            )

    conn.commit()
    conn.close()
    return candidates

