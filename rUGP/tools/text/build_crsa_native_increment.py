"""Build a reviewed native-field CRsa increment as a cumulative candidate RUO.

Inputs are pinned by whole-volume, inherited-RUO, record and field hashes.
The command never installs candidates, changes DLLs or overwrites an input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rUGP.formats.rio.crsa import read_crsa_record, encode_crsa_encrypted, decode_crsa_encrypted
from rUGP.formats.rio.crypto import decode_encrypted_block, decode_extent_offset, decode_extent_size, RIO_KEY
from rUGP.formats.rio.crsa_vm_edit import digest, require_hash, edit_native_fields
from rUGP.formats.rio.ruo import build_ruo, read_footer


def hash_file(path: Path) -> str:
    import hashlib
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def build(spec: dict, source_dir: Path, output: Path, base_ruo: Path | None = None) -> dict:
    if spec.get("schema") != "photon-crsa-native-increment/v1":
        raise ValueError("unsupported native increment schema")
    if spec["unit_size"] != 4 or spec["game"] not in ("pf", "pm"):
        raise ValueError("unsupported Photon layout")
    source_dir, output = source_dir.resolve(), output.resolve()
    if output.exists() or output.with_suffix(output.suffix + ".json").exists():
        raise ValueError("output and report must be new files")
    if base_ruo is not None:
        base_ruo = base_ruo.resolve()
        base_bytes = base_ruo.read_bytes()
        require_hash(digest(base_bytes), spec["base_ruo_sha256"], "inherited RUO")
        _, inherited = read_footer(base_ruo, spec["unit_size"])
    else:
        if spec["base_ruo_sha256"] is not None:
            raise ValueError("the reviewed increment requires its inherited RUO")
        base_bytes, inherited = b"", []
    if output == base_ruo:
        raise ValueError("output must be distinct from the inherited RUO")
    volumes = {}
    input_stats = {}
    for expected in spec["volumes"]:
        name = expected["name"]
        if not name or Path(name).name != name or name in volumes:
            raise ValueError("volume names must be unique basenames")
        path = source_dir / name
        if path == output or path.stat().st_size != expected["bytes"]:
            raise ValueError("source volume extent changed")
        require_hash(hash_file(path), expected["sha256"], "source volume")
        volumes[name] = expected
        input_stats[path] = (path.stat().st_size, path.stat().st_mtime_ns)
    routes = {route.source_raw_offset: route for route in inherited}
    replacements, reports = [], []
    keys, stable_ids = set(), set()
    for block in spec["blocks"]:
        key = int(block["source_raw_key"], 0)
        if key in keys:
            raise ValueError("duplicate CRsa route key")
        keys.add(key)
        volume = volumes[block["volume"]]
        if decode_extent_offset(key, 4) != volume["logical_offset"] + block["block_offset"]:
            raise ValueError("CRsa physical extent does not match its logical route")
        if key in routes:
            route = routes[key]
            original = read_crsa_record(base_ruo, decode_extent_offset(route.ruo_raw_offset, 4))
            if len(original.record) != decode_extent_size(route.replacement_raw_size):
                raise ValueError("inherited route has a mismatched CRsa extent")
        else:
            original = read_crsa_record(source_dir / block["volume"], block["block_offset"])
        require_hash(digest(original.record), block["effective_record_sha256"], "effective CRsa")
        for entry in block["entries"]:
            if entry["stable_id"] in stable_ids:
                raise ValueError("duplicate stable ID across blocks")
            stable_ids.add(entry["stable_id"])
        if original.header + encode_crsa_encrypted(original.plaintext, template_header=original.encrypted_header) != original.record:
            raise ValueError("identity reencode mismatch")
        edited = edit_native_fields(original.plaintext, spec["game"], block["entries"], block["payload_sha256"])
        encrypted = encode_crsa_encrypted(edited.payload, template_header=original.encrypted_header)
        plain, consumed, _ = decode_crsa_encrypted(encrypted)
        if plain != edited.payload or consumed != len(encrypted):
            raise ValueError("strict encrypted readback mismatch")
        if decode_encrypted_block(encrypted, RIO_KEY).plaintext != edited.payload:
            raise ValueError("independent compatible readback mismatch")
        record = original.header + encrypted
        replacements.append((key, record))
        reports.append(dict(volume=block["volume"], block_offset=block["block_offset"],
                            source_raw_key=block["source_raw_key"],
                            record_before_sha256=digest(original.record), record_after_sha256=digest(record),
                            record_before_bytes=len(original.record), record_after_bytes=len(record),
                            **edited.report))
    if not replacements:
        raise ValueError("increment has no reviewed CRsa blocks")
    for path, original_stat in input_stats.items():
        if (path.stat().st_size, path.stat().st_mtime_ns) != original_stat:
            raise ValueError("source volume changed during build")
    if base_ruo is not None and base_ruo.read_bytes() != base_bytes:
        raise ValueError("inherited RUO changed during build")
    report = build_ruo(output, 4, replacements, base_ruo=base_ruo)
    _, written = read_footer(output, 4)
    by_key = {r.source_raw_offset: r for r in written}
    output_bytes = output.read_bytes()
    for old in inherited:
        if old.source_raw_offset in keys:
            continue
        start = decode_extent_offset(old.ruo_raw_offset, 4)
        end = start + decode_extent_size(old.replacement_raw_size)
        if by_key[old.source_raw_offset] != old or output_bytes[start:end] != base_bytes[start:end]:
            raise ValueError("unrelated inherited route changed")
    for key, expected_record in replacements:
        route = by_key[key]
        actual = read_crsa_record(output, decode_extent_offset(route.ruo_raw_offset, 4))
        if actual.record != expected_record or decode_extent_size(route.replacement_raw_size) != len(actual.record):
            raise ValueError("candidate RUO CRsa extent/readback mismatch")
    report.update(increment_sha256=digest(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode("utf-8")),
                  blocks=reports, entry_count=len(stable_ids),
                  native_increment_validation=dict(
                      whole_input_hashes=True, identity_reencode=True, strict_all_checksums=True,
                      independent_plaintext_readback=True, all_native_commands_read_back=True,
                      reviewed_storage_contracts_enforced=True,
                      non_target_pool_bytes_preserved=True,
                      source_messages_and_voices_preserved=True, unrelated_inherited_routes_preserved=True,
                      installed=False, runtime_tested=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--base-ruo", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    report = build(spec, args.source_dir, args.output, args.base_ruo)
    args.output.with_suffix(args.output.suffix + ".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(sha256=report["file_sha256"], routes=report["redirect_count"],
                         blocks=len(report["blocks"]), entries=report["entry_count"],
                         validation=report["native_increment_validation"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
