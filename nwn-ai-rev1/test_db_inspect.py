import sqlite3, json

conn = sqlite3.connect("D:/nwn/hgxle/higher_grounds.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables:", tables)
for t in tables:
    cur.execute("SELECT COUNT(*) FROM " + t[0])
    print("  " + t[0] + ": " + str(cur.fetchone()[0]) + " rows")
conn.close()

with open("D:/1ClaudeCode/working scripts/creatures_data.json") as f:
    d = json.load(f)
creatures = d["creatures"]
print("creatures_data.json: " + str(len(creatures)) + " creatures")
for c in creatures:
    vals = [v for k,v in c.items() if k not in ("Name","Race","Type","SpellImmunities","OtherImmunities")]
    if any(v not in (0.0, 0, "") for v in vals):
        print("Sample with data:", json.dumps(c)[:800])
        break

# Show a creature with immunities
for c in creatures:
    if c.get("SpellImmunities") or c.get("OtherImmunities"):
        print("Sample with immunities:", json.dumps(c)[:800])
        break
