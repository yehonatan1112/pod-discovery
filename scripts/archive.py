"""
Download episodes for a digest window, ZIP them, upload to Cloudflare R2, send link.

Run by GitHub Actions (archive.yml) via workflow_dispatch.
Env required:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_URL
  window_start, window_end, fmt_override   (passed as env vars from workflow inputs)
"""
import os
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

import boto3
from botocore.config import Config

import config
import telegram
import youtube

CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
IL_TZ = ZoneInfo("Asia/Jerusalem")


# ─── download helpers ─────────────────────────────────────────────────────────

def download_audio(url: str, out_dir: Path, quality: int = 3) -> Path | None:
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", str(quality),
        "--no-playlist",
        "--output", str(out_dir / "%(title)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"[archive] audio download failed for {url}: {result.stderr[-300:]}")
        return None
    # Find the file that was created
    mp3s = list(out_dir.glob("*.mp3"))
    return mp3s[-1] if mp3s else None


def download_video(url: str, out_dir: Path) -> Path | None:
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--no-playlist",
        "--output", str(out_dir / "%(title)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[archive] video download failed for {url}: {result.stderr[-300:]}")
        return None
    videos = list(out_dir.glob("*.mp4")) + list(out_dir.glob("*.mkv")) + list(out_dir.glob("*.webm"))
    return videos[-1] if videos else None


# ─── R2 upload ────────────────────────────────────────────────────────────────

def upload_to_r2(local_path: Path) -> str:
    """Upload file to R2 and return the public URL."""
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket = os.environ["R2_BUCKET"]
    key = f"archives/{datetime.now().strftime('%Y%m')}/{uuid.uuid4().hex[:8]}/{local_path.name}"

    print(f"[archive] uploading {local_path.name} ({local_path.stat().st_size // 1024 // 1024} MB) to R2")
    s3.upload_file(str(local_path), bucket, key)

    public_base = os.environ["R2_PUBLIC_URL"].rstrip("/")
    return f"{public_base}/{key}"


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    window_start = datetime.fromisoformat(os.environ["INPUT_WINDOW_START"]).replace(tzinfo=IL_TZ)
    window_end = datetime.fromisoformat(os.environ["INPUT_WINDOW_END"]).replace(tzinfo=IL_TZ)
    fmt_override = os.environ.get("INPUT_FMT_OVERRIDE", "").strip().lower() or None

    cfg = config.load()
    podcasts = config.active_podcasts(cfg)
    archive_cfg = cfg.get("archives", {})
    audio_quality = archive_cfg.get("audio_quality", 3)

    status_msg = telegram.send_message(
        CHAT_ID,
        f"⏳ אוסף אפיזודות מ-{youtube.format_date_he(window_start.date())} "
        f"עד {youtube.format_date_he(window_end.date())}…",
    )
    status_id = status_msg.get("result", {}).get("message_id")

    # Collect all episodes in window
    all_episodes: list[tuple[dict, str]] = []  # (episode, format)
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

            status_text = f"⏬ מוריד {i}/{total}: {ep['title'][:50]}"
            print(f"[archive] {status_text}")
            if status_id:
                telegram.edit_message(CHAT_ID, status_id, status_text)

            if fmt == "video":
                f = download_video(ep["url"], ep_dir)
            else:
                f = download_audio(ep["url"], ep_dir, quality=audio_quality)

            if f:
                files.append(f)
            else:
                failed.append(ep["title"])

        if not files:
            telegram.send_message(CHAT_ID, "❌ כל ההורדות נכשלו. נסה שוב מאוחר יותר.")
            return

        # Build ZIP
        zip_name = f"podcast-digest-{window_start.strftime('%Y%m%d')}.zip"
        zip_path = tmp_path / zip_name
        print(f"[archive] creating ZIP: {zip_name}")
        if status_id:
            telegram.edit_message(CHAT_ID, status_id, "📦 יוצר קובץ ZIP…")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
            for f in files:
                zf.write(f, f.name)

        size_mb = zip_path.stat().st_size // 1024 // 1024

        if status_id:
            telegram.edit_message(CHAT_ID, status_id, f"☁️ מעלה ({size_mb} MB)…")

        public_url = upload_to_r2(zip_path)

    # Send result
    lines = [
        f"✅ הארכיון מוכן! ({size_mb} MB, {len(files)} אפיזודות)",
        f"⏰ הקישור פג תוקף תוך {cfg.get('archives', {}).get('link_expiry_hours', 48)} שעות",
        "",
        f"🔗 <a href=\"{public_url}\">הורדה</a>",
    ]
    if failed:
        lines.append(f"\n⚠️ לא הצלחתי להוריד {len(failed)} אפיזודה/ות: {', '.join(failed[:3])}")

    telegram.send_message(CHAT_ID, "\n".join(lines))
    if status_id:
        telegram.edit_message(CHAT_ID, status_id, "✅ הארכיון נשלח!")

    print(f"[archive] done. {len(files)}/{total} downloaded, {size_mb} MB")


if __name__ == "__main__":
    main()
