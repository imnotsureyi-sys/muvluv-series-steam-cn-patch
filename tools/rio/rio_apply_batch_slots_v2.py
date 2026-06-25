from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from rio_reencrypt_one_line import RIO_KEY, read_encrypted_at, write_encrypted


REPO_ROOT = Path(__file__).resolve().parents[2]
STEAM_GAME_DIR = Path(r"D:\Steam\steamapps\common\Muv-Luv photonmelodies")
SOURCE_TABLE = REPO_ROOT / "outputs" / "photonmelodies_text" / "photonmelodies_native_resource_worklist_v2.csv"
DEFAULT_BATCH = REPO_ROOT / "outputs" / "photonmelodies_cn" / "batches" / "batch_001_010_adoration_resurrection_revised.csv"
DEFAULT_OUT_DIR = REPO_ROOT / "outputs" / "photonmelodies_cn" / "repack" / "batch_001_010"

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


def read_bytes_chunked(path: Path, chunk_size: int = 64 * 1024 * 1024) -> bytes:
    data = bytearray()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            data.extend(chunk)
    return bytes(data)


def visible_to_raw(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 10))

    return VISIBLE_CONTROL_RE.sub(repl, text)


def raw_to_visible(text: str) -> str:
    return "".join(f"<{ord(ch):02d}>" if ord(ch) < 0x20 else ch for ch in text)


def find_utf16_nul(data: bytes | bytearray, start: int) -> int:
    pos = start
    while pos + 1 < len(data):
        if data[pos] == 0 and data[pos + 1] == 0:
            return pos
        pos += 2
    raise ValueError(f"unterminated UTF-16LE string at {start}")


def load_source_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["stable_id"]: row for row in csv.DictReader(handle)}


def load_batch(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def control_sequence(text: str) -> list[str]:
    return [f"{ord(ch):02d}" for ch in text if ord(ch) < 0x20 and ch != "\n"]


def patch_slots(base_rio: Path, batch_csv: Path, output_rio: Path, audit_json: Path) -> dict[str, object]:
    source_rows = load_source_rows(SOURCE_TABLE)
    batch_rows = load_batch(batch_csv)
    data = bytearray(read_bytes_chunked(base_rio))
    original_data = bytes(data)

    rows_by_file_block: dict[tuple[str, int], list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    for batch_row in batch_rows:
        stable_id = batch_row["stable_id"]
        if stable_id not in source_rows:
            raise KeyError(f"stable_id not found in source table: {stable_id}")
        source_row = source_rows[stable_id]
        if not batch_row.get("cn_text"):
            raise ValueError(f"empty cn_text row={batch_row.get('csv_row')} stable_id={stable_id}")
        rows_by_file_block[(source_row["crsa_file"], int(source_row["block_offset"]))].append((batch_row, source_row))

    if any(base_rio.name != rio_file for rio_file, _block in rows_by_file_block):
        raise ValueError(f"base RIO name mismatch for requested rows: {base_rio.name}")

    row_audits: list[dict[str, object]] = []
    slot_audits: list[dict[str, object]] = []

    for (rio_file, block_offset), rows in sorted(rows_by_file_block.items(), key=lambda item: item[0][1]):
        encrypted_offset = block_offset + ENCRYPTED_DELTA
        plain, encrypted_end = read_encrypted_at(data, encrypted_offset, RIO_KEY)
        original_plain = bytes(plain)
        patched = bytearray(plain)

        sorted_rows = sorted(rows, key=lambda pair: int(pair[1]["payload_offset"]))
        processed_stable_ids: set[str] = set()
        changed_ranges: list[tuple[int, int]] = []

        for batch_row, source_row in sorted_rows:
            if batch_row["stable_id"] in processed_stable_ids:
                continue

            payload_offset = int(source_row["payload_offset"])
            declared_jp = source_row["jp_text"].encode("utf-16le")
            if patched[payload_offset:payload_offset + len(declared_jp)] != declared_jp:
                raise ValueError(
                    f"text not found at payload offset row={batch_row['csv_row']} "
                    f"stable_id={batch_row['stable_id']}"
                )

            jp_end = find_utf16_nul(patched, payload_offset)
            en_start = jp_end + 2
            en_end = find_utf16_nul(patched, en_start)
            slot_end = en_end + 2
            slot_capacity = slot_end - payload_offset
            jp_raw = patched[payload_offset:jp_end].decode("utf-16le")

            members: list[tuple[dict[str, str], dict[str, str]]] = []
            for candidate_batch, candidate_source in sorted_rows:
                candidate_offset = int(candidate_source["payload_offset"])
                if payload_offset <= candidate_offset < jp_end:
                    candidate_jp = candidate_source["jp_text"].encode("utf-16le")
                    if patched[candidate_offset:candidate_offset + len(candidate_jp)] != candidate_jp:
                        raise ValueError(
                            f"fragment text not found row={candidate_batch['csv_row']} "
                            f"stable_id={candidate_batch['stable_id']}"
                        )
                    members.append((candidate_batch, candidate_source))

            cn_raw = "".join(visible_to_raw(member_batch["cn_text"]) for member_batch, _ in members)
            if control_sequence(jp_raw) != control_sequence(cn_raw):
                raise ValueError(
                    "control mismatch after fragment merge "
                    f"slot_start={payload_offset} rows={[m[0]['csv_row'] for m in members]}"
                )

            cn_bytes = cn_raw.encode("utf-16le")
            needed = len(cn_bytes) + 4
            if needed > slot_capacity:
                raise ValueError(
                    f"cn_text does not fit rows={[m[0]['csv_row'] for m in members]} "
                    f"needed={needed} capacity={slot_capacity}"
                )

            replacement = cn_bytes + b"\x00\x00\x00\x00"
            patched[payload_offset:slot_end] = b"\x00" * slot_capacity
            patched[payload_offset:payload_offset + len(replacement)] = replacement
            changed_ranges.append((payload_offset, slot_end))

            member_rows = [member_batch["csv_row"] for member_batch, _ in members]
            slot_audits.append(
                {
                    "rio_file": rio_file,
                    "block_offset": block_offset,
                    "slot_payload_offset": payload_offset,
                    "csv_rows": member_rows,
                    "stable_ids": [member_batch["stable_id"] for member_batch, _ in members],
                    "source_visible": raw_to_visible(jp_raw),
                    "cn_visible": raw_to_visible(cn_raw),
                    "slot_capacity": slot_capacity,
                    "cn_bytes": len(cn_bytes),
                    "needed_bytes": needed,
                    "remaining_bytes": slot_capacity - needed,
                    "merged_fragments": len(members) > 1,
                }
            )
            for member_batch, member_source in members:
                processed_stable_ids.add(member_batch["stable_id"])
                row_audits.append(
                    {
                        "csv_row": member_batch["csv_row"],
                        "stable_id": member_batch["stable_id"],
                        "payload_offset": int(member_source["payload_offset"]),
                        "slot_payload_offset": payload_offset,
                        "merged_slot_rows": member_rows,
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
            raise ValueError(f"unexpected plaintext changes outside slots: {outside_changes[:20]}")

    output_rio.parent.mkdir(parents=True, exist_ok=True)
    output_rio.write_bytes(data)

    # Re-open output once and verify every merged slot's CN string at the original slot start.
    output_bytes = read_bytes_chunked(output_rio)
    patched_plain_by_block: dict[int, bytes] = {}
    for block_offset in {int(slot["block_offset"]) for slot in slot_audits}:
        patched_plain_by_block[block_offset], _ = read_encrypted_at(
            output_bytes,
            block_offset + ENCRYPTED_DELTA,
            RIO_KEY,
        )
    for slot in slot_audits:
        block_offset = int(slot["block_offset"])
        patched_plain = patched_plain_by_block[block_offset]
        expected = visible_to_raw(str(slot["cn_visible"])).encode("utf-16le") + b"\x00\x00\x00\x00"
        offset = int(slot["slot_payload_offset"])
        if patched_plain[offset:offset + len(expected)] != expected:
            raise ValueError(f"post-write CN audit failed rows={slot['csv_rows']}")

    report = {
        "base_rio": str(base_rio),
        "output_rio": str(output_rio),
        "batch_csv": str(batch_csv),
        "source_table": str(SOURCE_TABLE),
        "base_sha256": hashlib.sha256(original_data).hexdigest(),
        "output_sha256": sha256(output_rio),
        "rows_changed": len(row_audits),
        "slots_changed": len(slot_audits),
        "merged_fragment_slots": [slot for slot in slot_audits if slot["merged_fragments"]],
        "rio_file": base_rio.name,
        "block_offsets": sorted({slot["block_offset"] for slot in slot_audits}),
        "method": "overwrite JP+EN adjacent UTF-16LE slots in place; supports multi-block and split extracted rows",
        "row_audits": row_audits,
        "slot_audits": slot_audits,
    }
    audit_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--base-rio", type=Path, default=STEAM_GAME_DIR / "photonmelodies11.rio.002")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    output_rio = args.out_dir / args.base_rio.name
    audit_json = args.out_dir / "batch_001_slot_patch_audit.json"
    report = patch_slots(args.base_rio, args.batch, output_rio, audit_json)
    print(f"output_rio={output_rio}")
    print(f"audit_json={audit_json}")
    print(f"rows_changed={report['rows_changed']}")
    print(f"slots_changed={report['slots_changed']}")
    print(f"merged_fragment_slots={len(report['merged_fragment_slots'])}")
    print(f"output_sha256={report['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
