from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STEAM_PM = Path(r"D:\Steam\steamapps\common\Muv-Luv photonmelodies")
DESKTOP_TABLE = Path(r"C:\Users\Administrator\Desktop\photonmelodies_RIO文本提取_查看\photonmelodies_rio_text_master_v1.csv")

ICI_KEY = 0xB29D5A0C
RIO_KEY = 0x7E6B8CE2


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
            raise ValueError(f"checksum mismatch at {pos}: got {stored:04x} expected {checksum:04x}")
    return bytes(out), pos


def decrypt_ici(input_data: bytes) -> bytes:
    output = bytearray(len(input_data))
    src = dst = 0
    chunk_count, tail_size = divmod(len(input_data), 6)
    for _ in range(chunk_count):
        for k in range(6):
            output[dst] = input_data[src + chunk_count * k]
            dst += 1
        src += 1
    if tail_size:
        output[dst:dst + tail_size] = input_data[len(input_data) - tail_size:]

    acc = 0
    for i in range(len(output)):
        output[i] = (output[i] - acc) & 0xFF
        acc = (acc + output[i]) & 0xFF
        output[i] ^= 0xA5

    temp = bytearray(len(input_data))
    src = dst = 0
    chunk_count, tail_size = divmod(len(input_data), 5)
    for _ in range(chunk_count):
        for k in range(5):
            temp[dst] = output[src + chunk_count * k]
            dst += 1
        src += 1
    if tail_size:
        temp[dst:dst + tail_size] = output[len(output) - tail_size:]

    acc = 0
    for i in range(len(temp) - 1, -1, -1):
        temp[i] = (temp[i] - acc) & 0xFF
        acc = (acc + temp[i]) & 0xFF

    final = bytearray(len(input_data))
    src = dst = 0
    chunk_count, tail_size = divmod(len(input_data), 3)
    masks = (0x18, 0x3F, 0xE2)
    for _ in range(chunk_count):
        for k in range(3):
            final[dst] = temp[src + chunk_count * k] ^ masks[k]
            dst += 1
        src += 1
    if tail_size:
        final[dst:dst + tail_size] = temp[len(temp) - tail_size:]
    return bytes(final)


def target_row() -> dict[str, str]:
    with DESKTOP_TABLE.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["stable_id"] == "pm:static:photonmelodies11.rio.002:1214091360:00200432":
                return row
    raise KeyError("target row not found")


def main() -> None:
    row = target_row()
    rio_file = STEAM_PM / row["rio_file"]
    rio_data = rio_file.read_bytes()
    block_offset = int(row["crsa_block_offset"])
    payload_offset = int(row["payload_offset"])
    header = rio_data[block_offset:block_offset + 16]

    probes: dict[str, object] = {
        "target": row,
        "rio_file": str(rio_file),
        "block_offset": block_offset,
        "payload_offset": payload_offset,
        "header_hex": header.hex(),
    }

    # PM data block currently starts with a 3-byte big-endian encrypted payload size,
    # followed by 8 bytes of object/header fields observed in the extraction table.
    encrypted_offset = block_offset + 11
    probes["encrypted_offset_assumed"] = encrypted_offset
    cipher_prefix = rio_data[encrypted_offset:encrypted_offset + 64]
    probes["cipher_prefix_sha256"] = hashlib.sha256(cipher_prefix).hexdigest()
    probes["cipher_prefix_hex"] = cipher_prefix.hex()

    for key_name, key in [("ici", ICI_KEY), ("rio", RIO_KEY), ("zero", 0)]:
        try:
            dec, end = read_encrypted_at(rio_data, block_offset, key)
            probes[f"read_encrypted_at_block_{key_name}"] = {
                "size": len(dec),
                "end": end,
                "head_hex": dec[:64].hex(),
            }
        except Exception as e:
            probes[f"read_encrypted_at_block_{key_name}_error"] = str(e)
        try:
            dec, end = read_encrypted_at(rio_data, encrypted_offset, key)
            probes[f"read_encrypted_at_payload_{key_name}"] = {
                "size": len(dec),
                "end": end,
                "head_hex": dec[:64].hex(),
                "target_utf16le_found": dec.find(row["jp_text"].encode("utf-16le")),
            }
        except Exception as e:
            probes[f"read_encrypted_at_payload_{key_name}_error"] = str(e)

    ici_path = STEAM_PM / "photonmelodies11.rio.ici"
    ici_raw = ici_path.read_bytes()
    try:
        ici_encrypted, ici_end = read_encrypted_at(ici_raw, 0, ICI_KEY)
        ici_dec = decrypt_ici(ici_encrypted)
        probes["ici"] = {
            "encrypted_size": len(ici_encrypted),
            "encrypted_end": ici_end,
            "decrypted_size": len(ici_dec),
            "head_hex": ici_dec[:64].hex(),
            "head_ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in ici_dec[:64]),
        }
    except Exception as e:
        probes["ici_error"] = str(e)

    out = REPO_ROOT / "outputs" / "photonmelodies_text" / "rio_crypto_probe_target.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(probes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    print(json.dumps(probes, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
