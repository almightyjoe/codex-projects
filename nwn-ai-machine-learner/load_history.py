"""Load existing log files into combat.db for testing/history."""
import os, sys, sqlite3, queue, argparse, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import NWN_LOG_DIR, NWN_LOG_FILES, COMBAT_DB, PLAYER_CHARACTERS
from parser.event_parser import parse_line
from parser.db_writer import DBWriter
from data.init_db import init_all


def _iter_chat_lines():
    for fn in NWN_LOG_FILES:
        path = os.path.join(NWN_LOG_DIR, fn)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='cp1252', errors='replace') as f:
            for raw in f:
                raw = raw.rstrip('\r\n')
                if '[CHAT WINDOW TEXT]' in raw:
                    yield fn, raw


def discover_pcs_from_logs() -> set[str]:
    pcs = set(PLAYER_CHARACTERS)
    for _, raw in _iter_chat_lines():
        ev = parse_line(raw)
        if ev and ev.get('type') == 'pc_detected':
            pcs.add(ev['name'])
        if ev and ev.get('type') == 'death_averted':
            pcs.add(ev['target'])
    return {p for p in pcs if p}


def is_pc_name(name: str, pc_set: set[str]) -> bool:
    return bool(name and (name in pc_set or name.strip(' .') in pc_set))


def reset_combat_db():
    if os.path.exists(COMBAT_DB):
        backup = COMBAT_DB + '.before-history-reset'
        if not os.path.exists(backup):
            shutil.copy2(COMBAT_DB, backup)
        os.remove(COMBAT_DB)
    for suffix in ('-wal', '-shm'):
        path = COMBAT_DB + suffix
        if os.path.exists(path):
            os.remove(path)
    init_all()

def load_all_logs(reset: bool = False):
    if reset:
        reset_combat_db()
    else:
        init_all()
    pc_set    = discover_pcs_from_logs()
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
                    if ev.get('type') == 'pc_detected':
                        pc_set.add(ev['name'])
                        continue
                    if ev.get('type') == 'death_averted':
                        pc_set.add(ev['target'])
                    if ev.get('type') == 'account_detected':
                        continue
                    parsed += 1
                    ev['attacker_is_pc'] = int(is_pc_name(ev.get('attacker',''), pc_set))
                    ev['defender_is_pc'] = int(is_pc_name(ev.get('defender',''), pc_set))
                    ev['target_is_pc']   = int(is_pc_name(ev.get('target',  ''), pc_set))
                    ev['killer_is_pc']   = int(is_pc_name(ev.get('killer',  ''), pc_set))
                    ev['victim_is_pc']   = int(is_pc_name(ev.get('victim',  ''), pc_set))
                    ev['caster_is_pc']   = int(is_pc_name(ev.get('caster',  ''), pc_set))
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
    ap = argparse.ArgumentParser()
    ap.add_argument('--reset', action='store_true', help='backup and rebuild combat.db from log files')
    args = ap.parse_args()
    load_all_logs(reset=args.reset)
