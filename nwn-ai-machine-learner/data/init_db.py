"""Create and initialize combat.db and bestiary.db.
Safe to re-run: uses IF NOT EXISTS + ALTER TABLE for new columns.
"""
import sqlite3, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import COMBAT_DB, BESTIARY_DB

COMBAT_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time  TEXT NOT NULL,
    end_time    TEXT,
    log_file    TEXT
);

CREATE TABLE IF NOT EXISTS attacks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER,
    ts              TEXT,
    attacker        TEXT,
    defender        TEXT,
    modes           TEXT,
    hit_type        TEXT,
    concealment_pct INTEGER,
    roll            INTEGER,
    bonus           INTEGER,
    total           INTEGER,
    threat_roll     INTEGER,
    threat_total    INTEGER,
    attacker_is_pc  INTEGER DEFAULT 0,
    defender_is_pc  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS damages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER,
    ts              TEXT,
    attacker        TEXT,
    defender        TEXT,
    total_damage    INTEGER,
    -- Physical subtypes. dmg_physical means the log did not split B/P/S.
    dmg_bludgeoning INTEGER DEFAULT 0,
    dmg_piercing    INTEGER DEFAULT 0,
    dmg_slashing    INTEGER DEFAULT 0,
    dmg_physical    INTEGER DEFAULT 0,
    -- Elemental
    dmg_acid        INTEGER DEFAULT 0,
    dmg_cold        INTEGER DEFAULT 0,
    dmg_electrical  INTEGER DEFAULT 0,
    dmg_fire        INTEGER DEFAULT 0,
    dmg_sonic       INTEGER DEFAULT 0,
    -- Planar/energy
    dmg_divine      INTEGER DEFAULT 0,
    dmg_magical     INTEGER DEFAULT 0,
    dmg_negative    INTEGER DEFAULT 0,
    dmg_positive    INTEGER DEFAULT 0,
    -- Exotic (HGX types 12-33)
    dmg_psionic     INTEGER DEFAULT 0,
    dmg_vile        INTEGER DEFAULT 0,
    dmg_sacred      INTEGER DEFAULT 0,
    dmg_force       INTEGER DEFAULT 0,
    dmg_anarchic    INTEGER DEFAULT 0,
    dmg_axiomatic   INTEGER DEFAULT 0,
    dmg_primal      INTEGER DEFAULT 0,
    dmg_subdual     INTEGER DEFAULT 0,
    dmg_ectoplasmic INTEGER DEFAULT 0,
    dmg_internal    INTEGER DEFAULT 0,
    dmg_desiccation INTEGER DEFAULT 0,
    dmg_venom       INTEGER DEFAULT 0,
    dmg_raw_arcane  INTEGER DEFAULT 0,
    dmg_raw_divine  INTEGER DEFAULT 0,
    dmg_raw_nature  INTEGER DEFAULT 0,
    dmg_dragonfire  INTEGER DEFAULT 0,
    dmg_blight      INTEGER DEFAULT 0,
    dmg_deception   INTEGER DEFAULT 0,
    dmg_degeneration INTEGER DEFAULT 0,
    dmg_digestion   INTEGER DEFAULT 0,
    dmg_retribution INTEGER DEFAULT 0,
    dmg_antimagic   INTEGER DEFAULT 0,
    dmg_other       INTEGER DEFAULT 0,
    attacker_is_pc  INTEGER DEFAULT 0,
    defender_is_pc  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS saves (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER,
    ts           TEXT,
    target       TEXT,
    save_type    TEXT,   -- Fortitude / Reflex / Will / AB
    check_type   TEXT DEFAULT 'save', -- save / skill / SR / SP / Turn / Dispel / Breach
    vs_source    TEXT,   -- attacking spell / creature name
    result       TEXT,
    roll         INTEGER,
    bonus        INTEGER,
    total        INTEGER,
    dc           INTEGER,
    spell_name   TEXT,
    target_is_pc INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kills (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER,
    ts           TEXT,
    killer       TEXT,
    victim       TEXT,
    xp_gained    INTEGER DEFAULT 0,
    killer_is_pc INTEGER DEFAULT 0,
    victim_is_pc INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS death_averts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER,
    ts           TEXT,
    target       TEXT,
    ability      TEXT,
    target_is_pc INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spells (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER,
    ts           TEXT,
    caster       TEXT,
    spell_name   TEXT,
    action       TEXT,   -- 'casts' / 'casting' / 'sings'
    is_song      INTEGER DEFAULT 0,  -- 1 = bard song
    caster_is_pc INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spell_checks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER,
    ts           TEXT,
    source       TEXT,
    target       TEXT,
    check_type   TEXT,   -- SR / SP / Turn / Dispel / Breach
    result       TEXT,
    roll         INTEGER,
    bonus        INTEGER,
    total        INTEGER,
    dc           INTEGER,
    sr_value     INTEGER,
    spell_name   TEXT,
    vs_value     INTEGER
);

CREATE TABLE IF NOT EXISTS detected_pcs (
    name        TEXT PRIMARY KEY,
    first_seen  TEXT,
    last_seen   TEXT,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS area_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER,
    ts          TEXT,
    area_name   TEXT
);

CREATE TABLE IF NOT EXISTS pc_status (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER,
    ts              TEXT,
    pc_name         TEXT DEFAULT 'Unknown PC',
    area_name       TEXT,
    imm_bludgeoning REAL DEFAULT 0,
    imm_piercing    REAL DEFAULT 0,
    imm_slashing    REAL DEFAULT 0,
    imm_magical     REAL DEFAULT 0,
    imm_acid        REAL DEFAULT 0,
    imm_cold        REAL DEFAULT 0,
    imm_divine      REAL DEFAULT 0,
    imm_electrical  REAL DEFAULT 0,
    imm_fire        REAL DEFAULT 0,
    imm_negative    REAL DEFAULT 0,
    imm_positive    REAL DEFAULT 0,
    imm_sonic       REAL DEFAULT 0,
    imm_subdual     REAL DEFAULT 0,
    imm_ectoplasmic REAL DEFAULT 0,
    imm_psionic     REAL DEFAULT 0,
    imm_sacred      REAL DEFAULT 0,
    imm_vile        REAL DEFAULT 0,
    imm_primal      REAL DEFAULT 0,
    imm_anarchic    REAL DEFAULT 0,
    imm_axiomatic   REAL DEFAULT 0,
    res_bludgeoning REAL DEFAULT 0,
    res_piercing    REAL DEFAULT 0,
    res_slashing    REAL DEFAULT 0,
    res_magical     REAL DEFAULT 0,
    res_acid        REAL DEFAULT 0,
    res_cold        REAL DEFAULT 0,
    res_divine      REAL DEFAULT 0,
    res_electrical  REAL DEFAULT 0,
    res_fire        REAL DEFAULT 0,
    res_negative    REAL DEFAULT 0,
    res_positive    REAL DEFAULT 0,
    res_sonic       REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS debuff_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER,
    ts          TEXT,
    pc_name     TEXT DEFAULT 'Unknown PC',
    area_name   TEXT,
    damage_type TEXT,
    old_value   REAL,
    new_value   REAL,
    drop_amount REAL,
    alert_level TEXT,
    reason      TEXT
);

CREATE TABLE IF NOT EXISTS unparsed_lines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER,
    ts          TEXT,
    source_file TEXT,
    area_name   TEXT,
    bucket      TEXT,
    content     TEXT,
    raw_line    TEXT,
    reviewed    INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parser_rule_candidates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket         TEXT,
    seen_count     INTEGER,
    first_seen     TEXT,
    last_seen      TEXT,
    samples_json   TEXT,
    proposed_type  TEXT,
    proposed_regex TEXT,
    notes          TEXT,
    status         TEXT DEFAULT 'new',
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parser_regression_cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER,
    raw_line        TEXT,
    expected_json   TEXT,
    status          TEXT DEFAULT 'new',
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attacks_attacker  ON attacks(attacker);
CREATE INDEX IF NOT EXISTS idx_attacks_defender  ON attacks(defender);
CREATE INDEX IF NOT EXISTS idx_attacks_ts        ON attacks(ts);
CREATE INDEX IF NOT EXISTS idx_damages_attacker  ON damages(attacker);
CREATE INDEX IF NOT EXISTS idx_damages_defender  ON damages(defender);
CREATE INDEX IF NOT EXISTS idx_damages_ts        ON damages(ts);
CREATE INDEX IF NOT EXISTS idx_saves_target      ON saves(target);
CREATE INDEX IF NOT EXISTS idx_saves_ts          ON saves(ts);
CREATE INDEX IF NOT EXISTS idx_kills_ts          ON kills(ts);
CREATE INDEX IF NOT EXISTS idx_death_averts_ts   ON death_averts(ts);
CREATE INDEX IF NOT EXISTS idx_spells_caster     ON spells(caster);
CREATE INDEX IF NOT EXISTS idx_unparsed_bucket   ON unparsed_lines(bucket);
CREATE INDEX IF NOT EXISTS idx_unparsed_reviewed ON unparsed_lines(reviewed);
"""

BESTIARY_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS creatures (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT UNIQUE NOT NULL,
    race                TEXT,
    type                TEXT,
    ac                  INTEGER,
    ab                  INTEGER,
    hp                  INTEGER,
    sr                  INTEGER,
    tr                  TEXT,
    saves_fort          INTEGER,
    saves_ref           INTEGER,
    saves_will          INTEGER,
    concealment         INTEGER,
    kb                  TEXT,
    takes               TEXT,
    heals               TEXT,
    deals               TEXT,
    spell_immunities    TEXT,
    other_immunities    TEXT,
    special_abilities   TEXT,
    areas               TEXT,
    notes               TEXT,
    imm_bludgeoning     REAL DEFAULT 0,
    imm_piercing        REAL DEFAULT 0,
    imm_slashing        REAL DEFAULT 0,
    imm_acid            REAL DEFAULT 0,
    imm_cold            REAL DEFAULT 0,
    imm_electrical      REAL DEFAULT 0,
    imm_fire            REAL DEFAULT 0,
    imm_sonic           REAL DEFAULT 0,
    imm_divine          REAL DEFAULT 0,
    imm_magical         REAL DEFAULT 0,
    imm_negative        REAL DEFAULT 0,
    imm_positive        REAL DEFAULT 0,
    imm_ectoplasmic     REAL DEFAULT 0,
    imm_internal        REAL DEFAULT 0,
    imm_psionic         REAL DEFAULT 0,
    imm_sacred          REAL DEFAULT 0,
    imm_vile            REAL DEFAULT 0,
    imm_anarchic        REAL DEFAULT 0,
    imm_axiomatic       REAL DEFAULT 0,
    imm_primal          REAL DEFAULT 0,
    imm_subdual         REAL DEFAULT 0,
    imm_force           REAL DEFAULT 0,
    res_bludgeoning     REAL DEFAULT 0,
    res_piercing        REAL DEFAULT 0,
    res_slashing        REAL DEFAULT 0,
    res_acid            REAL DEFAULT 0,
    res_cold            REAL DEFAULT 0,
    res_electrical      REAL DEFAULT 0,
    res_fire            REAL DEFAULT 0,
    res_sonic           REAL DEFAULT 0,
    res_divine          REAL DEFAULT 0,
    res_magical         REAL DEFAULT 0,
    res_negative        REAL DEFAULT 0,
    res_positive        REAL DEFAULT 0,
    res_ectoplasmic     REAL DEFAULT 0,
    res_internal        REAL DEFAULT 0,
    res_psionic         REAL DEFAULT 0,
    res_sacred          REAL DEFAULT 0,
    res_vile            REAL DEFAULT 0,
    res_anarchic        REAL DEFAULT 0,
    res_axiomatic       REAL DEFAULT 0,
    res_primal          REAL DEFAULT 0,
    res_subdual         REAL DEFAULT 0,
    res_force           REAL DEFAULT 0,
    source              TEXT DEFAULT 'creatures_json'
);

CREATE TABLE IF NOT EXISTS areas (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT UNIQUE NOT NULL,
    prevalent_damage_types  TEXT,
    recommended_protections TEXT,
    best_damage_types       TEXT,
    paragon_ab_bonus        INTEGER DEFAULT 0,
    paragon_ac_bonus        INTEGER DEFAULT 0,
    paragon_save_bonus      INTEGER DEFAULT 0,
    notes                   TEXT,
    wiki_url                TEXT,
    -- area guide fields (from /wiki/AreaName pages)
    level_min               INTEGER,
    level_max               INTEGER,
    required_ab             INTEGER,
    required_ac             INTEGER,
    required_saves          INTEGER,
    required_hp             INTEGER,
    area_dc_min             INTEGER,
    area_dc_max             INTEGER,
    enemy_ab_min            INTEGER,
    enemy_ab_max            INTEGER,
    enemy_ac_min            INTEGER,
    enemy_ac_max            INTEGER,
    tactical_notes          TEXT
);

CREATE TABLE IF NOT EXISTS creature_areas (
    creature_id INTEGER REFERENCES creatures(id),
    area_id     INTEGER REFERENCES areas(id),
    PRIMARY KEY (creature_id, area_id)
);

CREATE INDEX IF NOT EXISTS idx_creatures_name ON creatures(name);
CREATE INDEX IF NOT EXISTS idx_creatures_race ON creatures(race);
"""


def _migrate_combat(conn):
    """Add columns introduced after initial release."""
    existing_dmg = {r[1] for r in conn.execute("PRAGMA table_info(damages)")}
    new_dmg = [
        'dmg_bludgeoning','dmg_piercing','dmg_slashing',
        'dmg_physical',
        'dmg_ectoplasmic','dmg_internal','dmg_anarchic','dmg_axiomatic',
        'dmg_primal','dmg_subdual','dmg_desiccation','dmg_venom',
        'dmg_raw_arcane','dmg_raw_divine','dmg_raw_nature',
        'dmg_dragonfire','dmg_blight','dmg_deception','dmg_degeneration',
        'dmg_digestion','dmg_retribution','dmg_antimagic',
    ]
    for col in new_dmg:
        if col not in existing_dmg:
            conn.execute(f'ALTER TABLE damages ADD COLUMN {col} INTEGER DEFAULT 0')

    existing_saves = {r[1] for r in conn.execute("PRAGMA table_info(saves)")}
    if 'check_type' not in existing_saves:
        conn.execute("ALTER TABLE saves ADD COLUMN check_type TEXT DEFAULT 'save'")
    if 'spell_name' not in existing_saves:
        conn.execute("ALTER TABLE saves ADD COLUMN spell_name TEXT")

    existing_spells = {r[1] for r in conn.execute("PRAGMA table_info(spells)")}
    if 'is_song' not in existing_spells:
        conn.execute("ALTER TABLE spells ADD COLUMN is_song INTEGER DEFAULT 0")

    existing_checks = {r[1] for r in conn.execute("PRAGMA table_info(spell_checks)")}
    for col, typ in [
        ('total', 'INTEGER'),
        ('dc', 'INTEGER'),
        ('sr_value', 'INTEGER'),
        ('spell_name', 'TEXT'),
    ]:
        if col not in existing_checks:
            conn.execute(f"ALTER TABLE spell_checks ADD COLUMN {col} {typ}")

    existing_pc_status = {r[1] for r in conn.execute("PRAGMA table_info(pc_status)")}
    if 'pc_name' not in existing_pc_status:
        conn.execute("ALTER TABLE pc_status ADD COLUMN pc_name TEXT DEFAULT 'Unknown PC'")

    existing_alerts = {r[1] for r in conn.execute("PRAGMA table_info(debuff_alerts)")}
    for col, typ in [
        ('pc_name', "TEXT DEFAULT 'Unknown PC'"),
        ('area_name', 'TEXT'),
        ('reason', 'TEXT'),
    ]:
        if col not in existing_alerts:
            conn.execute(f"ALTER TABLE debuff_alerts ADD COLUMN {col} {typ}")

    conn.commit()


def _migrate_bestiary(conn):
    """Add columns introduced after initial release."""
    existing_areas = {r[1] for r in conn.execute("PRAGMA table_info(areas)")}
    new_area_cols = [
        ('level_min',     'INTEGER'), ('level_max',    'INTEGER'),
        ('required_ab',   'INTEGER'), ('required_ac',  'INTEGER'),
        ('required_saves','INTEGER'), ('required_hp',  'INTEGER'),
        ('area_dc_min',   'INTEGER'), ('area_dc_max',  'INTEGER'),
        ('enemy_ab_min',  'INTEGER'), ('enemy_ab_max', 'INTEGER'),
        ('enemy_ac_min',  'INTEGER'), ('enemy_ac_max', 'INTEGER'),
        ('tactical_notes','TEXT'),
    ]
    for col, typ in new_area_cols:
        if col not in existing_areas:
            conn.execute(f'ALTER TABLE areas ADD COLUMN {col} {typ}')
    conn.commit()


def init_all():
    os.makedirs(os.path.dirname(COMBAT_DB), exist_ok=True)

    for path, schema, label, migrate_fn in [
        (COMBAT_DB,   COMBAT_SCHEMA,   "combat",   _migrate_combat),
        (BESTIARY_DB, BESTIARY_SCHEMA, "bestiary", _migrate_bestiary),
    ]:
        conn = sqlite3.connect(path)
        conn.executescript(schema)
        if migrate_fn:
            migrate_fn(conn)
        conn.commit()
        conn.close()
        print(f"  {label}.db initialized: {path}")


if __name__ == "__main__":
    init_all()
    print("Databases ready.")
