"""Fetch recent episodes from a YouTube playlist using yt-dlp."""
import subprocess
from datetime import date, datetime
from zoneinfo import ZoneInfo

IL_TZ = ZoneInfo("Asia/Jerusalem")


def fetch_new_episodes(playlist_url: str, since: datetime) -> list[dict]:
    """
    Return videos published on or after `since.date()`.

    Fetches the last 20 entries without --dateafter (which silently drops all
    videos when dates are unavailable in flat-playlist mode) and filters in Python.
    If yt-dlp returns NA for all dates, falls back to full (non-flat) fetch for
    just the first 10 entries so we always get real dates.
    """
    playlist_id = _extract_playlist_id(playlist_url)
    fetch_url = f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else playlist_url

    rows = _flat_fetch(fetch_url, limit=20)

    # If every date came back as NA, flat mode couldn't read them — try full fetch
    if rows and all(r[2] == "NA" for r in rows):
        print(f"[youtube] flat dates all NA, falling back to full fetch for {fetch_url}")
        rows = _full_fetch(fetch_url, limit=10)

    episodes = []
    for video_id, title, upload_date in rows:
        if not upload_date or upload_date == "NA":
            continue
        try:
            pub_date = datetime.strptime(upload_date, "%Y%m%d").date()
        except ValueError:
            continue
        if pub_date >= since.date():
            episodes.append({
                "video_id": video_id,
                "title": title,
                "publish_date": pub_date,
                "url": f"https://youtu.be/{video_id}",
            })

    return episodes


def _flat_fetch(url: str, limit: int) -> list[tuple[str, str, str]]:
    """Fast fetch using --flat-playlist. Returns (id, title, upload_date) tuples."""
    cmd = [
        "yt-dlp", "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        "--playlist-end", str(limit),
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90, encoding="utf-8")
    except subprocess.TimeoutExpired:
        print(f"[youtube] flat fetch timeout: {url}")
        return []
    return _parse_tsv(r.stdout)


def _full_fetch(url: str, limit: int) -> list[tuple[str, str, str]]:
    """Slower fetch that retrieves full video metadata (guarantees upload_date)."""
    cmd = [
        "yt-dlp",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        "--playlist-end", str(limit),
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, encoding="utf-8")
    except subprocess.TimeoutExpired:
        print(f"[youtube] full fetch timeout: {url}")
        return []
    return _parse_tsv(r.stdout)


def _parse_tsv(stdout: str) -> list[tuple[str, str, str]]:
    rows = []
    for line in stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def fetch_latest_episode(playlist_url: str) -> dict | None:
    """Return the single most recent episode from a playlist."""
    playlist_id = _extract_playlist_id(playlist_url)
    fetch_url = f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else playlist_url

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(upload_date)s",
        "--playlist-end", "1",
        fetch_url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        return None

    for line in result.stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        video_id, title, upload_date = parts[0], parts[1], parts[2]
        pub_date = None
        try:
            pub_date = datetime.strptime(upload_date, "%Y%m%d").date() if upload_date != "NA" else None
        except ValueError:
            pass
        return {
            "video_id": video_id,
            "title": title,
            "publish_date": pub_date,
            "url": f"https://youtu.be/{video_id}",
        }
    return None


def _extract_playlist_id(url: str) -> str | None:
    import re
    m = re.search(r"[?&]list=([\w-]+)", url)
    return m.group(1) if m else None


def format_date_he(d: date | None) -> str:
    if d is None:
        return ""
    months = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני",
               "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]
    return f"{d.day} {months[d.month - 1]}"
