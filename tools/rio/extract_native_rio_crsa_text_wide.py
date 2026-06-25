#!/usr/bin/env python3
"""Wide photonflowers native RIO/CRsa text extraction.

Extraction only: no translation, no writeback, no patch creation.

This intentionally keeps short and uncertain native strings so the output can
be used as a completeness audit layer. A narrower translation worklist should
be derived from this table later.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "outputs" / "photonflowers_text"
CSV_PATH = OUTPUT_ROOT / "photonflowers_native_resource_worklist_wide_v1.csv"
AUDIT_PATH = OUTPUT_ROOT / "audit_native_resource_worklist_wide_v1.json"
STATUS_PATH = REPO_ROOT / "chapters" / "photonflowers" / "extraction_status_wide.md"
HIGH_CONFIDENCE_CSV = OUTPUT_ROOT / "photonflowers_native_resource_worklist_v1.csv"

RIO_KEY = 0x7E6B8CE2
CRSA_PATTERN = bytes.fromhex("00056e030100")
CRSA_HEADER_SIZE = 11
SOURCE_DIRS = [
    Path(r"D:\Steam\steamapps\common\Muv-Luv photonflowers"),
    Path(r"C:\Steam\steamapps\common\Muv-Luv photonflowers"),
]

FIELDS = [
    "chapter",
    "csv_row",
    "stable_id",
    "rio_file",
    "scene",
    "speaker_jp",
    "jp_text",
    "jp_text_visible",
    "control_codes",
    "row_kind",
    "curated_kind",
    "curation_evidence",
    "crsa_file",
    "block_offset",
    "payload_offset",
    "notes",
    "wide_flags",
]

SPEAKER_RE = re.compile(r"^\u3010([^\u3010\u3011]{1,40})\u3011")
DATE_RE = re.compile(r"^[0-9\uff10-\uff19]{1,2}\u6708[0-9\uff10-\uff19]{1,2}\u65e5")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class RawRow:
    rio_file: str
    block_offset: int
    payload_offset: int
    text: str
    notes: str


def u32le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little")


def read_encrypted_at(data: bytes, off: int, key: int) -> tuple[bytes, int]:
    if off + 8 > len(data):
        raise EOFError("encrypted chunk header beyond EOF")
    size1 = u32le(data, off) ^ 0xC92E568B
    size2 = u32le(data, off + 4) ^ 0xC92E568F
    size2 >>= 3
    size1 = (~size1) & 0xFFFFFFFF
    if size1 != size2 or size1 <= 0 or size1 > 5_000_000:
        raise ValueError(f"invalid encrypted chunk at {off}: {size1=} {size2=}")
    pos = off + 8
    out = bytearray(size1)
    dst = 0
    while dst < size1:
        checksum = 0
        portion = min(0x20, size1 - dst)
        chunk = data[pos : pos + portion]
        if len(chunk) != portion:
            raise EOFError("encrypted chunk truncated")
        pos += portion
        for i, enc in enumerate(chunk):
            b = enc ^ (key & 0xFF)
            out[dst] = b
            dst += 1
            checksum = (checksum + b * (portion - i)) & 0xFFFF
            bit = (key >> 15) & 1
            key = (~(bit + ((key * 2) & 0xFFFFFFFF) + 0xA3B376C9)) & 0xFFFFFFFF
        if portion < 0x20:
            break
        stored = int.from_bytes(data[pos : pos + 2], "little")
        pos += 2
        if stored != checksum:
            raise ValueError(f"checksum mismatch at {pos}: got {stored:04x} expected {checksum:04x}")
    return bytes(out), pos


def allowed_unit(code: int) -> bool:
    return (
        1 <= code <= 31
        or 0x20 <= code <= 0x7E
        or 0x3000 <= code <= 0x30FF
        or 0x4E00 <= code <= 0x9FFF
        or 0xFF01 <= code <= 0xFF5E
        or 0x2010 <= code <= 0x203B
        or code in (0x25A0, 0x25A1, 0x2665, 0x266A)
    )


def printable(text: str) -> str:
    return "".join(ch for ch in text if not (1 <= ord(ch) <= 31))


def visible(text: str) -> str:
    return "".join(f"<{ord(ch):02X}>" if 1 <= ord(ch) <= 31 else ch for ch in text)


def controls(text: str) -> str:
    codes = sorted({ord(ch) for ch in text if 1 <= ord(ch) <= 31})
    return " ".join(f"U+{code:04X}" for code in codes)


def char_counts(text: str) -> dict[str, int]:
    body = printable(text)
    return {
        "body_len": len(body),
        "hiragana": sum(1 for ch in body if 0x3040 <= ord(ch) <= 0x309F),
        "katakana": sum(1 for ch in body if 0x30A0 <= ord(ch) <= 0x30FF),
        "cjk": sum(1 for ch in body if 0x4E00 <= ord(ch) <= 0x9FFF),
        "fullwidth": sum(1 for ch in body if 0xFF01 <= ord(ch) <= 0xFF5E),
        "latin": len(ASCII_LETTER_RE.findall(body)),
    }


def swapped_ascii_score(text: str) -> float:
    checked = 0
    swapped = 0
    for ch in printable(text):
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            checked += 1
            lo = code & 0xFF
            hi = code >> 8
            if 0x20 <= lo <= 0x7E and 0x20 <= hi <= 0x7E:
                swapped += 1
    return swapped / checked if checked else 0.0


def wide_candidate(text: str) -> bool:
    counts = char_counts(text)
    if counts["body_len"] == 0:
        return False
    jpish = counts["hiragana"] + counts["katakana"] + counts["cjk"] + counts["fullwidth"]
    if jpish:
        return True
    # Keep ASCII-only native resource strings only when they look intentional,
    # not one-character binary noise.
    return counts["body_len"] >= 3 and counts["latin"] >= 2


def classify(text: str) -> tuple[str, str, str]:
    body = printable(text)
    counts = char_counts(text)
    speaker = SPEAKER_RE.match(body)
    flags: list[str] = []
    if len(body) <= 3:
        flags.append("short")
    if counts["hiragana"] + counts["katakana"] == 0 and counts["cjk"] > 0:
        flags.append("kanji_only_or_mostly")
    if counts["latin"] >= 4 and counts["latin"] > counts["hiragana"] + counts["katakana"] + counts["cjk"]:
        flags.append("latin_dominated")
    if swapped_ascii_score(text) >= 0.35 and counts["hiragana"] + counts["katakana"] < 2:
        flags.append("byte_swapped_ascii_risk")
    if controls(text):
        flags.append("has_control_codes")

    if speaker:
        row_kind = "dialogue"
    elif DATE_RE.match(body):
        row_kind = "date_or_scene_title"
    elif len(body) <= 3:
        row_kind = "short_text"
    elif counts["latin"] >= 4 and counts["latin"] > counts["hiragana"] + counts["katakana"] + counts["cjk"]:
        row_kind = "system_or_meta_candidate"
    elif counts["hiragana"] + counts["katakana"] + counts["cjk"] + counts["fullwidth"] >= 1:
        row_kind = "narration_or_text"
    else:
        row_kind = "uncertain"

    if row_kind in {"dialogue", "narration_or_text"} and "byte_swapped_ascii_risk" not in flags:
        curated_kind = row_kind
    elif row_kind in {"short_text", "date_or_scene_title", "ui_or_title"}:
        curated_kind = row_kind
    else:
        curated_kind = "uncertain"
    return row_kind, curated_kind, "; ".join(flags)


def scan_payload(payload: bytes) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    i = 0
    n = len(payload)
    while i < n - 1:
        code = int.from_bytes(payload[i : i + 2], "little")
        if code == 0 or not allowed_unit(code):
            i += 2
            continue
        start = i
        units: list[int] = []
        while i < n - 1:
            code = int.from_bytes(payload[i : i + 2], "little")
            if code == 0:
                break
            if not allowed_unit(code):
                break
            units.append(code)
            i += 2
        terminated = i < n - 1 and int.from_bytes(payload[i : i + 2], "little") == 0
        if terminated and units:
            text = "".join(chr(unit) for unit in units)
            if wide_candidate(text):
                rows.append((start, text, "wide_native_crsa_candidate"))
                i += 2
                continue
        i = start + 2
    return rows


def find_source_dir() -> Path:
    for source_dir in SOURCE_DIRS:
        if (source_dir / "photonflowers11.rio").exists():
            return source_dir
    raise FileNotFoundError("Muv-Luv photonflowers Steam directory was not found")


def crsa_offsets(data: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        pos = data.find(CRSA_PATTERN, start)
        if pos < 0:
            return offsets
        offsets.append(pos)
        start = pos + 1


def extract_volume(path: Path) -> tuple[list[RawRow], dict[str, object]]:
    data = path.read_bytes()
    offsets = crsa_offsets(data)
    rows: list[RawRow] = []
    decrypt_errors = 0
    blocks_with_text = 0
    for block_offset in offsets:
        payload_offset = block_offset + CRSA_HEADER_SIZE
        try:
            payload, _ = read_encrypted_at(data, payload_offset, RIO_KEY)
        except Exception:
            decrypt_errors += 1
            continue
        block_rows = scan_payload(payload)
        if block_rows:
            blocks_with_text += 1
        for rel_offset, text, notes in block_rows:
            rows.append(
                RawRow(
                    rio_file=path.name,
                    block_offset=block_offset,
                    payload_offset=rel_offset,
                    text=text,
                    notes=notes,
                )
            )
    meta = {
        "rio_file": path.name,
        "bytes": path.stat().st_size,
        "crsa_candidate_blocks": len(offsets),
        "decrypt_errors": decrypt_errors,
        "decrypted_blocks": len(offsets) - decrypt_errors,
        "blocks_with_text": blocks_with_text,
        "rows": len(rows),
    }
    return rows, meta


def stable_id(row: RawRow) -> str:
    return f"pf:static:{row.rio_file}:{row.block_offset}:{row.payload_offset:08d}"


def to_csv_row(row: RawRow, csv_row: int) -> dict[str, str]:
    body = printable(row.text)
    speaker_match = SPEAKER_RE.match(body)
    speaker = speaker_match.group(1) if speaker_match else ""
    row_kind, curated_kind, flags = classify(row.text)
    return {
        "chapter": "photonflowers",
        "csv_row": str(csv_row),
        "stable_id": stable_id(row),
        "rio_file": row.rio_file,
        "scene": f"crsa:{row.rio_file}@{row.block_offset}",
        "speaker_jp": speaker,
        "jp_text": row.text,
        "jp_text_visible": visible(row.text),
        "control_codes": controls(row.text),
        "row_kind": row_kind,
        "curated_kind": curated_kind,
        "curation_evidence": "wide_native_crsa_utf16le_candidate",
        "crsa_file": row.rio_file,
        "block_offset": str(row.block_offset),
        "payload_offset": str(row.payload_offset),
        "notes": row.notes,
        "wide_flags": flags,
    }


def high_confidence_ids() -> set[str]:
    if not HIGH_CONFIDENCE_CSV.exists():
        return set()
    with HIGH_CONFIDENCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["stable_id"] for row in csv.DictReader(f)}


def audit(csv_rows: list[dict[str, str]], rio_meta: list[dict[str, object]]) -> dict[str, object]:
    ids = [row["stable_id"] for row in csv_rows]
    high_ids = high_confidence_ids()
    text_counts = Counter(row["jp_text_visible"] for row in csv_rows)
    suspicious = [
        {
            "stable_id": row["stable_id"],
            "reason": row["wide_flags"],
            "sample": row["jp_text_visible"][:160],
        }
        for row in csv_rows
        if "byte_swapped_ascii_risk" in row["wide_flags"] or row["row_kind"] == "uncertain"
    ][:200]
    return {
        "chapter": "photonflowers",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "wide native RIO/CRsa UTF-16LE extraction only",
        "english_fallback_used": False,
        "old_chinese_fallback_used": False,
        "fuzzy_fallback_used": False,
        "wide_total_rows": len(csv_rows),
        "high_confidence_rows_reference": len(high_ids),
        "high_confidence_ids_found_in_wide": sum(1 for sid in high_ids if sid in set(ids)),
        "unique_stable_id_count": len(set(ids)),
        "duplicate_stable_id_count": len(ids) - len(set(ids)),
        "empty_jp_text_count": sum(1 for row in csv_rows if not row["jp_text"]),
        "rio_file_row_counts": dict(Counter(row["rio_file"] for row in csv_rows)),
        "scene_count": len({row["scene"] for row in csv_rows}),
        "scene_row_counts": dict(Counter(row["scene"] for row in csv_rows)),
        "row_kind_counts": dict(Counter(row["row_kind"] for row in csv_rows)),
        "curated_kind_counts": dict(Counter(row["curated_kind"] for row in csv_rows)),
        "wide_flag_counts": dict(Counter(flag for row in csv_rows for flag in row["wide_flags"].split("; ") if flag)),
        "recognized_control_codes": sorted({code for row in csv_rows for code in row["control_codes"].split() if code}),
        "rows_with_control_codes": sum(1 for row in csv_rows if row["control_codes"]),
        "duplicate_text_anomalies_top": [
            {"jp_text_visible": text, "count": count}
            for text, count in text_counts.most_common(50)
            if count >= 10
        ],
        "possible_garble_or_misalignment": {
            "count": len(suspicious),
            "examples": suspicious,
        },
        "rio_meta": rio_meta,
    }


def write_status(audit_data: dict[str, object]) -> None:
    STATUS_PATH.write_text(
        f"""# photonflowers Wide Extraction Status

Generated: {audit_data['generated_at']}

This is the wide native RIO/CRsa extraction layer. It intentionally keeps short
and uncertain strings for completeness auditing. It is not a translation
worklist.

## Counts

- wide_total_rows: {audit_data['wide_total_rows']}
- high_confidence_rows_reference: {audit_data['high_confidence_rows_reference']}
- high_confidence_ids_found_in_wide: {audit_data['high_confidence_ids_found_in_wide']}
- unique_stable_id_count: {audit_data['unique_stable_id_count']}
- duplicate_stable_id_count: {audit_data['duplicate_stable_id_count']}
- scene_count: {audit_data['scene_count']}

## Row Kinds

```json
{json.dumps(audit_data['row_kind_counts'], ensure_ascii=False, indent=2)}
```

## Notes

- No translation, writeback, patch creation, English fallback, old Chinese fallback, or fuzzy fallback was used.
- The previous 5322-row table should be treated as a high-confidence candidate table, not a full native table.
""",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    source_dir = find_source_dir()
    rio_paths = sorted(source_dir.glob("photonflowers11.rio*"))
    rio_paths = [path for path in rio_paths if path.name in {"photonflowers11.rio", "photonflowers11.rio.002"}]
    raw_rows: list[RawRow] = []
    rio_meta: list[dict[str, object]] = []
    for rio_path in rio_paths:
        rows, meta = extract_volume(rio_path)
        raw_rows.extend(rows)
        rio_meta.append(meta)
        print(f"{rio_path.name}: rows={meta['rows']} blocks={meta['crsa_candidate_blocks']} errors={meta['decrypt_errors']}")
    raw_rows.sort(key=lambda row: (row.rio_file, row.block_offset, row.payload_offset, row.text))
    csv_rows = [to_csv_row(row, i) for i, row in enumerate(raw_rows, start=1)]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(csv_rows)
    audit_data = audit(csv_rows, rio_meta)
    AUDIT_PATH.write_text(json.dumps(audit_data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_status(audit_data)
    print(f"wrote {CSV_PATH}")
    print(f"wrote {AUDIT_PATH}")
    print(f"rows={audit_data['wide_total_rows']} duplicate_ids={audit_data['duplicate_stable_id_count']}")


if __name__ == "__main__":
    main()
