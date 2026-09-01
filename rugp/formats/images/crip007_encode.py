#!/usr/bin/env python3
"""Audited literal encoder for the four legacy opaque CRip007 intertitles.

The scoped records use the legacy 0x28-byte header and an MSB-first RGB
bitstream.  They are exposed by AGES/GARbro as Bgr32: the native high byte
``0x80`` means fully opaque and is not a PNG alpha value.

This encoder deliberately targets only opaque grayscale canvases.  It changes
the three per-channel precision bytes in ``CompressInfo`` from 6 to 8, which
the CRip007 decoder supports, so every approved 8-bit antialiasing level can be
represented exactly.  The rest of the source header is preserved byte-for-byte
apart from the payload length field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from .crip007_decode import (
        decode_legacy_rip007_bgra,
        legacy_bgra_to_rgba,
    )
except ImportError:  # Direct script execution.
    from crip007_decode import (  # type: ignore
        decode_legacy_rip007_bgra,
        legacy_bgra_to_rgba,
    )


HEADER_SIZE = 0x28
PAYLOAD_LENGTH_OFFSET = 0x20
COMPRESS_Q_OFFSET = 0x16
PRED_FLAG_OFFSET = 0x19
B_BITS_OFFSET = 0x1A
G_BITS_OFFSET = 0x1B
R_BITS_OFFSET = 0x1C
EXTENT_OFFSET_BIAS = 0xA2FB6AD1
U32_MASK = 0xFFFFFFFF


class CRip007EncodeError(ValueError):
    """Raised when an input does not satisfy the narrow audited profile."""


@dataclass(frozen=True)
class LegacyHeader:
    width: int
    height: int
    draw_width: int
    draw_height: int
    kind: int
    q: int
    pred_flag: int
    b_bits: int
    g_bits: int
    r_bits: int
    payload_length: int


class MsbBitWriter:
    def __init__(self) -> None:
        self._bits: list[int] = []

    @property
    def bit_length(self) -> int:
        return len(self._bits)

    def bit(self, value: int | bool) -> None:
        self._bits.append(1 if value else 0)

    def get_int(self, value: int) -> None:
        """Inverse of ``rip_get_int`` for one strictly positive integer."""

        if value < 1:
            raise CRip007EncodeError(f"GetInt value must be positive: {value}")
        suffix = f"{value:b}"[1:]
        for digit in suffix:
            self.bit(1)
            self.bit(digit == "1")
        self.bit(0)

    def get_signed(self, value: int) -> None:
        if value == 0:
            raise CRip007EncodeError("GetSigned cannot encode zero")
        self.bit(value < 0)
        self.get_int(abs(value))

    def finish_exact(self) -> bytes:
        if self.bit_length % 8:
            raise CRip007EncodeError(
                f"bitstream is not byte-exact: {self.bit_length} bits"
            )
        output = bytearray(self.bit_length // 8)
        for index, value in enumerate(self._bits):
            output[index // 8] |= value << (7 - index % 8)
        return bytes(output)


class ReferenceMsbReader:
    """Small independent decoder used only as a cross-check for our profile."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.bit_index = 0

    def bit(self) -> int:
        if self.bit_index >= len(self.data) * 8:
            raise CRip007EncodeError("reference decoder reached end of payload")
        value = (self.data[self.bit_index // 8] >> (7 - self.bit_index % 8)) & 1
        self.bit_index += 1
        return value

    def get_int(self) -> int:
        value = 1
        while self.bit():
            value = (value << 1) | self.bit()
        return value

    def get_signed(self) -> int:
        negative = bool(self.bit())
        value = self.get_int()
        return -value if negative else value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_legacy_record(record: bytes) -> LegacyHeader:
    if len(record) < HEADER_SIZE:
        raise CRip007EncodeError("record is shorter than the 0x28-byte header")
    if record[:3] != b"\x00\x04\x45":
        raise CRip007EncodeError("record signature is not 00 04 45")
    width = int.from_bytes(record[0x06:0x08], "little")
    height = int.from_bytes(record[0x08:0x0A], "little")
    draw_width = int.from_bytes(record[0x0E:0x10], "little")
    draw_height = int.from_bytes(record[0x10:0x12], "little")
    kind = record[0x12]
    payload_length = int.from_bytes(
        record[PAYLOAD_LENGTH_OFFSET : PAYLOAD_LENGTH_OFFSET + 4], "little"
    )
    if min(width, height, draw_width, draw_height) <= 0:
        raise CRip007EncodeError("record dimensions are invalid")
    if (width, height) != (draw_width, draw_height):
        raise CRip007EncodeError("scoped encoder requires a full-canvas record")
    if kind != 2:
        raise CRip007EncodeError(f"scoped encoder requires opaque kind 2, got {kind}")
    if HEADER_SIZE + payload_length != len(record):
        raise CRip007EncodeError(
            "legacy record extent is not exactly 0x28 + payload length"
        )
    header = LegacyHeader(
        width=width,
        height=height,
        draw_width=draw_width,
        draw_height=draw_height,
        kind=kind,
        q=record[COMPRESS_Q_OFFSET],
        pred_flag=record[PRED_FLAG_OFFSET],
        b_bits=record[B_BITS_OFFSET],
        g_bits=record[G_BITS_OFFSET],
        r_bits=record[R_BITS_OFFSET],
        payload_length=payload_length,
    )
    if not all(1 <= value <= 8 for value in (header.b_bits, header.g_bits, header.r_bits)):
        raise CRip007EncodeError("source channel precision is outside 1..8")
    return header


def _explicit_bits(previous: int, value: int) -> list[int]:
    writer = MsbBitWriter()
    writer.bit(0)  # not a vertical copy
    delta = value - previous
    if delta:
        writer.bit(1)
        writer.get_signed(delta)
    else:
        writer.bit(0)
    writer.bit(0)  # no blue residual; grayscale follows green exactly
    writer.bit(0)  # no red residual
    return writer._bits  # Internal immutable-by-convention token.


def encode_opaque_grayscale_payload(gray: bytes, width: int, height: int) -> bytes:
    if width <= 0 or height <= 0 or len(gray) != width * height:
        raise CRip007EncodeError("grayscale buffer size does not match dimensions")

    # Each row is one literal run.  The decoder's run grammar needs no repeat
    # count after a literal run reaches the row width.
    prefix = MsbBitWriter()
    row_prefix_bits: list[list[int]] = []
    for _ in range(height):
        row_writer = MsbBitWriter()
        row_writer.get_int(width)
        row_prefix_bits.append(row_writer._bits)

    # Tokenise first so a small number of redundant explicit black pixels can
    # make the whole stream end exactly on a byte boundary.  A vertical copy is
    # 1 bit; an explicit unchanged grayscale pixel is 4 bits, i.e. +3 bits.
    tokens: list[list[int]] = []
    adjustable: list[tuple[int, int]] = []
    for y in range(height):
        tokens.append(row_prefix_bits[y])
        previous = 0
        for x in range(width):
            index = y * width + x
            value = gray[index]
            above_equal = y > 0 and value == gray[index - width]
            if above_equal:
                tokens.append([1])
                if value == previous:
                    adjustable.append((len(tokens) - 1, value))
            else:
                tokens.append(_explicit_bits(previous, value))
            previous = value

    bit_length = sum(len(token) for token in tokens)
    remainder = bit_length % 8
    if remainder:
        needed = next(
            (count for count in range(1, 8) if (remainder + 3 * count) % 8 == 0),
            None,
        )
        if needed is None or len(adjustable) < needed:
            raise CRip007EncodeError("could not make payload end on a byte boundary")
        for token_index, _pixel_value in adjustable[-needed:]:
            # These pixels equal both the pixel above and the current horizontal
            # predictor, so the explicit zero-delta form is semantically exact.
            tokens[token_index] = [0, 0, 0, 0]

    for token in tokens:
        for value in token:
            prefix.bit(value)
    return prefix.finish_exact()


def encode_record_from_rgba(
    source_record: bytes,
    rgba: bytes,
    width: int,
    height: int,
) -> bytes:
    source_header = parse_legacy_record(source_record)
    if (width, height) != (source_header.width, source_header.height):
        raise CRip007EncodeError("candidate dimensions differ from source record")
    if len(rgba) != width * height * 4:
        raise CRip007EncodeError("RGBA buffer size does not match dimensions")

    gray = bytearray(width * height)
    for pixel in range(width * height):
        red, green, blue, alpha = rgba[pixel * 4 : pixel * 4 + 4]
        if alpha != 0xFF:
            raise CRip007EncodeError("scoped CRip007 records must be fully opaque")
        if red != green or green != blue:
            raise CRip007EncodeError("scoped CRip007 records must be grayscale")
        gray[pixel] = red

    payload = encode_opaque_grayscale_payload(bytes(gray), width, height)
    output_header = bytearray(source_record[:HEADER_SIZE])
    # CRip007 accepts channel widths 1..8.  Eight-bit widths preserve the
    # approved antialiasing exactly; no blue/red residuals are emitted.
    output_header[B_BITS_OFFSET] = 8
    output_header[G_BITS_OFFSET] = 8
    output_header[R_BITS_OFFSET] = 8
    output_header[PAYLOAD_LENGTH_OFFSET : PAYLOAD_LENGTH_OFFSET + 4] = len(
        payload
    ).to_bytes(4, "little")
    return bytes(output_header) + payload


def decode_record_rgba(record: bytes) -> tuple[LegacyHeader, bytes]:
    header = parse_legacy_record(record)
    payload = record[HEADER_SIZE:]
    bgra = decode_legacy_rip007_bgra(
        payload,
        header.width,
        header.height,
        header.q,
        header.b_bits,
        header.g_bits,
        header.r_bits,
        header.pred_flag,
    )
    return header, bytes(legacy_bgra_to_rgba(bgra))


def decode_scoped_reference_rgba(record: bytes) -> bytes:
    """Decode the encoder's 8-bit/no-residual profile without shared helpers."""

    header = parse_legacy_record(record)
    if (header.b_bits, header.g_bits, header.r_bits) != (8, 8, 8):
        raise CRip007EncodeError("reference decoder requires 8-bit channel widths")
    bits = ReferenceMsbReader(record[HEADER_SIZE:])
    gray = bytearray(header.width * header.height)
    for y in range(header.height):
        x = 0
        previous = 0
        while x < header.width:
            literal_count = bits.get_int()
            if x + literal_count > header.width:
                raise CRip007EncodeError("reference literal run crosses row")
            for _ in range(literal_count):
                if bits.bit():
                    if y == 0:
                        raise CRip007EncodeError("first-row vertical copy is invalid")
                    value = gray[(y - 1) * header.width + x]
                else:
                    delta = bits.get_signed() if bits.bit() else 0
                    if bits.bit() or bits.bit():
                        raise CRip007EncodeError("scoped stream unexpectedly uses residuals")
                    value = previous + delta
                    if not 0 <= value <= 255:
                        raise CRip007EncodeError("reference grayscale predictor overflow")
                gray[y * header.width + x] = value
                previous = value
                x += 1
            if x >= header.width:
                break
            repeat_count = bits.get_int()
            if x + repeat_count > header.width:
                raise CRip007EncodeError("reference repeat run crosses row")
            gray[y * header.width + x : y * header.width + x + repeat_count] = bytes(
                (previous,)
            ) * repeat_count
            x += repeat_count
    if bits.bit_index != len(record[HEADER_SIZE:]) * 8:
        raise CRip007EncodeError("reference decoder did not consume payload exactly")
    return b"".join(bytes((value, value, value, 255)) for value in gray)


def encode_extent_offset_unit4(byte_offset: int) -> int:
    if byte_offset < 0 or byte_offset % 4:
        raise CRip007EncodeError("source byte offset is not unit-4 aligned")
    return ((byte_offset // 4) + EXTENT_OFFSET_BIAS) & U32_MASK


def read_source_record(path: Path, offset: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        header = stream.read(HEADER_SIZE)
        if len(header) != HEADER_SIZE:
            raise CRip007EncodeError(f"truncated source header at {path}:{offset:#x}")
        payload_length = int.from_bytes(
            header[PAYLOAD_LENGTH_OFFSET : PAYLOAD_LENGTH_OFFSET + 4], "little"
        )
        payload = stream.read(payload_length)
    if len(payload) != payload_length:
        raise CRip007EncodeError(f"truncated source payload at {path}:{offset:#x}")
    return header + payload


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def audit_four_records(
    *,
    pf_archive: Path,
    pm_archive: Path,
    candidate_png: Path,
    output_dir: Path,
) -> dict[str, Any]:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise CRip007EncodeError("Pillow is required for PNG input") from exc

    scopes = (
        ("PF", 0x1AD8246C, 0xA9B173EC, pf_archive),
        ("PF", 0x1B158BB4, 0xA9C0CDBE, pf_archive),
        ("PM", 0x65D765DC, 0xBC714448, pm_archive),
        ("PM", 0x663F3BEC, 0xBC8B39CC, pm_archive),
    )
    expected_source_record_sha = (
        "96c70b17d7a01f8335c42255e651aebba8a47c6d6a429b88e53fb5e745d8cfa1"
    )
    expected_source_rgba_sha = (
        "b97add760ed8f0092e139267c1b332365c01ad20e7dd9df84abac03956934aa2"
    )

    image = Image.open(candidate_png).convert("RGBA")
    candidate_rgba = image.tobytes()
    candidate_rgba_sha = sha256_bytes(candidate_rgba)
    rows: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    records_dir = output_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    for game, offset, expected_source_raw, archive in scopes:
        source_record = read_source_record(archive, offset)
        source_header, source_rgba = decode_record_rgba(source_record)
        source_sha = sha256_bytes(source_record)
        source_rgba_sha = sha256_bytes(source_rgba)
        computed_source_raw = encode_extent_offset_unit4(offset)
        if source_sha != expected_source_record_sha:
            raise CRip007EncodeError(f"source record identity changed at {game}:{offset:#x}")
        if source_rgba_sha != expected_source_rgba_sha:
            raise CRip007EncodeError(f"source decode identity changed at {game}:{offset:#x}")
        if computed_source_raw != expected_source_raw:
            raise CRip007EncodeError(f"unit-4 source key changed at {game}:{offset:#x}")
        if (image.width, image.height) != (source_header.width, source_header.height):
            raise CRip007EncodeError("candidate dimensions differ from source")

        encoded = encode_record_from_rgba(
            source_record, candidate_rgba, image.width, image.height
        )
        encoded_header, decoded_rgba = decode_record_rgba(encoded)
        if decoded_rgba != candidate_rgba:
            raise CRip007EncodeError(f"candidate roundtrip differs at {game}:{offset:#x}")
        reference_rgba = decode_scoped_reference_rgba(encoded)
        if reference_rgba != candidate_rgba or reference_rgba != decoded_rgba:
            raise CRip007EncodeError(
                f"independent reference decoder differs at {game}:{offset:#x}"
            )
        record_name = f"{game.lower()}_rio000_0x{offset:08x}_crip007.record.bin"
        record_path = records_dir / record_name
        record_path.write_bytes(encoded)
        rows.append(
            {
                "game": game,
                "source_byte_offset": offset,
                "source_byte_offset_hex": f"0x{offset:08X}",
                "source_raw_offset": expected_source_raw,
                "source_raw_offset_hex": f"0x{expected_source_raw:08X}",
                "unit_size": 4,
                "source_record_sha256": source_sha,
                "source_record_extent": len(source_record),
                "source_payload_consumed_exactly": True,
                "source_rgba_sha256": source_rgba_sha,
                "record_path": str(record_path.resolve()),
                "record_sha256": sha256_bytes(encoded),
                "record_size": len(encoded),
                "payload_length": encoded_header.payload_length,
                "payload_start": HEADER_SIZE,
                "trailer_size": 0,
                "channel_bits": [
                    encoded_header.b_bits,
                    encoded_header.g_bits,
                    encoded_header.r_bits,
                ],
                "native_high_byte": "0x80 Bgr32 full opacity",
                "decoded_png_alpha": 255,
                "candidate_rgba_sha256": candidate_rgba_sha,
                "decoded_rgba_sha256": sha256_bytes(decoded_rgba),
                "reference_decoded_rgba_sha256": sha256_bytes(reference_rgba),
                "independent_decoders_agree": True,
                "max_channel_absolute_error": 0,
                "changed_pixel_count_after_roundtrip": 0,
                "roundtrip_exact": True,
            }
        )

    report = {
        "schema": "photon-crip007-encoder-independent-audit/v1",
        "status": "pass",
        "scope_count": 4,
        "candidate_png": str(candidate_png.resolve()),
        "candidate_png_sha256": sha256_bytes(candidate_png.read_bytes()),
        "candidate_rgba_sha256": candidate_rgba_sha,
        "source_records_byte_identical": len({row["source_record_sha256"] for row in rows}) == 1,
        "replacement_records_byte_identical": len({row["record_sha256"] for row in rows}) == 1,
        "all_roundtrips_exact": all(row["roundtrip_exact"] for row in rows),
        "all_independent_decoders_agree": all(
            row["independent_decoders_agree"] for row in rows
        ),
        "all_unit4_keys_exact": True,
        "all_extents_exact": True,
        "rows": rows,
    }
    write_json(output_dir / "audit.json", report)
    return report


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pf-archive", type=Path, required=True)
    parser.add_argument("--pm-archive", type=Path, required=True)
    parser.add_argument("--candidate-png", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit_four_records(
        pf_archive=args.pf_archive,
        pm_archive=args.pm_archive,
        candidate_png=args.candidate_png,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
