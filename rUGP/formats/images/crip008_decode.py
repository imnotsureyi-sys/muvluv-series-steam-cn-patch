from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MASK32 = 0xFFFFFFFF
CRIP008_CODE_TABLE_SIZE = 0x1000 * 2
MAX_CRIP008_PIXELS = 16 * 1024 * 1024
SUPPORTED_CRIP008_HEADER_VERSIONS = {0, 0x81}
SUPPORTED_CRIP008_FLAG_MASK = 0x07


@dataclass(frozen=True)
class Crip008Header:
    width: int
    height: int
    x_offset: int
    y_offset: int
    draw_width: int
    draw_height: int
    kind: int
    depth: int
    header_version: int
    compress_flags: int
    b_bits: int
    g_bits: int
    r_bits: int
    predict_green: bool
    predict_red_blue: bool
    flag7: bool
    flag8: bool
    flag_c: bool
    payload_start: int
    payload_length: int


def u32(value: int) -> int:
    return value & MASK32


def i32(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


def parse_crip008_header(data: bytes) -> Crip008Header:
    if len(data) < 0x29:
        raise ValueError("CRip008 header is truncated")
    if data[:3] != b"\x00\x04\x45":
        raise ValueError(f"not a CRip008 resource: magic={data[:3].hex()}")
    flags = data[0x16]
    return Crip008Header(
        width=int.from_bytes(data[0x06:0x08], "little"),
        height=int.from_bytes(data[0x08:0x0A], "little"),
        x_offset=int.from_bytes(data[0x0A:0x0C], "little", signed=True),
        y_offset=int.from_bytes(data[0x0C:0x0E], "little", signed=True),
        draw_width=int.from_bytes(data[0x0E:0x10], "little"),
        draw_height=int.from_bytes(data[0x10:0x12], "little"),
        kind=data[0x12],
        depth=data[0x13],
        header_version=int.from_bytes(data[0x14:0x16], "little"),
        compress_flags=flags,
        b_bits=data[0x17],
        g_bits=data[0x18],
        r_bits=data[0x19],
        predict_green=bool(flags & 0x01),
        predict_red_blue=bool(flags & 0x02),
        flag7=bool(flags & 0x04),
        flag8=bool(flags & 0x08),
        flag_c=bool(flags & 0x10),
        payload_start=0x29,
        payload_length=int.from_bytes(data[0x1D:0x21], "little"),
    )


def read_crip008_resource(path: Path, offset: int) -> tuple[Crip008Header, bytes]:
    with path.open("rb") as handle:
        handle.seek(offset)
        head = handle.read(0x29)
        header = parse_crip008_header(head)
        payload = handle.read(header.payload_length)
    if len(payload) != header.payload_length:
        raise ValueError(
            f"payload truncated at 0x{offset:08X}: "
            f"{len(payload)} < {header.payload_length}"
        )
    return header, payload


_CODE_TABLE: bytes | None = None


def load_crip008_code_table() -> bytes:
    global _CODE_TABLE
    if _CODE_TABLE is None:
        table = bytearray(CRIP008_CODE_TABLE_SIZE)
        for index in range(0x1000):
            value = 1
            bit_count = 1
            bit = 12
            while True:
                bit_count += 2
                bit -= 1
                value = ((index >> (bit & 0x1F)) & 1) + value * 2
                bit -= 1
                if ((index >> (bit & 0x1F)) & 1) == 0:
                    break
            if bit_count >= 0x0E:
                value >>= 1
            table[index * 2] = value & 0xFF
            table[index * 2 + 1] = bit_count & 0xFF
        _CODE_TABLE = bytes(table)
    return _CODE_TABLE


class NativeMsbBitReader:
    def __init__(self, data: bytes, code_table: bytes):
        if len(code_table) != CRIP008_CODE_TABLE_SIZE:
            raise ValueError("CRip008 code table must contain 4096 two-byte entries")
        self.data = data
        self.table = code_table
        self.pos = 0
        self.end = len(data)
        self.bit_position = 0
        self.total_bits = len(data) * 8
        self.bits_left = 32
        self.bits = 0
        for shift in (24, 16, 8, 0):
            value = data[self.pos] if self.pos < self.end else 0
            self.pos += 1 if self.pos < self.end else 0
            self.bits = u32(self.bits | (value << shift))

    def _refill(self) -> None:
        if self.bits_left > 24:
            return
        shift = 24 - self.bits_left
        count = (shift >> 3) + 1
        self.bits_left += count * 8
        while count:
            if self.pos < self.end:
                self.bits = u32(self.bits | (self.data[self.pos] << (shift & 0x1F)))
                self.pos += 1
            shift -= 8
            count -= 1

    def consume(self, bit_count: int) -> None:
        if bit_count < 0:
            raise ValueError(f"negative bit count: {bit_count}")
        if bit_count > self.total_bits - self.bit_position:
            raise ValueError(
                "CRip008 payload ended while decoding: "
                f"need {bit_count} bits with "
                f"{self.total_bits - self.bit_position} remaining"
            )
        self.bit_position += bit_count
        self.bits = u32(self.bits << (bit_count & 0x1F))
        self.bits_left -= bit_count
        self._refill()

    def bit(self) -> int:
        value = 1 if self.bits & 0x80000000 else 0
        self.consume(1)
        return value

    def read_int(self) -> int:
        if not (self.bits & 0x80000000):
            self.consume(1)
            return 1
        index = (self.bits >> 19) & 0xFFF
        value = self.table[index * 2]
        bit_count = self.table[index * 2 + 1]
        if bit_count < 0x0E:
            self.consume(bit_count)
            return value

        self.consume(13)
        index = (self.bits >> 20) & 0xFFF
        low_value = self.table[index * 2]
        extra_bits = self.table[index * 2 + 1] - 1
        shift = extra_bits >> 1
        value = (value << shift) | (low_value - (1 << shift))
        self.consume(extra_bits)
        return value

    def read_signed_int(self) -> int:
        if not (self.bits & 0x80000000):
            self.consume(1)
            return 0
        sign = 1 if self.bits & 0x40000000 else 0
        self.consume(2)
        value = self.read_int()
        return -value if sign else value

    def validate_zero_padding(self) -> int:
        """Accept only the final zero bits required to reach a byte boundary."""

        remaining = self.total_bits - self.bit_position
        if remaining > 7:
            raise ValueError(f"excess CRip008 payload padding: {remaining} bits")
        for position in range(self.bit_position, self.total_bits):
            byte_index, bit_index = divmod(position, 8)
            if self.data[byte_index] & (1 << (7 - bit_index)):
                raise ValueError(
                    "CRip008 payload padding contains a set bit at "
                    f"payload bit {position}"
                )
        return remaining


def _clamp_relative(value: int, current: int, maximum: int) -> int:
    low = -current
    high = maximum - current
    if value < low:
        return low
    if value > high:
        return high
    return value


def _pixel_from_delta(delta: int, baseline: int, baseline_alpha: int) -> int:
    if i32(delta) == 0:
        return 0x80000000
    return 0x80000000 | (u32(baseline + i32(delta)) & 0x00FFFFFF)


def apply_crip008_rgb_delta(
    rgb: int,
    green_acc: int,
    raw_g: int,
    b_inc: int,
    r_inc: int,
    header: Crip008Header,
) -> tuple[int, int]:
    b_shift = 8 - header.b_bits
    g_shift = 16 - header.g_bits
    r_shift = 24 - header.r_bits
    max_b = 0xFF >> b_shift
    max_g = 0xFF >> (8 - header.g_bits)
    max_r = 0xFF >> (8 - header.r_bits)

    current_g = (u32(rgb) & 0x0000FF00) >> g_shift
    green_base = _clamp_relative(green_acc, current_g, max_g)
    green = raw_g + green_base

    current_b = (u32(rgb) & 0x000000FF) >> b_shift
    b_base = _clamp_relative(green, current_b, max_b)
    current_r = (u32(rgb) & 0x00FF0000) >> r_shift
    r_base = _clamp_relative(green, current_r, max_r)

    rgb = i32(
        rgb
        + ((b_base + b_inc) << b_shift)
        + (green << g_shift)
        + ((r_base + r_inc) << r_shift)
    )
    return rgb, green


def normalize_crip008_review_rgba(pixels: bytes | bytearray) -> bytearray:
    normalized = bytearray(pixels)
    for index in range(3, len(normalized), 4):
        alpha = normalized[index]
        if alpha:
            if alpha >= 0x80:
                normalized[index] = 0xFF
            else:
                normalized[index] = min(0xFF, round((alpha + 3) * 0xFF / 0x80))
    return normalized


def native_crip008_to_rgba(pixels: bytes | bytearray) -> bytearray:
    normalized = normalize_crip008_review_rgba(pixels)
    rgba = bytearray(len(normalized))
    for index in range(0, len(normalized), 4):
        c0, c1, c2, alpha = normalized[index : index + 4]
        rgba[index : index + 4] = bytes((c2, c0, c1, alpha))
    return rgba


def validate_crip008_decode_profile(header: Crip008Header) -> None:
    """Reject dimensions and header branches outside the proven decoder scope."""

    if header.kind not in (2, 3):
        raise ValueError(f"unsupported CRip008 kind: {header.kind}")
    if header.width <= 0 or header.height <= 0:
        raise ValueError(
            f"CRip008 canvas must be positive: {header.width}x{header.height}"
        )
    pixels = header.width * header.height
    if pixels > MAX_CRIP008_PIXELS:
        raise ValueError(
            "CRip008 canvas exceeds the review decoder safety limit: "
            f"{header.width}x{header.height} > {MAX_CRIP008_PIXELS} pixels"
        )
    if header.payload_length <= 0:
        raise ValueError("CRip008 payload length must be positive")
    if header.header_version not in SUPPORTED_CRIP008_HEADER_VERSIONS:
        raise ValueError(
            f"unsupported CRip008 header version: {header.header_version}"
        )
    unsupported_flags = header.compress_flags & ~SUPPORTED_CRIP008_FLAG_MASK
    if unsupported_flags:
        raise ValueError(
            "unsupported CRip008 compression flags: "
            f"0x{header.compress_flags:02X}"
        )
    if header.kind == 2:
        if header.depth not in (3, 6):
            raise ValueError(f"unsupported CRip008 kind=2 depth: {header.depth}")
        if (
            header.x_offset != 0
            or header.y_offset != 0
            or header.draw_width not in (0, header.width)
            or header.draw_height not in (0, header.height)
        ):
            raise ValueError(
                "CRip008 kind=2 requires a full-canvas draw rectangle"
            )
    elif header.depth != 3:
        raise ValueError(f"unsupported CRip008 kind=3 depth: {header.depth}")


def decode_crip008_kind2_native(
    payload: bytes,
    header: Crip008Header,
    *,
    code_table: bytes | None = None,
) -> bytearray:
    if header.kind != 2:
        raise ValueError(f"kind=2 decoder cannot decode kind={header.kind}")
    validate_crip008_decode_profile(header)
    if len(payload) != header.payload_length:
        raise ValueError(
            "CRip008 payload length mismatch: "
            f"{len(payload)} != {header.payload_length}"
        )
    for name, value in (("b_bits", header.b_bits), ("g_bits", header.g_bits), ("r_bits", header.r_bits)):
        if not 1 <= value <= 8:
            raise ValueError(f"unsupported {name}: {value}")

    bits = NativeMsbBitReader(payload, code_table or load_crip008_code_table())
    width = header.width
    height = header.height
    output = bytearray(width * height * 4)
    previous_row = [0] * width

    b_shift = 8 - header.b_bits
    g_shift = 16 - header.g_bits
    r_shift = 24 - header.r_bits
    max_b = 0xFF >> b_shift
    max_g = 0xFF >> (8 - header.g_bits)
    max_r = 0xFF >> (8 - header.r_bits)
    baseline = ((0xFF >> header.r_bits) << 16) | ((0xFF >> header.g_bits) << 8) | (
        0xFF >> header.b_bits
    )
    baseline_alpha = baseline | 0x80000000

    green_shift_mode = 0
    if header.b_bits == 6 and header.g_bits == 7 and header.r_bits == 6:
        green_shift_mode = 1
    elif header.b_bits == 6 and header.g_bits == 8 and header.r_bits == 6:
        green_shift_mode = 2

    for y in range(height):
        row_delta = 0
        x = 0
        while x < width:
            literal_count = bits.read_int()
            if literal_count < 0 or literal_count > width - x:
                raise ValueError(
                    f"literal run {literal_count} exceeds row remainder {width - x} "
                    f"at y={y} x={x}"
                )
            green_acc = 0
            for _ in range(literal_count):
                if bits.bit():
                    above = previous_row[x]
                    low = above & 0x00FFFFFF
                    green_acc = 0
                    row_delta = 0 if low == 0 else i32(low - baseline)
                else:
                    raw_g = bits.read_signed_int()
                    b_inc = bits.read_signed_int()
                    r_inc = bits.read_signed_int()

                    current_g = (u32(row_delta) & 0x0000FF00) >> g_shift
                    green_base = _clamp_relative(green_acc, current_g, max_g)
                    green = raw_g + green_base
                    green_acc = green
                    if green_shift_mode == 1:
                        green_pred = green >> 1
                    elif green_shift_mode == 2:
                        green_pred = green >> 2
                    else:
                        green_pred = green

                    if header.predict_red_blue:
                        current_b = (u32(row_delta) & 0x000000FF) >> b_shift
                        current_r = (u32(row_delta) & 0x00FF0000) >> r_shift
                        b_base = _clamp_relative(green_pred, current_b, max_b)
                        r_base = _clamp_relative(green_pred, current_r, max_r)
                    else:
                        b_base = green_pred
                        r_base = green_pred

                    b_value = b_base + b_inc
                    r_value = r_base + r_inc
                    row_delta = i32(
                        row_delta
                        + (b_value << b_shift)
                        + (green << g_shift)
                        + (r_value << r_shift)
                    )

                pixel = _pixel_from_delta(row_delta, baseline, baseline_alpha)
                out = (y * width + x) * 4
                output[out : out + 4] = pixel.to_bytes(4, "little")
                previous_row[x] = pixel
                x += 1

            if x >= width:
                break

            repeat_count = bits.read_int()
            if repeat_count < 0 or repeat_count > width - x:
                raise ValueError(
                    f"repeat run {repeat_count} exceeds row remainder {width - x} "
                    f"at y={y} x={x}"
                )
            pixel = _pixel_from_delta(row_delta, baseline, baseline_alpha)
            raw = pixel.to_bytes(4, "little")
            for _ in range(repeat_count):
                out = (y * width + x) * 4
                output[out : out + 4] = raw
                previous_row[x] = pixel
                x += 1

    bits.validate_zero_padding()
    return output


def decode_crip008_kind3_native(
    payload: bytes,
    header: Crip008Header,
    *,
    code_table: bytes | None = None,
) -> bytearray:
    if header.kind != 3:
        raise ValueError(f"kind=3 decoder cannot decode kind={header.kind}")
    validate_crip008_decode_profile(header)
    if len(payload) != header.payload_length:
        raise ValueError(
            "CRip008 payload length mismatch: "
            f"{len(payload)} != {header.payload_length}"
        )
    for name, value in (("b_bits", header.b_bits), ("g_bits", header.g_bits), ("r_bits", header.r_bits)):
        if not 1 <= value <= 8:
            raise ValueError(f"unsupported {name}: {value}")

    bits = NativeMsbBitReader(payload, code_table or load_crip008_code_table())
    width = header.width
    height = header.height
    decode_width = header.draw_width or header.width
    decode_height = header.draw_height or header.height
    if (
        decode_width <= 0
        or decode_height <= 0
        or header.x_offset < 0
        or header.y_offset < 0
        or header.x_offset + decode_width > width
        or header.y_offset + decode_height > height
    ):
        raise ValueError(
            "CRip008 kind=3 draw rect is outside canvas: "
            f"canvas={width}x{height} rect=({header.x_offset},{header.y_offset}) "
            f"{decode_width}x{decode_height}"
        )
    output = bytearray(width * height * 4)
    line_buf = [0] * decode_width

    b_shift = 8 - header.b_bits
    g_shift = 16 - header.g_bits
    r_shift = 24 - header.r_bits
    baseline = ((0xFF >> header.r_bits) << 16) | ((0xFF >> header.g_bits) << 8) | (
        0xFF >> header.b_bits
    )

    for y in range(decode_height):
        alpha = 0
        rgb = 0
        green_acc = 0
        repeat_count = 0
        repeat = True
        chunk_size = 0
        x = 0
        while x < decode_width:
            if chunk_size == 0:
                alpha += bits.read_signed_int()
                if alpha < 0 or alpha > 32:
                    raise ValueError(f"CRip008 kind=3 alpha out of range: {alpha} at y={y} x={x}")
                if alpha == 0 or alpha == 32:
                    chunk_size = bits.read_int()
                    if chunk_size < 0 or chunk_size > decode_width - x:
                        raise ValueError(
                            f"alpha chunk {chunk_size} exceeds row remainder {decode_width - x} "
                            f"at y={y} x={x}"
                        )

            if alpha != 0:
                if alpha == 32:
                    chunk_size -= 1
                if repeat_count == 0:
                    repeat_count = bits.read_int()
                    repeat = not repeat
                    green_acc = 0
                    if repeat_count < 0 or repeat_count > decode_width - x:
                        raise ValueError(
                            f"repeat segment {repeat_count} exceeds row remainder {decode_width - x} "
                            f"at y={y} x={x}"
                        )
                repeat_count -= 1

                if not repeat:
                    if bits.bit():
                        rgb = line_buf[x]
                        green_acc = 0
                    else:
                        raw_g = bits.read_signed_int()
                        b_inc = bits.read_signed_int()
                        r_inc = bits.read_signed_int()
                        rgb, green_acc = apply_crip008_rgb_delta(
                            rgb, green_acc, raw_g, b_inc, r_inc, header
                        )

                pixel = u32(baseline + i32(rgb)) & 0x00FFFFFF
                if alpha == 32:
                    pixel |= 0x80000000
                else:
                    pixel |= (alpha << 26) & 0xFF000000
                out = ((header.y_offset + y) * width + header.x_offset + x) * 4
                output[out : out + 4] = pixel.to_bytes(4, "little")
                line_buf[x] = rgb
                x += 1
            else:
                x += chunk_size
                chunk_size = 0

    bits.validate_zero_padding()
    return output
