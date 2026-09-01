from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from localization.tools.safe_output import OutputSafetyError, write_new_files


class SafeOutputTests(unittest.TestCase):
    def test_rejects_aliases_existing_files_and_duplicate_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            source.write_bytes(b"source")
            with self.assertRaisesRegex(OutputSafetyError, "aliases an input"):
                write_new_files({source: b"replacement"}, inputs=(source,))
            occupied = root / "reviewed.bin"
            occupied.write_bytes(b"reviewed")
            with self.assertRaisesRegex(OutputSafetyError, "already exists"):
                write_new_files({occupied: b"replacement"})
            self.assertEqual(source.read_bytes(), b"source")
            self.assertEqual(occupied.read_bytes(), b"reviewed")

    def test_exclusively_creates_multiple_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "nested" / "a.bin"
            second = root / "nested" / "b.bin"
            write_new_files({first: b"a", second: b"b"})
            self.assertEqual(first.read_bytes(), b"a")
            self.assertEqual(second.read_bytes(), b"b")

    def test_publishes_only_complete_bytes_and_removes_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "artifact.bin"
            payload = b"complete-artifact"
            real_link = os.link

            def inspect_then_link(source: object, target: object) -> None:
                self.assertFalse(Path(target).exists())
                self.assertEqual(Path(source).read_bytes(), payload)
                real_link(source, target)

            with patch(
                "localization.tools.safe_output.os.link",
                side_effect=inspect_then_link,
            ):
                write_new_files({output: payload})

            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual([], list(root.glob(f".{output.name}.*.tmp")))


if __name__ == "__main__":
    unittest.main()
