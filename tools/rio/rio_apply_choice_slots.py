from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from rio_apply_batch_slots_v2 import find_utf16_nul, raw_to_visible, read_bytes_chunked
from rio_reencrypt_one_line import RIO_KEY, read_encrypted_at, write_encrypted


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_TABLE = REPO_ROOT / "outputs" / "photonmelodies_text" / "photonmelodies_native_resource_worklist_v2.csv"
ENCRYPTED_DELTA = 11
VISIBLE_CONTROL_RE = re.compile(r"<(\d{2})>")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(64 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def visible_to_raw(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 10))

    return VISIBLE_CONTROL_RE.sub(repl, text)


def control_sequence(text: str) -> list[str]:
    return [f"{ord(ch):02d}" for ch in text if ord(ch) < 0x20 and ch != "\n"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def patch_choice_slots(
    base_rio: Path,
    batch_csv: Path,
    output_rio: Path,
    audit_json: Path,
    rows: set[int],
) -> dict[str, object]:
    source_rows = {row["stable_id"]: row for row in read_csv(SOURCE_TABLE)}
    batch_rows = [row for row in read_csv(batch_csv) if int(row["csv_row"]) in rows]
    if {int(row["csv_row"]) for row in batch_rows} != rows:
        raise ValueError("batch CSV does not contain all requested choice rows")

    data = bytearray(read_bytes_chunked(base_rio))
    row_audits: list[dict[str, object]] = []
    changed_ranges: list[tuple[int, int]] = []

    by_block: dict[int, list[tuple[dict[str, str], dict[str, str]]]] = {}
    for batch_row in batch_rows:
        source_row = source_rows[batch_row["stable_id"]]
        if source_row["crsa_file"] != base_rio.name:
            raise ValueError(f"base RIO mismatch row={batch_row['csv_row']}")
        by_block.setdefault(int(source_row["block_offset"]), []).append((batch_row, source_row))

    for block_offset, pairs in by_block.items():
        encrypted_offset = block_offset + ENCRYPTED_DELTA
        plain, encrypted_end = read_encrypted_at(data, encrypted_offset, RIO_KEY)
        original_plain = bytes(plain)
        patched = bytearray(plain)

        for batch_row, source_row in sorted(pairs, key=lambda pair: int(pair[1]["payload_offset"])):
            payload_offset = int(source_row["payload_offset"])
            jp_segment = source_row["jp_text"]
            slot_text_end = find_utf16_nul(patched, payload_offset)
            slot_end = slot_text_end + 2
            slot_capacity = slot_end - payload_offset
            raw = patched[payload_offset:slot_text_end].decode("utf-16le")

            if not raw.startswith(jp_segment + r"\|"):
                raise ValueError(
                    f"choice slot prefix mismatch row={batch_row['csv_row']} "
                    f"raw={raw_to_visible(raw)}"
                )
            if not raw.endswith(chr(2)):
                raise ValueError(f"choice slot does not end with <02> row={batch_row['csv_row']}")

            cn_visible = batch_row["cn_text"]
            if "<" in cn_visible:
                raise ValueError(f"choice cn_text must not contain visible control tags row={batch_row['csv_row']}")
            cn_branch = visible_to_raw(cn_visible)
            replacement_raw = cn_branch + r"\|" + cn_branch + chr(2)
            if control_sequence(raw) != control_sequence(replacement_raw):
                raise ValueError(f"choice control mismatch row={batch_row['csv_row']}")

            replacement = replacement_raw.encode("utf-16le") + b"\x00\x00"
            if len(replacement) > slot_capacity:
                raise ValueError(
                    f"choice replacement does not fit row={batch_row['csv_row']} "
                    f"needed={len(replacement)} capacity={slot_capacity}"
                )

            patched[payload_offset:slot_end] = b"\x00" * slot_capacity
            patched[payload_offset:payload_offset + len(replacement)] = replacement
            changed_ranges.append((payload_offset, slot_end))
            row_audits.append(
                {
                    "csv_row": batch_row["csv_row"],
                    "stable_id": batch_row["stable_id"],
                    "block_offset": block_offset,
                    "payload_offset": payload_offset,
                    "source_visible": raw_to_visible(raw),
                    "cn_visible": raw_to_visible(replacement_raw),
                    "slot_capacity": slot_capacity,
                    "needed_bytes": len(replacement),
                    "remaining_bytes": slot_capacity - len(replacement),
                }
            )

        encoded = write_encrypted(bytes(patched), RIO_KEY, data[encrypted_offset:encrypted_offset + 8])
        if len(encoded) != encrypted_end - encrypted_offset:
            raise ValueError("encoded block size changed unexpectedly")
        data[encrypted_offset:encrypted_end] = encoded

        changed = bytearray(len(patched))
        for start, end in changed_ranges:
            changed[start:end] = b"\x01" * (end - start)
        outside_changes = []
        for idx, (before, after) in enumerate(zip(original_plain, patched)):
            if before != after and not changed[idx]:
                outside_changes.append(idx)
                if len(outside_changes) >= 20:
                    break
        if outside_changes:
            raise ValueError(f"unexpected plaintext changes outside choice slots: {outside_changes[:20]}")

    output_rio.parent.mkdir(parents=True, exist_ok=True)
    output_rio.write_bytes(data)
    report = {
        "base_rio": str(base_rio),
        "output_rio": str(output_rio),
        "base_sha256": sha256(base_rio),
        "output_sha256": sha256(output_rio),
        "rows_changed": len(row_audits),
        "changed_ranges": changed_ranges,
        "row_audits": row_audits,
        "status": "pass",
    }
    audit_json.parent.mkdir(parents=True, exist_ok=True)
    audit_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-rio", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output-rio", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--rows", nargs="+", type=int, required=True)
    args = parser.parse_args()
    report = patch_choice_slots(args.base_rio, args.batch, args.output_rio, args.audit_json, set(args.rows))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
