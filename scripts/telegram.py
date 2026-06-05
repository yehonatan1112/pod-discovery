"""Thin wrapper around the Telegram Bot API."""
import os
import time
import requests

_BASE = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 10
_MAX_MESSAGE_LEN = 4096


def _url(method: str) -> str:
    return _BASE.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method=method)


def send_message(chat_id: str, text: str, parse_mode: str = "HTML", **kwargs) -> dict:
    """Send a message, splitting automatically if over the 4096-char limit."""
    chunks = _split(text)
    last = {}
    for chunk in chunks:
        resp = requests.post(
            _url("sendMessage"),
            json={"chat_id": chat_id, "text": chunk, "parse_mode": parse_mode, **kwargs},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        last = resp.json()
        if len(chunks) > 1:
            time.sleep(0.3)
    return last


def edit_message(chat_id: str, message_id: int, text: str, parse_mode: str = "HTML") -> None:
    requests.post(
        _url("editMessageText"),
        json={"chat_id": chat_id, "message_id": message_id,
              "text": text[:_MAX_MESSAGE_LEN], "parse_mode": parse_mode},
        timeout=_TIMEOUT,
    )


def get_updates(offset: int = 0) -> list[dict]:
    resp = requests.get(
        _url("getUpdates"),
        params={"offset": offset, "timeout": 30, "limit": 100},
        timeout=40,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


def answer_callback(callback_query_id: str, text: str = "") -> None:
    requests.post(
        _url("answerCallbackQuery"),
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=_TIMEOUT,
    )


def _split(text: str) -> list[str]:
    if len(text) <= _MAX_MESSAGE_LEN:
        return [text]
    chunks, current = [], []
    length = 0
    for line in text.split("\n"):
        if length + len(line) + 1 > _MAX_MESSAGE_LEN:
            chunks.append("\n".join(current))
            current, length = [], 0
        current.append(line)
        length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks
