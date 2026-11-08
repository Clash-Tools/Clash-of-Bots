"""Copy a tagged version of the unit database into assets/units (the bot bundles a pinned version).

    python scripts/update_units.py data-v1 [--repo ../clash-of-bots-data]

Takes index.json, units/ and detection/ from that tag of a local clone of
https://github.com/Clash-Tools/clash-of-bots-data and writes the tag to assets/units/VERSION.
"""

from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "units"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tag")
    p.add_argument("--repo", type=Path, default=ROOT.parent / "clash-of-bots-data")
    a = p.parse_args(argv)
    raw = subprocess.run(["git", "-C", str(a.repo), "archive", "--format=tar", a.tag, "index.json", "units",
                          "detection"], check=True, capture_output=True).stdout
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        tar.extractall(DEST, filter="data")
    for readme in DEST.rglob("README.md"):
        readme.unlink()
    (DEST / "VERSION").write_text(a.tag + "\n", "utf-8")
    n = sum(1 for _ in (DEST / "units").rglob("*.json"))
    print(f"assets/units <- {a.tag}: {n} units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
