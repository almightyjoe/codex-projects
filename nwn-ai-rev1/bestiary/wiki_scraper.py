r"""
Scrape the Higher Grounds wiki bestiary pages into bestiary.db.
Fills in AC, AB, Saves, SR, TR, HP, areas, special abilities, and tactical notes
that creatures_data.json doesn't have.

Run:  C:\Python312\python.exe wiki_scraper.py
  --area "Abyss/Demons"    (scrape one area)
  --all                    (scrape all bestiary pages, ~30 min polite rate)
"""
import re, time, sqlite3, sys, os, argparse
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import BESTIARY_DB, WIKI_BASE, WIKI_REQUEST_DELAY

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'NWN-AI-Scraper/1.0 (personal research tool)'

# All known bestiary pages on hgweb.org
BESTIARY_PAGES = [
    'Bestiary:_Abyss/Demons', 'Bestiary:_Abyss/ABPV',
    'Bestiary:_Abyss/Humanoids', 'Bestiary:_Abyss/Other',
    'Bestiary:_Hells', 'Bestiary:_Limbo', 'Bestiary:_Feywild',
    'Bestiary:_Oinos', 'Bestiary:_Elysium', 'Bestiary:_Penumbra',
    'Bestiary:_Rona', 'Bestiary:_Hive', 'Bestiary:_Toyshop',
    'Bestiary:_Desert', 'Bestiary:_Tragidore', 'Bestiary:_Uroboros_Peak',
    'Bestiary:_Locathah_Depths', 'Bestiary:_Arcane_Archive',
    "Bestiary:_Zorbgot's_Hive", 'Bestiary:_Catacombs_of_Dulvuroth',
    'Bestiary:_Pit_of_Moliation', 'Bestiary:_Black_Pyramid',
    'Bestiary:_Manatakloss', 'Bestiary:_Maze_of_the_Ancients',
    'Bestiary:_Myconid_Depths', 'Bestiary:_Ssithraks',
    'Bestiary:_Aboleths',
    'Bestiary:_Elemental_Planes/Air', 'Bestiary:_Elemental_Planes/Earth',
    'Bestiary:_Elemental_Planes/Fire', 'Bestiary:_Elemental_Planes/Water',
]

_INT  = re.compile(r'(-?\d+)')
_PCT  = re.compile(r'(\d+)%')


def _get(page: str) -> BeautifulSoup | None:
    url = f'{WIKI_BASE}/{page}'
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, 'lxml')
    except Exception as e:
        print(f'  WARN: fetch failed for {page}: {e}')
        return None


def _text(el) -> str:
    return el.get_text(strip=True) if el else ''


def _int_or_none(s: str):
    m = _INT.search(s)
    return int(m.group(1)) if m else None


def _parse_saves(s: str):
    """Parse 'Fort/Ref/Will' or individual numbers from a saves string."""
    nums = _INT.findall(s)
    if len(nums) >= 3:
        return int(nums[0]), int(nums[1]), int(nums[2])
    return None, None, None


def _extract_area_name(page: str) -> str:
    """Convert wiki page slug to readable area name."""
    name = page.replace('Bestiary:_', '').replace('_', ' ')
    return name


def _parse_creature_table(table, area_name: str) -> list[dict]:
    """
    Parse a MediaWiki table of creature entries.
    Each row is a creature; columns vary by page but we try to find known headers.
    """
    creatures = []
    headers = []
    rows = table.find_all('tr')

    for row in rows:
        cells = row.find_all(['th', 'td'])
        if not cells:
            continue
        texts = [_text(c) for c in cells]

        if all(c.name == 'th' for c in cells):
            headers = [t.lower().strip() for t in texts]
            continue

        if not headers or len(texts) < 2:
            continue

        entry = {'areas': area_name}
        for i, h in enumerate(headers):
            val = texts[i] if i < len(texts) else ''
            if 'name' in h:
                entry['name'] = val
            elif h == 'ac':
                entry['ac'] = _int_or_none(val)
            elif h == 'ab':
                entry['ab'] = _int_or_none(val)
            elif h == 'hp':
                entry['hp'] = _int_or_none(val)
            elif h == 'sr':
                entry['sr'] = _int_or_none(val)
            elif h == 'tr':
                entry['tr'] = val
            elif h in ('saves', 'fort/ref/will', 'save'):
                f, r, w = _parse_saves(val)
                entry['saves_fort'] = f
                entry['saves_ref']  = r
                entry['saves_will'] = w
            elif 'fort' in h:
                entry['saves_fort'] = _int_or_none(val)
            elif 'ref' in h:
                entry['saves_ref'] = _int_or_none(val)
            elif 'will' in h:
                entry['saves_will'] = _int_or_none(val)
            elif 'conceal' in h:
                m = _PCT.search(val)
                entry['concealment'] = int(m.group(1)) if m else None
            elif h == 'kb':
                entry['kb'] = val
            elif h in ('takes', 'vulnerable'):
                entry['takes'] = val
            elif h == 'heals':
                entry['heals'] = val
            elif h in ('deals', 'damage'):
                entry['deals'] = val
            elif 'spell imm' in h:
                entry['spell_immunities'] = val
            elif 'misc imm' in h or 'other imm' in h or 'imm' in h:
                entry['other_immunities'] = val
            elif 'special' in h or 'ability' in h:
                entry['special_abilities'] = val
            elif 'note' in h or 'strat' in h:
                entry['notes'] = val
            elif 'race' in h:
                entry['race'] = val

        if entry.get('name'):
            creatures.append(entry)

    return creatures


def scrape_page(page: str, conn: sqlite3.Connection) -> int:
    soup = _get(page)
    if not soup:
        return 0

    area_name = _extract_area_name(page)

    # ensure area exists
    conn.execute(
        'INSERT OR IGNORE INTO areas (name, wiki_url) VALUES (?, ?)',
        (area_name, f'{WIKI_BASE}/{page}')
    )

    area_id = conn.execute(
        'SELECT id FROM areas WHERE name=?', (area_name,)
    ).fetchone()[0]

    # find all tables on the page and try to parse creature rows
    tables = soup.find_all('table', class_=re.compile(r'wikitable', re.I))
    if not tables:
        tables = soup.find_all('table')

    total = 0
    for tbl in tables:
        creatures = _parse_creature_table(tbl, area_name)
        for c in creatures:
            name = c.get('name', '').strip()
            if not name or name.lower() in ('name', 'example'):
                continue

            # upsert creature — only update wiki-sourced fields, preserve immunity data
            conn.execute('''
                INSERT INTO creatures (name, race, ac, ab, hp, sr, tr,
                    saves_fort, saves_ref, saves_will, concealment,
                    kb, takes, heals, deals,
                    spell_immunities, other_immunities, special_abilities,
                    areas, notes, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'wiki')
                ON CONFLICT(name) DO UPDATE SET
                    ac=COALESCE(excluded.ac, ac),
                    ab=COALESCE(excluded.ab, ab),
                    hp=COALESCE(excluded.hp, hp),
                    sr=COALESCE(excluded.sr, sr),
                    tr=COALESCE(NULLIF(excluded.tr,''), tr),
                    saves_fort=COALESCE(excluded.saves_fort, saves_fort),
                    saves_ref=COALESCE(excluded.saves_ref, saves_ref),
                    saves_will=COALESCE(excluded.saves_will, saves_will),
                    concealment=COALESCE(excluded.concealment, concealment),
                    kb=COALESCE(NULLIF(excluded.kb,''), kb),
                    takes=COALESCE(NULLIF(excluded.takes,''), takes),
                    heals=COALESCE(NULLIF(excluded.heals,''), heals),
                    deals=COALESCE(NULLIF(excluded.deals,''), deals),
                    spell_immunities=COALESCE(NULLIF(excluded.spell_immunities,''), spell_immunities),
                    other_immunities=COALESCE(NULLIF(excluded.other_immunities,''), other_immunities),
                    special_abilities=COALESCE(NULLIF(excluded.special_abilities,''), special_abilities),
                    areas=CASE WHEN areas IS NULL OR areas='' THEN excluded.areas
                               WHEN instr(areas, excluded.areas)>0 THEN areas
                               ELSE areas || ', ' || excluded.areas END,
                    notes=COALESCE(NULLIF(excluded.notes,''), notes),
                    source='wiki'
            ''', (
                name,
                c.get('race', ''), c.get('ac'), c.get('ab'), c.get('hp'),
                c.get('sr'), c.get('tr', ''),
                c.get('saves_fort'), c.get('saves_ref'), c.get('saves_will'),
                c.get('concealment'), c.get('kb', ''),
                c.get('takes', ''), c.get('heals', ''), c.get('deals', ''),
                c.get('spell_immunities', ''), c.get('other_immunities', ''),
                c.get('special_abilities', ''), area_name, c.get('notes', ''),
            ))

            # link creature → area
            cid = conn.execute('SELECT id FROM creatures WHERE name=?', (name,)).fetchone()
            if cid:
                conn.execute(
                    'INSERT OR IGNORE INTO creature_areas (creature_id, area_id) VALUES (?,?)',
                    (cid[0], area_id)
                )
            total += 1

    conn.commit()
    print(f'  [{area_name}] {total} creatures upserted')
    return total


def scrape_all(pages=None):
    conn = sqlite3.connect(BESTIARY_DB)
    conn.execute('PRAGMA journal_mode=WAL')

    targets = pages or BESTIARY_PAGES
    grand_total = 0
    for page in targets:
        print(f'Scraping {page} ...')
        n = scrape_page(page, conn)
        grand_total += n
        time.sleep(WIKI_REQUEST_DELAY)

    conn.close()
    print(f'\nDone. {grand_total} creature entries scraped/updated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape HG wiki bestiary')
    parser.add_argument('--all',  action='store_true', help='Scrape all pages')
    parser.add_argument('--area', type=str, help='Scrape one page, e.g. Bestiary:_Hells')
    args = parser.parse_args()

    if args.area:
        conn = sqlite3.connect(BESTIARY_DB)
        conn.execute('PRAGMA journal_mode=WAL')
        scrape_page(args.area, conn)
        conn.close()
    elif args.all:
        scrape_all()
    else:
        parser.print_help()
