from __future__ import annotations

import argparse
from pathlib import Path


TEST_GAME_DIR = Path(r"C:\Users\Administrator\Documents\Codex-Safe-Workspace\MuvLuv_PM_patch_test")
STEAM_GAME_DIR = Path(r"D:\Steam\steamapps\common\Muv-Luv photonmelodies")

RIO_KEY = 0x7E6B8CE2

RIO_NAME = "photonmelodies11.rio.002"
BLOCK_OFFSET = 1214091360
ENCRYPTED_OFFSET = 1214091371
PAYLOAD_OFFSET = 200432

OLD_TEXT = "【清十郎】「…\x03…\x03何だ…\x03…\x03と！？」\x01"
NEW_TEXT = "【清十郎】「…\x03…\x03测试…\x03…\x03啊！？」\x01"


def u32le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little")


def read_encrypted_at(data: bytes, off: int, key: int) -> tuple[bytes, int]:
    size1 = u32le(data, off) ^ 0xC92E568B
    size2 = u32le(data, off + 4) ^ 0xC92E568F
    size2 >>= 3
    size1 = (~size1) & 0xFFFFFFFF
    if size1 != size2:
        raise ValueError(f"invalid encrypted chunk at {off}: {size1=} {size2=}")

    pos = off + 8
    out = bytearray(size1)
    dst = 0
    while dst < size1:
        checksum = 0
        portion = min(0x20, size1 - dst)
        chunk = data[pos:pos + portion]
        if len(chunk) != portion:
            raise EOFError
        pos += portion
        for i, enc in enumerate(chunk):
            weight = portion - i
            b = enc ^ (key & 0xFF)
            out[dst] = b
            dst += 1
            checksum = (checksum + b * weight) & 0xFFFF
            bit = (key >> 15) & 1
            key = (~(bit + ((key * 2) & 0xFFFFFFFF) + 0xA3B376C9)) & 0xFFFFFFFF
        if portion < 0x20:
            break
        stored = int.from_bytes(data[pos:pos + 2], "little")
        pos += 2
        if stored != checksum:
            raise ValueError(f"checksum mismatch near {pos}: got {stored:04x} expected {checksum:04x}")
    return bytes(out), pos


def write_encrypted(plain: bytes, key: int, original_header: bytes | None = None) -> bytes:
    size = len(plain)
    out = bytearray()
    stored1 = ((~size) & 0xFFFFFFFF) ^ 0xC92E568B
    stored2 = ((size << 3) & 0xFFFFFFFF) ^ 0xC92E568F
    header = stored1.to_bytes(4, "little") + stored2.to_bytes(4, "little")
    if original_header is not None:
        if len(original_header) != 8:
            raise ValueError("original_header must be 8 bytes")
        # The second size dword stores the payload size in bits 3..31; the
        # low 3 bits are not used by GARbro's reader. Preserve them for
        # same-size edits so the encrypted chunk round-trips byte-for-byte.
        if (u32le(header, 0) != u32le(original_header, 0) or
                (u32le(header, 4) >> 3) != (u32le(original_header, 4) >> 3)):
            raise ValueError("original header does not describe this payload size")
        header = original_header
    out += header

    src = 0
    while src < size:
        portion = min(0x20, size - src)
        checksum = 0
        enc = bytearray()
        for i in range(portion):
            b = plain[src + i]
            weight = portion - i
            enc.append(b ^ (key & 0xFF))
            checksum = (checksum + b * weight) & 0xFFFF
            bit = (key >> 15) & 1
            key = (~(bit + ((key * 2) & 0xFFFFFFFF) + 0xA3B376C9)) & 0xFFFFFFFF
        out += enc
        src += portion
        if portion == 0x20:
            out += checksum.to_bytes(2, "little")
    return bytes(out)


def rio_path(game_dir: Path) -> Path:
    return game_dir / RIO_NAME


def roundtrip(path: Path) -> tuple[bool, int, int]:
    data = path.read_bytes()
    plain, end = read_encrypted_at(data, ENCRYPTED_OFFSET, RIO_KEY)
    encoded = write_encrypted(plain, RIO_KEY, data[ENCRYPTED_OFFSET:ENCRYPTED_OFFSET + 8])
    original = data[ENCRYPTED_OFFSET:end]
    return encoded == original, len(plain), len(encoded)


def patch(path: Path) -> None:
    data = bytearray(path.read_bytes())
    backup = path.with_suffix(path.suffix + ".before_reencrypt_test.bak")
    if not backup.exists():
        backup.write_bytes(data)

    plain, end = read_encrypted_at(data, ENCRYPTED_OFFSET, RIO_KEY)
    old = OLD_TEXT.encode("utf-16le")
    new = NEW_TEXT.encode("utf-16le")
    if len(old) != len(new):
        raise ValueError((len(old), len(new)))
    if plain[PAYLOAD_OFFSET:PAYLOAD_OFFSET + len(old)] != old:
        found = plain.find(old)
        raise ValueError(f"old text not at payload offset; found={found}")

    patched_plain = bytearray(plain)
    patched_plain[PAYLOAD_OFFSET:PAYLOAD_OFFSET + len(old)] = new
    encoded = write_encrypted(bytes(patched_plain), RIO_KEY, data[ENCRYPTED_OFFSET:ENCRYPTED_OFFSET + 8])
    if len(encoded) != end - ENCRYPTED_OFFSET:
        raise ValueError((len(encoded), end - ENCRYPTED_OFFSET))

    data[ENCRYPTED_OFFSET:end] = encoded
    path.write_bytes(data)
    print(f"patched={path}")
    print(f"backup={backup}")
    print(f"encrypted_range={ENCRYPTED_OFFSET}:{end}")
    print("old_visible=【清十郎】「…<03>…<03>何だ…<03>…<03>と！？」<01>")
    print("new_visible=【清十郎】「…<03>…<03>测试…<03>…<03>啊！？」<01>")


def restore(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".before_reencrypt_test.bak")
    if not backup.exists():
        backup = path.with_suffix(path.suffix + ".before_one_line_test.bak")
    if not backup.exists():
        raise FileNotFoundError(backup)
    path.write_bytes(backup.read_bytes())
    print(f"restored={path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["roundtrip", "patch", "restore"])
    parser.add_argument("--steam", action="store_true", help="operate on Steam install instead of test copy")
    args = parser.parse_args()

    path = rio_path(STEAM_GAME_DIR if args.steam else TEST_GAME_DIR)
    if args.mode == "roundtrip":
        ok, plain_size, encoded_size = roundtrip(path)
        print(f"path={path}")
        print(f"roundtrip_identical={ok}")
        print(f"plain_size={plain_size}")
        print(f"encoded_size={encoded_size}")
        if not ok:
            raise SystemExit(2)
    elif args.mode == "patch":
        patch(path)
    elif args.mode == "restore":
        restore(path)


if __name__ == "__main__":
    main()
