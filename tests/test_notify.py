"""Phone alerts (#43): Discord webhook / Telegram bot, opt-in, configured on the Settings page."""

import json
import os
import urllib.error

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cob.core import notify  # noqa: E402
from cob.core.ui_settings import UiSettings  # noqa: E402

HOOK = "https://discord.com/api/webhooks/123456789012345678/AbC_def-GHI"
TOKEN = "123456789:" + "A" * 35
CHAT = "-1001234567890"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    from cob.ui.style import qss

    app = QApplication.instance() or QApplication([])
    qss.apply(app)
    return app


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"{}"


def test_inputs_are_checked():
    assert notify.valid_discord(HOOK) and notify.valid_discord(HOOK.replace("discord.com", "discordapp.com"))
    assert not notify.valid_discord("http://discord.com/api/webhooks/1/x")  # not https
    assert not notify.valid_discord("https://evil.example/api/webhooks/1/x")
    assert notify.valid_telegram_token(TOKEN) and not notify.valid_telegram_token("12:short")
    assert notify.valid_telegram_chat(CHAT) and notify.valid_telegram_chat("@my_channel")
    assert not notify.valid_telegram_chat("chat id")


def test_nothing_configured_sends_nothing():
    calls = []
    assert notify.send(notify.Targets(), "Farming stopped", "x", opener=lambda *a, **k: calls.append(a)) == []
    assert calls == [] and not notify.Targets().any
    assert not notify.Targets(telegram_token=TOKEN).any  # a token without a chat is not enough


def test_requests_carry_only_the_alert_text():
    reqs = dict(notify.requests(notify.Targets(HOOK, TOKEN, CHAT), "Farming stopped", "3 failures"))
    d = json.loads(reqs["Discord"].data)
    assert reqs["Discord"].full_url == HOOK and d["content"] == "Clash of Bots: Farming stopped\n3 failures"
    assert d["allowed_mentions"] == {"parse": []}  # an @everyone in a reason pings nobody
    tg = json.loads(reqs["Telegram"].data)
    assert reqs["Telegram"].full_url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert tg["chat_id"] == CHAT and tg["text"].startswith("Clash of Bots: Farming stopped")
    long = json.loads(dict(notify.requests(notify.Targets(HOOK), "t", "x" * 5000))["Discord"].data)
    assert len(long["content"]) == notify.MAX_TEXT
    same = json.loads(dict(notify.requests(notify.Targets(HOOK), "Clash of Bots", "ok"))["Discord"].data)
    assert same["content"] == "Clash of Bots\nok"


def test_send_reports_failures_without_the_secret():
    def opener(req, timeout):
        if "telegram" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        return _Resp()

    errors = notify.send(notify.Targets(HOOK, TOKEN, CHAT), "t", "x", opener=opener)
    assert errors == ["Telegram: HTTP 401"]
    assert TOKEN not in errors[0]


def test_settings_keep_alert_targets_and_drop_bad_ones(tmp_path):
    from cob.core import ui_settings

    p = tmp_path / "ui.json"
    ui_settings.save(UiSettings(discord_webhook=HOOK, telegram_token=TOKEN, telegram_chat=CHAT), p)
    s = ui_settings.load(p)
    assert (s.discord_webhook, s.telegram_token, s.telegram_chat) == (HOOK, TOKEN, CHAT)
    p.write_text(json.dumps({"discord_webhook": "https://evil.example/x", "telegram_chat": 5}), "utf-8")
    s = ui_settings.load(p)
    assert s.discord_webhook == "" and s.telegram_chat == ""


def test_settings_page_saves_good_values_and_warns_on_typos(qapp):
    from cob.ui.pages.settings import SettingsPage

    page = SettingsPage(UiSettings())
    seen = []
    page.changed.connect(seen.append)
    page.discord.setText(HOOK)
    page._alerts_edited()
    assert seen[-1].discord_webhook == HOOK
    page.set_settings(seen[-1])
    page.telegram_token.setText("not a token")
    page._alerts_edited()
    assert seen[-1].telegram_token == "" and "bot token" in page.alert_status.text()
    page.set_settings(seen[-1])
    assert page.telegram_token.text() == "not a token"  # the typo stays to be fixed
    page.telegram_token.setText(TOKEN)
    page._alerts_edited()
    assert "both" in page.alert_status.text()  # token without chat id


@pytest.fixture
def window(qapp, monkeypatch):
    from cob.ui.main_window import MainWindow

    win = MainWindow(devices=lambda: [("LDPlayer #0", "emulator-5554")])
    win.tray = type("Tray", (), {"showMessage": lambda self, *a: None})()

    def run_now(fn, done, failed, busy=()):
        try:
            done(fn())
        except Exception as exc:
            failed(str(exc))

    monkeypatch.setattr(win, "_start_job", run_now)
    monkeypatch.setattr("cob.ui.main_window.QMessageBox.critical", lambda *a, **k: None)
    return win


def test_alerts_follow_the_same_toggles(window, monkeypatch):
    from cob.tasks.farm import FarmStats

    sent = []
    monkeypatch.setattr(notify, "send", lambda targets, title, text: sent.append(title) or [])
    window.ui_settings = UiSettings(notify_finished=False, discord_webhook=HOOK)
    window.on_finished(FarmStats(stop_reason="5 cycles done"))
    window.on_failed("phone locked")
    window.on_break(60)
    assert sent == ["Farming failed"]


def test_test_button_reports_the_result(window, monkeypatch):
    window.ui_settings = UiSettings()
    window.settings_page.test_notification.emit()
    assert "tray only" in window.settings_page.alert_status.text()
    window.ui_settings = UiSettings(discord_webhook=HOOK)
    monkeypatch.setattr(notify, "send", lambda *a: ["Discord: HTTP 404"])
    window.settings_page.test_notification.emit()
    assert window.settings_page.alert_status.text() == "Not sent: Discord: HTTP 404"
    monkeypatch.setattr(notify, "send", lambda *a: [])
    window.settings_page.test_notification.emit()
    assert window.settings_page.alert_status.text() == "Sent."
