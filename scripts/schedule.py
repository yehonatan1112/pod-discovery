"""Compute which digest window is current based on Israel time."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IL_TZ = ZoneInfo("Asia/Jerusalem")

# isoweekday mapping: 1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat 7=Sun
# config mapping:     1=Mon 2=Tue 3=Wed 4=Thu 5=Fri 6=Sat 0=Sun
_DAILY_ISO = {7, 1, 2, 3}   # Sun, Mon, Tue, Wed
_SAT_ISO = 6


def now_il() -> datetime:
    return datetime.now(IL_TZ)


def get_window(now: datetime | None = None) -> tuple[datetime, datetime, str]:
    """
    Returns (window_start, window_end, digest_type).

    digest_type is 'daily' or 'saturday'.
    window_start is the end-time of the previous scheduled digest.
    window_end is `now` (the time of the current digest run).

    Schedule (Israel time, 20:00):
        Sun, Mon, Tue, Wed → daily   (covers previous day 20:00 → today 20:00)
        Sat               → saturday (covers Wed 20:00 → Sat 20:00, i.e. Thu/Fri/Sat content)
    """
    if now is None:
        now = now_il()

    send_hour = 20
    iso = now.isoweekday()  # 1=Mon … 7=Sun

    today_send = now.replace(hour=send_hour, minute=0, second=0, microsecond=0)

    if iso == _SAT_ISO:
        # Previous digest: Wednesday 20:00 (3 days ago)
        prev = today_send - timedelta(days=3)
        return prev, now, "saturday"

    if iso in _DAILY_ISO:
        # Previous digest: yesterday 20:00
        prev = today_send - timedelta(days=1)
        return prev, now, "daily"

    # Thu or Fri — no scheduled digest, but allow manual /archive to work:
    # treat as "since last Wednesday 20:00"
    days_since_wed = (iso - 3) % 7  # Thu→1, Fri→2
    prev = today_send - timedelta(days=days_since_wed)
    return prev, now, "daily"


def format_window_label(start: datetime, digest_type: str) -> str:
    """Human-readable Hebrew label for the digest period."""
    day_names = {1: "שני", 2: "שלישי", 3: "רביעי", 4: "חמישי",
                 5: "שישי", 6: "שבת", 7: "ראשון"}
    month_names = {1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
                   5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
                   9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"}
    now = now_il()
    if digest_type == "saturday":
        return f"סיכום שבועי | {start.day} {month_names[start.month]}–{now.day} {month_names[now.month]}"
    return f"יום {day_names[now.isoweekday()]} | {now.day} {month_names[now.month]} {now.year}"
