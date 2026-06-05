"""
Generate and send the Telegram digest.

Run by GitHub Actions on schedule (digest.yml).
Env required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

import config
import schedule as sched
import telegram
import youtube


def build_message(episodes_by_podcast: dict[str, list[dict]], label: str) -> str:
    lines = [f"<b>📻 {label}</b>\n"]
    total = 0
    for podcast_name, episodes in episodes_by_podcast.items():
        if not episodes:
            continue
        lines.append(f"<b>🎙 {podcast_name}</b>")
        for ep in episodes:
            date_str = youtube.format_date_he(ep["publish_date"])
            lines.append(f"  └ {ep['title']}")
            lines.append(f"    📅 {date_str}  ·  <a href=\"{ep['url']}\">▶ צפייה</a>")
        lines.append("")
        total += len(episodes)

    if total == 0:
        return ""

    lines.append("──────────────────")
    lines.append("להורדה:")
    lines.append("/archive — לפי ברירת מחדל של כל פודקאסט")
    lines.append("/archive audio — הכל כ-MP3")
    lines.append("/archive video — הכל כווידאו")
    return "\n".join(lines)


def main() -> None:
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    cfg = config.load()
    podcasts = config.active_podcasts(cfg)

    window_start, window_end, digest_type = sched.get_window()
    label = sched.format_window_label(window_start, digest_type)

    print(f"[digest] window: {window_start.isoformat()} → {window_end.isoformat()} ({digest_type})")
    print(f"[digest] scanning {len(podcasts)} podcasts")

    episodes_by_podcast: dict[str, list[dict]] = {}
    for pod in podcasts:
        name = pod["name"]
        try:
            eps = youtube.fetch_new_episodes(pod["url"], window_start)
            if eps:
                episodes_by_podcast[name] = eps
                print(f"[digest]   {name}: {len(eps)} new episode(s)")
            else:
                print(f"[digest]   {name}: nothing new")
        except Exception as e:
            print(f"[digest]   {name}: ERROR — {e}")

    if not episodes_by_podcast:
        print("[digest] no new episodes this period, skipping send")
        return

    message = build_message(episodes_by_podcast, label)
    total = sum(len(v) for v in episodes_by_podcast.values())
    print(f"[digest] sending digest with {total} episode(s)")

    telegram.send_message(chat_id, message)
    print("[digest] done")


if __name__ == "__main__":
    main()
