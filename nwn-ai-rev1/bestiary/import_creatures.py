"""
Import creatures_data.json into bestiary.db.
Run once, or re-run to update (upserts on creature name).
"""
import json, sqlite3, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import CREATURES_JSON, BESTIARY_DB

_IMM_FIELDS = [
    'Imm_Bludgeoning','Imm_Piercing','Imm_Slashing','Imm_Acid','Imm_Cold',
    'Imm_Electrical','Imm_Fire','Imm_Sonic','Imm_Divine','Imm_Magical',
    'Imm_Negative','Imm_Positive','Imm_Ectoplasmic','Imm_Internal','Imm_Psionic',
    'Imm_Sacred','Imm_Vile','Imm_Anarchic','Imm_Axiomatic','Imm_Primal',
    'Imm_Subdual','Imm_Force',
]
_RES_FIELDS = [f.replace('Imm_', 'Res_') for f in _IMM_FIELDS]

_ALL_NUMERIC = _IMM_FIELDS + _RES_FIELDS


def import_creatures(path: str = CREATURES_JSON, db: str = BESTIARY_DB):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    creatures = data.get('creatures', data) if isinstance(data, dict) else data

    conn = sqlite3.connect(db)
    conn.execute('PRAGMA journal_mode=WAL')
    upserted = 0

    for c in creatures:
        name = (c.get('Name') or '').strip()
        if not name:
            continue

        imm_vals = [float(c.get(f, 0) or 0) for f in _IMM_FIELDS]
        res_vals = [float(c.get(f, 0) or 0) for f in _RES_FIELDS]

        conn.execute('''
            INSERT INTO creatures (
                name, race, type,
                spell_immunities, other_immunities,
                imm_bludgeoning, imm_piercing, imm_slashing,
                imm_acid, imm_cold, imm_electrical, imm_fire, imm_sonic,
                imm_divine, imm_magical, imm_negative, imm_positive,
                imm_ectoplasmic, imm_internal, imm_psionic, imm_sacred,
                imm_vile, imm_anarchic, imm_axiomatic, imm_primal,
                imm_subdual, imm_force,
                res_bludgeoning, res_piercing, res_slashing,
                res_acid, res_cold, res_electrical, res_fire, res_sonic,
                res_divine, res_magical, res_negative, res_positive,
                res_ectoplasmic, res_internal, res_psionic, res_sacred,
                res_vile, res_anarchic, res_axiomatic, res_primal,
                res_subdual, res_force,
                source
            ) VALUES (
                ?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                ?
            )
            ON CONFLICT(name) DO UPDATE SET
                race=excluded.race,
                type=excluded.type,
                spell_immunities=excluded.spell_immunities,
                other_immunities=excluded.other_immunities,
                imm_bludgeoning=excluded.imm_bludgeoning,
                imm_piercing=excluded.imm_piercing,
                imm_slashing=excluded.imm_slashing,
                imm_acid=excluded.imm_acid,
                imm_cold=excluded.imm_cold,
                imm_electrical=excluded.imm_electrical,
                imm_fire=excluded.imm_fire,
                imm_sonic=excluded.imm_sonic,
                imm_divine=excluded.imm_divine,
                imm_magical=excluded.imm_magical,
                imm_negative=excluded.imm_negative,
                imm_positive=excluded.imm_positive,
                imm_ectoplasmic=excluded.imm_ectoplasmic,
                imm_internal=excluded.imm_internal,
                imm_psionic=excluded.imm_psionic,
                imm_sacred=excluded.imm_sacred,
                imm_vile=excluded.imm_vile,
                imm_anarchic=excluded.imm_anarchic,
                imm_axiomatic=excluded.imm_axiomatic,
                imm_primal=excluded.imm_primal,
                imm_subdual=excluded.imm_subdual,
                imm_force=excluded.imm_force,
                res_bludgeoning=excluded.res_bludgeoning,
                res_piercing=excluded.res_piercing,
                res_slashing=excluded.res_slashing,
                res_acid=excluded.res_acid,
                res_cold=excluded.res_cold,
                res_electrical=excluded.res_electrical,
                res_fire=excluded.res_fire,
                res_sonic=excluded.res_sonic,
                res_divine=excluded.res_divine,
                res_magical=excluded.res_magical,
                res_negative=excluded.res_negative,
                res_positive=excluded.res_positive,
                res_ectoplasmic=excluded.res_ectoplasmic,
                res_internal=excluded.res_internal,
                res_psionic=excluded.res_psionic,
                res_sacred=excluded.res_sacred,
                res_vile=excluded.res_vile,
                res_anarchic=excluded.res_anarchic,
                res_axiomatic=excluded.res_axiomatic,
                res_primal=excluded.res_primal,
                res_subdual=excluded.res_subdual,
                res_force=excluded.res_force
        ''', (
            name,
            c.get('Race', ''),
            c.get('Type', ''),
            c.get('SpellImmunities', ''),
            c.get('OtherImmunities', ''),
            *imm_vals,
            *res_vals,
            'creatures_json',
        ))
        upserted += 1

    conn.commit()
    conn.close()
    print(f'  Imported {upserted} creatures -> {db}')
    return upserted


if __name__ == '__main__':
    import_creatures()
