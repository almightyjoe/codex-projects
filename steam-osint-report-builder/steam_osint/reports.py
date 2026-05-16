from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from .models import CollectionResult


def minutes_to_hours(value: Any) -> float:
    try:
        return round(int(value) / 60, 1)
    except Exception:
        return 0.0


def unix_to_date(value: Any) -> str:
    if not value:
        return "Not public"
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def write_reports(result: CollectionResult) -> tuple[Path, Path]:
    md = build_markdown(result)
    html = build_html(result)
    md_path = result.output_dir / "report.md"
    html_path = result.output_dir / "report.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return md_path, html_path


def build_markdown(result: CollectionResult) -> str:
    profile_name = result.profile.get("personaname") or result.profile.get("persona_name") or "Unknown"
    lines = [
        "# Steam OSINT Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Mode: {result.mode}",
        f"Subject URL: {result.profile_url}",
        f"SteamID64: {result.steamid64 or 'Unknown'}",
        f"Persona name: {profile_name}",
        "",
        "## Profile",
        f"- Visibility: {result.profile.get('communityvisibilitystate', result.profile.get('privacy_note', 'Unknown'))}",
        f"- Created: {unix_to_date(result.profile.get('timecreated'))}",
        "",
        "## Games",
        f"Visible games collected: {len(result.games)}",
    ]
    for game in result.games[:100]:
        label = game.get("name") or game.get("appid") or "Unknown"
        hours = minutes_to_hours(game.get("playtime_forever", 0))
        lines.append(f"- {label} ({hours} hours)")
    lines += ["", "## Friends", f"Visible friends collected: {len(result.friends)}"]
    for friend in result.friends[:100]:
        lines.append(f"- {friend.get('name') or friend.get('steamid') or 'Friend'} {friend.get('url', '')}")
    lines += ["", "## Public Content", f"- Screenshots: {len(result.screenshots)}", f"- Reviews: {len(result.reviews)}", f"- Workshop items: {len(result.workshop_items)}", f"- Groups: {len(result.groups)}", f"- Badges: {len(result.badges)}"]
    lines += ["", "## Aliases"]
    if result.aliases:
        lines.extend(f"- {a.get('alias')} ({a.get('source')})" for a in result.aliases)
    else:
        lines.append("- None discovered.")
    lines += ["", "## Timeline"]
    lines.extend(f"- {t.get('date')}: {t.get('event')}" for t in result.timeline)
    lines += ["", "## Evidence"]
    for record in result.evidence:
        lines.append(f"- {record.label}: `{record.path}` SHA256 `{record.sha256}`")
    if result.warnings:
        lines += ["", "## Warnings"]
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines += ["", "## Boundary Notes", "- Public mode uses accessible steamcommunity.com pages only.", "- API mode uses official Steam Web API endpoints.", "- Private or unavailable data is not bypassed."]
    return "\n".join(lines)


def build_html(result: CollectionResult) -> str:
    profile_name = result.profile.get("personaname") or result.profile.get("persona_name") or "Unknown"
    avatar = result.media.get("avatar", "")
    graph = result.media.get("friend_graph", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Steam OSINT Report - {escape(profile_name)}</title>
<style>
:root {{ color-scheme: light dark; --bg:#f6f8fa; --fg:#1f2328; --muted:#656d76; --panel:#ffffff; --line:#d0d7de; --accent:#0969da; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#8b949e; --panel:#161b22; --line:#30363d; --accent:#58a6ff; }} }}
body {{ margin:0; font:14px/1.5 Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--fg); }}
main {{ max-width:1180px; margin:auto; padding:24px; }}
header {{ display:flex; gap:16px; align-items:center; border-bottom:1px solid var(--line); padding-bottom:16px; }}
header img {{ width:96px; height:96px; object-fit:cover; border-radius:8px; }}
a {{ color:var(--accent); }}
section {{ margin:22px 0; }}
table {{ width:100%; border-collapse:collapse; background:var(--panel); }}
th,td {{ border:1px solid var(--line); padding:8px; text-align:left; vertical-align:top; }}
th {{ color:var(--muted); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
.metric {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; }}
.muted {{ color:var(--muted); }}
.graph {{ max-width:100%; border:1px solid var(--line); border-radius:8px; }}
</style>
</head>
<body><main>
<header>{f'<img src="{escape(avatar)}" alt="Profile avatar">' if avatar else ''}
<div><h1>{escape(profile_name)}</h1><div><a href="{escape(result.profile_url)}">{escape(result.profile_url)}</a></div><div class="muted">Generated UTC {datetime.now(timezone.utc).isoformat(timespec='seconds')} | {escape(result.mode)}</div></div></header>
<section class="grid"><div class="metric"><b>SteamID64</b><br>{escape(result.steamid64 or 'Unknown')}</div><div class="metric"><b>Games</b><br>{len(result.games)}</div><div class="metric"><b>Friends</b><br>{len(result.friends)}</div><div class="metric"><b>Evidence files</b><br>{len(result.evidence)}</div></section>
{table_section('Games', result.games, ['name','appid','playtime_forever','source_url'])}
{table_section('Friends', result.friends, ['name','steamid','url'])}
{table_section('Screenshots', result.screenshots, ['title','url','source_url'])}
{table_section('Reviews', result.reviews, ['title','url','source_url'])}
{table_section('Workshop Items', result.workshop_items, ['title','url','source_url'])}
<section><h2>Friend Graph</h2>{f'<img class="graph" src="{escape(graph)}" alt="Friend graph">' if graph else '<p class="muted">No graph was generated.</p>'}</section>
{table_section('Aliases', result.aliases, ['alias','source'])}
{table_section('Timeline', result.timeline, ['date','event'])}
{table_section('Evidence Manifest', [evidence_record_to_dict(r) for r in result.evidence], ['label','kind','path','url','sha256','collected_at'])}
{warnings_section(result.warnings)}
</main></body></html>"""


def table_section(title: str, rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return f"<section><h2>{escape(title)}</h2><p class=\"muted\">No public records collected.</p></section>"
    head = "".join(f"<th>{escape(c.replace('_', ' ').title())}</th>" for c in columns)
    body = []
    for row in rows[:200]:
        cells = []
        for col in columns:
            value = str(row.get(col, ""))
            if value.startswith("http"):
                value = f'<a href="{escape(value)}">{escape(value)}</a>'
            else:
                value = escape(value)
            cells.append(f"<td>{value}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<section><h2>{escape(title)}</h2><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></section>"


def warnings_section(warnings: list[str]) -> str:
    if not warnings:
        return ""
    return "<section><h2>Warnings</h2><ul>" + "".join(f"<li>{escape(w)}</li>" for w in warnings) + "</ul></section>"


def evidence_record_to_dict(record: Any) -> dict[str, str]:
    return {
        "label": str(record.label),
        "kind": str(record.kind),
        "path": str(record.path),
        "url": str(record.url),
        "sha256": str(record.sha256),
        "collected_at": str(record.collected_at),
    }
