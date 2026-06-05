"""
Telegram bot — polls for updates and handles commands.

Run by GitHub Actions every 5 minutes (bot.yml).
Env required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GITHUB_TOKEN, GITHUB_REPOSITORY

Commands:
  /start | /help    — show available commands
  /latest           — show most recent episode per podcast
  /status           — show active podcast count and current schedule window
  /archive          — trigger archive with per-podcast defaults
  /archive audio    — trigger audio archive for all
  /archive video    — trigger video archive for all
  /add <name> <url> [audio|video]  — add a new podcast
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
import config
import schedule as sched
import telegram
import youtube

CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
OFFSET_FILE = Path("/tmp/tg_offset.txt")

HELP_TEXT = """<b>פקודות זמינות:</b>

/latest — האפיזודה האחרונה מכל פודקאסט
/status — מצב המערכת
/archive — הורדת ארכיון מהדייג'סט האחרון (ברירת מחדל לכל פודקאסט)
/archive audio — הכל כ-MP3
/archive video — הכל כווידאו
/add &lt;שם&gt; &lt;url&gt; [audio|video] — הוספת פודקאסט חדש

<i>הדייג'סט נשלח ב-20:00 בימים: ראשון, שני, שלישי, רביעי ושבת.</i>"""


# ─── offset persistence ──────────────────────────────────────────────────────

def load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except ValueError:
            pass
    return 0


def save_offset(offset: int) -> None:
    OFFSET_FILE.write_text(str(offset))


# ─── command handlers ─────────────────────────────────────────────────────────

def handle_latest() -> None:
    cfg = config.load()
    podcasts = config.active_podcasts(cfg)
    lines = ["<b>🎙 האפיזודה האחרונה מכל פודקאסט</b>\n"]
    for pod in podcasts:
        ep = youtube.fetch_latest_episode(pod["url"])
        if ep:
            date_str = youtube.format_date_he(ep["publish_date"])
            lines.append(f"<b>{pod['name']}</b>")
            lines.append(f"  {ep['title']}")
            lines.append(f"  📅 {date_str}  ·  <a href=\"{ep['url']}\">▶ צפייה</a>\n")
        else:
            lines.append(f"<b>{pod['name']}</b>\n  ⚠️ לא נמצא\n")
    telegram.send_message(CHAT_ID, "\n".join(lines))


def handle_status() -> None:
    cfg = config.load()
    podcasts = config.active_podcasts(cfg)
    start, end, dtype = sched.get_window()
    label = sched.format_window_label(start, dtype)
    lines = [
        "<b>📊 סטטוס</b>",
        f"פודקאסטים פעילים: {len(podcasts)}",
        f"חלון הדייג'סט הנוכחי: {label}",
        f"מתאריך: {youtube.format_date_he(start.date())} {start.strftime('%H:%M')}",
    ]
    telegram.send_message(CHAT_ID, "\n".join(lines))


def handle_archive(fmt_override: str | None) -> None:
    start, end, dtype = sched.get_window()
    cfg = config.load()
    label = sched.format_window_label(start, dtype)

    telegram.send_message(
        CHAT_ID,
        f"⏳ מתחיל ליצור ארכיון עבור: <b>{label}</b>\n"
        f"פורמט: {'ברירת מחדל לכל פודקאסט' if not fmt_override else fmt_override.upper()}\n"
        "זה יכול לקחת כמה דקות. אשלח לך קישור כשיהיה מוכן.",
    )
    _dispatch_archive_workflow(
        fmt_override=fmt_override or "",
        window_start=start.isoformat(),
        window_end=end.isoformat(),
    )


def handle_add(args: list[str]) -> None:
    if len(args) < 2:
        telegram.send_message(
            CHAT_ID,
            "שימוש: /add &lt;שם&gt; &lt;url&gt; [audio|video]\n"
            "דוגמה: /add הפודקאסט שלי https://youtube.com/playlist?list=PL... audio",
        )
        return

    # Last token might be format
    fmt = "audio"
    if args[-1].lower() in ("audio", "video"):
        fmt = args[-1].lower()
        name_url = args[:-1]
    else:
        name_url = args

    # URL is whatever token starts with http
    url_idx = next((i for i, a in enumerate(name_url) if a.startswith("http")), None)
    if url_idx is None:
        telegram.send_message(CHAT_ID, "לא מצאתי URL תקין בפקודה.")
        return

    name = " ".join(name_url[:url_idx]).strip()
    url = name_url[url_idx]

    if not name:
        telegram.send_message(CHAT_ID, "חסר שם לפודקאסט.")
        return

    try:
        slug = config.add_podcast(name, url, fmt)
        telegram.send_message(
            CHAT_ID,
            f"✅ הפודקאסט <b>{name}</b> נוסף בהצלחה!\n"
            f"פורמט ברירת מחדל: {fmt}\n"
            f"הוא יופיע בדייג'סט הבא.",
        )
        print(f"[bot] added podcast: {name} ({slug})")
    except ValueError as e:
        telegram.send_message(CHAT_ID, f"❌ שגיאה: {e}")
    except Exception as e:
        telegram.send_message(CHAT_ID, f"❌ שגיאה בלתי צפויה: {e}")
        raise


# ─── GitHub Actions workflow dispatch ────────────────────────────────────────

def _dispatch_archive_workflow(fmt_override: str, window_start: str, window_end: str) -> None:
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    resp = requests.post(
        f"https://api.github.com/repos/{repo}/actions/workflows/archive.yml/dispatches",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"},
        json={
            "ref": "main",
            "inputs": {
                "fmt_override": fmt_override,
                "window_start": window_start,
                "window_end": window_end,
            },
        },
        timeout=15,
    )
    if not resp.ok:
        raise RuntimeError(f"Workflow dispatch failed: {resp.status_code} {resp.text}")


# ─── update routing ───────────────────────────────────────────────────────────

def is_authorized(update: dict) -> bool:
    """Only respond to the configured chat."""
    msg = update.get("message") or update.get("callback_query", {}).get("message")
    if not msg:
        return False
    incoming = str(msg.get("chat", {}).get("id"))
    expected = str(CHAT_ID)
    if incoming != expected:
        print(f"[bot] IGNORED update from chat_id={incoming} (expected {expected})")
        return False
    return True


def process_update(update: dict) -> None:
    if not is_authorized(update):
        return

    msg = update.get("message", {})
    text: str = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].lower().split("@")[0]  # strip @botname suffix
    args = parts[1:]

    print(f"[bot] command: {cmd!r} args: {args}")

    if cmd in ("/start", "/help"):
        telegram.send_message(CHAT_ID, HELP_TEXT)
    elif cmd == "/latest":
        handle_latest()
    elif cmd == "/status":
        handle_status()
    elif cmd == "/archive":
        fmt = args[0].lower() if args and args[0].lower() in ("audio", "video") else None
        handle_archive(fmt)
    elif cmd == "/add":
        handle_add(args)
    else:
        telegram.send_message(CHAT_ID, f"פקודה לא מוכרת: {cmd}\nשלח /help לרשימת פקודות.")


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    offset = load_offset()
    print(f"[bot] polling from offset {offset}")

    updates = telegram.get_updates(offset)
    if not updates:
        print("[bot] no new updates")
        return

    for update in updates:
        try:
            process_update(update)
        except Exception as e:
            print(f"[bot] error processing update {update.get('update_id')}: {e}")
        finally:
            offset = update["update_id"] + 1
            save_offset(offset)

    print(f"[bot] processed {len(updates)} update(s), new offset: {offset}")


if __name__ == "__main__":
    main()
