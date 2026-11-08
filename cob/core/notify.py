"""Phone alerts (#43): the tray messages also go to a Discord webhook and / or a Telegram bot, opt-in.

Both are set by the user in Settings and kept only in ui.json. Nothing is sent until one is filled in;
then only the alert title and text go to that address (no device, account or log data). Sending runs
off the GUI thread and never raises: a failure comes back as an error message.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from cob import __version__

log = logging.getLogger(__name__)

DISCORD = re.compile(r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
TELEGRAM_TOKEN = re.compile(r"^\d{5,}:[\w-]{30,}$")
TELEGRAM_CHAT = re.compile(r"^(?:-?\d{1,20}|@\w{5,32})$")
MAX_TEXT = 1800  # Discord allows 2000 characters per message, Telegram 4096


def valid_discord(url: str) -> bool:
    return bool(DISCORD.match(url.strip()))


def valid_telegram_token(token: str) -> bool:
    return bool(TELEGRAM_TOKEN.match(token.strip()))


def valid_telegram_chat(chat: str) -> bool:
    return bool(TELEGRAM_CHAT.match(chat.strip()))


@dataclass(frozen=True)
class Targets:
    discord: str = ""  # webhook URL
    telegram_token: str = ""  # bot token from @BotFather
    telegram_chat: str = ""  # chat id (number) or @channel

    @classmethod
    def of(cls, settings) -> Targets:
        return cls(getattr(settings, "discord_webhook", ""), getattr(settings, "telegram_token", ""),
                   getattr(settings, "telegram_chat", ""))

    @property
    def use_discord(self) -> bool:
        return valid_discord(self.discord)

    @property
    def use_telegram(self) -> bool:
        return valid_telegram_token(self.telegram_token) and valid_telegram_chat(self.telegram_chat)

    @property
    def any(self) -> bool:
        return self.use_discord or self.use_telegram


def message(title: str, text: str) -> str:
    body = f"{title}\n{text}".strip() if text else title
    return body if len(body) <= MAX_TEXT else body[:MAX_TEXT - 1] + "…"


def requests(targets: Targets, title: str, text: str) -> list[tuple[str, urllib.request.Request]]:
    """(name, request) per configured target."""
    body = message(title if title.startswith("Clash of Bots") else f"Clash of Bots: {title}", text)
    headers = {"Content-Type": "application/json", "User-Agent": f"ClashOfBots/{__version__}"}
    out = []
    if targets.use_discord:
        data = json.dumps({"content": body, "allowed_mentions": {"parse": []}}).encode("utf-8")
        out.append(("Discord", urllib.request.Request(targets.discord.strip(), data, headers, method="POST")))
    if targets.use_telegram:
        url = f"https://api.telegram.org/bot{targets.telegram_token.strip()}/sendMessage"
        data = json.dumps({"chat_id": targets.telegram_chat.strip(), "text": body,
                           "disable_web_page_preview": True}).encode("utf-8")
        out.append(("Telegram", urllib.request.Request(url, data, headers, method="POST")))
    return out


def _reason(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)
    return type(exc).__name__  # never the URL: it holds the webhook / bot secret


def send(targets: Targets, title: str, text: str, timeout: float = 10.0, opener=None) -> list[str]:
    """Send to every configured target; the errors, one per target that failed (empty: all sent)."""
    open_url = opener or urllib.request.urlopen
    errors = []
    for name, req in requests(targets, title, text):
        try:
            with open_url(req, timeout=timeout) as resp:  # noqa: S310 (user's own https endpoint)
                resp.read()
        except Exception as exc:
            errors.append(f"{name}: {_reason(exc)}")
    for e in errors:
        log.info("alert not sent: %s", e)
    return errors
