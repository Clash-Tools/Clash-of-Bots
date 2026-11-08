import logging

import cob.core.log as cl


def test_session_file_written_and_old_ones_pruned(monkeypatch):
    folder = cl.sessions_dir()
    for i in range(35):
        (folder / f"session-20260101-0000{i:02d}.log").write_text("x", "utf-8")
    monkeypatch.setattr(cl, "_session_file", None)
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers = []
    try:
        path = cl.setup_logging(console=False)
        logging.getLogger("cob.test").info("hello session")
        for h in root.handlers:
            h.flush()
        assert path.exists() and "hello session" in path.read_text("utf-8")
        assert cl.latest_session_log() == path
        assert len(list(folder.glob("session-*.log"))) <= cl.KEEP_SESSIONS
        assert (cl.log_dir() / "cob.log").exists()
    finally:
        for h in root.handlers:
            h.close()
        root.handlers = saved


def test_logs_command_lists_without_creating_a_session(capsys):
    from cob.cli import main

    before = set(cl.sessions_dir().glob("session-*.log"))
    assert main(["logs"]) == 0
    assert "logs folder" in capsys.readouterr().out
    assert set(cl.sessions_dir().glob("session-*.log")) == before
