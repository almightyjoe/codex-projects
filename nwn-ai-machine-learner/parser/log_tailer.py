"""
Tail NWN log files in real-time.
Handles multi-line immunity blocks and dynamic PC name detection.
"""
import os, time, threading, sqlite3
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import (
    NWN_LOG_DIR, NWN_LOG_FILES, LOG_POLL_INTERVAL, COMBAT_DB, BESTIARY_DB,
    PLAYER_CHARACTERS,
)
from parser.event_parser import parse_line, parse_immunity_line
from parser.learning import make_unparsed_event

ALERTABLE_IMMUNITY_TYPES = {
    'bludgeoning', 'piercing', 'slashing', 'magical',
    'acid', 'cold', 'divine', 'electrical', 'fire',
    'negative', 'positive', 'sonic',
}


class LogTailer(threading.Thread):
    def __init__(self, event_queue, pc_set: set, socketio=None):
        super().__init__(daemon=True, name='LogTailer')
        self.queue      = event_queue
        self.pc_set     = pc_set
        self.socketio   = socketio
        self._stop_evt  = threading.Event()
        self._file_pos  = {}
        self._current_area = ''
        self._current_pc   = 'Unknown PC'

        # multi-line immunity block state
        self._in_imm_block = False
        self._imm_ts       = None
        self._imm_data     = {}
        self._imm_dr       = {}

        # debuff tracking: last known immunity values
        self._last_imm     = {}
        self._last_spell_by_caster = {}

    def stop(self):
        self._stop_evt.set()

    def _active_log(self) -> str | None:
        candidates = []
        for fn in NWN_LOG_FILES:
            path = os.path.join(NWN_LOG_DIR, fn)
            if os.path.isfile(path):
                candidates.append((os.path.getmtime(path), path))
        if not candidates:
            return None
        return sorted(candidates, reverse=True)[0][1]

    def _remember_current_pc_candidate(self, name: str, source: str):
        """Use strong PC identity lines to attach later immunity blocks to a PC."""
        if source in {'welcome', 'player_detected'} and name:
            self._current_pc = name

    def _infer_current_pc_from_log(self, path: str):
        """Pre-scan the current log so replayed early immunity blocks are named."""
        try:
            with open(path, 'r', encoding='cp1252', errors='replace') as fh:
                for raw in fh:
                    ev = parse_line(raw.rstrip('\r\n'))
                    if ev and ev.get('type') == 'pc_detected' and ev.get('is_current_pc'):
                        self._current_pc = ev.get('name', self._current_pc)
        except OSError:
            pass

    def _read_new_lines(self, path: str) -> list[str]:
        size = os.path.getsize(path)
        pos  = self._file_pos.get(path, 0)
        if size < pos:
            pos = 0
        if size == pos:
            return []
        lines = []
        with open(path, 'r', encoding='cp1252', errors='replace') as fh:
            fh.seek(pos)
            for raw in fh:
                lines.append(raw.rstrip('\r\n'))
            self._file_pos[path] = fh.tell()
        return lines

    def _register_pc(self, name: str, source: str, ts: str, is_current_pc: int = 0):
        if not name or len(name) < 2:
            return
        if name in self.pc_set:
            # just update last_seen
            try:
                conn = sqlite3.connect(COMBAT_DB)
                conn.execute(
                    'UPDATE detected_pcs SET last_seen=? WHERE name=?', (ts, name)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass
            return
        self.pc_set.add(name)
        try:
            conn = sqlite3.connect(COMBAT_DB)
            conn.execute(
                'INSERT OR IGNORE INTO detected_pcs (name, first_seen, last_seen, source)'
                ' VALUES (?,?,?,?)',
                (name, ts, ts, source)
            )
            conn.execute(
                'UPDATE detected_pcs SET last_seen=? WHERE name=?', (ts, name)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        print(f'[LogTailer] PC detected: {name} ({source})')

    def _check_debuffs(self, imm_data: dict, ts: str) -> list[dict]:
        """Compare current immunity values vs last known — emit debuff alerts."""
        alerts = []
        for dtype, pct in imm_data.items():
            prev = self._last_imm.get(dtype, pct)
            drop = prev - pct
            if drop >= 20:
                level = 'CRITICAL' if pct < 20 else 'WARNING'
                alerts.append({
                    'type':        'debuff_alert',
                    'ts':          ts,
                    'damage_type': dtype,
                    'old_value':   prev,
                    'new_value':   pct,
                    'drop_amount': drop,
                    'alert_level': level,
                })
        self._last_imm.update(imm_data)
        return alerts

    def _area_risk_for_damage(self, dtype: str) -> str:
        if not self._current_area or not os.path.isfile(BESTIARY_DB):
            return ''
        try:
            conn = sqlite3.connect(BESTIARY_DB)
            row = conn.execute(
                """
                SELECT GROUP_CONCAT(c.name, ', ') AS names
                FROM creatures c
                JOIN creature_areas ca ON ca.creature_id=c.id
                JOIN areas a ON a.id=ca.area_id
                WHERE a.name=?
                  AND (
                    LOWER(COALESCE(c.deals,'')) LIKE ?
                    OR LOWER(COALESCE(c.special_abilities,'')) LIKE ?
                  )
                LIMIT 1
                """,
                (self._current_area, f'%{dtype.lower()}%', f'%{dtype.lower()}%'),
            ).fetchone()
            conn.close()
            return row[0] if row and row[0] else ''
        except Exception:
            return ''

    def _check_debuffs(self, pc_name: str, imm_data: dict, ts: str) -> list[dict]:
        alerts = []
        last_for_pc = self._last_imm.setdefault(pc_name, {})
        for dtype, pct in imm_data.items():
            if dtype not in ALERTABLE_IMMUNITY_TYPES:
                continue
            prev = last_for_pc.get(dtype, pct)
            drop = prev - pct
            risk_mobs = self._area_risk_for_damage(dtype)
            reason = ''
            level = ''
            if pct < 0:
                level = 'CRITICAL'
                reason = 'immunity is below zero'
            elif pct < 20:
                level = 'CRITICAL'
                reason = 'immunity is critically low'
            elif drop >= 20:
                level = 'CRITICAL' if pct < 50 else 'WARNING'
                reason = f'immunity dropped by {drop:g} points'
            elif pct < 50 and risk_mobs:
                level = 'WARNING'
                reason = f'low immunity in area with known {dtype} threats: {risk_mobs}'

            if level:
                alerts.append({
                    'type':        'debuff_alert',
                    'ts':          ts,
                    'pc_name':     pc_name,
                    'area':        self._current_area,
                    'damage_type': dtype,
                    'old_value':   prev,
                    'new_value':   pct,
                    'drop_amount': drop,
                    'alert_level': level,
                    'reason':      reason,
                })
        last_for_pc.update(imm_data)
        return alerts

    def _flush_imm_block(self, ts: str) -> list[dict]:
        """Finalize accumulated immunity block into events."""
        if not self._imm_data:
            return []
        ev = {
            'type':      'pc_immunity',
            'ts':        ts,
            'pc_name':   self._current_pc,
            'area':      self._current_area,
            **{f'imm_{k}': v for k, v in self._imm_data.items()},
            **{f'res_{k}': v for k, v in self._imm_dr.items()},
        }
        debuffs = self._check_debuffs(self._current_pc, self._imm_data, ts)
        self._imm_data = {}
        self._imm_dr   = {}
        self._in_imm_block = False
        return [ev] + debuffs

    def _tag(self, ev: dict) -> dict:
        """Tag attacker/defender/target as PC or mob."""
        for role in ('attacker', 'defender', 'target', 'killer', 'victim', 'caster'):
            key = f'{role}_is_pc'
            name = ev.get(role, '')
            stripped = name.strip(' .')
            ev[key] = int(bool(name and (name in self.pc_set or stripped in self.pc_set)))
        return ev

    def _emit(self, ev: dict):
        self.queue.put(ev)
        if self.socketio:
            try:
                self.socketio.emit('event', ev)
            except Exception:
                pass

    def run(self):
        print('[LogTailer] started')
        last_path = None

        # Load existing detected PCs from DB into pc_set
        try:
            conn = sqlite3.connect(COMBAT_DB)
            for row in conn.execute('SELECT name FROM detected_pcs'):
                self.pc_set.add(row[0])
            conn.close()
        except Exception:
            pass

        while not self._stop_evt.is_set():
            path = self._active_log()
            if not path:
                time.sleep(LOG_POLL_INTERVAL)
                continue

            if path != last_path:
                print(f'[LogTailer] watching {os.path.basename(path)}')
                print('[LogTailer] replaying current log for restart context')
                self._infer_current_pc_from_log(path)
                self._file_pos[path] = 0
                last_path = path

            for raw in self._read_new_lines(path):
                # --- Multi-line immunity block continuation ---
                if self._in_imm_block and not raw.startswith('[CHAT WINDOW TEXT]'):
                    imm = parse_immunity_line(raw)
                    if imm:
                        self._imm_data[imm['dtype']] = imm['pct']
                        if imm['dr']:
                            self._imm_dr[imm['dtype']] = imm['dr']
                    continue
                elif self._in_imm_block:
                    # CHAT line arrived — flush accumulated block
                    for ev in self._flush_imm_block(self._imm_ts):
                        self._emit(self._tag(ev))

                ev = parse_line(raw)
                if ev is None:
                    if raw.startswith('[CHAT WINDOW TEXT]'):
                        self._emit(self._tag(make_unparsed_event(
                            raw,
                            source_file=os.path.basename(path),
                            area=self._current_area,
                        )))
                    continue

                # --- Handle special event types ---
                if ev['type'] == 'immunity_block_start':
                    self._in_imm_block = True
                    self._imm_ts = ev['ts']
                    self._imm_data = {}
                    self._imm_dr   = {}
                    continue

                if ev['type'] == 'area':
                    self._current_area = ev['area']
                    self._emit(ev)
                    continue

                if ev['type'] == 'pc_detected':
                    if ev.get('is_current_pc'):
                        self._current_pc = ev['name']
                    self._remember_current_pc_candidate(ev['name'], ev.get('channel', ''))
                    self._register_pc(
                        ev['name'], ev['channel'], ev['ts'],
                        ev.get('is_current_pc', 0),
                    )
                    # also emit so dashboard can update PC list
                    self._emit(ev)
                    continue

                if ev['type'] == 'account_detected':
                    self._emit(ev)
                    continue

                # infer PCs from kill/resurrect events
                if ev['type'] == 'kill':
                    # if victim in pc_set, killer is mob (and vice versa)
                    if ev.get('victim') in self.pc_set:
                        pass  # killer is mob, already known
                    elif ev.get('killer') in self.pc_set:
                        pass  # victim is mob, already known

                if ev['type'] == 'resurrect':
                    self._register_pc(ev.get('caster', ''), 'resurrect', ev['ts'])
                    self._register_pc(ev.get('target', ''), 'resurrect', ev['ts'])

                if ev['type'] == 'death_averted':
                    self._register_pc(ev.get('target', ''), 'death_averted', ev['ts'])

                if ev['type'] == 'spell':
                    caster = ev.get('caster', '')
                    if caster:
                        self._last_spell_by_caster[caster] = ev.get('spell_name', '')

                if ev['type'] == 'spell_check':
                    source = ev.get('source', '')
                    if source and not ev.get('spell_name'):
                        ev['spell_name'] = self._last_spell_by_caster.get(source, '')

                if ev['type'] == 'save':
                    source = ev.get('vs_source', '')
                    if source and not ev.get('spell_name'):
                        ev['spell_name'] = self._last_spell_by_caster.get(source, '')

                self._emit(self._tag(ev))

            time.sleep(LOG_POLL_INTERVAL)

        print('[LogTailer] stopped')
