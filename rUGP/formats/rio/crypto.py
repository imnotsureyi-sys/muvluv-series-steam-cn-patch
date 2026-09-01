from __future__ import annotations

from dataclasses import dataclass


U32_MASK = 0xFFFFFFFF
ENCRYPTED_SIZE_XOR_1 = 0xC92E568B
ENCRYPTED_SIZE_XOR_2 = 0xC92E568F
ENCRYPTED_KEY_STEP = 0xA3B376C9
RIO_KEY = 0x7E6B8CE2
ICI_KEY = 0xB29D5A0C
EXTENT_OFFSET_BIAS = 0xA2FB6AD1
EXTENT_SIZE_BIAS = 0xE7B5D9F8


class RioRebuildError(ValueError):
    pass


@dataclass(frozen=True)
class EncryptedBlock:
    plaintext: bytes
    consumed: int
    header: bytes


def round_up(value: int, alignment: int) -> int:
    if value < 0 or alignment <= 0:
        raise RioRebuildError("value must be non-negative and alignment must be positive")
    return (value + alignment - 1) // alignment * alignment


def decode_extent_offset(raw_offset: int, unit_size: int) -> int:
    if unit_size <= 0:
        raise RioRebuildError("unit_size must be positive")
    units = (raw_offset - EXTENT_OFFSET_BIAS) & U32_MASK
    return units * unit_size


def encode_extent_offset(byte_offset: int, unit_size: int) -> int:
    if byte_offset < 0 or unit_size <= 0 or byte_offset % unit_size:
        raise RioRebuildError("extent offset must be non-negative and aligned to unit_size")
    units = byte_offset // unit_size
    if units > U32_MASK:
        raise RioRebuildError("extent offset exceeds the 32-bit unit field")
    return (units + EXTENT_OFFSET_BIAS) & U32_MASK


def decode_extent_size(raw_size: int) -> int:
    a = (raw_size - EXTENT_SIZE_BIAS) & U32_MASK
    low_19 = a >> 13
    return ((((a - (low_19 & 0xFFF)) & U32_MASK) << 19) & U32_MASK) | low_19


def encode_extent_size(size: int) -> int:
    if not 0 <= size <= U32_MASK:
        raise RioRebuildError("extent size must fit in 32 bits")
    low_19 = size & 0x7FFFF
    high_13 = size >> 19
    low_13 = (high_13 + (low_19 & 0xFFF)) & 0x1FFF
    shuffled = ((low_19 << 13) | low_13) & U32_MASK
    encoded = (shuffled + EXTENT_SIZE_BIAS) & U32_MASK
    if decode_extent_size(encoded) != size:
        raise RioRebuildError("internal extent-size inverse check failed")
    return encoded


def encrypted_storage_size(plain_size: int) -> int:
    if plain_size < 0:
        raise RioRebuildError("plain_size must be non-negative")
    return 8 + plain_size + 2 * (plain_size // 0x20)


def _advance_key(key: int) -> int:
    bit = (key >> 15) & 1
    return (~(bit + ((key * 2) & U32_MASK) + ENCRYPTED_KEY_STEP)) & U32_MASK


def decode_encrypted_block(data: bytes, key: int) -> EncryptedBlock:
    if len(data) < 8:
        raise RioRebuildError("encrypted block header is truncated")
    stored1 = int.from_bytes(data[0:4], "little")
    stored2 = int.from_bytes(data[4:8], "little")
    size1 = (~(stored1 ^ ENCRYPTED_SIZE_XOR_1)) & U32_MASK
    size2 = ((stored2 ^ ENCRYPTED_SIZE_XOR_2) & U32_MASK) >> 3
    if size1 != size2:
        raise RioRebuildError(f"encrypted block size mismatch: {size1} != {size2}")
    expected = encrypted_storage_size(size1)
    if len(data) < expected:
        raise RioRebuildError(f"encrypted block is truncated: need {expected}, got {len(data)}")

    out = bytearray(size1)
    src = 8
    dst = 0
    state = key & U32_MASK
    while dst < size1:
        portion = min(0x20, size1 - dst)
        checksum = 0
        for i in range(portion):
            value = data[src + i] ^ (state & 0xFF)
            out[dst + i] = value
            checksum = (checksum + value * (portion - i)) & 0xFFFF
            state = _advance_key(state)
        src += portion
        dst += portion
        if portion == 0x20:
            stored_checksum = int.from_bytes(data[src : src + 2], "little")
            if stored_checksum != checksum:
                raise RioRebuildError(
                    f"encrypted checksum mismatch at stored offset 0x{src:X}: "
                    f"{stored_checksum:04X} != {checksum:04X}"
                )
            src += 2
    return EncryptedBlock(bytes(out), src, data[:8])


def encode_encrypted_block(plaintext: bytes, key: int, preserved_header: bytes | None = None) -> bytes:
    size = len(plaintext)
    if preserved_header is not None:
        if len(preserved_header) != 8:
            raise RioRebuildError("preserved encrypted header must be exactly 8 bytes")
        probe = decode_encrypted_header(preserved_header)
        if probe != size:
            raise RioRebuildError(f"preserved header describes {probe} bytes, not {size}")
        header = preserved_header
    else:
        stored1 = ((~size) & U32_MASK) ^ ENCRYPTED_SIZE_XOR_1
        stored2 = ((size << 3) & U32_MASK) ^ ENCRYPTED_SIZE_XOR_2
        header = stored1.to_bytes(4, "little") + stored2.to_bytes(4, "little")

    out = bytearray(header)
    src = 0
    state = key & U32_MASK
    while src < size:
        portion = min(0x20, size - src)
        checksum = 0
        for i in range(portion):
            value = plaintext[src + i]
            out.append(value ^ (state & 0xFF))
            checksum = (checksum + value * (portion - i)) & 0xFFFF
            state = _advance_key(state)
        src += portion
        if portion == 0x20:
            out.extend(checksum.to_bytes(2, "little"))
    return bytes(out)


def decode_encrypted_header(header: bytes) -> int:
    if len(header) != 8:
        raise RioRebuildError("encrypted header must be exactly 8 bytes")
    stored1 = int.from_bytes(header[0:4], "little")
    stored2 = int.from_bytes(header[4:8], "little")
    size1 = (~(stored1 ^ ENCRYPTED_SIZE_XOR_1)) & U32_MASK
    size2 = ((stored2 ^ ENCRYPTED_SIZE_XOR_2) & U32_MASK) >> 3
    if size1 != size2:
        raise RioRebuildError(f"encrypted header size mismatch: {size1} != {size2}")
    return size1


def _deinterleave_columns(data: bytes, lanes: int) -> bytes:
    count, tail = divmod(len(data), lanes)
    out = bytearray(len(data))
    src = 0
    dst = 0
    for _ in range(count):
        for lane in range(lanes):
            out[dst] = data[src + count * lane]
            dst += 1
        src += 1
    if tail:
        out[dst:] = data[len(data) - tail :]
    return bytes(out)


def _inverse_deinterleave_columns(data: bytes, lanes: int) -> bytes:
    count, tail = divmod(len(data), lanes)
    out = bytearray(len(data))
    src = 0
    for row in range(count):
        for lane in range(lanes):
            out[row + count * lane] = data[src]
            src += 1
    if tail:
        out[len(data) - tail :] = data[src:]
    return bytes(out)


def decrypt_ici_payload(data: bytes) -> bytes:
    stage1 = bytearray(_deinterleave_columns(data, 6))
    acc = 0
    for i, value in enumerate(stage1):
        value = (value - acc) & 0xFF
        acc = (acc + value) & 0xFF
        stage1[i] = value ^ 0xA5

    stage2 = bytearray(_deinterleave_columns(bytes(stage1), 5))
    acc = 0
    for i in range(len(stage2) - 1, -1, -1):
        value = (stage2[i] - acc) & 0xFF
        acc = (acc + value) & 0xFF
        stage2[i] = value

    stage3 = bytearray(_deinterleave_columns(bytes(stage2), 3))
    masks = (0x18, 0x3F, 0xE2)
    full = len(stage3) - len(stage3) % 3
    for i in range(full):
        stage3[i] ^= masks[i % 3]
    return bytes(stage3)


def encrypt_ici_payload(decoded: bytes) -> bytes:
    stage3 = bytearray(decoded)
    masks = (0x18, 0x3F, 0xE2)
    full = len(stage3) - len(stage3) % 3
    for i in range(full):
        stage3[i] ^= masks[i % 3]
    stage2_rolled = _inverse_deinterleave_columns(bytes(stage3), 3)

    stage2 = bytearray(len(stage2_rolled))
    next_original = 0
    for i in range(len(stage2_rolled) - 1, -1, -1):
        original = (stage2_rolled[i] + next_original) & 0xFF
        stage2[i] = original
        next_original = original
    stage1_rolled = _inverse_deinterleave_columns(bytes(stage2), 5)

    stage1 = bytearray(len(stage1_rolled))
    previous_original = 0
    for i, value in enumerate(stage1_rolled):
        delta = value ^ 0xA5
        original = (delta + previous_original) & 0xFF
        stage1[i] = original
        previous_original = original
    return _inverse_deinterleave_columns(bytes(stage1), 6)
