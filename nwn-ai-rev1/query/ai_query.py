"""
Ollama-backed natural language query handler.
Builds context from SQL results + bestiary data. LLM never sees raw log text.
"""
import json, requests, re, sqlite3
from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, COMBAT_DB
from query.sql_queries import (
    top_damage_to_pcs, top_damage_types_received, kills_by_mob,
    save_failures, save_summary, mob_info, best_damage_vs_mob,
    mobs_in_area, stat_snapshot, dangerous_dc_sources, search_mobs,
    mob_damage_dealt, attack_accuracy, spell_usage_summary, bard_songs_summary,
    area_threat_summary,
)

_SYSTEM = """You are a combat analyst for Neverwinter Nights 1.69 on the Higher Grounds persistent world.
You answer questions about combat performance using data from parsed combat logs and a bestiary database.
You know D&D 3.5 mechanics: Bludgeoning/Piercing/Slashing are separate physical damage subtypes.
Bard songs produce sonic damage (area, AoE). Spell Resistance (SR) and Turn Resistance (TR) matter.
Be concise and tactical. Lead with the most actionable advice. Use numbers from the data provided.
If data is missing, say so and explain what it would tell us.
When recommending damage types, cross-reference the bestiary immunity data — never recommend
a type if the target is 100% immune to it."""


def _current_area() -> str:
    """Get the most recently logged area name."""
    try:
        conn = sqlite3.connect(COMBAT_DB)
        row = conn.execute(
            'SELECT area_name FROM area_log ORDER BY id DESC LIMIT 1'
        ).fetchone()
        conn.close()
        return row[0] if row else ''
    except Exception:
        return ''


def _context_for_question(question: str, session_id=None) -> str:
    q = question.lower()
    parts = []

    # Always include snapshot
    snap = stat_snapshot(session_id)
    parts.append(f"Session snapshot: {json.dumps(snap)}")

    # Current area + mobs in it
    area = _current_area()
    if area:
        parts.append(f"Current area: {area}")
        # Area guide tactical data
        summary = area_threat_summary(area)
        guide = summary.get('guide', {})
        if guide.get('level_min'):
            stats_line = (
                f"Area stats — Level:{guide.get('level_min')}-{guide.get('level_max','?')} "
                f"NeedAC:{guide.get('required_ac','?')} NeedAB:{guide.get('required_ab','?')} "
                f"NeedSaves:{guide.get('required_saves','?')} NeedHP:{guide.get('required_hp','?')} "
                f"EnemyAB:{guide.get('enemy_ab_min','?')}-{guide.get('enemy_ab_max','?')} "
                f"EnemyAC:{guide.get('enemy_ac_min','?')}-{guide.get('enemy_ac_max','?')} "
                f"DC:{guide.get('area_dc_min','?')}-{guide.get('area_dc_max','?')}"
            )
            parts.append(stats_line)
        if guide.get('tactical_notes'):
            parts.append(f"Area tactical notes:\n{guide['tactical_notes'][:1200]}")

        mobs = mobs_in_area(area)
        if mobs:
            mob_names = [m['name'] for m in mobs[:20]]
            parts.append(f"Mobs in area: {json.dumps(mob_names)}")
            # summarize threatening mob stats
            threats = [
                f"{m['name']} (AC:{m.get('ac','?')} AB:{m.get('ab','?')} SR:{m.get('sr','?')} "
                f"SpellImm:{m.get('spell_immunities','none')} OtherImm:{m.get('other_immunities','none')} "
                f"Special:{m.get('special_abilities','none')})"
                for m in mobs[:10] if m.get('ac') or m.get('special_abilities')
            ]
            if threats:
                parts.append(f"Area mob details:\n" + "\n".join(threats))

    if any(w in q for w in ['kill','death','dying','dead','killing me']):
        parts.append("Mobs killing PCs: " + json.dumps(kills_by_mob(session_id)))
        parts.append("Top damage sources: " + json.dumps(top_damage_to_pcs(session_id, limit=5)))

    if any(w in q for w in ['damage','hurt','dmg','hp','hit','hurt']):
        parts.append("Damage types received by PCs: " + json.dumps(top_damage_types_received(session_id)))
        parts.append("Top mob damage dealers vs PCs: " + json.dumps(top_damage_to_pcs(session_id, limit=8)))

    if any(w in q for w in ['save','dc','fort','reflex','will','fail','fortitude']):
        parts.append("Save summary: " + json.dumps(save_summary(session_id)))
        parts.append("Worst DC sources: " + json.dumps(dangerous_dc_sources(session_id)))

    if any(w in q for w in ['spell','cast','bard','song','sonic','music']):
        parts.append("Spell usage: " + json.dumps(spell_usage_summary(session_id)))
        parts.append("Bard songs: " + json.dumps(bard_songs_summary(session_id)))

    if any(w in q for w in ['accuracy','hit','miss','crit','attack']):
        parts.append("PC attack accuracy: " + json.dumps(attack_accuracy(session_id=session_id)))

    # Mob-specific query — extended regex for natural questions
    mob_match = re.search(
        r'(?:kill|fight|attack|against|vs\.?|about|deal.*with|how.*kill|'
        r'how.*fight|weak(?:ness)?|immune|resist|what.*use|damage.*to)\s+'
        r'(?:a\s+|an\s+|the\s+)?([A-Za-z\'.\- ]{3,35})',
        question, re.I
    )
    if mob_match:
        mob_name = mob_match.group(1).strip().rstrip('?.,')
        info = mob_info(mob_name)
        if info:
            parts.append(f"Bestiary — {mob_name}: {json.dumps(info)}")
            best = best_damage_vs_mob(mob_name)
            # Only show types that aren't 100% immune
            effective = [d for d in best if d['immunity_pct'] < 100][:8]
            parts.append(f"Effective damage types vs {mob_name}: {json.dumps(effective)}")
            log_data = mob_damage_dealt(mob_name, session_id)
            if log_data:
                parts.append(f"Log data vs {mob_name}: {json.dumps(log_data)}")
        else:
            close = search_mobs(mob_name, limit=3)
            if close:
                parts.append(f"No exact match for '{mob_name}'. Closest: {[m['name'] for m in close]}")

    # Area-specific query
    if any(w in q for w in ['area','zone','where','location','region']):
        area_match = re.search(r'in\s+(?:the\s+)?([A-Za-z\' ]{3,30})', question, re.I)
        if area_match:
            aname = area_match.group(1).strip()
            mobs = mobs_in_area(aname)
            if mobs:
                parts.append(f"Mobs in {aname}: {json.dumps([m['name'] for m in mobs[:20]])}")
                summary = area_threat_summary(aname)
                parts.append(f"Area threat summary: {json.dumps(summary)}")

    return '\n'.join(parts)


def _get_available_model() -> str | None:
    """Return the first available Ollama model, preferring mistral."""
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=3)
        models = [m['name'] for m in r.json().get('models', [])]
        if not models:
            return None
        for pref in ('mistral', 'llama', 'phi', 'qwen', 'gemma'):
            for m in models:
                if pref in m.lower():
                    return m
        return models[0]
    except Exception:
        return None


def ask(question: str, session_id=None) -> str:
    model = _get_available_model()
    if model is None:
        status = ollama_status()
        if not status['running']:
            return (
                'Ollama service is not running.\n'
                'Fix: Open a command prompt and run:  ollama serve\n'
                'Then try your question again.'
            )
        return (
            'No Ollama model is installed yet.\n'
            'Fix: Run pull_model.bat to download mistral:7b (~4GB).\n'
            'Or run:  ollama pull mistral:7b'
        )

    context = _context_for_question(question, session_id)

    prompt = f"""{_SYSTEM}

--- Combat Data & Bestiary ---
{context}

--- Question ---
{question}

Answer:"""

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                'model':   model,
                'prompt':  prompt,
                'stream':  False,
                'options': {'temperature': 0.2, 'num_predict': 768},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get('response', '').strip()

    except requests.exceptions.ConnectionError:
        return 'Cannot reach Ollama.\nStart it with:  ollama serve\nThen try again.'
    except Exception as e:
        return f'AI query error: {e}'


def ollama_status() -> dict:
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=3)
        models = [m['name'] for m in r.json().get('models', [])]
        return {
            'running': True,
            'model_ready': any(OLLAMA_MODEL.split(':')[0] in m for m in models),
            'models': models,
        }
    except Exception:
        return {'running': False, 'model_ready': False, 'models': []}
