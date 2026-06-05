"""Fetch recent episodes from a YouTube playlist using yt-dlp."""
import json
import subprocess
from datetime import date, datetime
from zoneinfo import ZoneInfo

IL_TZ = ZoneInfo("Asia/Jerusalem")


def fetch_new_episodes(playlist_url: str, since: datetime) -> list[dict]:
    """
    Return videos published on or after `since.date()`.

    Uses --dump-json (full metadata per video) which reliably includes upload_date.
    Limited to the last 15 entries so it stays fast enough for daily use.
    """
    url = _clean_url(playlist_url)
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--playlist-end", "15",
        "--no-warnings",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        print(f"[youtube] timeout: {url}")
        return []

    episodes = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            info = json.loads(line)
        except json.JSONDecodeError:
            continue

        pub_date = _parse_date(info)
        if pub_date is None:
            continue

        # Skip YouTube Shorts (< 2 min)
        if (info.get("duration") or 999) < 120:
            continue

        if pub_date >= since.date():
            episodes.append({
                "video_id": info.get("id"),
                "title": info.get("title"),
                "publish_date": pub_date,
                "url": f"https://youtu.be/{info.get('id')}",
            })

    return episodes


def fetch_latest_episode(playlist_url: str) -> dict | None:
    """Return the single most recent episode from a playlist."""
    url = _clean_url(playlist_url)
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--playlist-end", "1",
        "--no-warnings",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        return None

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            info = json.loads(line)
        except json.JSONDecodeError:
            continue
        return {
            "video_id": info.get("id"),
            "title": info.get("title"),
            "publish_date": _parse_date(info),
            "url": f"https://youtu.be/{info.get('id')}",
        }
    return None


def _parse_date(info: dict) -> date | None:
    """Extract publish date from video metadata, trying multiple fields."""
    # upload_date is YYYYMMDD string
    raw = info.get("upload_date") or info.get("release_date")
    if raw:
        try:
            return datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            pass

    # Fall back to unix timestamp
    ts = info.get("timestamp") or info.get("release_timestamp")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts), tz=IL_TZ).date()
        except (ValueError, OSError):
            pass

    return None


def _clean_url(url: str) -> str:
    """Normalise to playlist URL, strip tracking params."""
    import re
    m = re.search(r"[?&]list=([\w-]+)", url)
    if m:
        return f"https://www.youtube.com/playlist?list={m.group(1)}"
    return url.split("&pp=")[0]


def format_date_he(d: date | None) -> str:
    if d is None:
        return ""
    months = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
               "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
    return f"{d.day} {months[d.month - 1]}"
