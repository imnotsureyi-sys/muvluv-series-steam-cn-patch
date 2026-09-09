from __future__ import annotations

import unittest

from rUGP.formats.images.crmti_decode import (
    CRMT_CHILD_WRAPPER,
    CrmtiBitReader,
    decode_crmt,
    parse_crmt,
)
from rUGP.formats.images.crmti_encode import (
    CrmtiBitWriter,
    encode_crmt,
)
from rUGP.formats.images.crmti_capacity import capacity_for_ranges


def template(width: int, height: int, meta: int, trailer: bytes = b"PARENT") -> bytes:
    parent = bytearray(0x41)
    parent[:4] = bytes.fromhex("80 04 02 05")
    parent[4:8] = b"KEEP"
    parent[0x40] = 1
    header = bytearray(18)
    header[0:2] = width.to_bytes(2, "little")
    header[2:4] = height.to_bytes(2, "little")
    header[4:8] = meta.to_bytes(4, "little")
    header[8:12] = (2).to_bytes(4, "little")
    header[12:16] = (width * height * 4).to_bytes(4, "little")
    header[16:18] = (0).to_bytes(2, "little")
    return bytes(parent) + CRMT_CHILD_WRAPPER + bytes(header) + b"\0\0" + trailer


def patterned_rgba(width: int, height: int) -> bytes:
    output = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * 4
            if y == 1 or x in (0, width - 1):
                value = (0, 0, 0, 0)
            elif x in (3, 4, 5):
                value = (235, 91, 17, 255)
            else:
                value = (
                    (x * 31 + y * 17) & 0xFF,
                    (x * 13 + y * 41) & 0xFF,
                    (x * 47 + y * 7) & 0xFF,
                    53 + x * 17 if x == 2 else 255,
                )
            output[offset : offset + 4] = bytes(value)
    return bytes(output)


def check_profile_roundtrip(meta: int) -> None:
    source = template(11, 5, meta)
    rgba = patterned_rgba(11, 5)
    first, expected, first_stats = encode_crmt(source, [rgba])
    second, expected_again, second_stats = encode_crmt(source, [rgba])
    assert first == second
    assert expected == expected_again
    assert first_stats == second_stats
    decoded, trailer = decode_crmt(first)
    assert decoded[0].rgba == expected[0]
    assert trailer == b"PARENT"
    assert first[:0x41] == source[:0x41]
    assert decoded[0].stats.zero_padding_bits >= 0


def check_empty_active_row_reset() -> None:
    width, height = 12, 3
    rgba = bytearray(width * height * 4)
    for x in (7, 8):
        at = x * 4
        rgba[at : at + 4] = bytes((200, 20, 80, 255))
    for x in (1, 2, 3):
        at = (2 * width + x) * 4
        rgba[at : at + 4] = bytes((20, 180, 90, 255))
    record, expected, _ = encode_crmt(
        template(width, height, 0x0707070F), [bytes(rgba)]
    )
    decoded, _ = decode_crmt(record)
    assert decoded[0].rgba == expected[0]
    assert decoded[0].active_ranges == ((7, 9), (0, 0), (1, 4))


def check_short_signed_127(lsb_first: bool) -> None:
    writer = CrmtiBitWriter(lsb_first=lsb_first)
    writer.signed(127)
    payload = writer.finish()
    reader = CrmtiBitReader(payload, lsb_first=lsb_first)
    assert reader.signed() == 127


def check_parent_and_child_immutable_fields() -> None:
    source = template(4, 3, 0x0606060F, trailer=b"\x91\x82TRAILER")
    rgba = bytes((100, 150, 200, 255)) * 12
    replacement, expected, _ = encode_crmt(source, [rgba])
    source_levels, source_trailer = parse_crmt(source)
    replacement_levels, replacement_trailer = parse_crmt(replacement)
    assert replacement[:0x41] == source[:0x41]
    assert replacement_trailer == source_trailer == b"\x91\x82TRAILER"
    before, after = source_levels[0], replacement_levels[0]
    assert (after.width, after.height, after.meta) == (
        before.width,
        before.height,
        before.meta,
    )
    decoded, _ = decode_crmt(replacement)
    assert decoded[0].rgba == expected[0]
    capacity = capacity_for_ranges(after.width, after.height, after.active_row_count, decoded[0].active_ranges)
    assert after.decoded_size_hint == capacity.replacement_hint(before.decoded_size_hint)
    assert after.decoded_size_hint > before.decoded_size_hint


def check_nonzero_tail_and_malformed_profiles() -> None:
    record, _, _ = encode_crmt(
        template(5, 2, 0x0707070F),
        [bytes((80, 120, 200, 255)) * 10],
    )
    decoded_before, _ = decode_crmt(record)
    levels, _ = parse_crmt(record)
    level = levels[0]
    tail_position = decoded_before[0].stats.consumed_bits
    assert tail_position < decoded_before[0].stats.payload_bits
    damaged = bytearray(record)
    damaged[level.blob_offset + tail_position // 8] |= 1 << (tail_position & 7)
    with unittest.TestCase().assertRaisesRegex(ValueError, "non-zero padding"):
        decode_crmt(bytes(damaged))

    bad_profile = bytearray(template(2, 2, 0x0404040F))
    with unittest.TestCase().assertRaisesRegex(ValueError, "unsupported CRmti RGB"):
        parse_crmt(bytes(bad_profile))


def check_truncated_child() -> None:
    source = template(2, 2, 0x0707070F)
    with unittest.TestCase().assertRaisesRegex(ValueError, "truncated"):
        parse_crmt(source[:-8])


class CrmtiCodecTests(unittest.TestCase):
    def test_all_observed_profiles_roundtrip(self) -> None:
        for meta in (0x0505050F, 0x0606060F, 0x0707070F, 0x07070707):
            with self.subTest(meta=f"0x{meta:08X}"):
                check_profile_roundtrip(meta)

    def test_empty_active_row_reset(self) -> None:
        check_empty_active_row_reset()

    def test_short_signed_127(self) -> None:
        for lsb_first in (False, True):
            with self.subTest(lsb_first=lsb_first):
                check_short_signed_127(lsb_first)

    def test_parent_and_child_immutable_fields(self) -> None:
        check_parent_and_child_immutable_fields()

    def test_fail_closed(self) -> None:
        check_nonzero_tail_and_malformed_profiles()

    def test_truncated_child(self) -> None:
        check_truncated_child()


if __name__ == "__main__":
    unittest.main()
