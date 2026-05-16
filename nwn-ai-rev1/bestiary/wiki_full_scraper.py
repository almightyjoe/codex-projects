"""
Full Higher Grounds wiki scraper.
Enumerates ALL wiki pages and extracts:
  - Bestiary pages   → creatures table (AC, AB, Saves, SR, immunities, special abilities)
  - Area pages       → areas table (description, mob list, damage types, recommended protections)
  - Area guide pages → areas table with level/stat requirements, tactical notes, DC ranges

Run:
  python wiki_full_scraper.py --all          # full crawl (slow, polite)
  python wiki_full_scraper.py --bestiary     # bestiary pages only
  python wiki_full_scraper.py --areas        # area/zone pages only
  python wiki_full_scraper.py --guides       # area guide pages (Hells, Abyss, etc.)
  python wiki_full_scraper.py --page "Rona"  # one specific page
"""

import re, time, sqlite3, sys, os, argparse
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import BESTIARY_DB, WIKI_BASE, WIKI_REQUEST_DELAY

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'NWN-AI-Scraper/1.0 (personal; non-commercial)'

# ── Helpers ────────────────────────────────────────────────────────────────

def _get(path: str) -> BeautifulSoup | None:
    url = path if path.startswith('http') else f'{WIKI_BASE}/{path}'
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, 'lxml')
    except Exception as e:
        print(f'  WARN fetch {path}: {e}')
        return None

def _txt(el) -> str:
    return el.get_text(strip=True) if el else ''

_INT = re.compile(r'(-?\d+)')
_PCT = re.compile(r'(\d+)%')
_DR  = re.compile(r'(\d+)/-')

def _int(s): m = _INT.search(str(s)); return int(m.group(1)) if m else None
def _pct(s): m = _PCT.search(str(s)); return int(m.group(1)) if m else None
def _dr(s):  m = _DR.search(str(s));  return int(m.group(1)) if m else None

def _area_slug(page: str) -> str:
    return page.replace('Bestiary:_','').replace('Bestiary:','').replace('_',' ')

# ── Page enumeration ───────────────────────────────────────────────────────

def enumerate_bestiary_pages() -> list[str]:
    """Dynamically fetch all Bestiary: pages from Special:AllPages/Bestiary:."""
    soup = _get('Special:AllPages/Bestiary:')
    if not soup:
        return []
    pages = []
    for a in soup.find_all('a', href=lambda h: h and '/wiki/Bestiary:' in (h or '')):
        href = a['href']
        title = href.split('/wiki/', 1)[-1]
        if title and title not in pages:
            pages.append(title)
    print(f'  Enumerated {len(pages)} Bestiary pages from wiki')
    return pages


def enumerate_all_pages(conn) -> list[str]:
    """Walk Special:AllPages range links to collect all wiki page titles."""
    # First get range links from the index page
    soup = _get('Special:AllPages')
    if not soup:
        return []
    range_hrefs = []
    for a in soup.select('.allpageslist a'):
        href = a.get('href', '')
        if 'Special:AllPages' in href and href not in range_hrefs:
            range_hrefs.append(href)
    print(f'  Found {len(range_hrefs)} AllPages ranges')

    pages = []
    seen = set()
    for href in range_hrefs:
        url = WIKI_BASE + '/' + href.lstrip('/')
        rsoup = _get(url)
        if not rsoup:
            continue
        for a in rsoup.find_all('a', href=lambda h: h and '/wiki/' in (h or '') and 'Special:' not in (h or '') and 'action=' not in (h or '')):
            title = a['href'].split('/wiki/', 1)[-1]
            if title and title not in seen and not title.startswith('File:') and not title.startswith('Template:'):
                seen.add(title)
                pages.append(title)
        time.sleep(WIKI_REQUEST_DELAY)

    print(f'  Enumerated {len(pages)} total pages')
    return pages

# ── Stat parsing ───────────────────────────────────────────────────────────

_SAVES_RE = re.compile(r'(-?\d+)\s*/\s*(-?\d+)\s*/\s*(-?\d+)')

def _parse_saves(s: str):
    m = _SAVES_RE.search(s)
    if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
    nums = _INT.findall(s)
    if len(nums) >= 3: return int(nums[0]), int(nums[1]), int(nums[2])
    return None, None, None

_DMG_ABBREV = {
    'bbl':'bludgeoning','bbl':'bludgeoning','ppi':'piercing','ssl':'slashing',
    'aac':'acid','cco':'cold','eel':'electrical','ffi':'fire','sso':'sonic',
    'mma':'magical','ddi':'divine','nne':'negative','ppo':'positive',
    'pps':'psionic','ssc':'sacred','vvi':'vile','ppr':'primal',
    'aan':'anarchic','aax':'axiomatic','ssu':'subdual',
}

def _expand_abbrev(s: str) -> list[str]:
    """Convert 'BBl PPi FFi' damage abbrevs to full type names."""
    out = []
    for tok in re.findall(r'[A-Za-z]{3}', s):
        name = _DMG_ABBREV.get(tok.lower())
        if name:
            out.append(name)
    return out

# ── Table parser ───────────────────────────────────────────────────────────

def _parse_creature_table(table, area_name: str) -> list[dict]:
    headers = []
    creatures = []
    for row in table.find_all('tr'):
        cells = row.find_all(['th', 'td'])
        if not cells:
            continue
        texts = [_txt(c) for c in cells]
        if all(c.name == 'th' for c in cells) or (not headers and any(
                h in ' '.join(texts).lower() for h in ['name','ac','ab','sr','saves'])):
            headers = [t.lower().strip() for t in texts]
            continue
        if not headers or len(texts) < 2:
            continue

        entry = {'area': area_name}
        for i, h in enumerate(headers):
            if i >= len(texts):
                break
            v = texts[i].strip()
            if not v or v == '—' or v == '-':
                continue
            if 'name' in h:               entry['name'] = v
            elif h == 'race':             entry['race'] = v
            elif h in ('ac','armor'):     entry['ac'] = _int(v)
            elif h in ('ab','attack'):    entry['ab'] = _int(v)
            elif h == 'hp':               entry['hp'] = _int(v)
            elif h == 'sr':               entry['sr'] = _int(v)
            elif h == 'tr':               entry['tr'] = v
            elif h == 'sp':               entry['sp'] = _int(v)
            elif 'saves' in h or h in ('fort/ref/will','save'):
                f,r,w = _parse_saves(v)
                entry['saves_fort'] = f; entry['saves_ref'] = r; entry['saves_will'] = w
            elif 'fort' in h:             entry['saves_fort'] = _int(v)
            elif 'ref' in h:              entry['saves_ref']  = _int(v)
            elif 'will' in h:             entry['saves_will'] = _int(v)
            elif 'conceal' in h:          entry['concealment'] = _pct(v)
            elif h == 'kb':               entry['kb'] = v
            elif h in ('takes','vuln'):   entry['takes'] = v
            elif h == 'heals':            entry['heals'] = v
            elif h in ('deals','dmg'):    entry['deals'] = v
            elif 'spell imm' in h:        entry['spell_immunities'] = v
            elif 'misc imm' in h or ('imm' in h and 'spell' not in h):
                entry['other_immunities'] = v
            elif 'special' in h:          entry['special_abilities'] = v
            elif 'note' in h or 'strat' in h: entry['notes'] = v

        if entry.get('name') and entry['name'].lower() not in ('name','example','creature'):
            creatures.append(entry)
    return creatures


def _parse_inline_creatures(soup, area_name: str) -> list[dict]:
    """
    Extract creatures from definition-list or heading+paragraph style pages
    where each mob is a heading with stats in adjacent text (not table rows).
    """
    creatures = []
    for h in soup.find_all(['h2','h3','h4']):
        name = _txt(h).strip()
        if not name or len(name) > 60 or name.lower() in ('contents','navigation','external links','references'):
            continue
        entry = {'name': name, 'area': area_name}
        # collect text from the next few siblings until next heading
        block = []
        for sib in h.find_next_siblings():
            if sib.name in ('h2','h3','h4'):
                break
            block.append(_txt(sib))
        text = ' '.join(block)

        # try to extract known stat patterns from free text
        m = re.search(r'AC[:\s]+(\d+)', text, re.I);        entry['ac'] = int(m.group(1)) if m else None
        m = re.search(r'AB[:\s]+(\d+)', text, re.I);        entry['ab'] = int(m.group(1)) if m else None
        m = re.search(r'HP[:\s]+(\d+)', text, re.I);        entry['hp'] = int(m.group(1)) if m else None
        m = re.search(r'SR[:\s]+(\d+)', text, re.I);        entry['sr'] = int(m.group(1)) if m else None
        m = re.search(r'Fort[a-z]*/Ref[a-z]*/Will[a-z]*[:\s]+(-?\d+)\s*/\s*(-?\d+)\s*/\s*(-?\d+)', text, re.I)
        if m: entry['saves_fort'] = int(m.group(1)); entry['saves_ref'] = int(m.group(2)); entry['saves_will'] = int(m.group(3))
        m = re.search(r'Conceal(?:ment)?[:\s]+(\d+)%', text, re.I); entry['concealment'] = int(m.group(1)) if m else None

        # special abilities with DC values
        specials = re.findall(r'([A-Za-z ]{3,40})[:\s]+DC\s*(\d+)', text)
        if specials:
            entry['special_abilities'] = '; '.join(f'{s} DC {d}' for s,d in specials)

        if text:
            entry['notes'] = text[:400]

        if entry.get('ac') or entry.get('sr') or entry.get('special_abilities'):
            creatures.append(entry)

    return creatures

# ── Area guide pages (not Bestiary pages — these have tactical/stat data) ──

AREA_GUIDE_PAGES = [
    'Hells', 'Abyss', 'Limbo', 'Elysium',
    'Maze_of_the_Ancients', 'Rona', 'Aboleths', 'Penumbra',
    'Hive', 'Black_Pyramid', 'Desert_of_Vashyk',
    'Locathah_Depths', 'Pit_of_Moliation', "Zorbgot%27s_Hive",
    'Feywild', 'Sigil', 'Mechanus', 'Gehenna', 'Baator',
    'Carceri', 'Pandemonium', 'Arborea', 'Beastlands',
    'Mount_Celestia', 'Bytopia', 'Arcadia', 'Outlands',
]

_DMG_KEYWORDS = [
    'fire','cold','acid','electrical','sonic','divine','negative',
    'magical','positive','psionic','vile','sacred','bludgeoning',
    'piercing','slashing','primal','anarchic','axiomatic',
]


def _build_sections(soup) -> dict[str, str]:
    """
    Walk the bodyContent div collecting heading→text pairs.
    Returns {heading_text: paragraph_text} for all headings found.
    """
    content = soup.find('div', id='bodyContent') or soup
    sections = {}
    current = 'intro'
    buf = []

    for tag in content.find_all(['h2','h3','h4','p','ul','ol','li']):
        if tag.name in ('h2','h3','h4'):
            if buf:
                sections[current] = sections.get(current, '') + ' ' + ' '.join(buf)
            current = _txt(tag).strip()
            buf = []
        else:
            t = _txt(tag).strip()
            if t:
                buf.append(t)

    if buf:
        sections[current] = sections.get(current, '') + ' ' + ' '.join(buf)

    return {k.lower(): v.strip() for k, v in sections.items() if k}


def _sec(sections: dict, *keys) -> str:
    """Return first section text that matches any of the given key substrings."""
    for key in keys:
        for k, v in sections.items():
            if key.lower() in k:
                return v
    return ''


def _parse_area_guide_page(soup, page_title: str) -> dict:
    """
    Extract structured tactical data from an area guide page (/wiki/Hells etc.).
    Returns a dict suitable for upsert into the areas table.
    """
    sections = _build_sections(soup)
    area = {}

    # ── Level range ────────────────────────────────────────────────────────
    level_txt = _sec(sections, 'level')
    m = re.search(r'level\s+(\d+)\s*[-–to]+\s*(\d+)', level_txt, re.I)
    if m:
        area['level_min'] = int(m.group(1))
        area['level_max'] = int(m.group(2))
    else:
        m = re.search(r'level\s+(\d+)', level_txt, re.I)
        if m:
            area['level_min'] = int(m.group(1))

    # ── Save DCs ──────────────────────────────────────────────────────────
    saves_txt = _sec(sections, 'saves', 'save')
    dc_nums = [int(x) for x in re.findall(r'DC\s*(\d+)', saves_txt, re.I)]
    if dc_nums:
        area['area_dc_min'] = min(dc_nums)
        area['area_dc_max'] = max(dc_nums)
    # What saves does the player need?
    m = re.search(r'saves?\s+(?:of\s+)?(\d+)\+', saves_txt, re.I)
    if not m:
        m = re.search(r'(\d{2,3})\+?\s+(?:for\s+all|across\s+all)', saves_txt, re.I)
    if not m:
        m = re.search(r'(?:ideally|aim\s+for|need|require)[^.]*?(\d{2,3})', saves_txt, re.I)
    if m:
        area['required_saves'] = int(m.group(1))

    # ── Attack Bonus (player needs to hit enemy AC) ───────────────────────
    ab_txt = _sec(sections, 'attack bonus', 'attack_bonus')
    m = re.search(r'AC\s+(?:in\s+the\s+)?(\d+)\s*[-–]\s*(\d+)', ab_txt, re.I)
    if m:
        area['enemy_ac_min'] = int(m.group(1))
        area['enemy_ac_max'] = int(m.group(2))
    m = re.search(r'(?:above|over|need|require)[^.]{0,30}?\+?(\d{2,3})', ab_txt, re.I)
    if m:
        area['required_ab'] = int(m.group(1))

    # ── Armor Class (player needs to survive enemy AB) ────────────────────
    ac_txt = _sec(sections, 'armor class', 'armour class')
    m = re.search(r'AB\s+(?:between\s+)?(\d+)\s+(?:and|[-–])\s+(\d+)', ac_txt, re.I)
    if m:
        area['enemy_ab_min'] = int(m.group(1))
        area['enemy_ab_max'] = int(m.group(2))
    m = re.search(r'(?:above|over|recommended|value\s+of|aim\s+for|a\s+value)[^.]{0,20}?(\d{2,3})', ac_txt, re.I)
    if m:
        area['required_ac'] = int(m.group(1))

    # ── Hit Points ────────────────────────────────────────────────────────
    hp_txt = _sec(sections, 'hit points', 'hp')
    m = re.search(r'(\d{3})\s*[-–]\s*(\d{3})', hp_txt)
    if m:
        area['required_hp'] = int(m.group(1))

    # ── Prevalent damage types ────────────────────────────────────────────
    full_text = ' '.join(sections.values()).lower()
    mentioned = [t for t in _DMG_KEYWORDS if t in full_text]
    area['prevalent_damage_types'] = ', '.join(mentioned) if mentioned else ''

    # ── Recommended weapon damage types (extract from weapon advice) ──────
    best_matches = re.findall(
        r'(?:best|good|recommend|consider|use|acid|cold|sonic|divine|positive|negative)'
        r'[^.]{0,120}?'
        r'((?:acid|cold|sonic|divine|positive|negative|fire|electrical|magical)[^.]{0,60})',
        full_text
    )
    if best_matches:
        area['recommended_protections'] = best_matches[0][:200].strip()

    # ── Tactical notes: concatenate key sections ──────────────────────────
    note_sections = [
        ('Level',          _sec(sections, 'level')),
        ('Saves',          _sec(sections, 'saves', 'save')),
        ('Attack Bonus',   _sec(sections, 'attack bonus')),
        ('Armor Class',    _sec(sections, 'armor class', 'armour class')),
        ('Checks',         _sec(sections, 'checks', 'check')),
        ('Spawn',          _sec(sections, 'spawn')),
        ('Boss Fights',    _sec(sections, 'boss')),
        ('Penalties',      _sec(sections, 'penalt')),
        ('Intro',          _sec(sections, 'intro')),
    ]
    parts = [f'[{label}] {txt[:400]}' for label, txt in note_sections if txt.strip()]
    area['tactical_notes'] = '\n'.join(parts)[:3000]

    # ── Short notes for area record ────────────────────────────────────────
    intro = _sec(sections, 'intro') or _sec(sections, 'entering', 'introduction')
    area['notes'] = intro[:500] if intro else full_text[:500]

    return area


def _parse_area_page(soup, page_title: str) -> dict:
    """Extract basic area info from a non-guide wiki page (fallback)."""
    text = soup.get_text(' ', strip=True)
    dmg_types = ['fire','cold','acid','electrical','sonic','divine','negative','magical','positive','psionic','vile','sacred']
    mentioned = [t for t in dmg_types if t in text.lower()]
    prot_matches = re.findall(
        r'(?:protect|resist|immune|immunity)[^.]{0,60}?(fire|cold|acid|electrical|sonic|divine|negative|magical)',
        text, re.I
    )
    body = soup.find('div', class_=re.compile(r'mw-parser-output'))
    return {
        'prevalent_damage_types':  ', '.join(mentioned),
        'recommended_protections': ', '.join(set(m[-1] for m in prot_matches)),
        'notes': (body or soup).get_text(' ', strip=True)[:500],
    }

# ── Upsert helpers ─────────────────────────────────────────────────────────

def _upsert_creature(conn, c: dict):
    name = (c.get('name') or '').strip()
    if not name:
        return
    conn.execute('''
        INSERT INTO creatures (name,race,ac,ab,hp,sr,tr,
            saves_fort,saves_ref,saves_will,concealment,
            kb,takes,heals,deals,
            spell_immunities,other_immunities,special_abilities,
            areas,notes,source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'wiki')
        ON CONFLICT(name) DO UPDATE SET
            race=COALESCE(NULLIF(excluded.race,''), race),
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
            areas=CASE
                WHEN areas IS NULL OR areas='' THEN excluded.areas
                WHEN excluded.areas IS NULL OR excluded.areas='' THEN areas
                WHEN instr(areas,excluded.areas)>0 THEN areas
                ELSE areas||', '||excluded.areas END,
            notes=COALESCE(NULLIF(excluded.notes,''), notes),
            source='wiki'
    ''', (
        name,
        c.get('race',''), c.get('ac'), c.get('ab'), c.get('hp'),
        c.get('sr'), c.get('tr',''),
        c.get('saves_fort'), c.get('saves_ref'), c.get('saves_will'),
        c.get('concealment'), c.get('kb',''),
        c.get('takes',''), c.get('heals',''), c.get('deals',''),
        c.get('spell_immunities',''), c.get('other_immunities',''),
        c.get('special_abilities',''),
        c.get('area',''), c.get('notes',''),
    ))


def _link_creature_area(conn, creature_name: str, area_name: str):
    cid = conn.execute('SELECT id FROM creatures WHERE name=?', (creature_name,)).fetchone()
    aid = conn.execute('SELECT id FROM areas WHERE name=?', (area_name,)).fetchone()
    if cid and aid:
        conn.execute('INSERT OR IGNORE INTO creature_areas VALUES (?,?)', (cid[0], aid[0]))


def _upsert_area(conn, name: str, data: dict, wiki_url: str):
    conn.execute('''
        INSERT INTO areas (
            name, prevalent_damage_types, recommended_protections, notes, wiki_url,
            level_min, level_max, required_ab, required_ac, required_saves, required_hp,
            area_dc_min, area_dc_max, enemy_ab_min, enemy_ab_max, enemy_ac_min, enemy_ac_max,
            tactical_notes
        )
        VALUES (?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?,?, ?)
        ON CONFLICT(name) DO UPDATE SET
            prevalent_damage_types  = COALESCE(NULLIF(excluded.prevalent_damage_types,''),  prevalent_damage_types),
            recommended_protections = COALESCE(NULLIF(excluded.recommended_protections,''), recommended_protections),
            notes                   = COALESCE(NULLIF(excluded.notes,''),                   notes),
            wiki_url                = COALESCE(NULLIF(excluded.wiki_url,''),                wiki_url),
            level_min               = COALESCE(excluded.level_min,    level_min),
            level_max               = COALESCE(excluded.level_max,    level_max),
            required_ab             = COALESCE(excluded.required_ab,  required_ab),
            required_ac             = COALESCE(excluded.required_ac,  required_ac),
            required_saves          = COALESCE(excluded.required_saves,required_saves),
            required_hp             = COALESCE(excluded.required_hp,  required_hp),
            area_dc_min             = COALESCE(excluded.area_dc_min,  area_dc_min),
            area_dc_max             = COALESCE(excluded.area_dc_max,  area_dc_max),
            enemy_ab_min            = COALESCE(excluded.enemy_ab_min, enemy_ab_min),
            enemy_ab_max            = COALESCE(excluded.enemy_ab_max, enemy_ab_max),
            enemy_ac_min            = COALESCE(excluded.enemy_ac_min, enemy_ac_min),
            enemy_ac_max            = COALESCE(excluded.enemy_ac_max, enemy_ac_max),
            tactical_notes          = COALESCE(NULLIF(excluded.tactical_notes,''), tactical_notes)
    ''', (
        name,
        data.get('prevalent_damage_types',''), data.get('recommended_protections',''),
        data.get('notes',''), wiki_url,
        data.get('level_min'), data.get('level_max'),
        data.get('required_ab'), data.get('required_ac'),
        data.get('required_saves'), data.get('required_hp'),
        data.get('area_dc_min'), data.get('area_dc_max'),
        data.get('enemy_ab_min'), data.get('enemy_ab_max'),
        data.get('enemy_ac_min'), data.get('enemy_ac_max'),
        data.get('tactical_notes',''),
    ))

# ── Page scraper ───────────────────────────────────────────────────────────

def scrape_page(page: str, conn: sqlite3.Connection) -> int:
    page_clean = page.replace('_', ' ')
    url = f'{WIKI_BASE}/{page}'
    soup = _get(page)
    if not soup:
        return 0

    is_bestiary = page.startswith('Bestiary:') or page.startswith('Bestiary_')
    area_name   = _area_slug(page) if is_bestiary else page_clean

    # Ensure area record exists
    _upsert_area(conn, area_name, _parse_area_page(soup, page_clean), url)
    conn.commit()

    total = 0
    tables = soup.find_all('table', class_=re.compile(r'wikitable|sortable', re.I))
    if not tables:
        tables = soup.find_all('table')

    for tbl in tables:
        creatures = _parse_creature_table(tbl, area_name)
        for c in creatures:
            _upsert_creature(conn, c)
            _link_creature_area(conn, c['name'], area_name)
            total += 1

    # fallback: inline heading-style creatures (for pages without proper tables)
    if total == 0 and is_bestiary:
        creatures = _parse_inline_creatures(soup, area_name)
        for c in creatures:
            _upsert_creature(conn, c)
            _link_creature_area(conn, c['name'], area_name)
            total += 1

    conn.commit()
    print(f'  [{area_name}] {total} creatures')
    return total


def scrape_guide_page(page: str, conn: sqlite3.Connection) -> dict:
    """
    Scrape a single area guide page (/wiki/PAGE) and upsert tactical data
    into the areas table.  Also extracts any creature tables found.
    Returns the parsed area dict.
    """
    page_clean = page.replace('_', ' ').replace('%27', "'")
    url = f'{WIKI_BASE}/{page}'
    soup = _get(page)
    if not soup:
        return {}

    data = _parse_area_guide_page(soup, page_clean)
    _upsert_area(conn, page_clean, data, url)
    conn.commit()

    # Also extract any creature stat tables embedded in the guide page
    creature_count = 0
    tables = soup.find_all('table', class_=re.compile(r'wikitable|sortable', re.I))
    if not tables:
        tables = soup.find_all('table')
    for tbl in tables:
        for c in _parse_creature_table(tbl, page_clean):
            _upsert_creature(conn, c)
            _link_creature_area(conn, c['name'], page_clean)
            creature_count += 1
    conn.commit()

    # Summary line
    stats = []
    if data.get('level_min'):
        stats.append(f"lvl {data.get('level_min')}-{data.get('level_max','?')}")
    if data.get('required_ac'):
        stats.append(f"need AC {data['required_ac']}")
    if data.get('required_ab'):
        stats.append(f"need AB {data['required_ab']}")
    if data.get('area_dc_max'):
        stats.append(f"DC {data.get('area_dc_min',0)}-{data['area_dc_max']}")
    print(f'  [{page_clean}] {", ".join(stats) or "parsed"} | {creature_count} creatures')
    return data


def run_guides(pages: list[str]):
    conn = sqlite3.connect(BESTIARY_DB)
    conn.execute('PRAGMA journal_mode=WAL')
    for i, page in enumerate(pages, 1):
        print(f'[{i}/{len(pages)}] {page}')
        scrape_guide_page(page, conn)
        time.sleep(WIKI_REQUEST_DELAY)
    conn.close()
    print(f'\nGuide scrape complete for {len(pages)} pages.')


# ── Entry point ────────────────────────────────────────────────────────────

def run(pages: list[str]):
    conn = sqlite3.connect(BESTIARY_DB)
    conn.execute('PRAGMA journal_mode=WAL')
    grand = 0
    for i, page in enumerate(pages, 1):
        print(f'[{i}/{len(pages)}] {page}')
        grand += scrape_page(page, conn)
        time.sleep(WIKI_REQUEST_DELAY)
    conn.close()
    print(f'\nComplete. {grand} creature entries scraped/updated.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--all',      action='store_true', help='Scrape all wiki pages')
    ap.add_argument('--bestiary', action='store_true', help='Scrape bestiary pages only')
    ap.add_argument('--areas',    action='store_true', help='Scrape area/zone pages only')
    ap.add_argument('--guides',   action='store_true', help='Scrape area guide pages (Hells, Abyss, etc.)')
    ap.add_argument('--page',     type=str,            help='Scrape one specific page title')
    args = ap.parse_args()

    if args.page:
        conn = sqlite3.connect(BESTIARY_DB)
        conn.execute('PRAGMA journal_mode=WAL')
        page = args.page.replace(' ', '_')
        if page in [p.replace(' ','_') for p in AREA_GUIDE_PAGES] or not page.startswith('Bestiary'):
            scrape_guide_page(page, conn)
        scrape_page(page, conn)
        conn.close()
    elif args.guides:
        run_guides(AREA_GUIDE_PAGES)
    elif args.bestiary:
        run(enumerate_bestiary_pages())
    elif args.all or args.areas:
        conn = sqlite3.connect(BESTIARY_DB)
        all_pages = enumerate_all_pages(conn)
        conn.close()
        if args.bestiary:
            all_pages = [p for p in all_pages if 'Bestiary' in p]
        elif args.areas:
            all_pages = [p for p in all_pages if 'Bestiary' not in p]
        run(all_pages)
    else:
        ap.print_help()
