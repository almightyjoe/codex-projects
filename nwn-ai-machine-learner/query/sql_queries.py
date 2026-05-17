"""
All structured question handlers — answered purely from SQLite without any LLM.
"""
import sqlite3
from config import COMBAT_DB, BESTIARY_DB

# All damage columns tracked in the damages table.
_ALL_DMG_TYPES = [
    ('Bludgeoning', 'dmg_bludgeoning'), ('Piercing',   'dmg_piercing'),
    ('Slashing',    'dmg_slashing'),    ('Acid',        'dmg_acid'),
    ('Cold',        'dmg_cold'),        ('Electrical',  'dmg_electrical'),
    ('Fire',        'dmg_fire'),        ('Sonic',       'dmg_sonic'),
    ('Divine',      'dmg_divine'),      ('Magical',     'dmg_magical'),
    ('Negative',    'dmg_negative'),    ('Positive',    'dmg_positive'),
    ('Psionic',     'dmg_psionic'),     ('Vile',        'dmg_vile'),
    ('Sacred',      'dmg_sacred'),      ('Force',       'dmg_force'),
    ('Anarchic',    'dmg_anarchic'),    ('Axiomatic',   'dmg_axiomatic'),
    ('Primal',      'dmg_primal'),      ('Subdual',     'dmg_subdual'),
    ('Ectoplasmic', 'dmg_ectoplasmic'), ('Internal',    'dmg_internal'),
    ('Desiccation', 'dmg_desiccation'), ('Venom',       'dmg_venom'),
    ('Dragonfire',  'dmg_dragonfire'),  ('Blight',      'dmg_blight'),
    ('RawArcane',   'dmg_raw_arcane'),  ('RawDivine',   'dmg_raw_divine'),
    ('RawNature',   'dmg_raw_nature'),  ('Deception',   'dmg_deception'),
    ('Degeneration','dmg_degeneration'),('Digestion',   'dmg_digestion'),
    ('Retribution', 'dmg_retribution'), ('Antimagic',   'dmg_antimagic'),
    ('Other',       'dmg_other'),
]


def _cdb():
    conn = sqlite3.connect(COMBAT_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _bdb():
    conn = sqlite3.connect(BESTIARY_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# COMBAT QUERIES
# ---------------------------------------------------------------------------

def top_damage_to_pcs(session_id=None, limit=10) -> list[dict]:
    """What is dealing the most damage TO the player characters?"""
    conn = _cdb()
    where = 'WHERE defender_is_pc=1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    # Include the top physical subtypes + energy for the summary
    rows = conn.execute(f'''
        SELECT attacker, SUM(total_damage) as total,
               SUM(dmg_bludgeoning) as bludgeoning,
               SUM(dmg_piercing)    as piercing,
               SUM(dmg_slashing)    as slashing,
               SUM(dmg_fire)        as fire,
               SUM(dmg_cold)        as cold,
               SUM(dmg_acid)        as acid,
               SUM(dmg_electrical)  as electrical,
               SUM(dmg_sonic)       as sonic,
               SUM(dmg_divine)      as divine,
               SUM(dmg_negative)    as negative,
               SUM(dmg_magical)     as magical,
               SUM(dmg_positive)    as positive,
               SUM(dmg_vile)        as vile,
               SUM(dmg_primal)      as primal,
               COUNT(*) as hits
        FROM damages {where}
        GROUP BY attacker ORDER BY total DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def top_damage_types_received(session_id=None) -> list[dict]:
    """What damage types are hitting PCs the most (by total)?"""
    conn = _cdb()
    where = 'WHERE defender_is_pc=1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    sel = ', '.join(f'SUM({col}) as {name}' for name, col in _ALL_DMG_TYPES)
    row = conn.execute(f'SELECT {sel} FROM damages {where}', params).fetchone()
    conn.close()
    if not row:
        return []
    result = [(k, v or 0) for k, v in dict(row).items()]
    result.sort(key=lambda x: x[1], reverse=True)
    return [{'type': k, 'total': v} for k, v in result if v > 0]


def kills_by_mob(session_id=None, limit=15) -> list[dict]:
    """Which mobs are killing us most often?"""
    conn = _cdb()
    where = 'WHERE victim_is_pc=1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT killer, COUNT(*) as kill_count
        FROM kills {where}
        GROUP BY killer ORDER BY kill_count DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_failures(session_id=None, limit=15) -> list[dict]:
    """Which saves are failing, at what DCs, from what source?"""
    conn = _cdb()
    where = "WHERE s.target_is_pc=1 AND s.result IN ('failure','automatic failure')"
    params = []
    if session_id:
        where += ' AND s.session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT save_type, check_type, vs_source, dc,
               COUNT(*) as fail_count, AVG(bonus) as avg_bonus
        FROM saves s {where}
        GROUP BY save_type, vs_source, dc
        ORDER BY fail_count DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_summary(session_id=None) -> list[dict]:
    """Pass/fail rate per save type for PCs, including skill/SR/SP checks."""
    conn = _cdb()
    where = 'WHERE target_is_pc=1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT save_type, check_type,
               COUNT(*) as total,
               SUM(CASE WHEN result IN ('success','automatic success','immune') THEN 1 ELSE 0 END) as passed,
               SUM(CASE WHEN result IN ('failure','automatic failure') THEN 1 ELSE 0 END) as failed,
               MAX(dc) as max_dc, ROUND(AVG(dc),1) as avg_dc,
               MAX(vs_source) as example_source
        FROM saves {where}
        GROUP BY save_type ORDER BY failed DESC
    ''', params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def dangerous_dc_sources(session_id=None) -> list[dict]:
    """What save DCs are causing the most trouble?"""
    return save_failures(session_id=session_id, limit=20)


def mob_damage_dealt(mob_name: str, session_id=None) -> dict:
    """How much damage of each type has a specific mob dealt to PCs?"""
    conn = _cdb()
    where = "WHERE attacker_is_pc=0 AND defender_is_pc=1 AND LOWER(attacker) LIKE LOWER(?)"
    params = [f'%{mob_name}%']
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    sel = ', '.join(f'SUM({col}) as {name.lower()}' for name, col in _ALL_DMG_TYPES)
    row = conn.execute(f'''
        SELECT attacker, SUM(total_damage) as total, COUNT(*) as hits, {sel}
        FROM damages {where}
    ''', params).fetchone()
    conn.close()
    if not row:
        return {}
    r = dict(row)
    # Filter out zero types for clean output
    return {k: v for k, v in r.items() if v is None or v != 0 or k in ('attacker','total','hits')}


def pc_damage_dealt(pc_name: str = None, session_id=None) -> list[dict]:
    """How much damage has the PC dealt to each mob, by type?"""
    conn = _cdb()
    where = 'WHERE attacker_is_pc=1'
    params = []
    if pc_name:
        where += ' AND LOWER(attacker) LIKE LOWER(?)'
        params.append(f'%{pc_name}%')
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT defender, SUM(total_damage) as total, COUNT(*) as hits,
               SUM(dmg_bludgeoning) as bludgeoning, SUM(dmg_piercing) as piercing,
               SUM(dmg_slashing) as slashing,
               SUM(dmg_fire) as fire, SUM(dmg_cold) as cold, SUM(dmg_acid) as acid,
               SUM(dmg_electrical) as electrical, SUM(dmg_sonic) as sonic,
               SUM(dmg_divine) as divine, SUM(dmg_negative) as negative,
               SUM(dmg_magical) as magical
        FROM damages {where}
        GROUP BY defender ORDER BY total DESC LIMIT 20
    ''', params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def spell_usage_summary(session_id=None, limit=20) -> list[dict]:
    """Top spells/songs cast, by caster."""
    conn = _cdb()
    where = 'WHERE 1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT caster, spell_name, is_song, COUNT(*) as cast_count,
               SUM(is_song) as song_count
        FROM spells {where}
        GROUP BY caster, spell_name
        ORDER BY cast_count DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def bard_songs_summary(session_id=None) -> list[dict]:
    """How many times has each bard character used songs?"""
    conn = _cdb()
    where = 'WHERE is_song=1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT caster, COUNT(*) as song_count
        FROM spells {where}
        GROUP BY caster ORDER BY song_count DESC
    ''', params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def bard_signal_summary(session_id=None, limit: int = 30) -> list[dict]:
    """Bard song / curse signals. Raw logs identify use, not exact aura math."""
    conn = _cdb()
    where = """
        WHERE (is_song=1
           OR LOWER(spell_name) LIKE '%curse%'
           OR LOWER(spell_name) LIKE '%song%')
    """
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT caster, spell_name,
               CASE WHEN caster_is_pc=1 THEN 'PC' ELSE 'Mob/Unknown' END AS source_type,
               CASE
                 WHEN is_song=1 THEN 'Bard song observed; exact buff/debuff values are not printed in the log'
                 WHEN LOWER(spell_name) LIKE '%curse%' THEN 'Curse effect observed; saves/DCs appear separately when logged'
                 ELSE 'Bard-related spell signal'
               END AS inferred_effect,
               MAX(ts) AS latest_ts
        FROM spells {where}
        GROUP BY caster, spell_name, caster_is_pc
        ORDER BY latest_ts DESC
        LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def attack_accuracy(pc_name: str = None, session_id=None) -> dict:
    """Hit/miss/crit statistics for PCs."""
    conn = _cdb()
    where = 'WHERE attacker_is_pc=1'
    params = []
    if pc_name:
        where += ' AND LOWER(attacker) LIKE LOWER(?)'
        params.append(f'%{pc_name}%')
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    row = conn.execute(f'''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN hit_type='hit' THEN 1 ELSE 0 END) as hits,
               SUM(CASE WHEN hit_type='critical_hit' THEN 1 ELSE 0 END) as crits,
               SUM(CASE WHEN hit_type='miss' THEN 1 ELSE 0 END) as misses,
               SUM(CASE WHEN hit_type='concealed' THEN 1 ELSE 0 END) as concealed
        FROM attacks {where}
    ''', params).fetchone()
    conn.close()
    return dict(row) if row else {}


def mob_hit_rate_vs_pcs(session_id=None, limit=10) -> list[dict]:
    """Which mobs land attacks on PCs at the highest rate?"""
    conn = _cdb()
    where = 'WHERE defender_is_pc=1 AND attacker_is_pc=0'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT attacker, COUNT(*) as total_attacks,
               SUM(CASE WHEN hit_type IN ('hit','critical_hit') THEN 1 ELSE 0 END) as hits,
               ROUND(100.0 * SUM(CASE WHEN hit_type IN ('hit','critical_hit') THEN 1 ELSE 0 END)
                     / COUNT(*), 1) as hit_pct
        FROM attacks {where}
        GROUP BY attacker HAVING total_attacks >= 3
        ORDER BY hit_pct DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_events(n=50, session_id=None) -> list[dict]:
    """Most recent N mixed events for the live feed."""
    conn = _cdb()
    sid_filter = f'AND session_id={session_id}' if session_id else ''

    attacks = conn.execute(f'''
        SELECT ts, 'attack' as type,
               attacker || ' -> ' || defender || ' [' || hit_type || ']' as summary
        FROM attacks WHERE 1 {sid_filter} ORDER BY id DESC LIMIT {n}
    ''').fetchall()

    damages = conn.execute(f'''
        SELECT ts, 'damage' as type,
               attacker || ' -> ' || defender || ': ' || total_damage || ' dmg' as summary
        FROM damages WHERE 1 {sid_filter} ORDER BY id DESC LIMIT {n}
    ''').fetchall()

    kills = conn.execute(f'''
        SELECT ts, 'kill' as type,
               killer || ' killed ' || victim as summary
        FROM kills WHERE 1 {sid_filter} ORDER BY id DESC LIMIT {n}
    ''').fetchall()

    saves = conn.execute(f'''
        SELECT ts, 'save' as type,
               target || ': ' || save_type || ' vs DC ' || COALESCE(dc,'?') || ' [' || result || ']' as summary
        FROM saves WHERE 1 {sid_filter} ORDER BY id DESC LIMIT {n}
    ''').fetchall()

    spells = conn.execute(f'''
        SELECT ts,
               CASE WHEN is_song=1 THEN 'song' ELSE 'spell' END as type,
               caster || ' ' || action || ' ' || spell_name as summary
        FROM spells WHERE 1 {sid_filter} ORDER BY id DESC LIMIT {n}
    ''').fetchall()

    combined = [dict(r) for r in attacks + damages + kills + saves + spells]
    combined.sort(key=lambda x: x['ts'], reverse=True)
    conn.close()
    return combined[:n]


def session_list() -> list[dict]:
    conn = _cdb()
    rows = conn.execute(
        'SELECT id, start_time, end_time FROM sessions ORDER BY id DESC LIMIT 20'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# BESTIARY QUERIES
# ---------------------------------------------------------------------------

def mob_info(mob_name: str) -> dict | None:
    """Full bestiary entry for a mob (fuzzy name match)."""
    conn = _bdb()
    row = conn.execute(
        'SELECT * FROM creatures WHERE LOWER(name) LIKE LOWER(?) LIMIT 1',
        (f'%{mob_name}%',)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def best_damage_vs_mob(mob_name: str) -> list[dict]:
    """Which damage types are most effective against this mob?"""
    conn = _bdb()
    row = conn.execute(
        'SELECT * FROM creatures WHERE LOWER(name) LIKE LOWER(?) LIMIT 1',
        (f'%{mob_name}%',)
    ).fetchone()
    conn.close()
    if not row:
        return []

    r = dict(row)
    dmg_types = [
        'bludgeoning','piercing','slashing','acid','cold','electrical',
        'fire','sonic','divine','magical','negative','positive',
        'ectoplasmic','psionic','sacred','vile','anarchic','axiomatic',
        'primal','subdual','force','internal','desiccation','venom',
        'dragonfire','blight',
    ]
    result = []
    for t in dmg_types:
        imm = r.get(f'imm_{t}', 0) or 0
        res = r.get(f'res_{t}', 0) or 0
        result.append({'type': t.capitalize(), 'immunity_pct': imm, 'resistance_dr': res})

    result.sort(key=lambda x: (x['immunity_pct'], x['resistance_dr']))
    return result


def mobs_in_area(area_name: str) -> list[dict]:
    """All creatures known to spawn in a given area."""
    conn = _bdb()
    rows = conn.execute('''
        SELECT c.name, c.race, c.ac, c.ab, c.sr,
               c.saves_fort, c.saves_ref, c.saves_will,
               c.other_immunities, c.spell_immunities, c.special_abilities,
               c.takes, c.deals
        FROM creatures c
        JOIN creature_areas ca ON ca.creature_id = c.id
        JOIN areas a ON a.id = ca.area_id
        WHERE LOWER(a.name) LIKE LOWER(?)
        ORDER BY c.name
    ''', (f'%{area_name}%',)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def area_threat_summary(area_name: str) -> dict:
    """Damage types prevalent in this area from bestiary immunity data + area guide stats."""
    mobs = mobs_in_area(area_name)
    immunity_totals = {}
    immune_100 = {}

    for mob in mobs:
        conn2 = _bdb()
        row = conn2.execute('SELECT * FROM creatures WHERE name=?', (mob['name'],)).fetchone()
        conn2.close()
        if not row:
            continue
        r = dict(row)
        for t in ['fire','cold','acid','electrical','sonic','divine','negative',
                  'magical','positive','psionic','sacred','vile','primal','blight']:
            imm = r.get(f'imm_{t}', 0) or 0
            if imm > 0:
                immunity_totals[t] = immunity_totals.get(t, 0) + imm
            if imm >= 100:
                immune_100[t] = immune_100.get(t, 0) + 1

    # Area guide stats
    conn3 = _bdb()
    area_row = conn3.execute(
        'SELECT level_min, level_max, required_ab, required_ac, required_saves, '
        'required_hp, area_dc_min, area_dc_max, enemy_ab_min, enemy_ab_max, '
        'enemy_ac_min, enemy_ac_max, tactical_notes, recommended_protections '
        'FROM areas WHERE LOWER(name) LIKE LOWER(?) LIMIT 1',
        (f'%{area_name}%',)
    ).fetchone()
    conn3.close()
    guide = dict(area_row) if area_row else {}

    return {
        'area': area_name,
        'mob_count': len(mobs),
        'avg_immunities': {k: round(v/len(mobs), 1) for k,v in immunity_totals.items()} if mobs else {},
        'full_immune_count': immune_100,
        'mobs': [m['name'] for m in mobs],
        'guide': guide,
    }


def search_mobs(query: str, limit=20) -> list[dict]:
    """Fuzzy name search across all creatures."""
    conn = _bdb()
    rows = conn.execute(
        'SELECT name, race, ac, ab, sr, other_immunities, areas FROM creatures '
        'WHERE LOWER(name) LIKE LOWER(?) ORDER BY name LIMIT ?',
        (f'%{query}%', limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def creature_list(limit=500) -> list[dict]:
    """Alphabetical list of all creatures for the bestiary browser."""
    conn = _bdb()
    rows = conn.execute(
        'SELECT name, race, ac, ab, sr, areas FROM creatures ORDER BY name LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stat_snapshot(session_id=None) -> dict:
    """One-shot dashboard summary."""
    conn = _cdb()
    sid = f'AND session_id={session_id}' if session_id else ''

    total_dmg_in = conn.execute(
        f'SELECT COALESCE(SUM(total_damage),0) FROM damages WHERE defender_is_pc=1 {sid}'
    ).fetchone()[0]

    total_dmg_out = conn.execute(
        f'SELECT COALESCE(SUM(total_damage),0) FROM damages WHERE attacker_is_pc=1 {sid}'
    ).fetchone()[0]
    pc_deaths = conn.execute(
        f'SELECT COUNT(*) FROM kills WHERE victim_is_pc=1 {sid}'
    ).fetchone()[0]
    averted_deaths = conn.execute(
        f'SELECT COUNT(*) FROM death_averts WHERE target_is_pc=1 {sid}'
    ).fetchone()[0]

    mob_kills = conn.execute(
        f'SELECT COUNT(*) FROM kills WHERE killer_is_pc=1 {sid}'
    ).fetchone()[0]

    total_attacks_in = conn.execute(
        f'SELECT COUNT(*) FROM attacks WHERE defender_is_pc=1 AND attacker_is_pc=0 {sid}'
    ).fetchone()[0]

    save_fails = conn.execute(
        f"SELECT COUNT(*) FROM saves WHERE target_is_pc=1 AND result IN ('failure','automatic failure') {sid}"
    ).fetchone()[0]

    dmg_type_select = ', '.join(
        f'COALESCE(SUM({col}),0) AS "{name}"'
        for name, col in _ALL_DMG_TYPES
        if name != 'Other'
    )
    dmg_type_row = conn.execute(
        f'SELECT {dmg_type_select} FROM damages WHERE defender_is_pc=1 {sid}'
    ).fetchone()
    top_dmg_type = None
    top_dmg_amount = 0
    if dmg_type_row:
        for key in dmg_type_row.keys():
            amount = dmg_type_row[key] or 0
            if amount > top_dmg_amount:
                top_dmg_type = key
                top_dmg_amount = amount

    spells_cast = conn.execute(
        f"SELECT COUNT(*) FROM spells WHERE caster_is_pc=1 {sid}"
    ).fetchone()[0]

    songs_sung = conn.execute(
        f"SELECT COUNT(*) FROM spells WHERE is_song=1 {sid}"
    ).fetchone()[0]

    last_killer = conn.execute(
        f"SELECT killer FROM kills WHERE victim_is_pc=1 {sid} ORDER BY id DESC LIMIT 1"
    ).fetchone()
    top_fail_save = conn.execute(
        f"SELECT save_type, COUNT(*) as n, MAX(dc) as max_dc FROM saves WHERE target_is_pc=1 {sid} "
        f"AND result IN ('failure','automatic failure') GROUP BY save_type ORDER BY n DESC, max_dc DESC LIMIT 1"
    ).fetchone()

    conn.close()
    return {
        'damage_received':  total_dmg_in,
        'damage_dealt':     total_dmg_out,
        'top_damage_type':   top_dmg_type,
        'top_damage_type_amount': top_dmg_amount,
        'top_damage_type_pct': round(100.0 * top_dmg_amount / total_dmg_in, 1) if total_dmg_in else 0,
        'pc_deaths':        pc_deaths,
        'averted_deaths':   averted_deaths,
        'mob_kills':        mob_kills,
        'attacks_received': total_attacks_in,
        'save_failures':    save_fails,
        'spells_cast':      spells_cast,
        'songs_sung':       songs_sung,
        'last_killer':      last_killer[0] if last_killer else None,
        'top_fail_save':    top_fail_save['save_type'] if top_fail_save else None,
        'top_fail_save_count': top_fail_save['n'] if top_fail_save else 0,
        'top_fail_save_dc': top_fail_save['max_dc'] if top_fail_save else None,
    }


# ---------------------------------------------------------------------------
# EXTENDED COMBAT ANALYSIS
# ---------------------------------------------------------------------------

# All 35 damage columns for dynamic SELECT building
_ALL_DMG_COLS = [
    'dmg_bludgeoning','dmg_piercing','dmg_slashing',
    'dmg_acid','dmg_cold','dmg_electrical','dmg_fire','dmg_sonic',
    'dmg_divine','dmg_magical','dmg_negative','dmg_positive',
    'dmg_psionic','dmg_vile','dmg_sacred','dmg_force',
    'dmg_anarchic','dmg_axiomatic','dmg_primal','dmg_subdual',
    'dmg_ectoplasmic','dmg_internal','dmg_desiccation','dmg_venom',
    'dmg_raw_arcane','dmg_raw_divine','dmg_raw_nature',
    'dmg_dragonfire','dmg_blight','dmg_deception','dmg_degeneration',
    'dmg_digestion','dmg_retribution','dmg_antimagic','dmg_other',
]


def damage_breakdown(session_id=None, vs_pc: bool = True, limit: int = 30) -> list[dict]:
    """
    Full damage-type breakdown per attacker or per defender.
    vs_pc=True  → mobs hitting PCs (rows = mobs, each column = damage type total)
    vs_pc=False → PCs hitting mobs (rows = mobs the PCs attacked)
    """
    conn = _cdb()
    name_col = 'attacker' if vs_pc else 'defender'
    where = 'WHERE ' + ('defender_is_pc=1' if vs_pc else 'attacker_is_pc=1')
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    type_sels = ', '.join(f'SUM({c}) as {c}' for c in _ALL_DMG_COLS)
    rows = conn.execute(f'''
        SELECT {name_col} as name, SUM(total_damage) as total, COUNT(*) as hits,
               {type_sels}
        FROM damages {where}
        GROUP BY {name_col} ORDER BY total DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def accuracy_detail(session_id=None, pc_attacks: bool = True, limit: int = 60) -> list[dict]:
    """
    Hit/miss/crit per attacker+defender pair.
    pc_attacks=True  → PC attacking each mob
    pc_attacks=False → mob attacking each PC
    """
    conn = _cdb()
    where = 'WHERE ' + ('attacker_is_pc=1' if pc_attacks else 'defender_is_pc=1 AND attacker_is_pc=0')
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT attacker, defender,
               COUNT(*) as total,
               SUM(CASE WHEN hit_type IN ('hit','critical_hit') THEN 1 ELSE 0 END) as hits,
               SUM(CASE WHEN hit_type='critical_hit' THEN 1 ELSE 0 END) as crits,
               SUM(CASE WHEN hit_type='miss' THEN 1 ELSE 0 END) as misses,
               SUM(CASE WHEN hit_type='concealed' THEN 1 ELSE 0 END) as concealed,
               ROUND(100.0 * SUM(CASE WHEN hit_type IN ('hit','critical_hit') THEN 1 ELSE 0 END)
                     / COUNT(*), 1) as hit_pct,
               ROUND(AVG(bonus), 0) as avg_bonus,
               MAX(bonus) as max_bonus
        FROM attacks {where}
        GROUP BY attacker, defender HAVING total >= 2
        ORDER BY total DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def spell_check_summary(session_id=None, limit: int = 40) -> list[dict]:
    """Spell resistance / penetration / turn / dispel check results with exact math."""
    conn = _cdb()
    where = 'WHERE 1'
    params = []
    if session_id:
        where += ' AND session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        WITH enriched AS (
          SELECT sc.*,
                 COALESCE(NULLIF(sc.spell_name, ''), (
                   SELECT sp.spell_name
                   FROM spells sp
                   WHERE sp.session_id=sc.session_id
                     AND sp.caster=sc.source
                     AND sp.ts<=sc.ts
                   ORDER BY sp.id DESC LIMIT 1
                 ), '') AS inferred_spell
          FROM spell_checks sc {where}
        )
        SELECT check_type, source, target, inferred_spell AS spell_name, result, dc, sr_value,
               COUNT(*) as count,
               ROUND(AVG(roll), 1) as avg_roll,
               ROUND(AVG(bonus), 1) as avg_bonus,
               ROUND(AVG(total), 1) as avg_total,
               MAX(total) as max_total,
               MIN(total) as min_total
        FROM enriched
        GROUP BY check_type, source, target, inferred_spell, result, dc, sr_value
        ORDER BY count DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def recent_save_failures(session_id=None, limit: int = 50) -> list[dict]:
    """Chronological list of recent PC save failures."""
    conn = _cdb()
    where = "WHERE s.target_is_pc=1 AND s.result IN ('failure','automatic failure')"
    params = []
    if session_id:
        where += ' AND s.session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT s.ts, s.target, s.save_type, s.check_type, s.vs_source,
               COALESCE(NULLIF(s.spell_name, ''), (
                 SELECT sp.spell_name
                 FROM spells sp
                 WHERE sp.session_id=s.session_id
                   AND sp.caster=s.vs_source
                   AND sp.ts<=s.ts
                 ORDER BY sp.id DESC LIMIT 1
               ), s.vs_source) AS source_spell,
               s.dc, s.roll, s.bonus, s.total
        FROM saves s {where}
        ORDER BY id DESC LIMIT ?
    ''', params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def pc_kill_detail(session_id=None, limit: int = 30) -> list[dict]:
    """
    PC deaths with killer, timestamp, and the last damage source before death.
    """
    conn = _cdb()
    where = 'WHERE k.victim_is_pc=1'
    params = []
    if session_id:
        where += ' AND k.session_id=?'
        params.append(session_id)
    rows = conn.execute(f'''
        SELECT k.ts, k.victim, k.killer, k.xp_gained, 'death' AS event_type,
               (SELECT d.attacker || ' (' || d.total_damage || ' ' ||
                CASE
                  WHEN d.dmg_fire>0     THEN 'fire'
                  WHEN d.dmg_cold>0     THEN 'cold'
                  WHEN d.dmg_acid>0     THEN 'acid'
                  WHEN d.dmg_electrical>0 THEN 'electrical'
                  WHEN d.dmg_sonic>0    THEN 'sonic'
                  WHEN d.dmg_negative>0 THEN 'negative'
                  WHEN d.dmg_divine>0   THEN 'divine'
                  WHEN d.dmg_magical>0  THEN 'magical'
                  WHEN d.dmg_bludgeoning>0 THEN 'bludgeoning'
                  WHEN d.dmg_piercing>0 THEN 'piercing'
                  WHEN d.dmg_slashing>0 THEN 'slashing'
                  ELSE 'dmg'
                END || ')'
                FROM damages d
                WHERE LOWER(d.defender) = LOWER(k.victim)
                  AND d.ts <= k.ts
                  AND (? IS NULL OR d.session_id = ?)
                ORDER BY d.id DESC LIMIT 1
               ) as last_hit
        FROM kills k {where}
        UNION ALL
        SELECT da.ts, da.target AS victim, 'Averted death' AS killer, 0 AS xp_gained,
               'averted' AS event_type, da.ability AS last_hit
        FROM death_averts da
        WHERE da.target_is_pc=1
          AND (? IS NULL OR da.session_id = ?)
        ORDER BY ts DESC LIMIT ?
    ''', params + [session_id, session_id, session_id, session_id, limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]
