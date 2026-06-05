"""Load and modify podcasts.yaml."""
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "podcasts.yaml"

_PLAYLIST_RE = re.compile(r"[?&]list=([\w-]+)")
_YOUTUBE_RE = re.compile(r"youtube\.com|youtu\.be")


def load() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def active_podcasts(cfg: dict) -> list[dict]:
    return [p for p in cfg["podcasts"] if p.get("active", True) and p.get("url")]


def playlist_id(url: str) -> str | None:
    m = _PLAYLIST_RE.search(url)
    return m.group(1) if m else None


def is_youtube_url(url: str) -> bool:
    return bool(_YOUTUBE_RE.search(url))


def add_podcast(name: str, url: str, default_format: str = "audio") -> str:
    """Append a new podcast to podcasts.yaml and commit the change. Returns slug."""
    if not is_youtube_url(url):
        raise ValueError("URL doesn't look like a YouTube URL")
    if default_format not in ("audio", "video"):
        raise ValueError("format must be 'audio' or 'video'")

    cfg = load()

    for p in cfg["podcasts"]:
        if p.get("url", "").split("list=")[-1] == url.split("list=")[-1]:
            raise ValueError(f"Playlist already tracked as '{p['name']}'")

    n = len(cfg["podcasts"]) + 1
    existing = {p.get("slug") for p in cfg["podcasts"]}
    slug = f"podcast_{n:02d}"
    while slug in existing:
        n += 1
        slug = f"podcast_{n:02d}"

    # Build new entry as a YAML block and insert before the digest section
    entry = (
        f"\n  - name: {name}\n"
        f"    slug: {slug}\n"
        f"    url: {url.split('&pp=')[0]}\n"  # strip tracking params
        f"    default_format: {default_format}\n"
        f"    active: true\n"
    )

    text = CONFIG_PATH.read_text(encoding="utf-8")
    marker = "# ─────────────────────────────────────────────────────────────\n# Digest schedule"
    if marker in text:
        text = text.replace(marker, entry + "\n" + marker)
    else:
        text += entry
    CONFIG_PATH.write_text(text, encoding="utf-8")

    # Commit and push (works inside GitHub Actions with contents:write permission)
    _git_commit_and_push(f"feat: add podcast {name}")
    return slug


def _git_commit_and_push(message: str) -> None:
    for cmd in [
        ["git", "config", "--global", "user.email", "podcast-bot@users.noreply.github.com"],
        ["git", "config", "--global", "user.name", "Podcast Bot"],
        ["git", "add", str(CONFIG_PATH)],
        ["git", "commit", "-m", message],
        ["git", "push"],
    ]:
        subprocess.run(cmd, check=True, cwd=ROOT)
