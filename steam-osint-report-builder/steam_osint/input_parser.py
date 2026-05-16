from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import SteamInputError

COMMUNITY_BASE = "https://steamcommunity.com"


def parse_subject_input(value: str) -> dict[str, str]:
    value = value.strip()
    if not value:
        raise SteamInputError("Enter a Steam profile URL, SteamID64, or vanity name.")

    if re.fullmatch(r"7656119\d{10}", value):
        return {"type": "steamid64", "value": value, "url": f"{COMMUNITY_BASE}/profiles/{value}"}

    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        parts = [p for p in parsed.path.split("/") if p]
        if "steamcommunity.com" not in parsed.netloc.lower():
            raise SteamInputError("URL must be from steamcommunity.com.")
        if len(parts) >= 2 and parts[0] == "profiles":
            steamid = parts[1]
            if not re.fullmatch(r"7656119\d{10}", steamid):
                raise SteamInputError("Invalid SteamID64 in /profiles/ URL.")
            return {"type": "steamid64", "value": steamid, "url": f"{COMMUNITY_BASE}/profiles/{steamid}"}
        if len(parts) >= 2 and parts[0] == "id":
            return {"type": "vanity", "value": parts[1], "url": f"{COMMUNITY_BASE}/id/{parts[1]}"}
        raise SteamInputError("Steam URL must be /profiles/SteamID64 or /id/VanityName.")

    if re.fullmatch(r"[A-Za-z0-9_-]{2,64}", value):
        return {"type": "vanity", "value": value, "url": f"{COMMUNITY_BASE}/id/{value}"}

    raise SteamInputError("Invalid Steam identifier.")
