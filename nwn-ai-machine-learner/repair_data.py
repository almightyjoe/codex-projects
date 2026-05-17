"""Repair local runtime data after parser/schema changes.

This is intentionally local and repeatable: it fixes player-character flags in
combat.db from observed log identity lines and can seed a richer legacy
bestiary.db when the copied Rev 1 database is present on this machine.
"""
import os
import re
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BESTIARY_DB, COMBAT_DB, NWN_LOG_DIR, NWN_LOG_FILES, PLAYER_CHARACTERS
from data.init_db import init_all
from parser.event_parser import parse_line

LEGACY_BESTIARY_DB = r"D:\1claudecode\NWN-AI\data\bestiary.db"

_PLAYER_DETECTED = re.compile(r"Player detected:\s*(.+)$")
_PARTY_STATUS = re.compile(r"Party:\s*(.+?)\s+\[Level\s+\d+\]")


def _chat_lines():
    for fn in NWN_LOG_FILES:
        path = os.path.join(NWN_LOG_DIR, fn)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="cp1252", errors="replace") as fh:
            for raw in fh:
                raw = raw.rstrip("\r\n")
                if "[CHAT WINDOW TEXT]" in raw:
                    yield raw


def discover_pcs() -> dict[str, str]:
    pcs = {name: "config" for name in PLAYER_CHARACTERS if name}
    for raw in _chat_lines():
        ev = parse_line(raw)
        if ev and ev.get("type") == "pc_detected":
            pcs[ev["name"]] = ev.get("channel", "log")
            continue
        content = raw.split("] ", 2)[-1]
        for regex, source in ((_PLAYER_DETECTED, "player_detected"), (_PARTY_STATUS, "party_status")):
            m = regex.search(content)
            if m:
                pcs[m.group(1).strip()] = source
    return pcs


def repair_combat_flags() -> set[str]:
    init_all()
    pcs = discover_pcs()
    conn = sqlite3.connect(COMBAT_DB)
    for name, source in pcs.items():
        conn.execute(
            """
            INSERT INTO detected_pcs(name, first_seen, last_seen, source)
            VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(name) DO UPDATE SET last_seen=CURRENT_TIMESTAMP, source=excluded.source
            """,
            (name, source),
        )

    # Tell senders were an old false-positive source; keep real PCs discovered elsewhere.
    if pcs:
        conn.execute(
            "DELETE FROM detected_pcs WHERE source='Tell' AND name NOT IN (%s)"
            % ",".join("?" for _ in pcs),
            tuple(pcs),
        )
    else:
        conn.execute("DELETE FROM detected_pcs WHERE source='Tell'")

    pc_names = [r[0] for r in conn.execute("SELECT name FROM detected_pcs")]
    if pc_names:
        placeholders = ",".join("?" for _ in pc_names)
        conn.execute(f"UPDATE attacks SET attacker_is_pc=CASE WHEN attacker IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE attacks SET defender_is_pc=CASE WHEN defender IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE damages SET attacker_is_pc=CASE WHEN attacker IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE damages SET defender_is_pc=CASE WHEN defender IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE kills SET killer_is_pc=CASE WHEN killer IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE kills SET victim_is_pc=CASE WHEN victim IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE saves SET target_is_pc=CASE WHEN target IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
        conn.execute(f"UPDATE spells SET caster_is_pc=CASE WHEN caster IN ({placeholders}) THEN 1 ELSE 0 END", pc_names)
    conn.commit()
    conn.close()
    return set(pc_names)


def seed_legacy_bestiary_if_better() -> bool:
    if not os.path.isfile(LEGACY_BESTIARY_DB):
        return False
    init_all()
    current_areas = 0
    if os.path.isfile(BESTIARY_DB):
        conn = sqlite3.connect(BESTIARY_DB)
        try:
            current_areas = conn.execute("SELECT COUNT(*) FROM areas").fetchone()[0]
        finally:
            conn.close()
    legacy = sqlite3.connect(LEGACY_BESTIARY_DB)
    try:
        legacy_areas = legacy.execute("SELECT COUNT(*) FROM areas").fetchone()[0]
    finally:
        legacy.close()
    if legacy_areas <= current_areas:
        return False
    backup = BESTIARY_DB + ".before-legacy-seed"
    if os.path.exists(BESTIARY_DB) and not os.path.exists(backup):
        shutil.copy2(BESTIARY_DB, backup)
    shutil.copy2(LEGACY_BESTIARY_DB, BESTIARY_DB)
    return True


if __name__ == "__main__":
    pcs = repair_combat_flags()
    copied = seed_legacy_bestiary_if_better()
    print(f"PCs tagged: {', '.join(sorted(pcs)) if pcs else '(none)'}")
    print(f"Legacy bestiary seeded: {copied}")
