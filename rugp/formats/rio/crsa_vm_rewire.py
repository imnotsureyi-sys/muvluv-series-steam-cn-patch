from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

try:
    from .ruo import build_ruo
    from .crsa_vm_pool import (
        CvmPoolError,
        extract_direct_slot,
        find_vm_message_commands,
        parse_direct_pool,
    )
    from .crsa import (
        CRSA_HEADER_SIZE,
        decode_crsa_encrypted,
        encode_crsa_encrypted,
        read_crsa_record,
    )
    from .crypto import RIO_KEY, decode_encrypted_block, decode_extent_offset
except ImportError:  # Direct script execution.
    from ruo import build_ruo
    from crsa_vm_pool import (
        CvmPoolError,
        extract_direct_slot,
        find_vm_message_commands,
        parse_direct_pool,
    )
    from crsa import (
        CRSA_HEADER_SIZE,
        decode_crsa_encrypted,
        encode_crsa_encrypted,
        read_crsa_record,
    )
    from crypto import RIO_KEY, decode_encrypted_block, decode_extent_offset


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replacement_direct_raw(slot, replacement_text: str) -> bytes:
    body = slot.text
    trailing_controls = ""
    while body and ord(body[-1]) < 0x20:
        trailing_controls = body[-1] + trailing_controls
        body = body[:-1]
    prefix = slot.raw[: slot.prefix_size]
    raw = prefix + (replacement_text + trailing_controls + "\x00").encode("utf-16le")
    if len(raw) <= len(slot.raw):
        raise CvmPoolError("replacement translation must be longer than the direct source slot")
    return raw


def build_append_rewire_ruo(
    *,
    base_rio: Path,
    block_offset: int,
    source_raw_offset: int,
    source_logical_byte_offset: int,
    unit_size: int,
    pool_base: int,
    target_command_order: int,
    replacement_text: str,
    output_ruo: Path,
    output_record: Path,
    output_manifest: Path,
) -> dict[str, object]:
    decoded_source = decode_extent_offset(source_raw_offset, unit_size)
    if decoded_source != source_logical_byte_offset:
        raise CvmPoolError(
            f"source key decodes to 0x{decoded_source:X}, not logical 0x{source_logical_byte_offset:X}"
        )
    original = read_crsa_record(base_rio, block_offset)
    commands = find_vm_message_commands(original.plaintext)
    if not 1 <= target_command_order <= len(commands):
        raise CvmPoolError("target command order is outside the command stream")
    target = commands[target_command_order - 1]
    if target.source_index == target.translation_index == 0:
        raise CvmPoolError("target command is control-only")
    layout = parse_direct_pool(original.plaintext, commands, pool_base)
    source_slot = extract_direct_slot(
        original.plaintext,
        base=pool_base,
        declared_units=layout.declared_units,
        index=target.source_index,
    )
    translation_slot = extract_direct_slot(
        original.plaintext,
        base=pool_base,
        declared_units=layout.declared_units,
        index=target.translation_index,
    )
    replacement_raw = _replacement_direct_raw(translation_slot, replacement_text)

    original_pool = original.plaintext[pool_base : layout.end]
    appended_source_index = layout.declared_units
    appended_translation_index = appended_source_index + len(source_slot.raw) // 2
    appended_pool = original_pool + source_slot.raw + replacement_raw
    new_units = len(appended_pool) // 2
    prefix = bytearray(original.plaintext[: pool_base - 4])
    if target.translation_index_field + 4 > len(prefix):
        raise CvmPoolError("target command index fields lie after the pool header")
    struct.pack_into("<I", prefix, target.source_index_field, appended_source_index)
    struct.pack_into("<I", prefix, target.translation_index_field, appended_translation_index)
    rebuilt_plain = (
        bytes(prefix)
        + struct.pack("<I", new_units)
        + appended_pool
        + original.plaintext[layout.end :]
    )

    rebuilt_commands = find_vm_message_commands(rebuilt_plain)
    if len(rebuilt_commands) != len(commands):
        raise AssertionError("CVMMsg3 command count changed")
    rebuilt_target = rebuilt_commands[target_command_order - 1]
    if (
        rebuilt_target.source_index != appended_source_index
        or rebuilt_target.translation_index != appended_translation_index
    ):
        raise AssertionError("target command indices did not read back")
    for order, (before, after) in enumerate(zip(commands, rebuilt_commands), 1):
        if order == target_command_order:
            continue
        if before.first_records != after.first_records:
            raise AssertionError(f"non-target command {order} first records changed")
    rebuilt_layout = parse_direct_pool(rebuilt_plain, rebuilt_commands, pool_base)
    rebuilt_source = extract_direct_slot(
        rebuilt_plain,
        base=pool_base,
        declared_units=rebuilt_layout.declared_units,
        index=rebuilt_target.source_index,
    )
    rebuilt_translation = extract_direct_slot(
        rebuilt_plain,
        base=pool_base,
        declared_units=rebuilt_layout.declared_units,
        index=rebuilt_target.translation_index,
    )
    if rebuilt_source.raw != source_slot.raw:
        raise AssertionError("appended source slot changed")
    if rebuilt_translation.raw != replacement_raw:
        raise AssertionError("appended translation slot changed")
    if rebuilt_plain[pool_base : pool_base + len(original_pool)] != original_pool:
        raise AssertionError("original pool bytes changed")
    if rebuilt_plain[rebuilt_layout.end :] != original.plaintext[layout.end :]:
        raise AssertionError("object suffix changed rather than shifting intact")

    identity = encode_crsa_encrypted(
        original.plaintext,
        template_header=original.encrypted_header,
    )
    if identity != original.record[CRSA_HEADER_SIZE:]:
        raise AssertionError("unchanged CRsa did not re-encode byte-identically")
    rebuilt_encrypted = encode_crsa_encrypted(
        rebuilt_plain,
        template_header=original.encrypted_header,
    )
    strict_plain, strict_consumed, strict_checksums = decode_crsa_encrypted(rebuilt_encrypted)
    if strict_plain != rebuilt_plain or strict_consumed != len(rebuilt_encrypted):
        raise AssertionError("strict CRsa encrypted readback failed")
    if decode_encrypted_block(rebuilt_encrypted, RIO_KEY).plaintext != rebuilt_plain:
        raise AssertionError("GARbro-compatible encrypted readback failed")
    rebuilt_record = original.header + rebuilt_encrypted

    output_record.parent.mkdir(parents=True, exist_ok=True)
    output_record.write_bytes(rebuilt_record)
    ruo_report = build_ruo(output_ruo, unit_size, [(source_raw_offset, rebuilt_record)])
    report = {
        "schema": 1,
        "purpose": "CVMMsg3 append-new-pair and rewire-one-command variable-length RUO proof",
        "strategy": "preserve original pool; append source+translation pair; rewire target only",
        "base_rio": str(base_rio.resolve()),
        "physical_block_offset_hex": f"0x{block_offset:X}",
        "source_logical_byte_offset_hex": f"0x{source_logical_byte_offset:X}",
        "source_raw_offset_hex": f"0x{source_raw_offset:08X}",
        "unit_size": unit_size,
        "pool_base": pool_base,
        "command_count": len(commands),
        "target_command_order": target_command_order,
        "target_indices_before": [target.source_index, target.translation_index],
        "target_indices_after": [appended_source_index, appended_translation_index],
        "source_text": source_slot.text,
        "translation_before": translation_slot.text,
        "translation_after": rebuilt_translation.text,
        "translation_units_before": len(translation_slot.raw) // 2,
        "translation_units_after": len(replacement_raw) // 2,
        "pool_units_before": layout.declared_units,
        "pool_units_after": rebuilt_layout.declared_units,
        "plaintext_size_before": len(original.plaintext),
        "plaintext_size_after": len(rebuilt_plain),
        "record_size_before": len(original.record),
        "record_size_after": len(rebuilt_record),
        "encrypted_chunk_count_before": len(original.chunk_checksums),
        "encrypted_chunk_count_after": len(strict_checksums),
        "original_record_sha256": sha256(original.record),
        "rebuilt_record_sha256": sha256(rebuilt_record),
        "verification": {
            "declared_pool_length_updated": True,
            "original_pool_preserved_byte_for_byte": True,
            "only_target_command_indices_changed": True,
            "appended_source_exact_readback": True,
            "appended_long_translation_exact_readback": True,
            "nested_or_alias_existing_references_need_no_rewrite": True,
            "object_stream_suffix_preserved_and_shifted": True,
            "strict_all_chunk_checksums_readback": True,
            "final_partial_checksum_readback": True,
            "garbro_compatible_plaintext_readback": True,
            "unchanged_record_byte_identical_reencode": True,
            "exact_ruo_extent_size": ruo_report["records"][0]["replacement_extent_size"] == len(rebuilt_record),
            "runtime_tested": False,
        },
        "output_record": str(output_record.resolve()),
        "output_ruo": str(output_ruo.resolve()),
        "ruo": ruo_report,
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-rio", type=Path, required=True)
    parser.add_argument("--block-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--source-raw-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--source-logical-byte-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--unit-size", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--pool-base", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--target-command-order", type=int, default=1)
    parser.add_argument("--replacement-translation", required=True)
    parser.add_argument("--output-ruo", type=Path, required=True)
    parser.add_argument("--output-record", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    report = build_append_rewire_ruo(
        base_rio=args.base_rio,
        block_offset=args.block_offset,
        source_raw_offset=args.source_raw_offset,
        source_logical_byte_offset=args.source_logical_byte_offset,
        unit_size=args.unit_size,
        pool_base=args.pool_base,
        target_command_order=args.target_command_order,
        replacement_text=args.replacement_translation,
        output_ruo=args.output_ruo,
        output_record=args.output_record,
        output_manifest=args.manifest,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
