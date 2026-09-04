"""Stage reviewed fixed-extent CRsa edits in new RIO volume copies.

The Photon Melodies loader rejects CRsa redirects into later archive volumes,
even when the redirected record is byte-identical.  This builder therefore
starts from hash-locked clean volumes, changes only reviewed CRsa extents, and
writes new copies for packaging.  It never installs files or overwrites inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from rUGP.formats.rio.crsa import (
    decode_crsa_encrypted,
    encode_crsa_encrypted,
    read_crsa_record,
)
from rUGP.formats.rio.crsa_vm_edit import digest, edit_native_fields, require_hash
from rUGP.formats.rio.crypto import RIO_KEY, decode_encrypted_block, decode_extent_offset


REPORT_NAME = "crsa-native-volume-stage.json"
CHUNK_SIZE = 8 * 1024 * 1024


def hash_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def _compare_span(left, right, start: int, end: int, label: str) -> None:
    left.seek(start)
    right.seek(start)
    remaining = end - start
    while remaining:
        count = min(CHUNK_SIZE, remaining)
        if left.read(count) != right.read(count):
            raise ValueError(f"non-target volume bytes changed: {label}")
        remaining -= count


def _verify_non_target_bytes(source: Path, staged: Path,
                             ranges: list[tuple[int, int]], size: int) -> None:
    cursor = 0
    with source.open("rb") as before, staged.open("rb") as after:
        for start, end in ranges:
            _compare_span(before, after, cursor, start, source.name)
            cursor = end
        _compare_span(before, after, cursor, size, source.name)


def _validate_locations(source_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    source_dir = source_dir.resolve(strict=True)
    output_dir = output_dir.resolve()
    if not source_dir.is_dir():
        raise ValueError("source directory is not a directory")
    if output_dir.exists():
        raise ValueError("output directory must be new")
    if not output_dir.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    if (output_dir == source_dir or source_dir in output_dir.parents
            or output_dir in source_dir.parents):
        raise ValueError("output directory must be separate from the source tree")
    return source_dir, output_dir


def build(spec: dict, source_dir: Path, output_dir: Path) -> dict:
    if spec.get("schema") != "photon-crsa-native-increment/v1":
        raise ValueError("unsupported native increment schema")
    if spec.get("unit_size") != 4 or spec.get("game") not in ("pf", "pm"):
        raise ValueError("unsupported Photon layout")
    if spec.get("base_ruo_sha256") is not None:
        raise ValueError("volume staging requires clean-volume inputs without an inherited RUO")
    source_dir, output_dir = _validate_locations(source_dir, output_dir)

    volumes: dict[str, dict] = {}
    input_stats: dict[Path, tuple[int, int]] = {}
    logical_cursor = 0
    for expected in spec.get("volumes", []):
        name = expected.get("name")
        if not name or Path(name).name != name or name == REPORT_NAME or name in volumes:
            raise ValueError("volume names must be unique basenames")
        if expected.get("logical_offset") != logical_cursor:
            raise ValueError("volume logical offsets must be contiguous and ordered")
        path = (source_dir / name).resolve(strict=True)
        if path.parent != source_dir:
            raise ValueError("source volume escaped the source directory")
        stat = path.stat()
        if stat.st_size != expected.get("bytes"):
            raise ValueError("source volume extent changed")
        require_hash(hash_file(path), expected.get("sha256", ""), "source volume")
        volume = dict(expected)
        volume["path"] = path
        volumes[name] = volume
        input_stats[path] = (stat.st_size, stat.st_mtime_ns)
        logical_cursor += stat.st_size
    if not volumes:
        raise ValueError("increment has no source volumes")

    prepared: dict[str, list[dict]] = {name: [] for name in volumes}
    reports: list[dict] = []
    keys: set[int] = set()
    stable_ids: set[str] = set()
    for block in spec.get("blocks", []):
        volume_name = block.get("volume")
        if volume_name not in volumes:
            raise ValueError("CRsa block refers to an unknown volume")
        volume = volumes[volume_name]
        key = int(block["source_raw_key"], 0)
        if key in keys:
            raise ValueError("duplicate CRsa route key")
        keys.add(key)
        block_offset = block["block_offset"]
        if decode_extent_offset(key, 4) != volume["logical_offset"] + block_offset:
            raise ValueError("CRsa physical extent does not match its logical route")
        original = read_crsa_record(volume["path"], block_offset)
        require_hash(digest(original.record), block["effective_record_sha256"], "effective CRsa")
        for entry in block["entries"]:
            stable_id = entry["stable_id"]
            if stable_id in stable_ids:
                raise ValueError("duplicate stable ID across blocks")
            stable_ids.add(stable_id)
        identity = original.header + encode_crsa_encrypted(
            original.plaintext, template_header=original.encrypted_header)
        if identity != original.record:
            raise ValueError("identity reencode mismatch")
        edited = edit_native_fields(
            original.plaintext, spec["game"], block["entries"], block["payload_sha256"])
        encrypted = encode_crsa_encrypted(
            edited.payload, template_header=original.encrypted_header)
        plain, consumed, _ = decode_crsa_encrypted(encrypted)
        if plain != edited.payload or consumed != len(encrypted):
            raise ValueError("strict encrypted readback mismatch")
        if decode_encrypted_block(encrypted, RIO_KEY).plaintext != edited.payload:
            raise ValueError("independent compatible readback mismatch")
        record = original.header + encrypted
        if len(record) != len(original.record):
            raise ValueError("volume staging supports fixed-extent CRsa records only")
        end = block_offset + len(record)
        if block_offset < 0 or end > volume["bytes"]:
            raise ValueError("CRsa record is outside its source volume")
        prepared[volume_name].append({
            "offset": block_offset,
            "before": original.record,
            "after": record,
        })
        reports.append(dict(
            volume=volume_name,
            block_offset=block_offset,
            source_raw_key=block["source_raw_key"],
            record_before_sha256=digest(original.record),
            record_after_sha256=digest(record),
            record_before_bytes=len(original.record),
            record_after_bytes=len(record),
            **edited.report,
        ))
    if not reports:
        raise ValueError("increment has no reviewed CRsa blocks")

    for name, replacements in prepared.items():
        replacements.sort(key=lambda item: item["offset"])
        previous_end = 0
        for item in replacements:
            if item["offset"] < previous_end:
                raise ValueError(f"overlapping CRsa record extents: {name}")
            previous_end = item["offset"] + len(item["before"])
    for path, original_stat in input_stats.items():
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != original_stat:
            raise ValueError("source volume changed during build")

    staged_volume_reports = []
    with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}-", dir=output_dir.parent) as temp:
        stage_root = Path(temp) / output_dir.name
        stage_root.mkdir()
        for name, volume in volumes.items():
            replacements = prepared[name]
            if not replacements:
                staged_volume_reports.append(dict(
                    name=name,
                    bytes=volume["bytes"],
                    source_sha256=volume["sha256"],
                    staged=False,
                    staged_sha256=None,
                    block_count=0,
                ))
                continue
            destination = stage_root / name
            shutil.copyfile(volume["path"], destination)
            with destination.open("r+b") as stream:
                for item in replacements:
                    stream.seek(item["offset"])
                    if stream.read(len(item["before"])) != item["before"]:
                        raise ValueError("staged CRsa source bytes changed before write")
                    stream.seek(item["offset"])
                    stream.write(item["after"])
                stream.flush()
                os.fsync(stream.fileno())
            if destination.stat().st_size != volume["bytes"]:
                raise ValueError("staged volume extent changed")
            ranges = [
                (item["offset"], item["offset"] + len(item["before"]))
                for item in replacements
            ]
            _verify_non_target_bytes(volume["path"], destination, ranges, volume["bytes"])
            for item in replacements:
                actual = read_crsa_record(destination, item["offset"])
                if actual.record != item["after"]:
                    raise ValueError("staged CRsa record/readback mismatch")
            staged_volume_reports.append(dict(
                name=name,
                bytes=volume["bytes"],
                source_sha256=volume["sha256"],
                staged=True,
                staged_sha256=hash_file(destination),
                block_count=len(replacements),
            ))

        for path, original_stat in input_stats.items():
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != original_stat:
                raise ValueError("source volume changed during staging")
        report = dict(
            schema="photon-crsa-native-volume-stage/v1",
            game=spec["game"],
            transport="fixed_extent_volume_stage",
            increment_sha256=digest(json.dumps(
                spec, ensure_ascii=False, sort_keys=True).encode("utf-8")),
            volumes=staged_volume_reports,
            blocks=reports,
            block_count=len(reports),
            entry_count=len(stable_ids),
            modified_volume_count=sum(row["staged"] for row in staged_volume_reports),
            native_increment_validation=dict(
                whole_input_hashes=True,
                identity_reencode=True,
                strict_all_checksums=True,
                independent_plaintext_readback=True,
                all_native_commands_read_back=True,
                reviewed_storage_contracts_enforced=True,
                fixed_record_extents=True,
                whole_output_hashes=True,
                non_target_volume_bytes_preserved=True,
                source_messages_and_voices_preserved=True,
                output_contains_only_modified_volumes=True,
                installed=False,
                runtime_tested=False,
            ),
        )
        (stage_root / REPORT_NAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stage_root.rename(output_dir)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    report = build(spec, args.source_dir, args.output_dir)
    print(json.dumps(dict(
        blocks=report["block_count"],
        entries=report["entry_count"],
        staged_volumes=report["modified_volume_count"],
        validation=report["native_increment_validation"],
    )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
