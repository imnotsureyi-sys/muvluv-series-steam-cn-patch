from __future__ import annotations

import unittest

from tools.egpack.egpack_codec import (
    EgpackFormatError,
    classify_resource,
    extract_control_codes,
    is_control_only,
    parse_egpack_bytes,
)

from .fixtures import FIELD_ORDER, build_egpack, encode_field, finalize_egpack


class EgpackCodecTests(unittest.TestCase):
    def test_parse_keeps_jp_en_and_control_only_records_separate(self) -> None:
        data = build_egpack(
            [
                {"id": "game_t00000", "jp": "「日本語」\\p", "en": "English"},
                {"id": "game_t00001", "jp": "\\f", "en": "\\f"},
                {"id": "game_t00002", "jp": "次の日本語", "en": ""},
            ]
        )

        document = parse_egpack_bytes(data)

        self.assertEqual([record.text_id for record in document.records], [
            "game_t00000",
            "game_t00001",
            "game_t00002",
        ])
        self.assertEqual(document.records[0].slots["jp"].text, "「日本語」\\p")
        self.assertEqual(document.records[0].slots["en"].text, "English")
        self.assertEqual(document.records[1].slots["jp"].text, "\\f")
        self.assertEqual(document.records[1].slots["en"].text, "\\f")
        self.assertEqual(document.records[2].slots["jp"].text, "次の日本語")
        self.assertEqual(document.records[2].slots["en"].text, "")

    def test_parse_exposes_exact_value_offsets(self) -> None:
        data = build_egpack([{"id": "game_t00000", "jp": "日本語", "en": "English"}])

        document = parse_egpack_bytes(data, source="fixture.egpack")
        jp = document.records[0].slots["jp"]

        self.assertEqual(document.source, "fixture.egpack")
        self.assertEqual(document.declared_size, len(data))
        self.assertEqual(data[jp.value_offset : jp.value_offset + jp.value_length], "日本語".encode("utf-8"))
        self.assertEqual(data[jp.field_offset], 0x87)
        self.assertEqual(len(document.records[0].slots), 10)

    def test_classifies_all_known_resource_kinds(self) -> None:
        self.assertEqual(classify_resource("scene.egpack", "game_t00000"), "scene")
        self.assertEqual(classify_resource("scene.egpack", "game_t00000_ruby"), "ruby")
        self.assertEqual(classify_resource("__speakers__.egpack", "game_s00000"), "speaker")
        self.assertEqual(classify_resource("__staffroll__.egpack", "game_staff00000"), "staffroll")
        self.assertEqual(classify_resource("__staffroll__.egpack", "staff90000"), "staffroll")
        self.assertEqual(classify_resource("scene.egpack", "custom00000"), "unknown")

    def test_control_helpers_distinguish_empty_control_and_visible_text(self) -> None:
        self.assertEqual(extract_control_codes("\\f"), ("\\f",))
        self.assertEqual(extract_control_codes("「待て」\\w…\\p"), ("\\w", "\\p"))
        self.assertTrue(is_control_only("\\f"))
        self.assertTrue(is_control_only("\\w　\\p"))
        self.assertFalse(is_control_only(""))
        self.assertFalse(is_control_only("「待て」\\p"))

    def test_rejects_bad_magic(self) -> None:
        with self.assertRaisesRegex(EgpackFormatError, "magic"):
            parse_egpack_bytes(b"BAD!" + b"\0" * 20)

    def test_rejects_declared_size_mismatch(self) -> None:
        data = bytearray(build_egpack([{"id": "game_t00000", "jp": "日本語"}]))
        data[8:12] = (len(data) + 1).to_bytes(4, "little")

        with self.assertRaisesRegex(EgpackFormatError, "declared size"):
            parse_egpack_bytes(bytes(data), source="bad-size.egpack")

    def test_rejects_invalid_utf8_with_offset(self) -> None:
        data = build_egpack([{"id": "game_t00000", "jp": b"\xff"}])

        with self.assertRaisesRegex(EgpackFormatError, "UTF-8.*offset"):
            parse_egpack_bytes(data, source="bad-utf8.egpack")

    def test_rejects_missing_field(self) -> None:
        body = b"".join(
            encode_field(slot, "game_t00000" if slot == "id" else "")
            for slot in FIELD_ORDER
            if slot != "fr"
        )

        with self.assertRaisesRegex(EgpackFormatError, "field count|layout"):
            parse_egpack_bytes(finalize_egpack(body), source="missing-field.egpack")

    def test_rejects_duplicate_field(self) -> None:
        body = b"".join(
            encode_field(slot, "game_t00000" if slot == "id" else "")
            for slot in FIELD_ORDER
        ) + encode_field("en", "duplicate")

        with self.assertRaisesRegex(EgpackFormatError, "field count|layout"):
            parse_egpack_bytes(finalize_egpack(body), source="duplicate-field.egpack")


if __name__ == "__main__":
    unittest.main()
