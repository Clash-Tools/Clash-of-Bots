"""Translation catalogs (#103).

  uv run python scripts/i18n.py extract        # every tr("...") string -> assets/i18n/template.json
  uv run python scripts/i18n.py check de       # what assets/i18n/de.json is missing or no longer uses
  uv run python scripts/i18n.py update de      # add missing keys (empty) to de.json, drop unused ones

A new language: copy template.json to <code>.json (de, pt_BR, ...), set "_language" to the language's
own name, fill the values. Empty values fall back to English.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ROOT / "assets" / "i18n"


def strings(root: Path = ROOT / "cob") -> dict[str, list[str]]:
    """Source text -> where it is used ("cob/ui/shell.py:42"), for tr() calls with a literal first arg."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text("utf-8"), str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, []).append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def _load(code: str) -> dict[str, str]:
    path = CATALOGS / f"{code}.json"
    return json.loads(path.read_text("utf-8")) if path.is_file() else {"_language": code}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n", "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extract")
    for name in ("check", "update"):
        sub.add_parser(name).add_argument("code")
    args = ap.parse_args(argv)
    found = strings()
    if args.cmd == "extract":
        _write(CATALOGS / "template.json", {"_language": "", **{k: "" for k in sorted(found)}})
        print(f"{len(found)} strings -> {CATALOGS / 'template.json'}")
        return 0
    cat = _load(args.code)
    missing = [k for k in sorted(found) if not cat.get(k)]
    unused = [k for k in cat if not k.startswith("_") and k not in found]
    if args.cmd == "check":
        print(f"{args.code}: {len(found) - len(missing)}/{len(found)} translated, {len(unused)} unused")
        for k in missing:
            print(f"  missing: {k!r}  ({found[k][0]})")
        for k in unused:
            print(f"  unused:  {k!r}")
        return 1 if missing else 0
    updated = {"_language": cat.get("_language", args.code), **{k: cat.get(k, "") for k in sorted(found)}}
    _write(CATALOGS / f"{args.code}.json", updated)
    print(f"{args.code}: {len(missing)} added (empty), {len(unused)} dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
