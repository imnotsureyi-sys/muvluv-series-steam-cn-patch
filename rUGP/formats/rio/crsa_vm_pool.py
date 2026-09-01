from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass, replace
from pathlib import Path

try:
    from .ruo import build_ruo
    from .crsa import (
        CRSA_HEADER_SIZE,
        decode_crsa_encrypted,
        encode_crsa_encrypted,
        read_crsa_record,
    )
    from .crypto import decode_encrypted_block, decode_extent_offset, RIO_KEY
except ImportError:  # Direct script execution.
    from ruo import build_ruo
    from crsa import (
        CRSA_HEADER_SIZE,
        decode_crsa_encrypted,
        encode_crsa_encrypted,
        read_crsa_record,
    )
    from crypto import decode_encrypted_block, decode_extent_offset, RIO_KEY


CVM_MSG3_DECLARATION = bytes.fromhex("ff ff 15 00 05 6a da 31 7d ff")


class CvmPoolError(ValueError):
    pass


@dataclass(frozen=True)
class VmMessageCommand:
    object_offset: int
    body_offset: int
    end_offset: int
    class_reference: int | None
    command_offset: int
    flags: int
    string_group: int
    string_index: int
    first_records: tuple[tuple[int, int, int], ...]
    second_records: tuple[tuple[int, int, int, int, int, int], ...]

    @property
    def source_index(self) -> int:
        return self.first_records[0][0]

    @property
    def translation_index(self) -> int:
        return self.first_records[1][0]

    @property
    def source_index_field(self) -> int:
        return self.body_offset + struct.calcsize("<IIHHBB")

    @property
    def translation_index_field(self) -> int:
        return self.source_index_field + 12


@dataclass(frozen=True)
class PoolPair:
    order: int
    source_index: int
    translation_index: int
    source_raw: bytes
    translation_raw: bytes

    @property
    def source_text(self) -> str:
        return self.source_raw.decode("utf-16le", errors="strict")[:-1]

    @property
    def translation_text(self) -> str:
        return self.translation_raw.decode("utf-16le", errors="strict")[:-1]


@dataclass(frozen=True)
class PoolLayout:
    base: int
    declared_units: int
    end: int
    prefix_raw: bytes
    pairs: tuple[PoolPair, ...]


@dataclass(frozen=True)
class DirectSlot:
    index: int
    offset: int
    prefix_size: int
    raw: bytes
    text: str


@dataclass(frozen=True)
class DirectPoolLayout:
    base: int
    declared_units: int
    end: int
    command_slots: tuple[tuple[DirectSlot, DirectSlot], ...]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_message_body(payload: bytes, body_offset: int) -> VmMessageCommand | None:
    fixed_size = struct.calcsize("<IIHHBB")
    if body_offset < 0 or body_offset + fixed_size > len(payload):
        return None
    command, flags, group, index, first_count, second_count = struct.unpack_from(
        "<IIHHBB", payload, body_offset
    )
    if (
        command % 4 != 0
        or command > 0x40000000
        or group != 1
        or first_count != 2
        or second_count > 16
    ):
        return None
    first_base = body_offset + fixed_size
    second_base = first_base + first_count * 12
    end_offset = second_base + second_count * 10
    if end_offset > len(payload):
        return None
    first_records = tuple(
        struct.unpack_from("<III", payload, first_base + ordinal * 12)
        for ordinal in range(first_count)
    )
    second_records = tuple(
        struct.unpack_from("<HHHHBB", payload, second_base + ordinal * 10)
        for ordinal in range(second_count)
    )
    source_index = first_records[0][0]
    translation_index = first_records[1][0]
    if not (source_index == translation_index == 0) and not (
        source_index < translation_index and translation_index * 2 < len(payload)
    ):
        return None
    return VmMessageCommand(
        object_offset=-1,
        body_offset=body_offset,
        end_offset=end_offset,
        class_reference=None,
        command_offset=command,
        flags=flags,
        string_group=group,
        string_index=index,
        first_records=first_records,
        second_records=second_records,
    )


def _identify(
    command: VmMessageCommand,
    object_offset: int,
    class_reference: int | None,
) -> VmMessageCommand:
    return replace(
        command,
        object_offset=object_offset,
        class_reference=class_reference,
    )


def find_vm_message_commands(payload: bytes) -> tuple[VmMessageCommand, ...]:
    declaration_offset = payload.find(CVM_MSG3_DECLARATION)
    if declaration_offset < 0:
        return ()
    first = _parse_message_body(payload, declaration_offset + len(CVM_MSG3_DECLARATION))
    if first is None:
        raise CvmPoolError("invalid first CVMMsg3 declaration body")
    first = _identify(first, declaration_offset, None)

    candidates: dict[int, list[VmMessageCommand]] = {}
    for body_offset in range(first.end_offset + 2, len(payload) - 37):
        class_reference = struct.unpack_from("<H", payload, body_offset - 2)[0]
        if class_reference & 0x8000 == 0 or class_reference == 0xFFFF:
            continue
        command = _parse_message_body(payload, body_offset)
        if command is not None:
            candidates.setdefault(class_reference, []).append(
                _identify(command, body_offset - 2, class_reference)
            )

    matching: list[list[VmMessageCommand]] = []
    for commands in candidates.values():
        commands.sort(key=lambda item: item.object_offset)
        stream = [first, *commands]
        if all(a.command_offset < b.command_offset for a, b in zip(stream, stream[1:])):
            matching.append(commands)
    if not matching:
        return (first,)
    largest = max(len(commands) for commands in matching)
    matching = [commands for commands in matching if len(commands) == largest]
    if len(matching) != 1:
        raise CvmPoolError("ambiguous cached CVMMsg3 class stream")
    return (first, *matching[0])


def _validate_utf16_slot(raw: bytes, label: str) -> None:
    if not raw or len(raw) % 2 or not raw.endswith(b"\x00\x00"):
        raise CvmPoolError(f"{label} is not a NUL-terminated UTF-16LE slot")
    try:
        raw.decode("utf-16le", errors="strict")
    except UnicodeDecodeError as error:
        raise CvmPoolError(f"{label} is invalid UTF-16LE") from error
    # A minority of current-Steam slots contain a proven serialized wrapper
    # with embedded NUL code units before the visible text.  Preserve those
    # code units exactly; only the final NUL is the pair boundary invariant.


def _direct_prefix_size(data: bytes, offset: int, end: int) -> int:
    if data[offset : offset + 8] == b"\x01\x00\x00\x00\x01\x00\x00\x00":
        return 8
    if data[offset : offset + 2] == b"\x10\x00":
        return 2
    if data[offset : offset + 2] == b"\x00\x00" and offset + 2 < end:
        return 2
    return 0


def extract_direct_slot(
    payload: bytes,
    *,
    base: int,
    declared_units: int,
    index: int,
) -> DirectSlot:
    pool_end = base + declared_units * 2
    offset = base + index * 2
    if not base <= offset < pool_end:
        raise CvmPoolError(f"direct slot index {index} is outside the declared pool")
    prefix_size = _direct_prefix_size(payload, offset, pool_end)
    cursor = offset + prefix_size
    while cursor + 1 < pool_end and payload[cursor : cursor + 2] != b"\x00\x00":
        cursor += 2
    if cursor + 1 >= pool_end:
        raise CvmPoolError(f"direct slot index {index} has no UTF-16 NUL terminator")
    raw = payload[offset : cursor + 2]
    try:
        text = payload[offset + prefix_size : cursor].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as error:
        raise CvmPoolError(f"direct slot index {index} is invalid UTF-16LE") from error
    return DirectSlot(
        index=index,
        offset=offset,
        prefix_size=prefix_size,
        raw=raw,
        text=text,
    )


def parse_direct_pool(
    payload: bytes,
    commands: tuple[VmMessageCommand, ...],
    base: int,
) -> DirectPoolLayout:
    if base < 4 or base > len(payload):
        raise CvmPoolError("pool base is outside the payload")
    declared_units = struct.unpack_from("<I", payload, base - 4)[0]
    end = base + declared_units * 2
    if end > len(payload):
        raise CvmPoolError("declared pool extends beyond the payload")
    slots: list[tuple[DirectSlot, DirectSlot]] = []
    for order, command in enumerate(commands, 1):
        if command.source_index == command.translation_index == 0:
            continue
        if not 0 <= command.source_index < command.translation_index < declared_units:
            raise CvmPoolError(f"command {order} has indices outside the declared pool")
        source = extract_direct_slot(
            payload,
            base=base,
            declared_units=declared_units,
            index=command.source_index,
        )
        translation = extract_direct_slot(
            payload,
            base=base,
            declared_units=declared_units,
            index=command.translation_index,
        )
        slots.append((source, translation))
    return DirectPoolLayout(
        base=base,
        declared_units=declared_units,
        end=end,
        command_slots=tuple(slots),
    )


def parse_pool(payload: bytes, commands: tuple[VmMessageCommand, ...], base: int) -> PoolLayout:
    if not commands:
        raise CvmPoolError("payload has no CVMMsg3 commands")
    if base < 4 or base > len(payload):
        raise CvmPoolError("pool base is outside the payload")
    declared_units = struct.unpack_from("<I", payload, base - 4)[0]
    end = base + declared_units * 2
    if end > len(payload):
        raise CvmPoolError("declared pool extends beyond the payload")

    text_commands = tuple(
        command for command in commands
        if not (command.source_index == command.translation_index == 0)
    )
    if not text_commands:
        raise CvmPoolError("CVMMsg3 stream has no text commands")
    pair_by_source: dict[int, tuple[int, int]] = {}
    for command in text_commands:
        pair = (command.source_index, command.translation_index)
        previous = pair_by_source.setdefault(command.source_index, pair)
        if previous != pair:
            raise CvmPoolError(
                f"source index {command.source_index} has conflicting translation indices"
            )
    unique_pairs = tuple(sorted(pair_by_source.values()))
    if not all(
        source < translation <= following_source
        for (source, translation), (following_source, _) in zip(unique_pairs, unique_pairs[1:])
    ):
        raise CvmPoolError("unique CVMMsg3 pool pairs are not monotonic")
    if unique_pairs[-1][1] >= declared_units:
        raise CvmPoolError("last translation index is outside the declared pool")

    prefix_end = unique_pairs[0][0] * 2
    prefix_raw = payload[base : base + prefix_end]
    pairs: list[PoolPair] = []
    for order, (source_index, translation_index) in enumerate(unique_pairs):
        source_start = base + source_index * 2
        translation_start = base + translation_index * 2
        translation_end = (
            base + unique_pairs[order + 1][0] * 2
            if order + 1 < len(unique_pairs)
            else end
        )
        source_raw = payload[source_start:translation_start]
        translation_raw = payload[translation_start:translation_end]
        _validate_utf16_slot(source_raw, f"command {order + 1} source")
        _validate_utf16_slot(translation_raw, f"command {order + 1} translation")
        pairs.append(PoolPair(
            order=order + 1,
            source_index=source_index,
            translation_index=translation_index,
            source_raw=source_raw,
            translation_raw=translation_raw,
        ))
    return PoolLayout(
        base=base,
        declared_units=declared_units,
        end=end,
        prefix_raw=prefix_raw,
        pairs=tuple(pairs),
    )


def infer_pool_base(payload: bytes, commands: tuple[VmMessageCommand, ...]) -> int:
    text_commands = tuple(
        command for command in commands
        if not (command.source_index == command.translation_index == 0)
    )
    if not text_commands:
        raise CvmPoolError("cannot infer a pool without text commands")
    minimum_units = max(command.translation_index for command in text_commands) + 1
    candidates: list[int] = []
    for base in range(4, len(payload)):
        declared_units = struct.unpack_from("<I", payload, base - 4)[0]
        if declared_units < minimum_units or base + declared_units * 2 > len(payload):
            continue
        try:
            parse_pool(payload, commands, base)
        except CvmPoolError:
            continue
        candidates.append(base)
    if len(candidates) != 1:
        raise CvmPoolError(f"expected one CVMMsg3 pool base, found {candidates[:20]}")
    return candidates[0]


def _replacement_slot(original_raw: bytes, replacement_text: str) -> bytes:
    _validate_utf16_slot(original_raw, "original replacement target")
    original = original_raw.decode("utf-16le", errors="strict")[:-1]
    trailing_controls = ""
    while original and ord(original[-1]) < 0x20:
        trailing_controls = original[-1] + trailing_controls
        original = original[:-1]
    replacement = replacement_text + trailing_controls + "\x00"
    raw = replacement.encode("utf-16le", errors="strict")
    _validate_utf16_slot(raw, "rebuilt replacement target")
    if len(raw) <= len(original_raw):
        raise CvmPoolError("replacement translation must be longer than its original slot")
    return raw


def rebuild_pool_translation(
    payload: bytes,
    commands: tuple[VmMessageCommand, ...],
    layout: PoolLayout,
    target_order: int,
    replacement_text: str,
) -> tuple[bytes, PoolLayout]:
    if not 1 <= target_order <= len(layout.pairs):
        raise CvmPoolError("target command order is outside the text command stream")
    rebuilt_pool = bytearray(layout.prefix_raw)
    new_pairs: list[PoolPair] = []
    for pair in layout.pairs:
        if len(rebuilt_pool) % 2:
            raise AssertionError("rebuilt pool lost UTF-16 alignment")
        source_index = len(rebuilt_pool) // 2
        rebuilt_pool.extend(pair.source_raw)
        translation_index = len(rebuilt_pool) // 2
        translation_raw = (
            _replacement_slot(pair.translation_raw, replacement_text)
            if pair.order == target_order
            else pair.translation_raw
        )
        rebuilt_pool.extend(translation_raw)
        new_pairs.append(PoolPair(
            order=pair.order,
            source_index=source_index,
            translation_index=translation_index,
            source_raw=pair.source_raw,
            translation_raw=translation_raw,
        ))

    rebuilt_units = len(rebuilt_pool) // 2
    prefix = bytearray(payload[: layout.base - 4])
    pair_map = {
        (before.source_index, before.translation_index): after
        for before, after in zip(layout.pairs, new_pairs)
    }
    for command in commands:
        if command.source_index == command.translation_index == 0:
            continue
        pair = pair_map.get((command.source_index, command.translation_index))
        if pair is None:
            raise CvmPoolError("command references a pair missing from the rebuilt pool map")
        if command.translation_index_field + 4 > len(prefix):
            raise CvmPoolError("CVMMsg3 index field lies after the pool header")
        struct.pack_into("<I", prefix, command.source_index_field, pair.source_index)
        struct.pack_into("<I", prefix, command.translation_index_field, pair.translation_index)
    rebuilt = bytes(prefix) + struct.pack("<I", rebuilt_units) + bytes(rebuilt_pool) + payload[layout.end :]
    new_commands = find_vm_message_commands(rebuilt)
    new_layout = parse_pool(rebuilt, new_commands, layout.base)
    return rebuilt, new_layout


def build_cvmmsg3_variable_ruo(
    *,
    base_rio: Path,
    block_offset: int,
    source_raw_offset: int,
    source_logical_byte_offset: int,
    unit_size: int,
    pool_base: int | None,
    target_order: int,
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
    if pool_base is None:
        resolved_base = infer_pool_base(original.plaintext, commands)
        pool_base_resolution = "unique_structural_inference"
    else:
        resolved_base = pool_base
        pool_base_resolution = "supplied_native_index_then_structurally_verified"
    layout = parse_pool(original.plaintext, commands, resolved_base)
    rebuilt_plain, rebuilt_layout = rebuild_pool_translation(
        original.plaintext,
        commands,
        layout,
        target_order,
        replacement_text,
    )
    rebuilt_commands = find_vm_message_commands(rebuilt_plain)
    if len(rebuilt_commands) != len(commands):
        raise AssertionError("CVMMsg3 command count changed")

    # Every source slot and every non-target translation slot must survive
    # exactly; the selected translation is the sole pool-content mutation.
    for old_pair, new_pair in zip(layout.pairs, rebuilt_layout.pairs):
        if old_pair.source_raw != new_pair.source_raw:
            raise AssertionError(f"source slot {old_pair.order} changed")
        if old_pair.order != target_order and old_pair.translation_raw != new_pair.translation_raw:
            raise AssertionError(f"non-target translation slot {old_pair.order} changed")
    target_before = layout.pairs[target_order - 1]
    target_after = rebuilt_layout.pairs[target_order - 1]
    expected_target = _replacement_slot(target_before.translation_raw, replacement_text)
    if target_after.translation_raw != expected_target:
        raise AssertionError("target translation readback mismatch")
    if rebuilt_plain[rebuilt_layout.end :] != original.plaintext[layout.end :]:
        raise AssertionError("object-stream suffix changed rather than shifting intact")

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
        "purpose": "CVMMsg3 variable-length translation pool rebuild RUO proof",
        "base_rio": str(base_rio.resolve()),
        "physical_block_offset": block_offset,
        "physical_block_offset_hex": f"0x{block_offset:X}",
        "source_logical_byte_offset": source_logical_byte_offset,
        "source_logical_byte_offset_hex": f"0x{source_logical_byte_offset:X}",
        "source_raw_offset_hex": f"0x{source_raw_offset:08X}",
        "unit_size": unit_size,
        "pool_base": layout.base,
        "pool_base_hex": f"0x{layout.base:X}",
        "pool_base_resolution": pool_base_resolution,
        "command_count_before": len(commands),
        "command_count_after": len(rebuilt_commands),
        "pool_units_before": layout.declared_units,
        "pool_units_after": rebuilt_layout.declared_units,
        "pool_bytes_before": layout.declared_units * 2,
        "pool_bytes_after": rebuilt_layout.declared_units * 2,
        "pool_end_before": layout.end,
        "pool_end_after": rebuilt_layout.end,
        "target_order": target_order,
        "target_source_text": target_before.source_text,
        "target_translation_before": target_before.translation_text,
        "target_translation_after": target_after.translation_text,
        "target_translation_units_before": len(target_before.translation_raw) // 2,
        "target_translation_units_after": len(target_after.translation_raw) // 2,
        "plaintext_size_before": len(original.plaintext),
        "plaintext_size_after": len(rebuilt_plain),
        "record_size_before": len(original.record),
        "record_size_after": len(rebuilt_record),
        "encrypted_chunk_count_before": len(original.chunk_checksums),
        "encrypted_chunk_count_after": len(strict_checksums),
        "original_record_sha256": sha256(original.record),
        "rebuilt_record_sha256": sha256(rebuilt_record),
        "suffix_sha256": sha256(original.plaintext[layout.end :]),
        "verification": {
            "pool_base_resolved_and_structurally_verified": True,
            "declared_pool_length_updated": True,
            "all_command_indices_rewritten_and_reparsed": True,
            "all_source_slots_preserved": True,
            "all_non_target_translation_slots_preserved": True,
            "target_translation_longer_and_exact_readback": len(target_after.translation_raw) > len(target_before.translation_raw),
            "pool_end_exact": rebuilt_layout.end == rebuilt_layout.base + rebuilt_layout.declared_units * 2,
            "object_stream_suffix_preserved_and_shifted": True,
            "strict_all_chunk_checksums_readback": True,
            "final_partial_checksum_readback": True,
            "garbro_compatible_plaintext_readback": True,
            "unchanged_record_byte_identical_reencode": True,
            "exact_ruo_extent_size": ruo_report["records"][0]["replacement_extent_size"] == len(rebuilt_record),
            "runtime_tested": False,
        },
        "indices": [
            {
                "order": before.order,
                "source_before": before.source_index,
                "translation_before": before.translation_index,
                "source_after": after.source_index,
                "translation_after": after.translation_index,
            }
            for before, after in zip(layout.pairs, rebuilt_layout.pairs)
        ],
        "output_record": str(output_record.resolve()),
        "output_ruo": str(output_ruo.resolve()),
        "ruo": ruo_report,
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild one complete CVMMsg3 UTF-16 pool and emit a CRsa RUO leaf."
    )
    parser.add_argument("--base-rio", type=Path, required=True)
    parser.add_argument("--block-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--source-raw-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--source-logical-byte-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--unit-size", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--pool-base", type=lambda value: int(value, 0))
    parser.add_argument("--target-order", type=int, default=1)
    parser.add_argument("--replacement-translation", required=True)
    parser.add_argument("--output-ruo", type=Path, required=True)
    parser.add_argument("--output-record", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    report = build_cvmmsg3_variable_ruo(
        base_rio=args.base_rio,
        block_offset=args.block_offset,
        source_raw_offset=args.source_raw_offset,
        source_logical_byte_offset=args.source_logical_byte_offset,
        unit_size=args.unit_size,
        pool_base=args.pool_base,
        target_order=args.target_order,
        replacement_text=args.replacement_translation,
        output_ruo=args.output_ruo,
        output_record=args.output_record,
        output_manifest=args.manifest,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
