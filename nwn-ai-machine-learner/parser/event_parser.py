"""
Parse raw NWN 1.69 log lines into structured event dicts.
All regex patterns reverse-engineered from HGX source (Hgx.Services.Parsers.*).
"""
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Log line wrapper
# [CHAT WINDOW TEXT] [Www Mmm DD HH:MM:SS] {content}
# ---------------------------------------------------------------------------
_LOG_LINE = re.compile(
    r'^\[CHAT WINDOW TEXT\] \[(\w{3} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2})\] (.+)$'
)

# ---------------------------------------------------------------------------
# All 34 HGX damage types (DamageType enum + DamageTypes.ParseHelper)
# Maps log text (lower) → DB column name
# ---------------------------------------------------------------------------
_DMG_TYPE_MAP = {
    # physical subtypes. If the log only says "Physical", keep it as uncertainty.
    'bludgeoning':   'dmg_bludgeoning',
    'piercing':      'dmg_piercing',
    'slashing':      'dmg_slashing',
    'physical':      'dmg_physical',
    # elemental
    'acid':          'dmg_acid',
    'cold':          'dmg_cold',
    'electrical':    'dmg_electrical',
    'fire':          'dmg_fire',
    'sonic':         'dmg_sonic',
    # planar / energy
    'divine':        'dmg_divine',
    'magical':       'dmg_magical',
    'negative energy': 'dmg_negative',
    'negativeenergy': 'dmg_negative',
    'negative':      'dmg_negative',
    'positive energy': 'dmg_positive',
    'positiveenergy': 'dmg_positive',
    'positive':      'dmg_positive',
    # exotic
    'psionic':       'dmg_psionic',
    'vile':          'dmg_vile',
    'sacred':        'dmg_sacred',
    'force':         'dmg_force',
    'anarchic':      'dmg_anarchic',
    'axiomatic':     'dmg_axiomatic',
    'primal':        'dmg_primal',
    'subdual':       'dmg_subdual',
    'ectoplasmic':   'dmg_ectoplasmic',
    'internal':      'dmg_internal',
    'desiccation':   'dmg_desiccation',
    'venom':         'dmg_venom',
    # raw / advanced
    'rawarcane':     'dmg_raw_arcane',
    'raw arcane':    'dmg_raw_arcane',
    'rawdivine':     'dmg_raw_divine',
    'raw divine':    'dmg_raw_divine',
    'rawnature':     'dmg_raw_nature',
    'raw nature':    'dmg_raw_nature',
    'dragonfire':    'dmg_dragonfire',
    'blight':        'dmg_blight',
    'deception':     'dmg_deception',
    'degeneration':  'dmg_degeneration',
    'digestion':     'dmg_digestion',
    'retribution':   'dmg_retribution',
    'antimagic':     'dmg_antimagic',
}

# Canonical ordered list of all damage DB columns (used for INSERT ordering)
DMG_COLS = [
    'dmg_bludgeoning', 'dmg_piercing',   'dmg_slashing',
    'dmg_physical',
    'dmg_acid',        'dmg_cold',        'dmg_electrical',
    'dmg_fire',        'dmg_sonic',       'dmg_divine',
    'dmg_magical',     'dmg_negative',    'dmg_positive',
    'dmg_psionic',     'dmg_vile',        'dmg_sacred',
    'dmg_force',       'dmg_anarchic',    'dmg_axiomatic',
    'dmg_primal',      'dmg_subdual',     'dmg_ectoplasmic',
    'dmg_internal',    'dmg_desiccation', 'dmg_venom',
    'dmg_raw_arcane',  'dmg_raw_divine',  'dmg_raw_nature',
    'dmg_dragonfire',  'dmg_blight',      'dmg_deception',
    'dmg_degeneration','dmg_digestion',   'dmg_retribution',
    'dmg_antimagic',   'dmg_other',
]

# ---------------------------------------------------------------------------
# Attack modes prefix
# ---------------------------------------------------------------------------
_MODE_NAME = (
    r'(?:Sneak Attack|Death Attack|Off Hand|Attack Of Opportunity|'
    r'Expertise|Improved Expertise|Power Attack|Improved Power Attack|'
    r'Flurry Of Blows|Rapid Shot|Defensive Stance|Dirty Fighting|'
    r'Great Cleave|Cleave|Whirlwind Attack|Called Shot|Disarm|Knockdown|'
    r'Improved Knockdown|Circle Kick|Stunning Fist|Quivering Palm)'
)
_MODES_PREFIX = re.compile(
    rf'^({_MODE_NAME}(?:\s*[+:]\s*{_MODE_NAME})*)\s*:\s*(.+)$'
)

# ---------------------------------------------------------------------------
# Core combat patterns (from HGX AttackGameEventParser / DamageGameEventParser)
# ---------------------------------------------------------------------------
_ATTACK_CORE = re.compile(
    r'^(?P<attacker>.+?) attacks (?P<defender>.+?) : \*(?P<result>.+?)\* '
    r': \((?P<roll>\d+) \+ (?P<bonus>\d+) = (?P<total>\d+)'
    r'(?: : Threat Roll: (?P<threat_roll>\d+) \+ \d+ = (?P<threat_total>\d+))?\)$'
)
_ATTEMPT_CORE = re.compile(
    r'^(?P<attacker>.+?) attempts (?P<ability>.+?) on (?P<defender>.+?) : \*(?P<result>.+?)\* '
    r': \((?P<roll>\d+) \+ (?P<bonus>\d+) = (?P<total>\d+)'
    r'(?: : Threat Roll: (?P<threat_roll>\d+) \+ \d+ = (?P<threat_total>\d+))?\)$'
)

# damage: "attacker damages defender: TOTAL (N Type N Type ...)"
# HGX Damage.Parse() reads from the last (…) using abbreviated type names
_DAMAGE = re.compile(
    r'^(?P<attacker>.+?) damages (?P<defender>.+?): (?P<total>\d+) \((?P<breakdown>.+)\)$'
)
# Match pairs of "number typename" inside the breakdown
_DMG_PART = re.compile(r'(\d+)\s+([A-Za-z][A-Za-z ]*?)(?=\s+\d|\s*$)')

# ---------------------------------------------------------------------------
# Save / check patterns (from HGX CheckGameEventParser)
# ---------------------------------------------------------------------------
# Standard save: target : Type[/Sub] Save vs. source : *result* : (roll +/- bonus = N vs. DC: dc)
_SAVE = re.compile(
    r'^(?P<target>.+?) : (?P<save_type>[^:]+?) (?:Save )?vs\. '
    r'(?P<source>.+?) : \*(?P<result>success|failure|automatic success|automatic failure|immune)\* '
    r': \((?P<roll>\d+) (?P<sign>[+\-]) (?P<bonus>\d+) = (?P<total>-?\d+) (?:vs\. DC:|/) (?P<dc>\d+)\)$'
)
# Skill check (simple or vs opponent)
_SKILL = re.compile(
    r'^(?P<take20>Take 20 : )?(?P<character>.+?) : (?P<skill>[^:]+?) '
    r'(?:vs\. (?P<opponent>.+?) )?'
    r': \*(?P<result>success|failure|automatic success|automatic failure|success not possible)\* '
    r': \((?P<roll>\d+) (?P<sign>[+\-]) (?P<bonus>\d+) = (?P<total>-?\d+) (?:vs\. DC:|/) (?P<dc>\d+)\)$'
)
# Spell resistance check
_SR = re.compile(
    r'^(?P<source>.+?) : (?:SR|Spell Resistance) : \*(?P<result>resisted|defeated|immune|absorbed)\*'
    r'(?:\s*:\s*\((?P<roll>\d+) (?P<sign>[+\-]) (?P<bonus>\d+) = (?P<total>\d+) (?:vs\. SR:|/) (?P<sr>\d+)\))?$'
)
# Spell penetration check
_SP = re.compile(
    r'^(?P<target>.+?) : (?:SP|Spell Penetration) : \*(?P<result>success|failure|immune|absorbed)\*'
    r'(?:\s*:\s*\((?P<roll>\d+) (?P<sign>[+\-]) (?P<bonus>\d+) = (?P<total>\d+) (?:vs\. SR:|/) (?P<sr>\d+)\))?$'
)
# Turn resistance
_TURN = re.compile(
    r'^(?P<target>.+?) : (?P<type>Turn .+?|T\.) : \*(?P<result>success|failure)\*'
    r'(?:\s*:\s*\((?P<roll>\d+) (?P<sign>[+\-]) (?P<bonus>\d+) = (?P<total>\d+) (?:vs\. TR:|/) (?P<tr>\d+)\))?$'
)
# Dispel / Breach
_DISPEL = re.compile(
    r'^(?P<source>.+?) : (?P<dtype>Dispel|Breach) (?P<effect>.+?) : '
    r'\*(?P<result>resisted|defeated|dispelled)\*'
    r'(?:\s*:\s*\((?P<roll>\d+) (?P<sign>[+\-]) (?P<bonus>\d+) = (?P<total>\d+) (?:vs\. DC:|/) (?P<dc>\d+)\))?$'
)
# Initiative
_INITIATIVE = re.compile(
    r'^(?P<character>.+?) : Initiative Roll : \d+ : \(\d+ [+\-] \d+ = \d+\)$'
)

# ---------------------------------------------------------------------------
# Other event patterns
# ---------------------------------------------------------------------------
_KILL   = re.compile(r'^(?P<killer>.+?) killed (?P<victim>.+)$')
_XP     = re.compile(r'^Experience Points Gained:\s+(?P<xp>\d+)$')
_AREA   = re.compile(r'^You are now in (?P<area>.+?)\.$')
_CHAT   = re.compile(r'^(?P<name>.+?) : \[(?P<channel>Party|Shout|Tell|Talk|Whisper|DM)\] ')
_LOGIN  = re.compile(r'^(?P<name>.+?) has joined as a player\.\.?$')
_PARTY_JOIN = re.compile(r'^(?P<name>.+?) has joined the party\.$')
_PARTY_LEADER = re.compile(r'^(?P<name>.+?) is now the Party Leader\.$')
_PARTY_INVITE_FROM = re.compile(r'^You have received a Party Invitation from (?P<name>.+?)\.$')
_WELCOME = re.compile(r'^Welcome to Higher Ground, (?P<name>.+?)!$')
_PLAYER_DETECTED = re.compile(r'^Player detected: (?P<name>.+?)$')
_PARTY_STATUS = re.compile(r'^Party: (?P<name>.+?) \[Level \d+\]')
_SPELL  = re.compile(r'^(?P<caster>.+?) (?P<action>casting|casts) (?P<spell>.+)$')
_SINGS  = re.compile(r'^(?P<caster>.+?) sings\.$')
_RESURRECT = re.compile(
    r'^(?P<caster>.+?) resurrects (?P<target>.+?) : (?P<spell>.+?) : \*(?P<result>.+?)\*$'
)
_AVERT_DEATH = re.compile(r'^(?P<target>.+?) averts death : (?P<ability>.+)$')

# Immunity block: [Server] Damage immunities: (starts the multi-line block)
# Continuation lines: "    Bludgeoning: ..........49%..............40/-..."
_IMM_LINE = re.compile(
    r'^\s+(?P<dtype>[A-Za-z]+):\s*\.+(?P<pct>\d+)%'
    r'(?:\.+(?P<dr>\d+)/-)?'
)

# Normalize immunity dtype names (log → canonical)
_IMM_TYPE_NORM = {
    'bludgeoning': 'bludgeoning', 'piercing': 'piercing', 'slashing': 'slashing',
    'acid': 'acid', 'cold': 'cold', 'electrical': 'electrical', 'fire': 'fire',
    'sonic': 'sonic', 'divine': 'divine', 'magical': 'magical',
    'negative': 'negative', 'positive': 'positive', 'psionic': 'psionic',
    'vile': 'vile', 'sacred': 'sacred', 'force': 'force', 'primal': 'primal',
    'anarchic': 'anarchic', 'axiomatic': 'axiomatic', 'subdual': 'subdual',
    'ectoplasmic': 'ectoplasmic', 'internal': 'internal', 'desiccation': 'desiccation',
    'venom': 'venom', 'dragonfire': 'dragonfire', 'blight': 'blight',
}


def _parse_damage_breakdown(raw: str) -> dict:
    """
    Parse '112 Sonic' or '50 Bludgeoning 30 Piercing 20 Slashing' etc.
    Returns dict of dmg_* columns with integer values.
    """
    result = {col: 0 for col in DMG_COLS}
    # Remove " Energy" and "Raw " run-together (HGX Damage.Parse normalization)
    raw = raw.replace(' Energy', 'Energy').replace('Raw ', 'Raw')
    for m in _DMG_PART.finditer(raw):
        amt  = int(m.group(1))
        kind = m.group(2).strip().lower()
        col  = _DMG_TYPE_MAP.get(kind, 'dmg_other')
        result[col] = result.get(col, 0) + amt
    return result


def parse_immunity_line(raw_line: str) -> dict | None:
    """Parse a continuation immunity line (no [CHAT WINDOW TEXT] prefix)."""
    m = _IMM_LINE.match(raw_line)
    if not m:
        return None
    dtype = _IMM_TYPE_NORM.get(m.group('dtype').lower())
    if not dtype:
        return None
    return {
        'dtype': dtype,
        'pct':   float(m.group('pct')),
        'dr':    float(m.group('dr')) if m.group('dr') else 0.0,
    }


def parse_line(raw_line: str) -> dict | None:
    """
    Parse one raw log line.
    Returns a dict with 'type' key, or None if the line is not a recognized event.
    """
    m = _LOG_LINE.match(raw_line)
    if not m:
        return None
    ts_str, content = m.group(1), m.group(2).strip()

    try:
        ts = datetime.strptime(ts_str, '%a %b %d %H:%M:%S').replace(
            year=datetime.now().year
        ).isoformat()
    except ValueError:
        ts = ts_str

    server_line = content.startswith('[Server] ')
    if server_line:
        content = content[9:].strip()

    # ── IMMUNITY BLOCK HEADER ────────────────────────────────────────────────
    if content == 'Damage immunities:':
        return {'type': 'immunity_block_start', 'ts': ts}

    # ── AREA CHANGE ──────────────────────────────────────────────────────────
    ma = _AREA.match(content)
    if ma:
        return {'type': 'area', 'ts': ts, 'area': ma.group('area')}

    # ── PC CHAT DETECTION ────────────────────────────────────────────────────
    mw = _WELCOME.match(content)
    if mw:
        return {'type': 'pc_detected', 'ts': ts,
                'name': mw.group('name').strip(),
                'channel': 'welcome', 'is_current_pc': 1}

    md = _PLAYER_DETECTED.match(content)
    if md:
        return {'type': 'pc_detected', 'ts': ts,
                'name': md.group('name').strip(),
                'channel': 'player_detected', 'is_current_pc': 1}

    mps = _PARTY_STATUS.match(content)
    if mps:
        return {'type': 'pc_detected', 'ts': ts,
                'name': mps.group('name').strip(),
                'channel': 'party_status', 'is_current_pc': 0}

    ml = _LOGIN.match(content)
    if ml:
        return {'type': 'account_detected', 'ts': ts,
                'name': ml.group('name').strip(), 'channel': 'login'}

    mp = _PARTY_JOIN.match(content)
    if mp:
        return {'type': 'pc_detected', 'ts': ts,
                'name': mp.group('name').strip(),
                'channel': 'party_join', 'is_current_pc': 0}

    mpl = _PARTY_LEADER.match(content)
    if mpl:
        return {'type': 'pc_detected', 'ts': ts,
                'name': mpl.group('name').strip(),
                'channel': 'party_leader', 'is_current_pc': 0}

    mpi = _PARTY_INVITE_FROM.match(content)
    if mpi:
        return {'type': 'pc_detected', 'ts': ts,
                'name': mpi.group('name').strip(),
                'channel': 'party_invite', 'is_current_pc': 0}

    mc = _CHAT.match(content)
    if mc:
        if mc.group('channel') == 'Tell':
            return None
        return {'type': 'pc_detected', 'ts': ts,
                'name': mc.group('name').strip(),
                'channel': mc.group('channel'), 'is_current_pc': 0}

    # ── BARD SINGS ───────────────────────────────────────────────────────────
    ms = _SINGS.match(content)
    if ms:
        return {
            'type': 'spell', 'ts': ts,
            'caster': ms.group('caster'), 'spell_name': 'Bard Song',
            'action': 'sings', 'is_song': 1,
        }

    # ── ATTACK ───────────────────────────────────────────────────────────────
    modes = ''
    attack_content = content
    mm = _MODES_PREFIX.match(content)
    if mm:
        modes = mm.group(1).strip()
        attack_content = mm.group(2).strip()

    def _build_attack(m2, modes_str=''):
        result_str = m2.group('result')
        concealment = 0
        hit_type = result_str
        if result_str.startswith('target concealed'):
            hit_type = 'concealed'
            cm = re.search(r'(\d+)%', result_str)
            concealment = int(cm.group(1)) if cm else 0
        elif result_str == 'critical hit':
            hit_type = 'critical_hit'
        elif result_str == 'critical attempt':
            hit_type = 'critical_attempt'
        return {
            'type':            'attack',
            'ts':              ts,
            'attacker':        m2.group('attacker'),
            'defender':        m2.group('defender'),
            'modes':           modes_str,
            'hit_type':        hit_type,
            'concealment_pct': concealment,
            'roll':            int(m2.group('roll')),
            'bonus':           int(m2.group('bonus')),
            'total':           int(m2.group('total')),
            'threat_roll':     int(m2.group('threat_roll'))  if m2.group('threat_roll')  else None,
            'threat_total':    int(m2.group('threat_total')) if m2.group('threat_total') else None,
        }

    m2 = _ATTACK_CORE.match(attack_content)
    if m2:
        return _build_attack(m2, modes)

    m2b = _ATTEMPT_CORE.match(content)
    if m2b:
        ev = _build_attack(m2b, m2b.group('ability'))
        ev['modes'] = m2b.group('ability')
        return ev

    # ── DAMAGE ───────────────────────────────────────────────────────────────
    m3 = _DAMAGE.match(content)
    if m3:
        breakdown = _parse_damage_breakdown(m3.group('breakdown'))
        return {
            'type':         'damage',
            'ts':           ts,
            'attacker':     m3.group('attacker'),
            'defender':     m3.group('defender'),
            'total_damage': int(m3.group('total')),
            **breakdown,
        }

    # ── SAVES (Fort / Reflex / Will / AB) ────────────────────────────────────
    m4 = _SAVE.match(content)
    if m4:
        bonus = int(m4.group('bonus'))
        if m4.group('sign') == '-':
            bonus = -bonus
        return {
            'type':       'save',
            'ts':         ts,
            'target':     m4.group('target'),
            'save_type':  m4.group('save_type'),
            'check_type': 'save',
            'vs_source':  m4.group('source'),
            'result':     m4.group('result'),
            'roll':       int(m4.group('roll')),
            'bonus':      bonus,
            'total':      int(m4.group('total')),
            'dc':         int(m4.group('dc')),
        }

    m4b = _SKILL.match(content)
    if m4b:
        bonus = int(m4b.group('bonus'))
        if m4b.group('sign') == '-':
            bonus = -bonus
        return {
            'type':       'save',
            'ts':         ts,
            'target':     m4b.group('character'),
            'save_type':  m4b.group('skill'),
            'check_type': 'skill',
            'vs_source':  m4b.group('opponent') or '',
            'result':     m4b.group('result'),
            'roll':       int(m4b.group('roll')),
            'bonus':      bonus,
            'total':      int(m4b.group('total')),
            'dc':         int(m4b.group('dc')),
        }

    # ── KILL ─────────────────────────────────────────────────────────────────
    m5 = _KILL.match(content)
    if m5:
        return {'type': 'kill', 'ts': ts,
                'killer': m5.group('killer'), 'victim': m5.group('victim')}

    # ── XP ───────────────────────────────────────────────────────────────────
    m6 = _XP.match(content)
    if m6:
        return {'type': 'xp', 'ts': ts, 'xp': int(m6.group('xp'))}

    # ── SPELL RESISTANCE ─────────────────────────────────────────────────────
    m7 = _SR.match(content)
    if m7:
        bonus = int(m7.group('bonus')) if m7.group('bonus') else None
        if bonus is not None and m7.group('sign') == '-':
            bonus = -bonus
        return {
            'type': 'spell_check', 'ts': ts,
            'check_type': 'SR', 'source': m7.group('source'),
            'result': m7.group('result'),
            'roll': int(m7.group('roll')) if m7.group('roll') else None,
            'bonus': bonus,
            'total': int(m7.group('total')) if m7.group('total') else None,
            'dc': int(m7.group('sr')) if m7.group('sr') else None,
            'sr_value': int(m7.group('sr')) if m7.group('sr') else None,
            'vs_value': int(m7.group('sr')) if m7.group('sr') else None,
        }

    # ── SPELL PENETRATION ─────────────────────────────────────────────────────
    m8 = _SP.match(content)
    if m8:
        bonus = int(m8.group('bonus')) if m8.group('bonus') else None
        if bonus is not None and m8.group('sign') == '-':
            bonus = -bonus
        return {
            'type': 'spell_check', 'ts': ts,
            'check_type': 'SP', 'target': m8.group('target'),
            'result': m8.group('result'),
            'roll': int(m8.group('roll')) if m8.group('roll') else None,
            'bonus': bonus,
            'total': int(m8.group('total')) if m8.group('total') else None,
            'dc': int(m8.group('sr')) if m8.group('sr') else None,
            'sr_value': int(m8.group('sr')) if m8.group('sr') else None,
            'vs_value': int(m8.group('sr')) if m8.group('sr') else None,
        }

    # ── TURN CHECK ───────────────────────────────────────────────────────────
    m9 = _TURN.match(content)
    if m9:
        bonus = int(m9.group('bonus')) if m9.group('bonus') else None
        if bonus is not None and m9.group('sign') == '-':
            bonus = -bonus
        return {
            'type': 'spell_check', 'ts': ts,
            'check_type': 'Turn', 'target': m9.group('target'),
            'result': m9.group('result'),
            'roll': int(m9.group('roll')) if m9.group('roll') else None,
            'bonus': bonus,
            'total': int(m9.group('total')) if m9.group('total') else None,
            'dc': int(m9.group('tr')) if m9.group('tr') else None,
            'vs_value': int(m9.group('tr')) if m9.group('tr') else None,
        }

    # ── DISPEL / BREACH ──────────────────────────────────────────────────────
    m10 = _DISPEL.match(content)
    if m10:
        bonus = int(m10.group('bonus')) if m10.group('bonus') else None
        if bonus is not None and m10.group('sign') == '-':
            bonus = -bonus
        return {
            'type': 'spell_check', 'ts': ts,
            'check_type': m10.group('dtype'),
            'source': m10.group('source'),
            'target': m10.group('effect'),
            'result': m10.group('result'),
            'roll': int(m10.group('roll')) if m10.group('roll') else None,
            'bonus': bonus,
            'total': int(m10.group('total')) if m10.group('total') else None,
            'dc': int(m10.group('dc')) if m10.group('dc') else None,
            'vs_value': int(m10.group('dc')) if m10.group('dc') else None,
        }

    # ── RESURRECT ────────────────────────────────────────────────────────────
    m11 = _RESURRECT.match(content)
    if m11:
        return {
            'type': 'resurrect', 'ts': ts,
            'caster': m11.group('caster'), 'target': m11.group('target'),
            'spell': m11.group('spell'), 'result': m11.group('result'),
        }

    m11b = _AVERT_DEATH.match(content)
    if m11b:
        return {
            'type': 'death_averted', 'ts': ts,
            'target': m11b.group('target'), 'ability': m11b.group('ability'),
        }

    # ── SPELL CAST ───────────────────────────────────────────────────────────
    m12 = _SPELL.match(content)
    if m12:
        return {
            'type': 'spell', 'ts': ts,
            'caster': m12.group('caster'), 'action': m12.group('action'),
            'spell_name': m12.group('spell'), 'is_song': 0,
        }

    return None


def parse_file_chunk(lines: list[str]) -> list[dict]:
    """Parse a list of raw log lines, return list of event dicts."""
    results = []
    for line in lines:
        ev = parse_line(line)
        if ev:
            results.append(ev)
    return results
