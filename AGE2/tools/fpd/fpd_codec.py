"""Strict FPD index reader used by the AGE2 extraction workflow.

The key schedule is derived from ``Scrambler.cs`` in FatePackageManager so
that this repository does not silently embed a second, drifting key table.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import struct
from typing import NamedTuple
import zlib


HEADER_SIZE = 0x38
ENTRY_SIZE = 0x20
SALT = b"11f32b0d98cfe8395fe4deeb75fff578"


class FpdEntry(NamedTuple):
    name: str
    data_offset: int
    stored_length: int
    decompressed_length: int


def crc32_with_initial_hash(data: bytes, initial_hash: int, mode: str = "zlib") -> int:
    if mode == "zlib":
        return zlib.crc32(data, initial_hash) & 0xFFFFFFFF
    if mode == "internal":
        # System.IO.Hashing.Crc32 stores the bitwise-inverted public hash.
        # This is a sanity-check variant in case continuation semantics differ.
        return (~zlib.crc32(data, (~initial_hash) & 0xFFFFFFFF)) & 0xFFFFFFFF
    if mode == "plain":
        return zlib.crc32(data) & 0xFFFFFFFF
    raise ValueError(mode)


def load_base_keys(scrambler_cs: pathlib.Path) -> list[int]:
    text = scrambler_cs.read_text(encoding="utf-8")
    pairs = re.findall(r"new UInt128\(0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+)\)", text)
    if not pairs:
        raise RuntimeError(f"no UInt128 keys found in {scrambler_cs}")
    return [(int(hi, 16) << 64) | int(lo, 16) for hi, lo in pairs]


def make_keys(base_keys: list[int], crc_mode: str = "zlib") -> list[int]:
    keys = []
    for i, base in enumerate(base_keys):
        idx = struct.pack(">I", i)
        crc = crc32_with_initial_hash(idx, 0x73FBCBBE, crc_mode)
        digest = hashlib.md5(SALT + struct.pack(">I", crc)).digest()
        md5_int = int.from_bytes(digest, "little")
        keys.append(base ^ md5_int)
    return keys


def xor_bytes(data: bytes, keys: list[int], key_offset: int = 0) -> bytes:
    if not keys:
        raise ValueError("FPD key table must not be empty")
    if key_offset < 0:
        raise ValueError("FPD key offset must not be negative")
    out = bytearray(len(data))
    n = len(keys)
    for i, b in enumerate(data):
        j = i + key_offset
        k = keys[(j // 16) % n]
        out[i] = b ^ ((k >> ((j & 15) * 8)) & 0xFF)
    return bytes(out)


def parse_pack(
    pack_path: pathlib.Path, keys: list[int], key_offset: int = 0
) -> tuple[int, int, list[FpdEntry]]:
    pack_size = pack_path.stat().st_size
    with pack_path.open("rb") as f:
        header = f.read(HEADER_SIZE)
        if len(header) != HEADER_SIZE:
            raise RuntimeError("truncated FPD header")
        if header[:4] != b"FPD\x00":
            raise RuntimeError("not an FPD pack")
        version = struct.unpack(">I", header[4:8])[0]
        file_count = struct.unpack(">Q", header[8:16])[0]
        data_start = struct.unpack(">Q", header[16:24])[0]
        if not HEADER_SIZE <= data_start <= pack_size:
            raise RuntimeError("FPD index extent is outside the file")
        encrypted_index = f.read(data_start - HEADER_SIZE)

    index = xor_bytes(encrypted_index, keys, key_offset)
    names_start = ENTRY_SIZE * file_count
    if names_start > len(index):
        raise RuntimeError("FPD entry table exceeds the decrypted index")
    names_buffer = index[names_start:]
    try:
        names = zlib.decompress(names_buffer)
    except zlib.error:
        names = names_buffer

    entries: list[FpdEntry] = []
    for i in range(file_count):
        row = index[i * ENTRY_SIZE : (i + 1) * ENTRY_SIZE]
        name_off, data_off, data_len, full_len = struct.unpack(">QQQQ", row)
        if name_off >= len(names):
            raise RuntimeError(f"FPD entry {i} has an invalid name offset")
        try:
            end = names.index(0, name_off)
        except ValueError as exc:
            raise RuntimeError(f"FPD entry {i} has no NUL-terminated name") from exc
        try:
            name = names[name_off:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"FPD entry {i} has an invalid UTF-8 name") from exc
        if not name:
            raise RuntimeError(f"FPD entry {i} has an empty name")
        if data_start + data_off + data_len > pack_size:
            raise RuntimeError(f"FPD entry {i} data extent exceeds the file")
        entries.append(FpdEntry(name, data_off, data_len, full_len))
    return version, data_start, entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=pathlib.Path)
    parser.add_argument("--scrambler", type=pathlib.Path, required=True)
    parser.add_argument("--contains", default="", help="case-insensitive path filter")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    keys = make_keys(load_base_keys(args.scrambler))
    version, data_start, entries = parse_pack(args.pack, keys)
    print(f"version={version} entries={len(entries)} data_start=0x{data_start:X}")
    shown = 0
    for name, data_off, data_len, full_len in entries:
        if args.contains and args.contains.casefold() not in name.casefold():
            continue
        print(f"{data_off:012X} {data_len:10d} {full_len:10d} {name}")
        shown += 1
        if shown >= args.limit:
            break
    print(f"shown={shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
