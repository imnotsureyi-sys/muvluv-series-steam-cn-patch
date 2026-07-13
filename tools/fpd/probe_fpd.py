import hashlib
import pathlib
import re
import struct
import sys
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


HEADER_SIZE = 0x38
ENTRY_SIZE = 0x20
SALT = b"11f32b0d98cfe8395fe4deeb75fff578"


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
    out = bytearray(len(data))
    n = len(keys)
    for i, b in enumerate(data):
        j = i + key_offset
        k = keys[(j // 16) % n]
        out[i] = b ^ ((k >> ((j & 15) * 8)) & 0xFF)
    return bytes(out)


def parse_pack(pack_path: pathlib.Path, keys: list[int], key_offset: int = 0) -> tuple[int, int, list[tuple[str, int, int, int]]]:
    with pack_path.open("rb") as f:
        header = f.read(HEADER_SIZE)
        if header[:4] != b"FPD\x00":
            raise RuntimeError("not an FPD pack")
        version = struct.unpack(">I", header[4:8])[0]
        file_count = struct.unpack(">Q", header[8:16])[0]
        data_start = struct.unpack(">Q", header[16:24])[0]
        f.seek(HEADER_SIZE)
        encrypted_index = f.read(data_start - HEADER_SIZE)

    index = xor_bytes(encrypted_index, keys, key_offset)
    names_start = ENTRY_SIZE * file_count
    names_buffer = index[names_start:]
    try:
        names = zlib.decompress(names_buffer)
    except zlib.error:
        names = names_buffer

    entries = []
    for i in range(file_count):
        row = index[i * ENTRY_SIZE : (i + 1) * ENTRY_SIZE]
        name_off, data_off, data_len, full_len = struct.unpack(">QQQQ", row)
        if name_off >= names_start + HEADER_SIZE:
            name_off -= names_start + HEADER_SIZE
        elif name_off >= names_start:
            name_off -= names_start
        try:
            end = names.index(0, name_off)
        except ValueError:
            continue
        name = names[name_off:end].decode("utf-8", "replace")
        if not name or "\ufffd" in name:
            continue
        entries.append((name, data_off, data_len, full_len))
    return version, data_start, entries


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python tools/fpd/probe_fpd.py <Scrambler.cs> <pack.bin> [filter]")
        return 2

    scrambler = pathlib.Path(sys.argv[1])
    pack = pathlib.Path(sys.argv[2])
    needle = sys.argv[3] if len(sys.argv) > 3 else ""

    crc_mode = "zlib"
    key_offset = 0
    if len(sys.argv) > 4:
        crc_mode = sys.argv[4]
    if len(sys.argv) > 5:
        key_offset = int(sys.argv[5], 0)

    keys = make_keys(load_base_keys(scrambler), crc_mode)
    version, data_start, entries = parse_pack(pack, keys, key_offset)
    print(f"version={version} entries={len(entries)} data_start=0x{data_start:X}")
    shown = 0
    for name, data_off, data_len, full_len in entries:
        if needle and needle.lower() not in name.lower():
            continue
        print(f"{data_off:012X} {data_len:10d} {full_len:10d} {name}")
        shown += 1
        if shown >= 200:
            break
    print(f"shown={shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
