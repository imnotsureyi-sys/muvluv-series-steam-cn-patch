from __future__ import annotations

import struct
import unittest

from rUGP.formats.rio.crsa_vm_fields import inventory_vm_pool
from rUGP.formats.rio.crsa_vm_pool import CvmPoolError, VmMessageCommand


def fixture(annotation_index: int | None = None) -> tuple[bytes, tuple[VmMessageCommand, ...], int]:
    pool = "\0原文\0Example\0Example:注释\0Other:其他\0".encode("utf-16le")
    base = 128
    annotation_index = 12 if annotation_index is None else annotation_index
    command = VmMessageCommand(0, 2, 40, None, 4, 0, 1, 0, ((1, 0, 0), (4, annotation_index, 0)), ())
    data = b"\0"*(base-4) + struct.pack("<I", len(pool)//2) + pool
    return data, (command,), base


class NativeFieldInventoryTests(unittest.TestCase):
    def test_stale_index_keeps_native_and_physical_locations_separate(self) -> None:
        data, commands, base = fixture(99999)
        result = inventory_vm_pool(data, commands, base)
        annotation = result.annotations[0]
        self.assertEqual("adjacent_to_owned_message_stale_index", annotation.binding)
        self.assertEqual(99999, annotation.native_index)
        self.assertEqual(base+12*2, annotation.cell.offset)
        self.assertEqual((True,), annotation.keys_in_message)
        self.assertIn("outside_declared_pool", " ".join(result.issues))
        self.assertEqual(data, fixture(99999)[0])

    def test_conflicting_valid_annotation_does_not_silently_rebind(self) -> None:
        data, commands, base = fixture(23)
        result = inventory_vm_pool(data, commands, base)
        self.assertEqual("exact_native_reference", result.annotations[0].binding)
        self.assertEqual("Other:其他", result.annotations[0].cell.text)
        self.assertIn("native_reference_conflicts", " ".join(result.issues))
        self.assertIn("Example:注释", [c.text for c in result.unclaimed_cells])

    def test_zero_primary_index_never_borrows_the_next_cell(self) -> None:
        data, _, base = fixture(0)
        command = VmMessageCommand(0, 2, 40, None, 4, 0, 1, 0, ((0, 0, 0), (4, 0, 0)), ())
        result = inventory_vm_pool(data, (command,), base)
        self.assertEqual("", result.references[0].text)
        self.assertEqual(base, result.references[0].offset)
        self.assertIn("原文", [c.text for c in result.unclaimed_cells])

    def test_bad_utf16_or_missing_terminator_is_not_reported_complete(self) -> None:
        for raw in (b"\x00\xd8\0\0", b"A\0"):
            data = struct.pack("<I", len(raw)//2)+raw
            with self.subTest(raw=raw), self.assertRaises(CvmPoolError):
                inventory_vm_pool(data, (), 4)


if __name__ == "__main__":
    unittest.main()
