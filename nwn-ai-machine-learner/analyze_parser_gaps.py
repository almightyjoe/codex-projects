"""Scan historical NWN logs for unparsed patterns and create learning candidates."""
import os
import sqlite3

from config import COMBAT_DB, NWN_LOG_DIR, NWN_LOG_FILES
from data.init_db import init_all
from parser.event_parser import parse_line
from parser.learning import analyze_unparsed, make_unparsed_event


def main():
    init_all()
    conn = sqlite3.connect(COMBAT_DB)
    inserted = 0

    for name in NWN_LOG_FILES:
        path = os.path.join(NWN_LOG_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="cp1252", errors="replace") as handle:
            for raw in handle:
                raw = raw.rstrip("\r\n")
                if not raw.startswith("[CHAT WINDOW TEXT]"):
                    continue
                if parse_line(raw) is not None:
                    continue
                ev = make_unparsed_event(raw, source_file=name)
                conn.execute(
                    """
                    INSERT INTO unparsed_lines
                    (session_id,ts,source_file,area_name,bucket,content,raw_line)
                    VALUES (NULL,?,?,?,?,?,?)
                    """,
                    (
                        ev["ts"],
                        ev["source_file"],
                        ev["area"],
                        ev["bucket"],
                        ev["content"],
                        ev["raw_line"],
                    ),
                )
                inserted += 1

    conn.commit()
    conn.close()
    candidates = analyze_unparsed()
    print(f"Inserted {inserted} unparsed historical lines.")
    print(f"Generated/updated {len(candidates)} parser learning buckets.")
    for item in candidates[:20]:
        print(f"{item['seen_count']:5d}  {item['bucket']}")


if __name__ == "__main__":
    main()

