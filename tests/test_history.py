from cob.attack.loot import Loot
from cob.core import history
from cob.tasks.farm import CycleResult


def test_append_and_read_back(tmp_path):
    p = tmp_path / "history.csv"
    history.append(CycleResult(1, "accepted", 2, Loot(500_000, 400_000, 3_000), "done",
                               Loot(300_000, 200_000, 1_000), 181.4), path=p)
    history.append(CycleResult(2, "failed", reason="search blocked: try again later", seconds=40), path=p)
    rows = history.read(path=p)
    assert [r["cycle"] for r in rows] == ["1", "2"]
    assert rows[0]["gained_gold"] == "300000" and rows[0]["seconds"] == "181"
    assert rows[1]["gained_gold"] == "" and rows[1]["reason"].startswith("search blocked")


def test_read_limit_keeps_newest(tmp_path):
    p = tmp_path / "h.csv"
    for n in range(1, 8):
        history.append(CycleResult(n, "accepted"), path=p)
    assert [r["cycle"] for r in history.read(limit=3, path=p)] == ["5", "6", "7"]


def test_missing_or_unwritable_never_raises(tmp_path):
    assert history.read(path=tmp_path / "none.csv") == []
    history.append(CycleResult(1, "x"), path=tmp_path / "no_dir" / "h.csv")  # logged, not raised


def test_default_path_is_isolated_in_tests():
    assert "localappdata" in str(history.history_path()) or "xdg" in str(history.history_path())


def test_mode_column_and_old_files_upgraded(tmp_path):
    import csv

    p = tmp_path / "h.csv"
    old_columns = [c for c in history.COLUMNS if c not in ("mode", "profile")]
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, old_columns)
        w.writeheader()
        w.writerow({c: "" for c in old_columns} | {"cycle": "1", "gained_gold": "5"})
    history.append(CycleResult(2, "accepted"), path=p, mode="bb", profile="alt")
    rows = history.read(path=p)
    assert p.read_text("utf-8").splitlines()[0].endswith(",mode,profile")
    assert [(r["cycle"], r["mode"], r["gained_gold"], r["profile"]) for r in rows] == [
        ("1", "", "5", ""), ("2", "bb", "", "alt")]
    assert not (tmp_path / "h.tmp").exists()
