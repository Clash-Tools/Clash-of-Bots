import cob.cli as cli
from cob.cli import main


def test_selftest_passes(capsys):
    assert main(["selftest"]) == 0
    assert "selftest ok" in capsys.readouterr().out


def test_no_args_opens_gui(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "cmd_gui", lambda args: calls.append(args) or 0)
    assert main([]) == 0 and calls == [None]


def test_no_args_falls_back_to_help_when_gui_fails(monkeypatch, capsys):
    def broken(_args):
        raise ImportError("no Qt")

    monkeypatch.setattr(cli, "cmd_gui", broken)
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "usage: cob" in out and "ClashOfBots.exe devices" in out
