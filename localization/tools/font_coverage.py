#!/usr/bin/env python3
"""Audit visible translation characters against a font's Unicode cmap.

The tool never rewrites translation text. It accepts CSV/TSV source tables,
selects explicitly named columns (or well-known localized-text columns),
removes engine control tokens, and emits a deterministic JSON report. A
non-zero exit status means at least one visible character is not mapped by the
font.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Sequence

from localization.tools.safe_output import write_new_files


DEFAULT_COLUMNS = (
    "translated_text",
    "translation_text",
    "runtime_text",
    "replacement_text",
    "cn_text",
    "zh_cn",
)
ANGLE_CONTROL_RE = re.compile(r"<[0-9A-Fa-f]{2}>")
BACKSLASH_CONTROL_RE = re.compile(r"\\[A-Za-z]")


class CoverageError(RuntimeError):
    """Input data cannot be audited without guessing."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def visible_codepoints(text: str) -> set[int]:
    """Return codepoints expected to select a visible font glyph."""

    text = ANGLE_CONTROL_RE.sub("", text)
    text = BACKSLASH_CONTROL_RE.sub("", text)
    return {
        ord(character)
        for character in text
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    }


def read_table(path: Path, requested_columns: Sequence[str]) -> tuple[set[int], list[str], int]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        fieldnames = tuple(reader.fieldnames or ())
        if not fieldnames:
            raise CoverageError(f"table has no header: {path}")
        if requested_columns:
            columns = list(requested_columns)
            missing = [column for column in columns if column not in fieldnames]
            if missing:
                raise CoverageError(f"missing columns in {path}: {missing}")
        else:
            columns = [column for column in DEFAULT_COLUMNS if column in fieldnames]
            if not columns:
                raise CoverageError(
                    f"no known localized-text column in {path}; pass --column"
                )
        codepoints: set[int] = set()
        rows = 0
        for row in reader:
            rows += 1
            for column in columns:
                codepoints.update(visible_codepoints(row.get(column, "")))
    return codepoints, columns, rows


def font_codepoints(path: Path, face_index: int | None = None) -> set[int]:
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError as exc:  # pragma: no cover - CLI environment dependent
        raise CoverageError(
            "fontTools is required; install the repository requirements first"
        ) from exc

    if path.suffix.lower() in {".ttc", ".otc"}:
        collection = TTCollection(path, lazy=True)
        try:
            if face_index is None:
                raise CoverageError(
                    "TTC/OTC collections require an explicit --face-index; "
                    "coverage is never unioned across faces"
                )
            if not 0 <= face_index < len(collection.fonts):
                raise CoverageError(
                    f"font face index {face_index} is outside 0..{len(collection.fonts) - 1}"
                )
            font = collection.fonts[face_index]
            result: set[int] = set()
            cmap = font["cmap"]
            for table in cmap.tables:
                if table.isUnicode():
                    result.update(table.cmap)
            return result
        finally:
            collection.close()
    else:
        if face_index not in (None, 0):
            raise CoverageError("a standalone font only has face index 0")
        font = TTFont(path, lazy=True)
        try:
            result: set[int] = set()
            cmap = font["cmap"]
            for table in cmap.tables:
                if table.isUnicode():
                    result.update(table.cmap)
            return result
        finally:
            font.close()


def audit(
    font: Path,
    tables: Sequence[Path],
    columns: Sequence[str],
    *,
    face_index: int | None = None,
) -> dict[str, object]:
    font = font.resolve(strict=True)
    if not tables:
        raise CoverageError("at least one translation table is required")
    required: set[int] = set()
    table_reports: list[dict[str, object]] = []
    for raw_path in tables:
        path = raw_path.resolve(strict=True)
        codepoints, selected, rows = read_table(path, columns)
        required.update(codepoints)
        table_reports.append(
            {
                "file": path.name,
                "rows": rows,
                "columns": selected,
                "visible_codepoints": len(codepoints),
                "sha256": sha256_file(path),
            }
        )
    available = font_codepoints(font, face_index)
    missing = sorted(required - available)
    return {
        "schema": "muvluv-font-coverage/v1",
        "status": "PASS" if not missing else "FAIL",
        "font": {
            "path": font.name,
            "bytes": font.stat().st_size,
            "sha256": sha256_file(font),
            "face_index": face_index if font.suffix.lower() in {".ttc", ".otc"} else 0,
            "unicode_codepoints": len(available),
        },
        "tables": table_reports,
        "required_visible_codepoints": len(required),
        "missing": [
            {
                "codepoint": f"U+{value:04X}",
                "character": chr(value),
                "name": unicodedata.name(chr(value), "UNNAMED"),
            }
            for value in missing
        ],
        "limitations": [
            "cmap coverage does not prove that the game selected this font",
            "metrics, shaping, fallback, clipping and line wrapping require in-game QA",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("font", type=Path)
    parser.add_argument("tables", nargs="+", type=Path)
    parser.add_argument(
        "--column",
        action="append",
        default=[],
        help="localized-text column; repeat for multiple columns",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--face-index",
        type=int,
        help="zero-based face to audit; mandatory for TTC/OTC collections",
    )
    args = parser.parse_args(argv)
    try:
        report = audit(args.font, args.tables, args.column, face_index=args.face_index)
    except Exception as exc:
        report = {
            "schema": "muvluv-font-coverage/v1",
            "status": "ERROR",
            "error": str(exc),
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        write_new_files(
            {args.output: payload.encode("utf-8")},
            inputs=(args.font, *args.tables),
        )
    print(payload, end="")
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
