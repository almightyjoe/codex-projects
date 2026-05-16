"""
Tail NWN log files in real-time.
Handles multi-line immunity blocks and dynamic PC name detection.
"""
import os, time, threading, sqlite3
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import NWN_LOG_DIR, NWN_LOG_FILES, LOG_POLL_INTERVAL, COMBAT_DB, PLAYER_CHARACTERS
from parser.event_parser import parse_line, parse_immunity_line
from parser.learning import make_unparsed_event


class LogTailer(threading.Thread):
    def __init__(self, event_queue, pc_set: set, socketio=None):
        super().__init__(daemon=True, name='LogTailer')
        self.queue      = event_queue
        self.pc_set     = pc_set
        self.socketio   = socketio
        self._stop_evt  = threading.Event()
        self._file_pos  = {}
        self._current_area = ''

        # multi-line immunity block state
        self._in_imm_block = False
        self._imm_ts       = None
        self._imm_data     = {}
        self._imm_dr       = {}

        # debuff tracking: last known immunity values
        self._last_imm     = {}

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

    def _register_pc(self, name: str, source: str, ts: str):
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

    def _flush_imm_block(self, ts: str) -> list[dict]:
        """Finalize accumulated immunity block into events."""
        if not self._imm_data:
            return []
        ev = {
            'type':      'pc_immunity',
            'ts':        ts,
            'area':      self._current_area,
            **{f'imm_{k}': v for k, v in self._imm_data.items()},
            **{f'res_{k}': v for k, v in self._imm_dr.items()},
        }
        debuffs = self._check_debuffs(self._imm_data, ts)
        self._imm_data = {}
        self._imm_dr   = {}
        self._in_imm_block = False
        return [ev] + debuffs

    def _tag(self, ev: dict) -> dict:
        """Tag attacker/defender/target as PC or mob."""
        for role in ('attacker', 'defender', 'target', 'killer', 'victim', 'caster'):
            key = f'{role}_is_pc'
            name = ev.get(role, '')
            ev[key] = int(bool(name and name in self.pc_set))
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
                self._file_pos[path] = os.path.getsize(path)
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
                    self._register_pc(ev['name'], ev['channel'], ev['ts'])
                    # also emit so dashboard can update PC list
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

                self._emit(self._tag(ev))

            time.sleep(LOG_POLL_INTERVAL)

        print('[LogTailer] stopped')
