import os

# --- Paths ---
NWN_LOG_DIR        = r"D:\nwn\logs"
NWN_LOG_FILES      = ["nwclientLog1.txt", "nwclientLog2.txt",
                      "nwclientLog3.txt", "nwclientLog4.txt"]
CREATURES_JSON     = r"D:\1ClaudeCode\working scripts\creatures_data.json"
HGX_DIR            = r"D:\nwn\hgxle"

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
DATA_DIR           = os.path.join(BASE_DIR, "data")
COMBAT_DB          = os.path.join(DATA_DIR, "combat.db")
BESTIARY_DB        = os.path.join(DATA_DIR, "bestiary.db")

# --- Web Server ---
WEB_HOST           = "127.0.0.1"
WEB_PORT           = 5000

# --- Ollama ---
OLLAMA_URL         = "http://localhost:11434/api/generate"
OLLAMA_MODEL       = "mistral:7b"
OLLAMA_TIMEOUT     = 60

# --- Parser ---
LOG_POLL_INTERVAL  = 0.1   # seconds between log tail checks
DB_FLUSH_INTERVAL  = 0.5   # seconds between queue → SQLite flushes
MAX_QUEUE_SIZE     = 5000

# --- Known player characters (auto-detected + manual override) ---
# Add your character names here; parser also auto-detects from kill/resurrect events
PLAYER_CHARACTERS  = [
    "Lyra", ".SilverTiger", "RoseBud", "Rosie rezzer for silly rose",
    "dopplegang", "almightyjoe", "gator", "kensei", "joecool",
    "Ayla", "amber", "BlackCat", "SherlockHolmes", "RedBear",
    "KITTYS", "dopplesdaughter", "Darksky", "LadyWarrior11",
    "Sugarbelle", "blackwolf",
]

# --- Wiki ---
WIKI_BASE          = "https://wiki.hgweb.org/wiki"
WIKI_BESTIARY_ROOT = f"{WIKI_BASE}/Special:AllPages?from=Bestiary"
WIKI_REQUEST_DELAY = 1.0   # polite delay between wiki requests (seconds)
