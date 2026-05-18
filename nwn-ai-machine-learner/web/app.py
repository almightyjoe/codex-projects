"""
Flask + SocketIO web server.
Serves the dashboard and handles AI query API calls.
"""
import os, sys, threading, subprocess, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

from query.sql_queries import (
    stat_snapshot, top_damage_to_pcs, top_damage_types_received,
    kills_by_mob, save_summary, save_failures, recent_events,
    mob_info, best_damage_vs_mob, search_mobs, mobs_in_area,
    session_list, mob_damage_dealt, pc_damage_dealt, attack_accuracy,
    area_threat_summary, creature_list, spell_usage_summary, bard_songs_summary,
    bard_signal_summary,
    damage_breakdown, accuracy_detail, spell_check_summary,
    recent_save_failures, pc_kill_detail,
    pc_save_pressure, monster_save_summary, recent_monster_saves,
)
from query.ai_query import ask, ollama_status
from parser.learning import analyze_unparsed
from config import BESTIARY_DB, COMBAT_DB, CREATURES_JSON, HGX_DIR, NWN_LOG_DIR, WEB_PORT

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'nwnai-secret'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _delayed_exit():
    os._exit(0)


def _bestiary_counts():
    conn = sqlite3.connect(BESTIARY_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        '''
        SELECT
          (SELECT COUNT(*) FROM creatures) AS creatures,
          (SELECT COUNT(*) FROM areas) AS areas,
          (SELECT COUNT(*) FROM creature_areas) AS links
        '''
    ).fetchone()
    conn.close()
    return dict(row)


def _spawn_restart():
    helper = os.path.join(BASE_DIR, 'restart_service.py')
    args = [sys.executable, helper, str(os.getpid()), str(WEB_PORT), BASE_DIR]
    flags = 0
    if os.name == 'nt':
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    log_path = os.path.join(BASE_DIR, 'data', 'restart_service.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log = open(log_path, 'a', encoding='utf-8')
    subprocess.Popen(
        args,
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        close_fds=True,
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route('/')
def dashboard():
    return render_template('dashboard.html')


# ---------------------------------------------------------------------------
# REST API — dashboard data
# ---------------------------------------------------------------------------

@app.route('/api/snapshot')
def api_snapshot():
    sid = request.args.get('session')
    return jsonify(stat_snapshot(int(sid) if sid else None))


@app.route('/api/damage_in')
def api_damage_in():
    sid = request.args.get('session')
    return jsonify(top_damage_types_received(int(sid) if sid else None))


@app.route('/api/top_attackers')
def api_top_attackers():
    sid = request.args.get('session')
    return jsonify(top_damage_to_pcs(int(sid) if sid else None))


@app.route('/api/kills_by_mob')
def api_kills_by_mob():
    sid = request.args.get('session')
    return jsonify(kills_by_mob(int(sid) if sid else None))


@app.route('/api/save_summary')
def api_save_summary():
    sid = request.args.get('session')
    return jsonify(save_summary(int(sid) if sid else None))


@app.route('/api/pc_save_pressure')
def api_pc_save_pressure():
    sid = request.args.get('session')
    return jsonify(pc_save_pressure(int(sid) if sid else None))


@app.route('/api/monster_save_summary')
def api_monster_save_summary():
    sid = request.args.get('session')
    return jsonify(monster_save_summary(int(sid) if sid else None))


@app.route('/api/monster_saves_recent')
def api_monster_saves_recent():
    sid = request.args.get('session')
    return jsonify(recent_monster_saves(int(sid) if sid else None))


@app.route('/api/save_failures')
def api_save_failures():
    sid = request.args.get('session')
    return jsonify(save_failures(int(sid) if sid else None))


@app.route('/api/recent')
def api_recent():
    sid = request.args.get('session')
    n   = int(request.args.get('n', 60))
    return jsonify(recent_events(n, int(sid) if sid else None))


@app.route('/api/accuracy')
def api_accuracy():
    sid = request.args.get('session')
    return jsonify(attack_accuracy(session_id=int(sid) if sid else None))


@app.route('/api/sessions')
def api_sessions():
    return jsonify(session_list())


@app.route('/api/service/status')
def api_service_status():
    try:
        bestiary = _bestiary_counts()
    except Exception as e:
        bestiary = {'error': str(e)}
    return jsonify({
        'running': True,
        'pid': os.getpid(),
        'python': sys.executable,
        'port': WEB_PORT,
        'base_dir': BASE_DIR,
        'combat_db': COMBAT_DB,
        'bestiary_db': BESTIARY_DB,
        'creatures_json': CREATURES_JSON,
        'nwn_log_dir': NWN_LOG_DIR,
        'hgx_dir': HGX_DIR,
        'bestiary': bestiary,
    })


@app.route('/api/service/start', methods=['POST'])
def api_service_start():
    return jsonify({
        'ok': True,
        'message': 'NWN-AI is already running. Use restart to relaunch it.',
        'pid': os.getpid(),
    })


@app.route('/api/service/stop', methods=['POST'])
def api_service_stop():
    threading.Timer(0.8, _delayed_exit).start()
    return jsonify({'ok': True, 'message': 'Stopping NWN-AI server.'})


@app.route('/api/service/restart', methods=['POST'])
def api_service_restart():
    _spawn_restart()
    threading.Timer(0.8, _delayed_exit).start()
    return jsonify({'ok': True, 'message': 'Restarting NWN-AI server.'})


# ---------------------------------------------------------------------------
# Bestiary API
# ---------------------------------------------------------------------------

@app.route('/api/pc_status')
def api_pc_status():
    import sqlite3
    from config import COMBAT_DB
    conn = sqlite3.connect(COMBAT_DB)
    conn.row_factory = sqlite3.Row
    sid = request.args.get('session')
    params = []
    where = ''
    if sid:
        where = 'AND session_id=?'
        params.append(int(sid))
    named_count = conn.execute(
        f"SELECT COUNT(*) FROM pc_status WHERE COALESCE(pc_name, 'Unknown PC')<>'Unknown PC' {where}",
        params,
    ).fetchone()[0]
    status_filter = "AND COALESCE(pc_name, 'Unknown PC')<>'Unknown PC'" if named_count else ""
    rows = conn.execute(
        f'''
        SELECT ps.*
        FROM pc_status ps
        JOIN (
          SELECT pc_name, MAX(id) AS id
          FROM pc_status
          WHERE 1 {where} {status_filter}
          GROUP BY pc_name
        ) latest ON latest.id=ps.id
        ORDER BY ps.pc_name
        ''',
        params,
    ).fetchall()
    pcs = conn.execute(
        'SELECT name, first_seen, last_seen, source FROM detected_pcs ORDER BY last_seen DESC LIMIT 50'
    ).fetchall()
    alerts = conn.execute(
        f'SELECT * FROM debuff_alerts WHERE 1 {where} ORDER BY id DESC LIMIT 20',
        params,
    ).fetchall()
    area = conn.execute(
        f'SELECT area_name FROM area_log WHERE 1 {where} ORDER BY id DESC LIMIT 1',
        params,
    ).fetchone()
    conn.close()
    immunities = [dict(r) for r in rows]
    return jsonify({
        'immunity': immunities[0] if immunities else {},
        'immunities': immunities,
        'pcs': [dict(r) for r in pcs],
        'alerts': [dict(r) for r in alerts],
        'current_area': area['area_name'] if area else '',
    })


@app.route('/api/mob')
def api_mob():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    info = mob_info(name)
    if not info:
        return jsonify({'error': f'No creature found matching "{name}"'}), 404
    info['best_damage'] = best_damage_vs_mob(name)[:8]
    return jsonify(info)


@app.route('/api/search')
def api_search():
    q = request.args.get('q', '')
    return jsonify(search_mobs(q))


@app.route('/api/creatures')
def api_creatures():
    return jsonify(creature_list())


@app.route('/api/bestiary/status')
def api_bestiary_status():
    return jsonify(_bestiary_counts())


@app.route('/api/bestiary/repair', methods=['POST'])
def api_bestiary_repair():
    try:
        from repair_data import seed_legacy_bestiary_if_better
        changed = seed_legacy_bestiary_if_better()
        return jsonify({'ok': True, 'changed': changed, 'bestiary': _bestiary_counts()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'bestiary': _bestiary_counts()}), 500


@app.route('/api/spells')
def api_spells():
    sid = request.args.get('session')
    return jsonify(spell_usage_summary(int(sid) if sid else None))


@app.route('/api/songs')
def api_songs():
    sid = request.args.get('session')
    return jsonify(bard_songs_summary(int(sid) if sid else None))


@app.route('/api/bard_signals')
def api_bard_signals():
    sid = request.args.get('session')
    return jsonify(bard_signal_summary(int(sid) if sid else None))


@app.route('/api/area')
def api_area():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'name required'}), 400
    return jsonify({
        'mobs':    mobs_in_area(name),
        'summary': area_threat_summary(name),
    })


@app.route('/api/mob_damage')
def api_mob_damage():
    mob  = request.args.get('mob', '')
    sid  = request.args.get('session')
    return jsonify(mob_damage_dealt(mob, int(sid) if sid else None))


@app.route('/api/pc_damage')
def api_pc_damage():
    pc   = request.args.get('pc', '')
    sid  = request.args.get('session')
    return jsonify(pc_damage_dealt(pc or None, int(sid) if sid else None))


# ---------------------------------------------------------------------------
# Extended combat analysis
# ---------------------------------------------------------------------------

@app.route('/api/damage_breakdown')
def api_damage_breakdown():
    sid    = request.args.get('session')
    vs_pc  = request.args.get('vs', 'pc') == 'pc'
    return jsonify(damage_breakdown(int(sid) if sid else None, vs_pc=vs_pc))


@app.route('/api/accuracy_detail')
def api_accuracy_detail():
    sid     = request.args.get('session')
    pc_atk  = request.args.get('attacker', 'pc') == 'pc'
    return jsonify(accuracy_detail(int(sid) if sid else None, pc_attacks=pc_atk))


@app.route('/api/spell_checks')
def api_spell_checks():
    sid = request.args.get('session')
    return jsonify(spell_check_summary(int(sid) if sid else None))


@app.route('/api/save_failures_recent')
def api_save_failures_recent():
    sid = request.args.get('session')
    return jsonify(recent_save_failures(int(sid) if sid else None))


@app.route('/api/pc_kills')
def api_pc_kills():
    sid = request.args.get('session')
    return jsonify(pc_kill_detail(int(sid) if sid else None))


# ---------------------------------------------------------------------------
# AI Query API
# ---------------------------------------------------------------------------

@app.route('/api/ask', methods=['POST'])
def api_ask():
    data     = request.get_json(silent=True) or {}
    question = data.get('question', '').strip()
    sid      = data.get('session_id')
    if not question:
        return jsonify({'error': 'question required'}), 400
    answer = ask(question, session_id=sid)
    return jsonify({'answer': answer})


@app.route('/api/ollama_status')
def api_ollama_status():
    return jsonify(ollama_status())


# ---------------------------------------------------------------------------
# Parser learning API
# ---------------------------------------------------------------------------

@app.route('/api/learning/unparsed')
def api_learning_unparsed():
    import sqlite3
    from config import COMBAT_DB
    limit = int(request.args.get('limit', 50))
    conn = sqlite3.connect(COMBAT_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT bucket, COUNT(*) AS seen_count, MAX(ts) AS last_seen,
               MIN(id) AS first_id, MAX(id) AS last_id
        FROM unparsed_lines
        WHERE reviewed=0
        GROUP BY bucket
        ORDER BY seen_count DESC, last_seen DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    result = []
    for row in rows:
        samples = conn.execute(
            """
            SELECT id, ts, area_name, content
            FROM unparsed_lines
            WHERE bucket=? AND reviewed=0
            ORDER BY id DESC
            LIMIT 5
            """,
            (row['bucket'],),
        ).fetchall()
        item = dict(row)
        item['samples'] = [dict(s) for s in samples]
        result.append(item)
    conn.close()
    return jsonify(result)


@app.route('/api/learning/analyze', methods=['POST'])
def api_learning_analyze():
    data = request.get_json(silent=True) or {}
    limit = int(data.get('limit', 100))
    return jsonify(analyze_unparsed(limit=limit))


# ---------------------------------------------------------------------------
# SocketIO — real-time event push (called by LogTailer)
# ---------------------------------------------------------------------------

def emit_event(ev: dict):
    socketio.emit('event', ev)


def get_socketio():
    return socketio
