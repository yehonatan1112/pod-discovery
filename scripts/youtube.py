"""
Fetch recent episodes via YouTube RSS feed (no auth, no bot detection).
Downloads still use yt-dlp (see archive.py).
"""
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

IL_TZ = ZoneInfo("Asia/Jerusalem")

_NS = {
    "atom":  "http://www.w3.org/2005/Atom",
    "yt":    "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
_RSS_BASE = "https://www.youtube.com/feeds/videos.xml"
_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0"


def _playlist_id(url: str) -> str | None:
    m = re.search(r"[?&]list=([\w-]+)", url)
    return m.group(1) if m else None


def _rss_entries(playlist_url: str) -> list[dict]:
    pid = _playlist_id(playlist_url)
    if not pid:
        print(f"[youtube] cannot extract playlist ID from {playlist_url}")
        return []

    rss_url = f"{_RSS_BASE}?playlist_id={pid}"
    try:
        resp = _SESSION.get(rss_url, timeout=20)
    except requests.RequestException as e:
        print(f"[youtube] RSS request failed for {pid}: {e}")
        return []

    if resp.status_code != 200:
        print(f"[youtube] RSS {resp.status_code} for {pid}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"[youtube] RSS parse error for {pid}: {e}")
        return []

    entries = []
    for entry in root.findall("atom:entry", _NS):
        video_id  = entry.findtext("yt:videoId",  namespaces=_NS)
        title     = entry.findtext("atom:title",   namespaces=_NS)
        published = entry.findtext("atom:published", namespaces=_NS)

        if not video_id or not published:
            continue

        try:
            pub_date = datetime.fromisoformat(published).date()
        except ValueError:
            continue

        entries.append({
            "video_id":    video_id,
            "title":       title or video_id,
            "publish_date": pub_date,
            "url":         f"https://youtu.be/{video_id}",
        })

    return entries   # RSS returns newest-first


def fetch_new_episodes(playlist_url: str, since: datetime) -> list[dict]:
    """Return episodes published on or after since.date()."""
    entries = _rss_entries(playlist_url)
    pid = _playlist_id(playlist_url)
    print(f"[youtube] {pid}: {len(entries)} entries from RSS, window_since={since.date()}")
    for e in entries:
        print(f"[youtube]   {e['publish_date']}  {e['title'][:60]}")

    result = [e for e in entries if e["publish_date"] >= since.date()]
    print(f"[youtube]   → {len(result)} in window")
    return result


def fetch_latest_episode(playlist_url: str) -> dict | None:
    """Return the most recent episode."""
    entries = _rss_entries(playlist_url)
    return entries[0] if entries else None


def format_date_he(d: date | None) -> str:
    if d is None:
        return ""
    months = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
               "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
    return f"{d.day} {months[d.month - 1]}"
