from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .evidence import EvidenceStore
from .http_client import RequestManager
from .models import CollectionResult, SteamAPIError, SteamInputError, SteamReportError

API_BASE = "https://api.steampowered.com"


def optional_collect(result: CollectionResult, label: str, func):
    try:
        return func()
    except SteamReportError as exc:
        result.add_warning(f"{label}: {exc}")
        return None
    except Exception as exc:
        result.add_warning(f"{label}: unexpected parse failure: {exc}")
        return None


class PublicCollector:
    def __init__(self, http: RequestManager, evidence: EvidenceStore):
        self.http = http
        self.evidence = evidence

    def collect(self, target: str, profile_url: str, output_dir: Path) -> CollectionResult:
        result = CollectionResult(target=target, profile_url=profile_url, output_dir=output_dir)
        html = self.http.text(profile_url, "Public profile")
        self.evidence.save_text("public_profile.html", html, "Public profile", profile_url)
        result.profile = self._parse_profile(profile_url, html)
        result.steamid64 = result.profile.get("steamid64", "")
        result.aliases = self._discover_aliases(html)
        result.media = self._capture_media(html, profile_url, result)

        for attr, suffix, parser in [
            ("games", "/games/?tab=all", self._parse_games),
            ("friends", "/friends/", self._parse_friends),
            ("screenshots", "/screenshots/", self._parse_content_cards),
            ("reviews", "/recommended/", self._parse_content_cards),
            ("workshop_items", "/myworkshopfiles/", self._parse_content_cards),
            ("groups", "/groups/", self._parse_content_cards),
            ("badges", "/badges/", self._parse_content_cards),
        ]:
            page_url = profile_url.rstrip("/") + suffix
            data = optional_collect(result, attr, lambda u=page_url, a=attr, p=parser: self._collect_page(u, a, p))
            if data is not None:
                setattr(result, attr, data)

        result.timeline = build_timeline(result)
        result.evidence = list(self.evidence.records)
        return result

    def _collect_page(self, url: str, label: str, parser):
        html = self.http.text(url, f"Public {label} page")
        self.evidence.save_text(f"public_{label}.html", html, f"Public {label}", url)
        parsed = parser(url, html)
        self.evidence.save_json(f"parsed_{label}.json", parsed, f"Parsed {label}", url)
        return parsed

    def _parse_profile(self, profile_url: str, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find("title")
        persona = soup.select_one(".actual_persona_name")
        steamid = self._extract_steamid(html)
        privacy = bool(soup.find(string=re.compile("This profile is private", re.I)))
        profile = {
            "profile_url": profile_url,
            "steamid64": steamid or "",
            "title": title.get_text(strip=True) if title else "Unknown",
            "persona_name": persona.get_text(strip=True) if persona else "Unknown",
            "privacy_note": "Profile appears private." if privacy else "Public page loaded.",
            "public_links": {
                "games": profile_url.rstrip("/") + "/games/?tab=all",
                "friends": profile_url.rstrip("/") + "/friends/",
                "screenshots": profile_url.rstrip("/") + "/screenshots/",
                "reviews": profile_url.rstrip("/") + "/recommended/",
                "workshop": profile_url.rstrip("/") + "/myworkshopfiles/",
                "badges": profile_url.rstrip("/") + "/badges/",
                "groups": profile_url.rstrip("/") + "/groups/",
            },
        }
        self.evidence.save_json("public_profile_summary.json", profile, "Parsed public profile", profile_url)
        return profile

    @staticmethod
    def _extract_steamid(html: str) -> str:
        for pattern in [
            r'"steamid"\s*:\s*"(\d{17})"',
            r'g_rgProfileData\s*=\s*{[^}]*"steamid"\s*:\s*"(\d{17})"',
            r'steamid&quot;:&quot;(\d{17})',
        ]:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _discover_aliases(html: str) -> list[dict[str, str]]:
        aliases: list[dict[str, str]] = []
        seen: set[str] = set()
        for pattern in [r'"personaname"\s*:\s*"([^"]+)"', r"data-miniprofile=\"\d+\"[^>]*>([^<]+)<"]:
            for match in re.finditer(pattern, html):
                alias = BeautifulSoup(match.group(1), "html.parser").get_text(" ", strip=True)
                if alias and alias not in seen:
                    aliases.append({"alias": alias, "source": "public_profile_html"})
                    seen.add(alias)
        return aliases

    def _capture_media(self, html: str, profile_url: str, result: CollectionResult) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        media: dict[str, str] = {}
        candidates = {
            "avatar": soup.select_one(".playerAvatarAutoSizeInner img, .profile_header_size img, .playerAvatar img"),
            "background": soup.select_one(".profile_background_image_content, .no_header.profile_page"),
        }
        avatar_url = candidates["avatar"].get("src") if candidates["avatar"] else ""
        background_url = ""
        bg_el = candidates["background"]
        if bg_el and bg_el.get("style"):
            match = re.search(r"url\(['\"]?([^'\")]+)", bg_el.get("style", ""))
            background_url = match.group(1) if match else ""
        for name, url in {"avatar": avatar_url, "profile_background": background_url}.items():
            if not url:
                continue
            try:
                response = self.http.get(url, f"Download {name}")
                ext = Path(urlparse(url).path).suffix or ".jpg"
                record = self.evidence.save_bytes(f"{name}{ext}", response.content, name, url)
                media[name] = str(record.path)
                media[f"{name}_url"] = url
            except SteamReportError as exc:
                result.add_warning(f"{name} capture: {exc}")
        return media

    @staticmethod
    def _parse_games(url: str, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        private = bool(re.search(r"profile is private|games are private", soup.get_text("\n", strip=True), re.I))
        games: list[dict[str, Any]] = []
        seen: set[str] = set()
        for el in soup.select(".gameListRowItemName, .game_name"):
            name = el.get_text(" ", strip=True)
            if name and name not in seen:
                games.append({"name": name, "source_url": url})
                seen.add(name)
        return games or ([{"private_or_unavailable": True, "source_url": url}] if private else [])

    @staticmethod
    def _parse_friends(url: str, html: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        friends: list[dict[str, str]] = []
        seen: set[str] = set()
        for a in soup.select("a[href*='steamcommunity.com/id/'], a[href*='steamcommunity.com/profiles/']"):
            href = a.get("href", "")
            label = a.get_text(" ", strip=True)
            if href and href not in seen:
                friends.append({"name": label or href.rstrip('/').split('/')[-1], "url": href})
                seen.add(href)
        return friends

    @staticmethod
    def _parse_content_cards(url: str, html: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        selectors = "a[href*='/sharedfiles/filedetails/'], a[href*='/screenshots/'], a[href*='/recommended/'], .review_box a, .profile_group_links a, .badge_row a"
        for a in soup.select(selectors):
            href = a.get("href", "")
            title = a.get_text(" ", strip=True) or a.get("title", "")
            if href and href not in seen:
                items.append({"title": title[:200], "url": href, "source_url": url})
                seen.add(href)
        return items


class ApiCollector:
    def __init__(self, http: RequestManager, evidence: EvidenceStore, api_key: str):
        self.http = http
        self.evidence = evidence
        self.api_key = api_key

    def resolve_vanity(self, vanity: str) -> str:
        url = f"{API_BASE}/ISteamUser/ResolveVanityURL/v1/"
        data = self.http.json(url, "Resolve vanity", {"key": self.api_key, "vanityurl": vanity, "format": "json"})
        self.evidence.save_json("resolve_vanity.json", data, "Resolve vanity", url)
        response = data.get("response", {})
        if response.get("success") != 1:
            raise SteamInputError(f"Could not resolve vanity name '{vanity}'.")
        return response["steamid"]

    def collect(self, target: str, parsed: dict[str, str], output_dir: Path) -> CollectionResult:
        steamid = parsed["value"] if parsed["type"] == "steamid64" else self.resolve_vanity(parsed["value"])
        profile_url = f"https://steamcommunity.com/profiles/{steamid}"
        result = CollectionResult(target=target, profile_url=profile_url, steamid64=steamid, mode="API Mode", output_dir=output_dir)
        result.profile = self._profile(steamid)
        result.games = optional_collect(result, "owned games", lambda: self._owned_games(steamid)) or []
        result.recent_games = optional_collect(result, "recent games", lambda: self._recent_games(steamid)) or []
        result.friends = optional_collect(result, "friend list", lambda: self._friends(steamid)) or []
        result.aliases = [{"alias": result.profile.get("personaname", ""), "source": "api_player_summary"}] if result.profile.get("personaname") else []
        result.timeline = build_timeline(result)
        result.evidence = list(self.evidence.records)
        return result

    def _profile(self, steamid: str) -> dict[str, Any]:
        url = f"{API_BASE}/ISteamUser/GetPlayerSummaries/v2/"
        data = self.http.json(url, "Profile summary", {"key": self.api_key, "steamids": steamid, "format": "json"})
        self.evidence.save_json("api_player_summary.json", data, "API profile summary", url)
        players = data.get("response", {}).get("players", [])
        if not players:
            raise SteamAPIError("No profile returned.")
        return players[0]

    def _owned_games(self, steamid: str) -> list[dict[str, Any]]:
        url = f"{API_BASE}/IPlayerService/GetOwnedGames/v1/"
        data = self.http.json(url, "Owned games", {"key": self.api_key, "steamid": steamid, "include_appinfo": True, "include_played_free_games": True, "format": "json"})
        self.evidence.save_json("api_owned_games.json", data, "API owned games", url)
        return data.get("response", {}).get("games", [])

    def _recent_games(self, steamid: str) -> list[dict[str, Any]]:
        url = f"{API_BASE}/IPlayerService/GetRecentlyPlayedGames/v1/"
        data = self.http.json(url, "Recent games", {"key": self.api_key, "steamid": steamid, "format": "json"})
        self.evidence.save_json("api_recent_games.json", data, "API recent games", url)
        return data.get("response", {}).get("games", [])

    def _friends(self, steamid: str) -> list[dict[str, Any]]:
        url = f"{API_BASE}/ISteamUser/GetFriendList/v1/"
        data = self.http.json(url, "Friend list", {"key": self.api_key, "steamid": steamid, "relationship": "friend", "format": "json"})
        self.evidence.save_json("api_friend_list.json", data, "API friend list", url)
        return data.get("friendslist", {}).get("friends", [])


def build_timeline(result: CollectionResult) -> list[dict[str, str]]:
    timeline = [{"date": "collection", "event": f"Collected target {result.target} in {result.mode}"}]
    created = result.profile.get("timecreated")
    if created:
        timeline.append({"date": str(created), "event": "Account creation timestamp reported by Steam API"})
    for alias in result.aliases:
        timeline.append({"date": "collection", "event": f"Alias observed: {alias.get('alias')}"})
    for game in result.recent_games:
        timeline.append({"date": "recent", "event": f"Recently played: {game.get('name', game.get('appid', 'Unknown'))}"})
    return timeline
