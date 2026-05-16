"""Load all existing log files into combat.db for testing/history."""
import os, sys, sqlite3, queue
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import NWN_LOG_DIR, NWN_LOG_FILES, COMBAT_DB, PLAYER_CHARACTERS
from parser.event_parser import parse_line
from parser.db_writer import DBWriter

def load_all_logs():
    pc_set    = set(PLAYER_CHARACTERS)
    ev_queue  = queue.Queue()
    writer    = DBWriter(ev_queue)
    writer.start()

    total_lines = 0
    total_parsed = 0

    for fn in NWN_LOG_FILES:
        path = os.path.join(NWN_LOG_DIR, fn)
        if not os.path.isfile(path):
            continue
        print(f'Loading {fn}...')
        lines = 0
        parsed = 0
        with open(path, encoding='cp1252', errors='replace') as f:
            for raw in f:
                raw = raw.rstrip('\r\n')
                if '[CHAT WINDOW TEXT]' not in raw:
                    continue
                lines += 1
                ev = parse_line(raw)
                if ev:
                    parsed += 1
                    ev['attacker_is_pc'] = int(ev.get('attacker','') in pc_set)
                    ev['defender_is_pc'] = int(ev.get('defender','') in pc_set)
                    ev['target_is_pc']   = int(ev.get('target',  '') in pc_set)
                    ev['killer_is_pc']   = int(ev.get('killer',  '') in pc_set)
                    ev['victim_is_pc']   = int(ev.get('victim',  '') in pc_set)
                    ev['caster_is_pc']   = int(ev.get('caster',  '') in pc_set)
                    ev_queue.put(ev)
        print(f'  {parsed}/{lines} lines parsed ({100*parsed//lines if lines else 0}%)')
        total_lines  += lines
        total_parsed += parsed

    # wait for writer to flush
    import time
    while not ev_queue.empty():
        time.sleep(0.2)
    time.sleep(1)
    writer.stop()
    writer.join(timeout=5)

    conn = sqlite3.connect(COMBAT_DB)
    counts = {
        'attacks': conn.execute('SELECT COUNT(*) FROM attacks').fetchone()[0],
        'damages': conn.execute('SELECT COUNT(*) FROM damages').fetchone()[0],
        'kills':   conn.execute('SELECT COUNT(*) FROM kills').fetchone()[0],
        'saves':   conn.execute('SELECT COUNT(*) FROM saves').fetchone()[0],
    }
    conn.close()
    print(f'\nDB totals: {counts}')
    print(f'Total: {total_parsed}/{total_lines} lines parsed.')

if __name__ == '__main__':
    load_all_logs()
