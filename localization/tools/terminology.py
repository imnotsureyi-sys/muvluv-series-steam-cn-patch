"""Read a game's explicitly scoped terminology; never rewrite dialogue."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[2]
GAMES = {**{g: "AGE2" for g in ("tda00", "tda01", "tda02", "tda03", "imperial-capital-burns")},
         **{g: "rUGP" for g in ("photonflowers", "photonmelodies")}}
COLUMNS = ["jp", "cn", "context"]


def read_table(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"Unexpected terminology columns: {path}")
        result = {}
        for row in reader:
            if set(row) != set(COLUMNS) or not all(row.values()):
                raise ValueError(f"Missing/extra terminology cells: {path}")
            if row["jp"] in result:
                raise ValueError(f"Duplicate JP key: {path}: {row['jp']}")
            if any(ord(char) < 32 for value in row.values() for char in value):
                raise ValueError(f"Control character in terminology: {path}")
            result[row["jp"]] = row
        return result


def load_game(game: str, root: Path = ROOT) -> dict[str, dict[str, str]]:
    """Load only common + this game's table, rejecting silent conflicts."""
    if game not in GAMES:
        raise ValueError(f"Unknown game: {game}")
    folder = root / GAMES[game] / "games" / game
    manifest = tomllib.loads((folder / "project.toml").read_text(encoding="utf-8"))
    expected = {
        "terminology_common_authority": root / "localization/glossaries/muv-luv.ja-zh-Hans.csv",
        "terminology_authority": root / "localization/glossaries" / f"{game}.ja-zh-Hans.csv",
    }
    result = {}
    for key, correct_path in expected.items():
        path = (folder / manifest[key]).resolve()
        if path != correct_path.resolve():
            raise ValueError(f"Wrong scope in {game}: {key}")
        for jp, row in read_table(path).items():
            if jp in result and result[jp]["cn"] != row["cn"]:
                raise ValueError(f"Unreviewed common/game conflict: {game}: {jp}")
            result[jp] = dict(row, scope="common" if key.endswith("common_authority") else game)
    return result


def candidate_terms(text: str, glossary: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """Longest-first candidates only. Context still needs human judgement."""
    if not glossary:
        return []
    patterns = []
    for jp in sorted(glossary, key=lambda value: (-len(value), value)):
        left = r"(?<![ァ-ヿA-Za-z])" if re.match(r"[ァ-ヿA-Za-z]", jp) else ""
        right = r"(?![ァ-ヿA-Za-z])" if re.search(r"[ァ-ヿA-Za-z]$", jp) else ""
        patterns.append(left + re.escape(jp) + right)
    return [glossary[m.group()] for m in re.finditer("|".join(patterns), text)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=GAMES)
    parser.add_argument("--term", help="Exact JP key to inspect, not a replacement command")
    args = parser.parse_args()
    result = load_game(args.game)
    print(json.dumps(result.get(args.term) if args.term else
                     {"game": args.game, "effective_terms": len(result)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
