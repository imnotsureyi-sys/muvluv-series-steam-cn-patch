#!/usr/bin/env python3
"""Apply an exact, ID-scoped JP-to-ZH patch to a decrypted uistring DAT.

The third ``::``-separated field is the visible string.  Every replacement
must carry the exact Japanese source expected at that ID; a mismatch or a
missing/duplicate ID aborts the build instead of falling back to another
language slot or fuzzy matching.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Mapping, NamedTuple


class Change(NamedTuple):
    expected: str
    replacement: str


def apply_changes(source: str, changes: Mapping[str, Change]) -> str:
    """Return *source* with only the requested visible fields replaced."""

    pending = set(changes)
    seen: set[str] = set()
    output: list[str] = []

    for line in source.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        fields = body.split("::")
        row_id = fields[0] if fields else ""

        if row_id in changes:
            if row_id in seen:
                raise ValueError(f"duplicate uistring ID: {row_id}")
            if len(fields) < 3:
                raise ValueError(f"uistring ID {row_id} has no visible field")
            change = changes[row_id]
            if fields[2] != change.expected:
                raise ValueError(
                    f"Japanese source mismatch for uistring ID {row_id}: "
                    f"expected {change.expected!r}, got {fields[2]!r}"
                )
            fields[2] = change.replacement
            pending.remove(row_id)
            seen.add(row_id)
            body = "::".join(fields)

        output.append(body + ending)

    if pending:
        raise ValueError(f"missing uistring ID(s): {', '.join(sorted(pending))}")
    return "".join(output)


def load_changes(path: Path) -> dict[str, Change]:
    changes: dict[str, Change] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"id", "jp", "zh_cn"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain TSV columns: id, jp, zh_cn")
        for row in reader:
            row_id = row["id"].strip()
            if not row_id or row_id.startswith("#"):
                continue
            if row_id in changes:
                raise ValueError(f"duplicate change ID: {row_id}")
            changes[row_id] = Change(
                row["jp"].replace(r"\t", "\t"),
                row["zh_cn"].replace(r"\t", "\t"),
            )
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="decrypted uistring EPK/DAT")
    parser.add_argument("--changes", required=True, type=Path, help="JP/ZH TSV")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    patched = apply_changes(source, load_changes(args.changes))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(patched, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
