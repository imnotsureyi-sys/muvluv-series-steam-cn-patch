from __future__ import annotations

import struct
import unittest

from rUGP.formats.rio.crsa import UNICODE_MARKER
from rUGP.formats.rio.crsa_text import (
    StructuralTextPair,
    derive_pool_base_from_source_offsets,
    expand_seeded_text_slots,
    extract_text_slots,
    find_owning_candidate,
    find_structural_source_pairs,
    parse_payload_spans,
    parse_text_slots,
    recover_seeded_source_strings,
    scan_inline_unicode_records,
    scan_utf16_strings,
)
from rUGP.formats.rio.crsa_vm_pool import (
    CVM_MSG3_DECLARATION,
    find_vm_message_commands,
)


def pair(source: str, translation: str) -> bytes:
    return (
        source.encode("utf-16le")
        + b"\x00\x00"
        + translation.encode("utf-16le")
        + b"\x00\x00"
    )


def vm_body(
    command: int,
    source: int,
    translation: int,
    *,
    flags: int = 0x60000001,
    string_index: int = 0,
) -> bytes:
    return (
        struct.pack("<IIHHBB", command, flags, 1, string_index, 2, 0)
        + struct.pack("<III", source, 0, 0)
        + struct.pack("<III", translation, 0, 0)
    )


class CrsaTextParserTests(unittest.TestCase):
    def test_unseeded_structural_pair_recovers_source_and_translation(self) -> None:
        source = "起立\x01"
        translation = "Stand up.\x01"
        payload = b"\xff\xff" + pair(source, translation) + b"\xaa"

        result = find_structural_source_pairs(payload, allow_empty_translation=True)

        self.assertEqual(
            result,
            [
                StructuralTextPair(
                    source_start=2,
                    source_end=2 + len(source.encode("utf-16le")),
                    translation_start=4 + len(source.encode("utf-16le")),
                    pair_end=6
                    + len(source.encode("utf-16le"))
                    + len(translation.encode("utf-16le")),
                    source_text=source,
                    translation_text=translation,
                    auxiliary_texts=(),
                    evidence="adjacent_source_translation",
                )
            ],
        )

    def test_structural_pair_allows_auxiliary_gloss_and_empty_translation(self) -> None:
        source = "ドーバー基地群。\x01"
        gloss = "基地群:コンプレックス"
        translation = "Dover Base Complex.\x01"
        payload = b"".join(
            text.encode("utf-16le") + b"\x00\x00"
            for text in (source, gloss, translation)
        )
        result = find_structural_source_pairs(payload)
        self.assertEqual(result[0].auxiliary_texts, (gloss,))

        empty = "ハッ！\x01".encode("utf-16le") + b"\x00\x00\x00\x00"
        result = find_structural_source_pairs(empty, allow_empty_translation=True)
        self.assertEqual(result[0].translation_text, "")
        self.assertEqual(result[0].evidence, "source_with_empty_translation")

    def test_structural_pair_rejects_bytecode_and_invalid_internal_terminator(self) -> None:
        false_candidate = "䈀む$\r\x01"
        payload = (
            b"\x02\x00\x00\x00\x02\x00\x00\x00"
            + false_candidate.encode("utf-16le")
            + b"\x00\x00\x00\x00"
        )
        self.assertEqual(
            find_structural_source_pairs(payload, allow_empty_translation=True),
            [],
        )
        bad = "ᄀ岀\x01䎀怀\x01"
        self.assertEqual(find_structural_source_pairs(pair(bad, "Metadata\x01")), [])

    def test_scanner_is_maximal_and_supports_odd_payload_parity(self) -> None:
        prefix = b"\xff\x00\x00"
        source = "【武】「前半\x03後半」\x01"
        payload = prefix + pair(source, "Odd\x01")
        candidates = scan_utf16_strings(payload)
        owner = find_owning_candidate(candidates, len(prefix) + 8, 4)
        self.assertEqual(owner.start, len(prefix))
        self.assertEqual(owner.text, source)
        slots = parse_text_slots(payload, known_text_offsets=(len(prefix) + 8,))
        self.assertEqual(slots[0].payload_offset, 3)
        self.assertEqual(slots[0].source_text, source)

    def test_seeded_expansion_and_auxiliary_recovery(self) -> None:
        prefix = b"\xaa\xbb\x00\x00"
        first = pair("起立\x01", "Stand\x01")
        second = pair("…\x01", "")
        third = pair("了解\x01", "Roger\x01")
        payload = prefix + first + second + third + b"\xff"
        second_offset = len(prefix) + len(first)
        slots = expand_seeded_text_slots(payload, (second_offset,))
        self.assertEqual(
            [slot.source_text for slot in slots],
            ["起立\x01", "…\x01", "了解\x01"],
        )

        chain = b"\x00\x00" + b"".join(
            value.encode("utf-16le") + b"\x00\x00"
            for value in ("基地群。\x01", "基地群:コンプレックス", "Base.\x01", "起立\x01", "Stand.\x01")
        )
        recovered = recover_seeded_source_strings(chain, (2,))
        self.assertEqual([item.text for item in recovered], ["基地群。\x01", "起立\x01"])

    def test_payload_spans_account_for_every_byte(self) -> None:
        prefix = b"\x10\x20\xff\xff\x00\x00"
        body = pair("起立\x01", "Stand\x01")
        suffix = b"\x7f\x00\xff"
        payload = prefix + body + suffix
        spans = parse_payload_spans(payload, known_text_offsets=(len(prefix),))
        self.assertEqual(b"".join(span.raw_bytes for span in spans), payload)
        self.assertEqual([span.kind for span in spans], ["binary", "text", "binary"])

    def test_counted_unicode_reader_splits_inline_translation(self) -> None:
        body = "選択肢\\|Choice"
        payload = (
            b"\x88\x99"
            + UNICODE_MARKER
            + bytes((len(body),))
            + body.encode("utf-16le")
            + b"\x02\x00\x00\x00"
        )
        records = scan_inline_unicode_records(payload)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_text, "選択肢")
        self.assertEqual(records[0].translation_text, "Choice")
        self.assertEqual(records[0].control_codes, (2,))
        self.assertTrue(records[0].has_translation_delimiter)

    def test_counted_unicode_reader_supports_extended_length_without_nul(self) -> None:
        text = "壁" * 257
        payload = (
            UNICODE_MARKER
            + b"\xff"
            + len(text).to_bytes(2, "little")
            + text.encode("utf-16le")
            + b"\x3c\xed"
        )
        records = scan_inline_unicode_records(payload)
        self.assertEqual(records[0].text_offset, 6)
        self.assertEqual(records[0].source_text, text)
        self.assertEqual(records[0].end_offset, 6 + len(text.encode("utf-16le")))

    def test_vm_pool_is_inferred_and_exact_reference_wins(self) -> None:
        source = "起立\x01\x00".encode("utf-16le")
        translation = "Stand\x01\x00".encode("utf-16le")
        pool = b"\x00\x00" + source + translation
        source_index = 1
        translation_index = source_index + len(source) // 2
        command = CVM_MSG3_DECLARATION + vm_body(4, source_index, translation_index)
        pool_base = 96
        payload = (
            command
            + b"\xa5" * (pool_base - 4 - len(command))
            + struct.pack("<I", len(pool) // 2)
            + pool
            + b"binary-suffix"
        )

        report = extract_text_slots(payload)

        self.assertEqual(report.vm_pool_base, pool_base)
        exact = [slot for slot in report.slots if slot.evidence == "cvmmsg3_exact_reference"]
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0].source_text, "起立\x01")
        self.assertEqual(exact[0].existing_translation_text, "Stand\x01")

    def test_vm_command_parser_keeps_cached_and_control_messages(self) -> None:
        payload = (
            CVM_MSG3_DECLARATION
            + vm_body(100, 0, 0, flags=5)
            + b"other-object"
            + struct.pack("<H", 0x802B)
            + vm_body(144, 1, 8, flags=0x22000010, string_index=2)
        )
        commands = find_vm_message_commands(payload)
        self.assertEqual([command.command_offset for command in commands], [100, 144])
        self.assertEqual(commands[0].source_index, 0)
        self.assertEqual(commands[1].class_reference, 0x802B)
        self.assertEqual(commands[1].flags, 0x22000010)
        self.assertEqual(commands[1].string_index, 2)

    def test_source_anchored_pool_base_fallback_uses_current_command_parser(self) -> None:
        payload = bytearray(CVM_MSG3_DECLARATION + vm_body(4, 1, 8))
        payload.extend(b"\x00" * (200 - len(payload)))
        base = 120
        pool = b"\x00\x00" + "起立\x01\x00".encode("utf-16le") + "Stand\x01\x00".encode("utf-16le")
        payload[base - 4 : base] = struct.pack("<I", len(pool) // 2)
        payload[base : base + len(pool)] = pool
        commands = find_vm_message_commands(bytes(payload))
        source_offset = base + 2
        self.assertEqual(
            derive_pool_base_from_source_offsets(bytes(payload), commands, (source_offset,)),
            base,
        )

    def test_source_anchored_pool_base_accepts_native_prefix_wrapper(self) -> None:
        source = b"\x10\x00" + "起立\x01\x00".encode("utf-16le")
        translation = "Stand\x01\x00".encode("utf-16le")
        pool = b"\x00\x00" + source + translation
        source_index = 1
        translation_index = source_index + len(source) // 2
        command = CVM_MSG3_DECLARATION + vm_body(4, source_index, translation_index)
        base = 120
        payload = (
            command
            + b"\xa5" * (base - 4 - len(command))
            + struct.pack("<I", len(pool) // 2)
            + pool
        )
        commands = find_vm_message_commands(payload)
        visible_source = base + source_index * 2 + 2
        self.assertEqual(
            derive_pool_base_from_source_offsets(payload, commands, (visible_source,)),
            base,
        )


if __name__ == "__main__":
    unittest.main()
