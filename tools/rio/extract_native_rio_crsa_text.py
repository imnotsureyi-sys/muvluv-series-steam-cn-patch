#!/usr/bin/env python3
"""Extract photonflowers native RIO/CRsa Japanese text.

Extraction only: no translation, no writeback, no patch creation.
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
CSV_PATH = OUTPUT_ROOT / "photonflowers_native_resource_worklist_v1.csv"
AUDIT_PATH = OUTPUT_ROOT / "audit_native_resource_worklist_v1.json"
SCHEMA_PATH = OUTPUT_ROOT / "SCHEMA.md"
README_PATH = OUTPUT_ROOT / "README.md"
STATUS_PATH = REPO_ROOT / "chapters" / "photonflowers" / "extraction_status.md"

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
]

SPEAKER_RE = re.compile(r"^【([^】]{1,40})】")
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


def jp_signal(code: int) -> bool:
    return (
        0x3040 <= code <= 0x30FF
        or code in (0x3001, 0x3002, 0x300C, 0x300D, 0x3010, 0x3011, 0x2026, 0x2015)
        or 0xFF01 <= code <= 0xFF5E
    )


def jp_core(code: int) -> bool:
    return 0x3040 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FFF or 0xFF01 <= code <= 0xFF5E


def printable(text: str) -> str:
    return "".join(ch for ch in text if not (1 <= ord(ch) <= 31))


def visible(text: str) -> str:
    return "".join(f"<{ord(ch):02X}>" if 1 <= ord(ch) <= 31 else ch for ch in text)


def controls(text: str) -> str:
    codes = sorted({ord(ch) for ch in text if 1 <= ord(ch) <= 31})
    return " ".join(f"U+{code:04X}" for code in codes)


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


def strip_english_tail(text: str) -> tuple[str, str]:
    if "\\|" not in text:
        if ":" in text:
            left, right = text.split(":", 1)
            left_body = printable(left)
            right_body = printable(right)
            left_jp = sum(1 for ch in left_body if 0x3040 <= ord(ch) <= 0x30FF or 0x4E00 <= ord(ch) <= 0x9FFF)
            right_latin = len(ASCII_LETTER_RE.findall(right_body))
            if left_jp >= 2 and right_latin >= 4 and right_latin > left_jp:
                return left, "source_string_had_colon_english_tail_excluded"
        return text, ""
    return text.split("\\|", 1)[0], "source_string_had_pipe_english_tail_excluded"


def trim_alignment_prefix(text: str) -> tuple[str, str]:
    starts = ["【", "「", "『", "（", "《", "マ", "シ", "セ", "プ", "ク", "こ", "そ", "あ", "い", "う", "え", "お"]
    hits = [text.find(start) for start in starts if text.find(start) > 0]
    if not hits:
        return text, ""
    idx = min(hits)
    if idx <= 2:
        return text[idx:], "trimmed_probable_alignment_prefix"
    return text, ""


def normalize_candidate(text: str) -> tuple[str, str]:
    notes: list[str] = []
    text, note = strip_english_tail(text)
    if note:
        notes.append(note)
    text, note = trim_alignment_prefix(text)
    if note:
        notes.append(note)
    return text, "; ".join(notes)


def looks_like_japanese(text: str) -> bool:
    body = printable(text)
    if len(body) < 2:
        return False
    signal_count = sum(1 for ch in body if jp_signal(ord(ch)))
    core_count = sum(1 for ch in body if jp_core(ord(ch)))
    kana_count = sum(1 for ch in body if 0x3040 <= ord(ch) <= 0x30FF)
    jp_letter_count = sum(1 for ch in body if 0x3041 <= ord(ch) <= 0x30FA or 0x4E00 <= ord(ch) <= 0x9FFF)
    has_quote = any(ch in body for ch in "「」『』【】。、？！…〜～")
    starts_dialogue = body.startswith("【")
    if signal_count < 1 or core_count < 2:
        return False
    if kana_count < 2 and swapped_ascii_score(body) >= 0.35:
        return False
    if not starts_dialogue:
        if len(body) < 4 and kana_count < 2:
            return False
        if kana_count < 2 and not (has_quote and core_count >= 3):
            return False
    latin_count = len(ASCII_LETTER_RE.findall(body))
    if latin_count >= 4 and latin_count > jp_letter_count:
        return False
    if latin_count and latin_count > max(8, int(len(body) * 0.45)):
        return False
    return True


def scan_payload(payload: bytes) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    i = 0
    n = len(payload)
    while i < n - 1:
        code = int.from_bytes(payload[i : i + 2], "little")
        if code == 0 or 1 <= code <= 31 or not allowed_unit(code):
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
        if terminated and len(units) >= 2:
            text = "".join(chr(unit) for unit in units)
            text, note = normalize_candidate(text)
            if looks_like_japanese(text):
                rows.append((start, text, note))
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
        off = data.find(CRSA_PATTERN, start)
        if off < 0:
            return offsets
        offsets.append(off)
        start = off + 1


def extract_rio(path: Path) -> tuple[list[RawRow], dict[str, object]]:
    data = path.read_bytes()
    offsets = crsa_offsets(data)
    rows: list[RawRow] = []
    decrypt_errors = 0
    blocks_with_text = 0
    for block_offset in offsets:
        try:
            payload, _ = read_encrypted_at(data, block_offset + CRSA_HEADER_SIZE, RIO_KEY)
        except Exception:
            decrypt_errors += 1
            continue
        strings = scan_payload(payload)
        if strings:
            blocks_with_text += 1
        for payload_offset, text, note in strings:
            rows.append(RawRow(path.name, block_offset, payload_offset, text, note))
    return rows, {
        "rio_file": path.name,
        "bytes": path.stat().st_size,
        "crsa_candidate_blocks": len(offsets),
        "decrypt_errors": decrypt_errors,
        "decrypted_blocks": len(offsets) - decrypt_errors,
        "blocks_with_text": blocks_with_text,
        "rows": len(rows),
    }


def stable_id(row: RawRow) -> str:
    return f"pf:static:{row.rio_file}:{row.block_offset}:{row.payload_offset:08d}"


def classify(text: str) -> tuple[str, str, str]:
    match = SPEAKER_RE.match(text)
    if match:
        return match.group(1), "dialogue", "dialogue"
    if any(token in text for token in ("セーブ", "データ", "システム", "ロード", "タイトル", "チャプター")):
        return "", "ui_or_title", "ui_or_title"
    if len(printable(text)) <= 32 and not any(ch in text for ch in "。、？！「」"):
        return "", "ui_or_title", "ui_or_title"
    return "", "narration", "narration"


def to_csv_row(row: RawRow, index: int) -> dict[str, str]:
    speaker, row_kind, curated_kind = classify(row.text)
    return {
        "chapter": "photonflowers",
        "csv_row": str(index),
        "stable_id": stable_id(row),
        "rio_file": row.rio_file,
        "scene": f"crsa:{row.rio_file}@{row.block_offset}",
        "speaker_jp": speaker,
        "jp_text": row.text,
        "jp_text_visible": visible(row.text),
        "control_codes": controls(row.text),
        "row_kind": row_kind,
        "curated_kind": curated_kind,
        "curation_evidence": "native_crsa_utf16le_japanese_signal",
        "crsa_file": row.rio_file,
        "block_offset": str(row.block_offset),
        "payload_offset": str(row.payload_offset),
        "notes": row.notes or "pf_native_resource_text; true_decoded_crsa_scene",
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(rows: list[dict[str, str]], rio_meta: list[dict[str, object]]) -> dict[str, object]:
    ids = [row["stable_id"] for row in rows]
    scene_counts = Counter(row["scene"] for row in rows)
    rio_counts = Counter(row["rio_file"] for row in rows)
    kind_counts = Counter(row["row_kind"] for row in rows)
    speaker_counts = Counter(row["speaker_jp"] for row in rows if row["speaker_jp"])
    text_counts = Counter(row["jp_text"] for row in rows)
    required = ["chapter", "csv_row", "stable_id", "rio_file", "scene", "jp_text", "crsa_file", "block_offset", "payload_offset"]
    suspicious = []
    for row in rows:
        body = printable(row["jp_text"])
        kana_count = sum(1 for ch in body if 0x3040 <= ord(ch) <= 0x30FF)
        latin_count = len(ASCII_LETTER_RE.findall(body))
        if latin_count > max(8, int(len(body) * 0.45)):
            suspicious.append({"stable_id": row["stable_id"], "reason": "latin_ratio_high", "sample": row["jp_text_visible"][:160]})
        elif kana_count < 2 and swapped_ascii_score(body) >= 0.35:
            suspicious.append({"stable_id": row["stable_id"], "reason": "byte_swapped_ascii_like", "sample": row["jp_text_visible"][:160]})
    repeated = [
        {"jp_text_visible": visible(text), "count": count}
        for text, count in text_counts.most_common(30)
        if count >= 10
    ]
    return {
        "chapter": "photonflowers",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "native RIO/CRsa UTF-16LE extraction only",
        "english_fallback_used": False,
        "old_chinese_fallback_used": False,
        "fuzzy_fallback_used": False,
        "row_count": len(rows),
        "unique_stable_id_count": len(set(ids)),
        "duplicate_stable_id_count": len(ids) - len(set(ids)),
        "empty_jp_text_count": sum(1 for row in rows if not row["jp_text"]),
        "empty_required_fields": {field: sum(1 for row in rows if not row.get(field, "")) for field in required},
        "rio_file_row_counts": dict(sorted(rio_counts.items())),
        "scene_count": len(scene_counts),
        "scene_row_counts": dict(sorted(scene_counts.items())),
        "row_kind_counts": dict(sorted(kind_counts.items())),
        "speaker_row_count": sum(1 for row in rows if row["speaker_jp"]),
        "speaker_count": len(speaker_counts),
        "top_speakers": dict(speaker_counts.most_common(30)),
        "recognized_control_codes": sorted({code for row in rows for code in row["control_codes"].split() if code}),
        "rows_with_control_codes": sum(1 for row in rows if row["control_codes"]),
        "duplicate_text_anomalies_top": repeated,
        "possible_garble_or_misalignment": {"count": len(suspicious), "samples": suspicious[:50]},
        "rio_scan": rio_meta,
    }


def write_docs(source_dir: Path, audit_data: dict[str, object]) -> None:
    SCHEMA_PATH.write_text(
        """# photonflowers Native RIO/CRsa Text Schema

Primary table: `photonflowers_native_resource_worklist_v1.csv`

This is extraction only. It contains Japanese text decoded from photonflowers
native RIO/CRsa payloads. No English slot, old Chinese text, or fuzzy fallback
is used.

Columns:

- `chapter`: always `photonflowers`.
- `csv_row`: 1-based row number in this table.
- `stable_id`: stable locator from `rio_file`, `block_offset`, and `payload_offset`.
- `rio_file`: source RIO volume.
- `scene`: `crsa:<rio_file>@<block_offset>`.
- `speaker_jp`: speaker parsed from leading `【speaker】` when present.
- `jp_text`: Japanese/source text with control codes preserved.
- `jp_text_visible`: control-code visible form using tags such as `<01>`.
- `control_codes`: unique control codes in the row.
- `row_kind`, `curated_kind`: broad extraction kind.
- `curation_evidence`: why the row was retained.
- `crsa_file`: source RIO volume containing the CRsa block.
- `block_offset`: byte offset of the CRsa block in the RIO file.
- `payload_offset`: byte offset of the UTF-16LE string in the decrypted payload.
- `notes`: extraction notes. For native `JP\\|EN` strings, only the JP side is retained.
""",
        encoding="utf-8",
    )
    README_PATH.write_text(
        f"""# photonflowers Native Text Extraction

Source directory: `{source_dir}`

Artifacts:

- `photonflowers_native_resource_worklist_v1.csv`
- `audit_native_resource_worklist_v1.json`
- `SCHEMA.md`

Scope:

- Native RIO/CRsa text only.
- Extraction only; no translation, writeback, or patch.
- No TDA/ATE/egpack path is used.
- No English fallback, old Chinese fallback, or fuzzy fallback is used.

Audit headline:

- rows: {audit_data['row_count']}
- unique stable ids: {audit_data['unique_stable_id_count']}
- duplicate stable ids: {audit_data['duplicate_stable_id_count']}
- scenes: {audit_data['scene_count']}
- speaker rows: {audit_data['speaker_row_count']}
- rows with control codes: {audit_data['rows_with_control_codes']}
""",
        encoding="utf-8",
    )
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(
        f"""# photonflowers extraction status

Status: native RIO/CRsa extraction v1 generated.

Completed:

- Extracted photonflowers native RIO/CRsa Japanese text.
- Parsed `speaker_jp` from leading `【speaker】`.
- Generated `stable_id` from `rio_file + block_offset + payload_offset`.
- Preserved control codes in `jp_text` and rendered them in `jp_text_visible`.
- Excluded English tails from native `JP\\|EN` UI strings.
- Did not translate, write back, or build a patch.

Source: `{source_dir}`

Artifacts:

- `outputs/photonflowers_text/photonflowers_native_resource_worklist_v1.csv`
- `outputs/photonflowers_text/SCHEMA.md`
- `outputs/photonflowers_text/README.md`
- `outputs/photonflowers_text/audit_native_resource_worklist_v1.json`

Audit:

- rows: {audit_data['row_count']}
- unique stable IDs: {audit_data['unique_stable_id_count']}
- duplicate stable IDs: {audit_data['duplicate_stable_id_count']}
- empty JP text rows: {audit_data['empty_jp_text_count']}
- scenes: {audit_data['scene_count']}
- speaker rows: {audit_data['speaker_row_count']}
- possible garble/misalignment flags: {audit_data['possible_garble_or_misalignment']['count']}
""",
        encoding="utf-8",
    )


def main() -> int:
    source_dir = find_source_dir()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    raw_rows: list[RawRow] = []
    rio_meta: list[dict[str, object]] = []
    for rio_path in sorted(source_dir.glob("photonflowers11.rio*")):
        if rio_path.suffix == ".ici":
            continue
        rows, meta = extract_rio(rio_path)
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
    write_docs(source_dir, audit_data)
    audit_data["artifacts"] = {
        "csv": str(CSV_PATH.relative_to(REPO_ROOT)),
        "schema": str(SCHEMA_PATH.relative_to(REPO_ROOT)),
        "readme": str(README_PATH.relative_to(REPO_ROOT)),
        "status": str(STATUS_PATH.relative_to(REPO_ROOT)),
    }
    audit_data["sha256"] = {
        str(path.relative_to(REPO_ROOT)): sha256(path)
        for path in (CSV_PATH, SCHEMA_PATH, README_PATH, STATUS_PATH)
    }
    AUDIT_PATH.write_text(json.dumps(audit_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {CSV_PATH}")
    print(f"wrote {AUDIT_PATH}")
    print(f"rows={audit_data['row_count']} duplicate_ids={audit_data['duplicate_stable_id_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
