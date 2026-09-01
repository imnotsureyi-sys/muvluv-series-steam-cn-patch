from __future__ import annotations

import struct
import unittest

from rugp.formats.rio.crsa_vm_pool import (
    CVM_MSG3_DECLARATION,
    find_vm_message_commands,
    infer_pool_base,
    parse_pool,
    rebuild_pool_translation,
)


class CvmMsg3VariablePoolTests(unittest.TestCase):
    def test_whole_pool_rebuild_updates_indices_length_and_suffix(self) -> None:
        source = "JP\x01\x00".encode("utf-16le")
        translation = "EN\x01\x00".encode("utf-16le")
        pool = b"\x00\x00" + source + translation
        source_index = 1
        translation_index = source_index + len(source) // 2
        body = struct.pack("<IIHHBB", 4, 1, 1, 0, 2, 0)
        body += struct.pack("<III", source_index, 0, 0)
        body += struct.pack("<III", translation_index, 0, 0)
        command_stream = CVM_MSG3_DECLARATION + body
        pool_base = 64
        before_length = command_stream + b"\xA5" * (pool_base - 4 - len(command_stream))
        suffix = b"binary-object-suffix"
        payload = before_length + struct.pack("<I", len(pool) // 2) + pool + suffix

        commands = find_vm_message_commands(payload)
        self.assertEqual(1, len(commands))
        self.assertEqual(pool_base, infer_pool_base(payload, commands))
        layout = parse_pool(payload, commands, pool_base)
        rebuilt, rebuilt_layout = rebuild_pool_translation(
            payload,
            commands,
            layout,
            target_order=1,
            replacement_text="这是一条明显更长的中文翻译",
        )
        self.assertGreater(rebuilt_layout.declared_units, layout.declared_units)
        self.assertEqual(source, rebuilt_layout.pairs[0].source_raw)
        self.assertEqual(
            "这是一条明显更长的中文翻译\x01",
            rebuilt_layout.pairs[0].translation_text,
        )
        self.assertEqual(suffix, rebuilt[rebuilt_layout.end :])
        self.assertEqual(
            rebuilt_layout.declared_units,
            struct.unpack_from("<I", rebuilt, pool_base - 4)[0],
        )


if __name__ == "__main__":
    unittest.main()
