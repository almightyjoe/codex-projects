"""
Flask + SocketIO web server.
Serves the dashboard and handles AI query API calls.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

from query.sql_queries import (
    stat_snapshot, top_damage_to_pcs, top_damage_types_received,
    kills_by_mob, save_summary, save_failures, recent_events,
    mob_info, best_damage_vs_mob, search_mobs, mobs_in_area,
    session_list, mob_damage_dealt, pc_damage_dealt, attack_accuracy,
    area_threat_summary, creature_list, spell_usage_summary, bard_songs_summary,
    damage_breakdown, accuracy_detail, spell_check_summary,
    recent_save_failures, pc_kill_detail,
)
from query.ai_query import ask, ollama_status

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'nwnai-secret'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')


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
    where = f'AND session_id={sid}' if sid else ''
    row = conn.execute(
        f'SELECT * FROM pc_status WHERE 1 {where} ORDER BY id DESC LIMIT 1'
    ).fetchone()
    pcs = conn.execute(
        'SELECT name, first_seen, last_seen, source FROM detected_pcs ORDER BY last_seen DESC LIMIT 50'
    ).fetchall()
    alerts = conn.execute(
        f'SELECT * FROM debuff_alerts WHERE 1 {where} ORDER BY id DESC LIMIT 20'
    ).fetchall()
    area = conn.execute(
        f'SELECT area_name FROM area_log WHERE 1 {where} ORDER BY id DESC LIMIT 1'
    ).fetchone()
    conn.close()
    return jsonify({
        'immunity': dict(row) if row else {},
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


@app.route('/api/spells')
def api_spells():
    sid = request.args.get('session')
    return jsonify(spell_usage_summary(int(sid) if sid else None))


@app.route('/api/songs')
def api_songs():
    sid = request.args.get('session')
    return jsonify(bard_songs_summary(int(sid) if sid else None))


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
# SocketIO — real-time event push (called by LogTailer)
# ---------------------------------------------------------------------------

def emit_event(ev: dict):
    socketio.emit('event', ev)


def get_socketio():
    return socketio
