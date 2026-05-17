"""
Consume parsed event dicts from the queue and batch-flush to combat.db.
Runs as a daemon thread so the main process never blocks on disk I/O.
"""
import sqlite3, queue, threading, time, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import COMBAT_DB, DB_FLUSH_INTERVAL, PLAYER_CHARACTERS
from datetime import datetime
from parser.event_parser import DMG_COLS   # canonical ordered column list


class DBWriter(threading.Thread):
    def __init__(self, event_queue):
        super().__init__(daemon=True, name='DBWriter')
        self.queue     = event_queue
        self._stop_evt = threading.Event()
        self.pc_set    = set(PLAYER_CHARACTERS)
        self.session_id = None

    def stop(self):
        self._stop_evt.set()

    def _connect(self):
        conn = sqlite3.connect(COMBAT_DB, check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn

    def _start_session(self, conn):
        cur = conn.execute(
            'INSERT INTO sessions (start_time, log_file) VALUES (?, ?)',
            (datetime.now().isoformat(), 'nwclientLog')
        )
        conn.commit()
        self.session_id = cur.lastrowid
        print(f'[DBWriter] session {self.session_id} started')

    def _end_session(self, conn):
        if self.session_id:
            conn.execute(
                'UPDATE sessions SET end_time=? WHERE id=?',
                (datetime.now().isoformat(), self.session_id)
            )
            conn.commit()

    # Damage INSERT: uses DMG_COLS to build statement dynamically
    _DMG_INSERT_COLS = (
        'session_id,ts,attacker,defender,total_damage,'
        + ','.join(DMG_COLS)
        + ',attacker_is_pc,defender_is_pc'
    )
    _DMG_INSERT_STMT = (
        'INSERT INTO damages (' + _DMG_INSERT_COLS + ') VALUES ('
        + ','.join(['?'] * (5 + len(DMG_COLS) + 2)) + ')'
    )

    def _dmg_row(self, ev, sid):
        base = (sid, ev['ts'], ev['attacker'], ev['defender'], ev['total_damage'])
        dmg_vals = tuple(ev.get(col, 0) for col in DMG_COLS)
        tail = (ev.get('attacker_is_pc', 0), ev.get('defender_is_pc', 0))
        return base + dmg_vals + tail

    def _flush(self, conn, batch: list):
        if not batch:
            return

        attacks, damages, saves, kills, averts, spells, checks, unparsed = [], [], [], [], [], [], [], []

        for ev in batch:
            t   = ev.get('type')
            sid = self.session_id

            if t == 'attack':
                attacks.append((
                    sid, ev['ts'], ev['attacker'], ev['defender'],
                    ev.get('modes', ''), ev['hit_type'],
                    ev.get('concealment_pct', 0),
                    ev['roll'], ev['bonus'], ev['total'],
                    ev.get('threat_roll'), ev.get('threat_total'),
                    ev.get('attacker_is_pc', 0), ev.get('defender_is_pc', 0),
                ))

            elif t == 'damage':
                damages.append(self._dmg_row(ev, sid))

            elif t == 'save':
                saves.append((
                    sid, ev['ts'], ev['target'], ev['save_type'],
                    ev.get('check_type', 'save'), ev.get('vs_source', ''), ev['result'],
                    ev['roll'], ev['bonus'], ev['total'], ev['dc'],
                    ev.get('spell_name', ''),
                    ev.get('target_is_pc', 0),
                ))

            elif t == 'kill':
                kills.append((
                    sid, ev['ts'], ev['killer'], ev['victim'], 0,
                    ev.get('killer_is_pc', 0), ev.get('victim_is_pc', 0),
                ))

            elif t == 'death_averted':
                averts.append((
                    sid, ev['ts'], ev.get('target', ''), ev.get('ability', ''),
                    ev.get('target_is_pc', 0),
                ))

            elif t == 'xp':
                if kills:
                    kills[-1] = kills[-1][:4] + (ev['xp'],) + kills[-1][5:]

            elif t == 'spell':
                spells.append((
                    sid, ev['ts'], ev['caster'],
                    ev.get('spell_name', ''), ev.get('action', ''),
                    ev.get('is_song', 0), ev.get('caster_is_pc', 0),
                ))

            elif t == 'spell_check':
                checks.append((
                    sid, ev['ts'],
                    ev.get('source', ''), ev.get('target', ''),
                    ev.get('check_type', ''), ev.get('result', ''),
                    ev.get('roll'), ev.get('bonus'), ev.get('total'),
                    ev.get('dc'), ev.get('sr_value'), ev.get('spell_name', ''),
                    ev.get('vs_value'),
                ))

            elif t == 'area':
                conn.execute(
                    'INSERT INTO area_log (session_id,ts,area_name) VALUES (?,?,?)',
                    (sid, ev['ts'], ev.get('area', ''))
                )

            elif t == 'pc_immunity':
                cols = ['session_id', 'ts', 'pc_name', 'area_name']
                vals = [sid, ev['ts'], ev.get('pc_name', 'Unknown PC'), ev.get('area', '')]
                for field in [
                    'imm_bludgeoning','imm_piercing','imm_slashing','imm_magical',
                    'imm_acid','imm_cold','imm_divine','imm_electrical','imm_fire',
                    'imm_negative','imm_positive','imm_sonic','imm_subdual',
                    'imm_ectoplasmic','imm_psionic','imm_sacred','imm_vile',
                    'imm_primal','imm_anarchic','imm_axiomatic',
                    'res_bludgeoning','res_piercing','res_slashing','res_magical',
                    'res_acid','res_cold','res_divine','res_electrical','res_fire',
                    'res_negative','res_positive','res_sonic',
                ]:
                    if field in ev:
                        cols.append(field)
                        vals.append(ev[field])
                conn.execute(
                    f'INSERT INTO pc_status ({",".join(cols)}) VALUES ({",".join(["?"]*len(vals))})',
                    vals
                )

            elif t == 'debuff_alert':
                conn.execute(
                    'INSERT INTO debuff_alerts '
                    '(session_id,ts,pc_name,area_name,damage_type,old_value,new_value,drop_amount,alert_level,reason)'
                    ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (sid, ev['ts'], ev.get('pc_name', 'Unknown PC'), ev.get('area', ''),
                     ev['damage_type'], ev['old_value'], ev['new_value'],
                     ev['drop_amount'], ev['alert_level'], ev.get('reason', ''))
                )

            elif t == 'unparsed':
                unparsed.append((
                    sid,
                    ev.get('ts'),
                    ev.get('source_file', ''),
                    ev.get('area', ''),
                    ev.get('bucket', ''),
                    ev.get('content', ''),
                    ev.get('raw_line', ''),
                ))

        if attacks:
            conn.executemany(
                'INSERT INTO attacks (session_id,ts,attacker,defender,modes,hit_type,'
                'concealment_pct,roll,bonus,total,threat_roll,threat_total,'
                'attacker_is_pc,defender_is_pc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                attacks)
        if damages:
            conn.executemany(self._DMG_INSERT_STMT, damages)
        if saves:
            conn.executemany(
                'INSERT INTO saves (session_id,ts,target,save_type,check_type,vs_source,'
                'result,roll,bonus,total,dc,spell_name,target_is_pc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                saves)
        if kills:
            conn.executemany(
                'INSERT INTO kills (session_id,ts,killer,victim,xp_gained,'
                'killer_is_pc,victim_is_pc) VALUES (?,?,?,?,?,?,?)',
                kills)
        if averts:
            conn.executemany(
                'INSERT INTO death_averts (session_id,ts,target,ability,target_is_pc)'
                ' VALUES (?,?,?,?,?)',
                averts)
        if spells:
            conn.executemany(
                'INSERT INTO spells (session_id,ts,caster,spell_name,action,is_song,caster_is_pc)'
                ' VALUES (?,?,?,?,?,?,?)',
                spells)
        if checks:
            conn.executemany(
                'INSERT INTO spell_checks (session_id,ts,source,target,check_type,'
                'result,roll,bonus,total,dc,sr_value,spell_name,vs_value) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                checks)
        if unparsed:
            conn.executemany(
                'INSERT INTO unparsed_lines '
                '(session_id,ts,source_file,area_name,bucket,content,raw_line) '
                'VALUES (?,?,?,?,?,?,?)',
                unparsed)

        conn.commit()

    def run(self):
        conn = self._connect()
        self._start_session(conn)
        print('[DBWriter] started')

        while not self._stop_evt.is_set():
            batch = []
            try:
                while True:
                    batch.append(self.queue.get_nowait())
            except queue.Empty:
                pass

            if batch:
                try:
                    self._flush(conn, batch)
                except Exception as e:
                    print(f'[DBWriter] flush error: {e}')

            time.sleep(DB_FLUSH_INTERVAL)

        batch = []
        while not self.queue.empty():
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        self._flush(conn, batch)
        self._end_session(conn)
        conn.close()
        print('[DBWriter] stopped')
