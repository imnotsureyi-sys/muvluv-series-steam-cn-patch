from __future__ import annotations

import unittest

from rUGP.formats.rio.crsa import (
    UNICODE_MARKER,
    crsa_encrypted_storage_size,
    decode_crsa_encrypted,
    encode_crsa_encrypted,
    find_unicode_string,
    rebuild_unicode_string,
    utf16_code_units,
)


class CrsaVariableStringTests(unittest.TestCase):
    def test_every_chunk_including_partial_has_checksum(self) -> None:
        for size in (1, 5, 31, 32, 33, 63, 64, 65, 3557, 3605):
            plain = bytes((index * 29 + 7) & 0xFF for index in range(size))
            encoded = encode_crsa_encrypted(plain)
            decoded, consumed, checksums = decode_crsa_encrypted(encoded)
            self.assertEqual(plain, decoded)
            self.assertEqual(len(encoded), consumed)
            self.assertEqual(crsa_encrypted_storage_size(size), len(encoded))
            self.assertEqual((size + 31) // 32, len(checksums))

    def test_template_header_low_bits_are_preserved(self) -> None:
        plain = b"template-header-test"
        default = encode_crsa_encrypted(plain)
        template = default[:4] + ((int.from_bytes(default[4:8], "little") & ~7) | 3).to_bytes(4, "little")
        encoded = encode_crsa_encrypted(plain, template_header=template)
        self.assertEqual(3, int.from_bytes(encoded[4:8], "little") & 7)
        decoded, _, _ = decode_crsa_encrypted(encoded)
        self.assertEqual(plain, decoded)

    def test_rebuild_grows_unicode_string_and_shifts_suffix(self) -> None:
        source = "タイトルメニューへ戻る"
        replacement = "返回标题菜单（这是一个明显超出原槽位并跨越分块边界的验证）"
        prefix = b"prefix-object-data"
        suffix = b"suffix-object-data"
        payload = prefix + UNICODE_MARKER + bytes((utf16_code_units(source),)) + source.encode("utf-16le") + suffix
        rebuilt, old, new = rebuild_unicode_string(payload, source, replacement)
        self.assertGreater(new.code_units, old.code_units)
        self.assertEqual(prefix, rebuilt[: old.marker_offset])
        self.assertEqual(suffix, rebuilt[new.end_offset :])
        self.assertEqual(replacement, find_unicode_string(rebuilt, replacement).text)


if __name__ == "__main__":
    unittest.main()
