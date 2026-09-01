from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

try:
    from .ruo import build_ruo
    from .crypto import RIO_KEY, decode_encrypted_block, decode_extent_offset
except ImportError:  # Direct script execution.
    from ruo import build_ruo
    from crypto import RIO_KEY, decode_encrypted_block, decode_extent_offset


CRSA_HEADER_SIZE = 11
CRSA_PREFIX = bytes.fromhex("00 05 6e 03 01 00")
ENCRYPTED_SIZE_XOR_1 = 0xC92E568B
ENCRYPTED_SIZE_XOR_2 = 0xC92E568F
ENCRYPTED_KEY_STEP = 0xA3B376C9
U32_MASK = 0xFFFFFFFF
UNICODE_MARKER = bytes.fromhex("ff fe ff")
CVM_MSG3_DECLARATION = bytes.fromhex("ff ff 15 00 05 6a da 31 7d ff")


class CrsaRebuildError(ValueError):
    pass


@dataclass(frozen=True)
class CrsaRecord:
    header: bytes
    plaintext: bytes
    encrypted_header: bytes
    consumed: int
    record: bytes
    chunk_checksums: tuple[int, ...]


@dataclass(frozen=True)
class UnicodeStringRecord:
    marker_offset: int
    text_offset: int
    end_offset: int
    code_units: int
    length_field_size: int
    text: str


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _advance_key(key: int) -> int:
    bit = (key >> 15) & 1
    return (~(bit + ((key * 2) & U32_MASK) + ENCRYPTED_KEY_STEP)) & U32_MASK


def decode_encrypted_header(header: bytes) -> int:
    if len(header) != 8:
        raise CrsaRebuildError("encrypted header must be exactly 8 bytes")
    stored1 = int.from_bytes(header[0:4], "little")
    stored2 = int.from_bytes(header[4:8], "little")
    size1 = (~(stored1 ^ ENCRYPTED_SIZE_XOR_1)) & U32_MASK
    size2 = ((stored2 ^ ENCRYPTED_SIZE_XOR_2) & U32_MASK) >> 3
    if size1 != size2:
        raise CrsaRebuildError(f"encrypted size mismatch: {size1} != {size2}")
    return size1


def crsa_encrypted_storage_size(plain_size: int) -> int:
    """Return CRsa encrypted bytes, including the final partial checksum.

    GARbro's generic reader stops before the final partial checksum.  A CRsa
    archive extent nevertheless stores it, so a complete relocatable record is
    8 + plaintext + two bytes for every started 0x20-byte chunk.
    """

    if plain_size <= 0:
        raise CrsaRebuildError("CRsa plaintext must not be empty")
    chunk_count = (plain_size + 0x1F) // 0x20
    return 8 + plain_size + 2 * chunk_count


def decode_crsa_encrypted(data: bytes, key: int = RIO_KEY) -> tuple[bytes, int, tuple[int, ...]]:
    if len(data) < 8:
        raise CrsaRebuildError("encrypted CRsa header is truncated")
    size = decode_encrypted_header(data[:8])
    expected = crsa_encrypted_storage_size(size)
    if len(data) < expected:
        raise CrsaRebuildError(f"encrypted CRsa is truncated: need {expected}, got {len(data)}")

    output = bytearray(size)
    src = 8
    dst = 0
    state = key & U32_MASK
    checksums: list[int] = []
    while dst < size:
        portion = min(0x20, size - dst)
        checksum = 0
        for index in range(portion):
            value = data[src + index] ^ (state & 0xFF)
            output[dst + index] = value
            checksum = (checksum + value * (portion - index)) & 0xFFFF
            state = _advance_key(state)
        src += portion
        dst += portion
        stored = int.from_bytes(data[src : src + 2], "little")
        if stored != checksum:
            raise CrsaRebuildError(
                f"CRsa checksum mismatch at 0x{src:X}: {stored:04X} != {checksum:04X}"
            )
        checksums.append(stored)
        src += 2
    return bytes(output), src, tuple(checksums)


def encode_crsa_encrypted(
    plaintext: bytes,
    key: int = RIO_KEY,
    template_header: bytes | None = None,
) -> bytes:
    size = len(plaintext)
    if size <= 0:
        raise CrsaRebuildError("CRsa plaintext must not be empty")
    stored1 = ((~size) & U32_MASK) ^ ENCRYPTED_SIZE_XOR_1
    stored2 = ((size << 3) & U32_MASK) ^ ENCRYPTED_SIZE_XOR_2
    if template_header is not None:
        if len(template_header) != 8:
            raise CrsaRebuildError("template encrypted header must be exactly 8 bytes")
        # The reader discards the low three bits after XOR/shift.  They are
        # therefore metadata rather than size bits; preserve the source value
        # even when rebuilding to a different plaintext length.
        stored2 = (stored2 & ~7) | (int.from_bytes(template_header[4:8], "little") & 7)
    output = bytearray(stored1.to_bytes(4, "little") + stored2.to_bytes(4, "little"))

    src = 0
    state = key & U32_MASK
    while src < size:
        portion = min(0x20, size - src)
        checksum = 0
        for index in range(portion):
            value = plaintext[src + index]
            output.append(value ^ (state & 0xFF))
            checksum = (checksum + value * (portion - index)) & 0xFFFF
            state = _advance_key(state)
        src += portion
        output.extend(checksum.to_bytes(2, "little"))
    if len(output) != crsa_encrypted_storage_size(size):
        raise AssertionError("internal CRsa encrypted-size mismatch")
    return bytes(output)


def read_crsa_record(path: Path, block_offset: int, key: int = RIO_KEY) -> CrsaRecord:
    with path.open("rb") as stream:
        stream.seek(block_offset)
        header = stream.read(CRSA_HEADER_SIZE)
        if len(header) != CRSA_HEADER_SIZE or not header.startswith(CRSA_PREFIX):
            raise CrsaRebuildError(
                f"0x{block_offset:X} is not the expected CRsa record: {header.hex(' ')}"
            )
        encrypted_header = stream.read(8)
        plain_size = decode_encrypted_header(encrypted_header)
        encrypted_size = crsa_encrypted_storage_size(plain_size)
        encrypted = encrypted_header + stream.read(encrypted_size - 8)
    plaintext, consumed, checksums = decode_crsa_encrypted(encrypted, key)
    if consumed != encrypted_size:
        raise AssertionError("strict CRsa decoder did not consume the exact extent")
    return CrsaRecord(
        header=header,
        plaintext=plaintext,
        encrypted_header=encrypted_header,
        consumed=consumed,
        record=header + encrypted,
        chunk_checksums=checksums,
    )


def _decode_count(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data):
        raise CrsaRebuildError("string length field is truncated")
    short = data[offset]
    if short < 0xFF:
        return short, 1
    if offset + 3 > len(data):
        raise CrsaRebuildError("16-bit string length field is truncated")
    medium = int.from_bytes(data[offset + 1 : offset + 3], "little")
    if medium < 0xFFFF:
        return medium, 3
    if offset + 7 > len(data):
        raise CrsaRebuildError("32-bit string length field is truncated")
    return int.from_bytes(data[offset + 3 : offset + 7], "little"), 7


def _encode_count(value: int) -> bytes:
    if not 0 <= value <= U32_MASK:
        raise CrsaRebuildError("string length must fit in 32 bits")
    if value < 0xFF:
        return bytes((value,))
    if value < 0xFFFF:
        return b"\xff" + value.to_bytes(2, "little")
    return b"\xff\xff\xff" + value.to_bytes(4, "little")


def utf16_code_units(text: str) -> int:
    encoded = text.encode("utf-16le", errors="strict")
    return len(encoded) // 2


def parse_unicode_string_at(data: bytes, marker_offset: int) -> UnicodeStringRecord:
    if data[marker_offset : marker_offset + len(UNICODE_MARKER)] != UNICODE_MARKER:
        raise CrsaRebuildError(f"no Unicode CString marker at 0x{marker_offset:X}")
    code_units, length_size = _decode_count(data, marker_offset + len(UNICODE_MARKER))
    text_offset = marker_offset + len(UNICODE_MARKER) + length_size
    end_offset = text_offset + code_units * 2
    if end_offset > len(data):
        raise CrsaRebuildError("Unicode CString payload is truncated")
    try:
        text = data[text_offset:end_offset].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as error:
        raise CrsaRebuildError("Unicode CString contains invalid UTF-16LE") from error
    if utf16_code_units(text) != code_units:
        raise AssertionError("decoded UTF-16 code-unit count changed")
    return UnicodeStringRecord(
        marker_offset=marker_offset,
        text_offset=text_offset,
        end_offset=end_offset,
        code_units=code_units,
        length_field_size=length_size,
        text=text,
    )


def find_unicode_string(data: bytes, text: str) -> UnicodeStringRecord:
    expected = text.encode("utf-16le", errors="strict")
    matches: list[UnicodeStringRecord] = []
    cursor = 0
    while True:
        marker = data.find(UNICODE_MARKER, cursor)
        if marker < 0:
            break
        try:
            record = parse_unicode_string_at(data, marker)
        except CrsaRebuildError:
            cursor = marker + 1
            continue
        if data[record.text_offset : record.end_offset] == expected:
            matches.append(record)
        cursor = marker + 1
    if len(matches) != 1:
        raise CrsaRebuildError(f"expected one serialized Unicode CString, found {len(matches)}")
    return matches[0]


def rebuild_unicode_string(
    plaintext: bytes,
    source_text: str,
    replacement_text: str,
) -> tuple[bytes, UnicodeStringRecord, UnicodeStringRecord]:
    source = find_unicode_string(plaintext, source_text)
    replacement_raw = replacement_text.encode("utf-16le", errors="strict")
    replacement_field = UNICODE_MARKER + _encode_count(utf16_code_units(replacement_text)) + replacement_raw
    rebuilt = plaintext[: source.marker_offset] + replacement_field + plaintext[source.end_offset :]
    replacement = parse_unicode_string_at(rebuilt, source.marker_offset)
    if replacement.text != replacement_text:
        raise AssertionError("rebuilt CString did not decode to replacement text")
    if rebuilt[: source.marker_offset] != plaintext[: source.marker_offset]:
        raise AssertionError("bytes before the CString changed")
    if rebuilt[replacement.end_offset :] != plaintext[source.end_offset :]:
        raise AssertionError("object-stream suffix was not preserved byte-for-byte")
    return rebuilt, source, replacement


def build_variable_crsa_ruo(
    *,
    base_rio: Path,
    block_offset: int,
    source_raw_offset: int,
    source_text: str,
    replacement_text: str,
    unit_size: int,
    output_ruo: Path,
    output_record: Path,
    output_manifest: Path,
) -> dict[str, object]:
    decoded_source_offset = decode_extent_offset(source_raw_offset, unit_size)
    if decoded_source_offset != block_offset:
        raise CrsaRebuildError(
            f"source raw offset resolves to 0x{decoded_source_offset:X}, not block 0x{block_offset:X}"
        )
    original = read_crsa_record(base_rio, block_offset)
    rebuilt_plain, source, replacement = rebuild_unicode_string(
        original.plaintext,
        source_text,
        replacement_text,
    )
    identity_encrypted = encode_crsa_encrypted(
        original.plaintext,
        template_header=original.encrypted_header,
    )
    if identity_encrypted != original.record[CRSA_HEADER_SIZE:]:
        raise AssertionError("unchanged CRsa did not re-encode byte-identically")
    rebuilt_encrypted = encode_crsa_encrypted(
        rebuilt_plain,
        template_header=original.encrypted_header,
    )
    rebuilt_record = original.header + rebuilt_encrypted

    strict_plain, strict_consumed, strict_checksums = decode_crsa_encrypted(rebuilt_encrypted)
    if strict_plain != rebuilt_plain or strict_consumed != len(rebuilt_encrypted):
        raise AssertionError("strict CRsa encrypted readback failed")
    # GARbro's implementation matches the engine's normal plaintext read path
    # and intentionally stops before the final partial checksum.
    generic = decode_encrypted_block(rebuilt_encrypted, RIO_KEY)
    if generic.plaintext != rebuilt_plain:
        raise AssertionError("GARbro-compatible encrypted readback failed")

    readback = find_unicode_string(strict_plain, replacement_text)
    if readback != replacement:
        raise AssertionError("serialized Unicode CString readback changed")

    output_record.parent.mkdir(parents=True, exist_ok=True)
    output_record.write_bytes(rebuilt_record)
    ruo_report = build_ruo(output_ruo, unit_size, [(source_raw_offset, rebuilt_record)])

    old_cvm = original.plaintext.count(CVM_MSG3_DECLARATION)
    new_cvm = rebuilt_plain.count(CVM_MSG3_DECLARATION)
    if old_cvm != new_cvm:
        raise AssertionError("CVMMsg3 declaration count changed")

    report = {
        "schema": 1,
        "purpose": "PF CRsa variable-length serialized Unicode CString RUO proof",
        "base_rio": str(base_rio.resolve()),
        "block_offset": block_offset,
        "block_offset_hex": f"0x{block_offset:X}",
        "source_raw_offset": source_raw_offset,
        "source_raw_offset_hex": f"0x{source_raw_offset:08X}",
        "decoded_source_byte_offset": decoded_source_offset,
        "decoded_source_byte_offset_hex": f"0x{decoded_source_offset:X}",
        "unit_size": unit_size,
        "crsa_header_hex": original.header.hex(" "),
        "source_text": source_text,
        "replacement_text": replacement_text,
        "source_utf16_code_units": source.code_units,
        "replacement_utf16_code_units": replacement.code_units,
        "source_marker_offset": source.marker_offset,
        "source_text_offset": source.text_offset,
        "source_end_offset": source.end_offset,
        "replacement_end_offset": replacement.end_offset,
        "plaintext_size_before": len(original.plaintext),
        "plaintext_size_after": len(rebuilt_plain),
        "plaintext_growth": len(rebuilt_plain) - len(original.plaintext),
        "encrypted_chunk_count_before": len(original.chunk_checksums),
        "encrypted_chunk_count_after": len(strict_checksums),
        "final_chunk_plain_bytes_before": len(original.plaintext) % 0x20 or 0x20,
        "final_chunk_plain_bytes_after": len(rebuilt_plain) % 0x20 or 0x20,
        "final_partial_checksum_before_hex": f"0x{original.chunk_checksums[-1]:04X}",
        "final_partial_checksum_after_hex": f"0x{strict_checksums[-1]:04X}",
        "record_size_before": len(original.record),
        "record_size_after": len(rebuilt_record),
        "record_growth": len(rebuilt_record) - len(original.record),
        "original_record_sha256": sha256(original.record),
        "rebuilt_record_sha256": sha256(rebuilt_record),
        "prefix_before_string_sha256": sha256(original.plaintext[: source.marker_offset]),
        "suffix_after_string_sha256": sha256(original.plaintext[source.end_offset :]),
        "cvmmsg3_declarations_before": old_cvm,
        "cvmmsg3_declarations_after": new_cvm,
        "cvmmsg3_index_rebuild": "not_applicable_non_CVMMsg3_UI_object",
        "verification": {
            "serialized_unicode_marker_and_length_readback": True,
            "replacement_exceeds_original_utf16_slot": replacement.code_units > source.code_units,
            "object_stream_prefix_preserved": True,
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
    parser = argparse.ArgumentParser(
        description="Build a variable-length Unicode CString replacement inside one CRsa RUO leaf."
    )
    parser.add_argument("--base-rio", type=Path, required=True)
    parser.add_argument("--block-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--source-raw-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--unit-size", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--source-text", required=True)
    parser.add_argument("--replacement-text", required=True)
    parser.add_argument("--output-ruo", type=Path, required=True)
    parser.add_argument("--output-record", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    report = build_variable_crsa_ruo(
        base_rio=args.base_rio,
        block_offset=args.block_offset,
        source_raw_offset=args.source_raw_offset,
        source_text=args.source_text,
        replacement_text=args.replacement_text,
        unit_size=args.unit_size,
        output_ruo=args.output_ruo,
        output_record=args.output_record,
        output_manifest=args.manifest,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
