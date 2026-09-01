from __future__ import annotations

import random
import mmap
import tempfile
import unittest
from pathlib import Path

from rUGP.formats.rio.crypto import (
    ICI_KEY,
    RIO_KEY,
    decode_encrypted_block,
    decode_extent_offset,
    decode_extent_size,
    decrypt_ici_payload,
    encode_encrypted_block,
    encode_extent_offset,
    encode_extent_size,
    encrypt_ici_payload,
)
from rUGP.formats.rio.references import iter_encrypted_header_candidates
from rUGP.formats.rio.ruo import build_ruo, read_footer


class RioRebuildCoreTests(unittest.TestCase):
    def test_extent_offset_roundtrip(self) -> None:
        for unit_size in (1, 2, 4, 8):
            for offset in (0, unit_size, 0x1CA70FB8 // unit_size * unit_size, 0xE31D9AAC):
                offset -= offset % unit_size
                encoded = encode_extent_offset(offset, unit_size)
                self.assertEqual(decode_extent_offset(encoded, unit_size), offset)

    def test_extent_size_roundtrip(self) -> None:
        values = [0, 1, 2, 31, 32, 33, 13492, 26868, 0x7FFFF, 0x80000, 0xFFFFFFFF]
        for value in values:
            encoded = encode_extent_size(value)
            self.assertEqual(decode_extent_size(encoded), value)

    def test_encrypted_block_roundtrip_and_header_preservation(self) -> None:
        rng = random.Random(20260810)
        for key in (RIO_KEY, ICI_KEY):
            for size in (0, 1, 31, 32, 33, 1024, 52149):
                plain = bytes(rng.randrange(256) for _ in range(size))
                encoded = encode_encrypted_block(plain, key)
                decoded = decode_encrypted_block(encoded, key)
                self.assertEqual(decoded.plaintext, plain)
                self.assertEqual(decoded.consumed, len(encoded))
                rebuilt = encode_encrypted_block(decoded.plaintext, key, decoded.header)
                self.assertEqual(rebuilt, encoded)

    def test_ici_transform_roundtrip(self) -> None:
        rng = random.Random(0x673CE92A)
        for size in (0, 1, 2, 3, 5, 6, 31, 32, 8192, 10240):
            source = bytes(rng.randrange(256) for _ in range(size))
            decoded = decrypt_ici_payload(source)
            self.assertEqual(encrypt_ici_payload(decoded), source)

            plain = bytes(rng.randrange(256) for _ in range(size))
            encrypted = encrypt_ici_payload(plain)
            self.assertEqual(decrypt_ici_payload(encrypted), plain)

    def test_encrypted_header_scan_covers_unaligned_offsets_and_chunks(self) -> None:
        first_plain = bytes(range(80))
        second_plain = bytes(reversed(range(97)))
        first = encode_encrypted_block(first_plain, RIO_KEY)
        second = encode_encrypted_block(second_plain, RIO_KEY)
        source = b"abc" + first + b"12345" + second + b"tail"
        expected = [(3, len(first_plain)), (3 + len(first) + 5, len(second_plain))]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "scan.bin"
            path.write_bytes(source)
            with path.open("rb") as handle, mmap.mmap(
                handle.fileno(), 0, access=mmap.ACCESS_READ
            ) as data:
                found = [
                    (item.offset, item.plain_size)
                    for item in iter_encrypted_header_candidates(data, chunk_size=32)
                    if (item.offset, item.plain_size) in expected
                ]
        self.assertEqual(found, expected)

    def test_minimal_ruo_roundtrip_and_cumulative_override(self) -> None:
        unit_size = 4
        source_a = encode_extent_offset(0x100, unit_size)
        source_b = encode_extent_offset(0x200, unit_size)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base = root / "base.ruo1"
            merged = root / "merged.ruo1"
            base_report = build_ruo(base, unit_size, [(source_a, b"old")])
            base_data_end, base_redirects = read_footer(base, unit_size)
            base_data = base.read_bytes()[:base_data_end]

            merged_report = build_ruo(
                merged,
                unit_size,
                [(source_a, b"new-a"), (source_b, b"new-b")],
                base_ruo=base,
            )
            merged_data_end, merged_redirects = read_footer(merged, unit_size)

            self.assertEqual(base_report["redirect_count"], 1)
            self.assertEqual(merged_report["inherited_redirect_count"], 1)
            self.assertEqual(merged_report["redirect_count"], 2)
            self.assertTrue(merged.read_bytes()[:base_data_end] == base_data)
            self.assertGreater(merged_data_end, base_data_end)
            by_source = {item.source_raw_offset: item for item in merged_redirects}
            self.assertEqual(set(by_source), {source_a, source_b})
            self.assertNotEqual(
                by_source[source_a].ruo_raw_offset,
                base_redirects[0].ruo_raw_offset,
            )


if __name__ == "__main__":
    unittest.main()
