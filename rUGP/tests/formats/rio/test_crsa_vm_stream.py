from __future__ import annotations

import struct
import unittest

from rUGP.formats.rio.crsa_vm_fields import inventory_vm_pool
from rUGP.formats.rio.crsa_vm_stream import (
    CrsaVmStream, NativeVmSchema, VmStreamError, native_message_commands,
)
from rUGP.tests.catalog.test_rio_inventory import class_ref


def archive(commands: bytes, count: int, pool: bytes = b"\0\0", suffix: bytes = b"\0\0") -> bytes:
    return struct.pack("<HH5I", 48, 1, 0xFFFF0000, 18, 4096, count, 0) + commands + struct.pack("<I", len(pool)//2) + pool + suffix


def common() -> bytes:
    return struct.pack("<II", 4, 0)


def call_with_inline(name: str, schema: int, value: bytes) -> bytes:
    # First ObjRef has a zero-length ancestor preload followed by null.
    body = common() + b"\0\0\0" + struct.pack("<H", 1)
    body += struct.pack("<I", 0) + class_ref(name, schema) + struct.pack("<H", 0x40) + value
    return class_ref("CVmCall", 21) + body + b"\0"


class NativeStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = NativeVmSchema("pf")

    def parse(self, data: bytes) -> dict:
        return CrsaVmStream(data, self.schema).parse()

    def test_reads_all_language_columns_and_auxiliary_fields(self) -> None:
        pool = bytearray(b"\0\0")

        def cell(text: str) -> int:
            index = len(pool)//2
            pool.extend((text+"\0").encode("utf-16le"))
            return index

        source, display = cell("\x05"), cell("Example note")
        annotation, directive, third = cell("note:translation"), cell("name:value"), cell("其他语言")
        body = common() + struct.pack("<HHBB", 7, 2, 3, 0)
        body += struct.pack("<9I", source, 0, 0, display, annotation, directive, third, 0, 0)
        data = archive(class_ref("CVmMsg3", 21)+body, 1, bytes(pool))
        result = self.parse(data)
        messages = native_message_commands(result)
        self.assertEqual(7, messages[0].string_group)
        inventory = inventory_vm_pool(data, messages, result["pool_base"])
        self.assertEqual({0, 1, 2}, {r.language for r in inventory.references})
        self.assertEqual({"message", "annotation", "directive"}, {r.role for r in inventory.references})
        self.assertEqual((), inventory.unclaimed_cells)
        self.assertEqual("note:translation", inventory.annotations[0].cell.text)

    def test_cstrings_need_no_unicode_marker_and_share_object_cache(self) -> None:
        resource = class_ref("CRsa", 5) + struct.pack("<HIIHB", 0xC108, 0x12345678, 0, 0, 0)
        # command class=2, resource class=3, resource object=4.
        body = common() + b"\0" + resource + struct.pack("<H", 2)
        body += struct.pack("<I", 1) + bytes((11,)) + b"Hidden note"
        body += struct.pack("<I", 1) + b"\xff\xfe\xff\x02" + "中文".encode("utf-16le")
        command = class_ref("CVmCall", 21) + body + b"\0"
        result = self.parse(archive(command, 1, suffix=struct.pack("<HH", 1, 4)))
        self.assertEqual([(1, "Hidden note"), (2, "中文")], [(s["width"], s["text"]) for s in result["strings"]])
        self.assertEqual(["call.argument.0", "call.argument.1"], [s["role"] for s in result["strings"]])
        self.assertEqual(0x12345678, result["resource_references"][0]["key"])
        self.assertEqual(1, result["suffix_refs"])

    def test_unknown_command_does_not_resynchronize_at_later_text(self) -> None:
        command = class_ref("CVmUnimplemented", 21) + common()
        parser = CrsaVmStream(archive(command+b"hidden"+class_ref("CVmMsg3", 21), 2), self.schema)
        with self.assertRaisesRegex(VmStreamError, "unimplemented command"):
            parser.parse()
        self.assertEqual([], parser.commands)

    def test_nonzero_trailing_bytes_are_not_silently_ignored(self) -> None:
        data = archive(class_ref("CVmRet", 21)+common(), 1)
        self.assertEqual(12, self.parse(data+b"\0"*12)["zero_padding"])
        with self.assertRaisesRegex(VmStreamError, "nonzero trailing"):
            self.parse(data+b"orphaned text")
        with self.assertRaisesRegex(VmStreamError, "archive preamble"):
            self.parse(b"\x31\0"+data[2:])

    def test_geometry_buffers_do_not_become_false_cstrings(self) -> None:
        fake_string = b"\xff\xfe\xff\x05" + "Ghost".encode("utf-16le")
        geometry = b"\x01" + struct.pack("<I", 4) + b"\0"*12
        geometry += struct.pack("<I", len(fake_string)) + fake_string
        geometry += struct.pack("<IHH", 0, 0, 0) + b"\0"*8
        result = self.parse(archive(call_with_inline("CDcAgesModelQsT", 2, geometry), 1))
        self.assertEqual([], result["strings"])
        self.assertEqual(1, result["command_count"])

    def test_mfc_easing_classes_use_the_same_cache(self) -> None:
        # Call class=2, curve class=3, curve object=4, MFC class=5, object=6.
        point = b"\x03\x02" + b"\0"*12 + b"\0\0"
        declaration = struct.pack("<HHH", 0xFFFF, 0, 11) + b"CMN_Time_2G" + struct.pack("<I", 1)
        curve = b"\0"*12 + point + declaration
        curve += point + struct.pack("<HI", 0x8005, 2)  # New object of the cached MFC class.
        curve += point + struct.pack("<H", 6)          # Reference to the first object.
        curve += b"\x70" + b"\0"*15
        parser = CrsaVmStream(archive(call_with_inline("CMoveAcsOngen", 3, curve), 1), self.schema)
        result = parser.parse()
        self.assertEqual(1, parser.cache[6]["value"])
        self.assertEqual(2, parser.cache[7]["value"])
        self.assertEqual(1, result["command_count"])


if __name__ == "__main__":
    unittest.main()
