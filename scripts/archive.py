"""
Download episodes for a digest window, ZIP them, upload to transfer.sh, send link.

Run by GitHub Actions (archive.yml) via workflow_dispatch.
Env required:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  INPUT_FMT_OVERRIDE, INPUT_WINDOW_START, INPUT_WINDOW_END  (from workflow inputs)
"""
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

import requests

import config
import telegram
import youtube

CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
IL_TZ = ZoneInfo("Asia/Jerusalem")

_COOKIES_FILE = "/tmp/yt-cookies.txt"


def _cookies_args() -> list[str]:
    """Return --cookies flag if the cookies file was written by the workflow."""
    return ["--cookies", _COOKIES_FILE] if Path(_COOKIES_FILE).exists() else []


# ─── download helpers ─────────────────────────────────────────────────────────

def download_audio(url: str, out_dir: Path, quality: int = 3) -> Path | None:
    cmd = [
        "yt-dlp",
        *_cookies_args(),
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", str(quality),
        "--no-playlist",
        "--output", str(out_dir / "%(title)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[archive] audio download failed for {url}:\n{result.stderr[-400:]}")
        return None
    mp3s = list(out_dir.glob("*.mp3"))
    return mp3s[-1] if mp3s else None


def download_video(url: str, out_dir: Path) -> Path | None:
    cmd = [
        "yt-dlp",
        *_cookies_args(),
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--no-playlist",
        "--output", str(out_dir / "%(title)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[archive] video download failed for {url}:\n{result.stderr[-400:]}")
        return None
    videos = list(out_dir.glob("*.mp4")) + list(out_dir.glob("*.mkv")) + list(out_dir.glob("*.webm"))
    return videos[-1] if videos else None


# ─── upload ───────────────────────────────────────────────────────────────────

def upload(file_path: Path, expiry_days: int = 3) -> str:
    """
    Upload to transfer.sh — no account or credentials required.
    Returns a direct public download URL.
    """
    print(f"[archive] uploading {file_path.name} ({file_path.stat().st_size // 1024 // 1024} MB)…")
    with open(file_path, "rb") as f:
        resp = requests.put(
            f"https://transfer.sh/{file_path.name}",
            data=f,
            headers={"Max-Days": str(expiry_days)},
            timeout=600,
        )
    resp.raise_for_status()
    return resp.text.strip()


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    window_start = datetime.fromisoformat(os.environ["INPUT_WINDOW_START"]).replace(tzinfo=IL_TZ)
    window_end   = datetime.fromisoformat(os.environ["INPUT_WINDOW_END"]).replace(tzinfo=IL_TZ)
    fmt_override = os.environ.get("INPUT_FMT_OVERRIDE", "").strip().lower() or None

    cfg = config.load()
    podcasts = config.active_podcasts(cfg)
    audio_quality = cfg.get("archives", {}).get("audio_quality", 3)
    expiry_hours  = cfg.get("archives", {}).get("link_expiry_hours", 48)
    expiry_days   = max(1, expiry_hours // 24)

    # Send initial status message (we'll edit it with progress)
    status_msg = telegram.send_message(
        CHAT_ID,
        f"⏳ אוסף אפיזודות מ-{youtube.format_date_he(window_start.date())} "
        f"עד {youtube.format_date_he(window_end.date())}…",
    )
    status_id = status_msg.get("result", {}).get("message_id")

    # Collect all episodes in window across all podcasts
    all_episodes: list[tuple[dict, str]] = []  # (episode_dict, format)
    for pod in podcasts:
        fmt = fmt_override or pod.get("default_format", "audio")
        try:
            eps = youtube.fetch_new_episodes(pod["url"], window_start)
            for ep in eps:
                all_episodes.append((ep, fmt))
        except Exception as e:
            print(f"[archive] error fetching {pod['name']}: {e}")

    if not all_episodes:
        telegram.send_message(CHAT_ID, "❌ לא נמצאו אפיזודות בחלון הזמן הזה.")
        return

    total = len(all_episodes)
    print(f"[archive] {total} episodes to download")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        files: list[Path] = []
        failed: list[str] = []

        for i, (ep, fmt) in enumerate(all_episodes, 1):
            ep_dir = tmp_path / f"ep_{i:03d}"
            ep_dir.mkdir()

            status_text = f"⏬ מוריד {i}/{total}:\n{ep['title'][:60]}"
            print(f"[archive] {status_text.replace(chr(10), ' ')}")
            if status_id:
                telegram.edit_message(CHAT_ID, status_id, status_text)

            f = (download_video if fmt == "video" else download_audio)(
                ep["url"], ep_dir, **({"quality": audio_quality} if fmt != "video" else {})
            )
            if f:
                files.append(f)
            else:
                failed.append(ep["title"])

        if not files:
            telegram.send_message(CHAT_ID, "❌ כל ההורדות נכשלו. נסה שוב מאוחר יותר.")
            return

        # Create ZIP
        zip_name = f"podcast-digest-{window_start.strftime('%Y%m%d')}.zip"
        zip_path = tmp_path / zip_name
        print(f"[archive] creating {zip_name}")
        if status_id:
            telegram.edit_message(CHAT_ID, status_id, "📦 יוצר קובץ ZIP…")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for f in files:
                zf.write(f, f.name)

        size_mb = zip_path.stat().st_size // 1024 // 1024

        if status_id:
            telegram.edit_message(CHAT_ID, status_id, f"☁️ מעלה ({size_mb} MB)…")

        public_url = upload(zip_path, expiry_days=expiry_days)

    # Send final message
    lines = [
        f"✅ הארכיון מוכן! ({size_mb} MB · {len(files)} אפיזודות)",
        f"⏰ הקישור בתוקף ל-{expiry_hours} שעות",
        "",
        f'🔗 <a href="{public_url}">הורדה</a>',
    ]
    if failed:
        lines.append(f"\n⚠️ לא הורדו {len(failed)}: {', '.join(failed[:3])}")

    telegram.send_message(CHAT_ID, "\n".join(lines))
    if status_id:
        telegram.edit_message(CHAT_ID, status_id, "✅ נשלח!")

    print(f"[archive] done — {len(files)}/{total} downloaded, {size_mb} MB")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"[archive] FATAL ERROR:\n{err}")
        try:
            telegram.send_message(os.environ["TELEGRAM_CHAT_ID"], f"❌ הארכיון נכשל:\n<code>{str(e)[:300]}</code>")
        except Exception:
            pass
        raise
