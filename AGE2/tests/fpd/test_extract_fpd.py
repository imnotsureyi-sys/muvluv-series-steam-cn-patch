from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from AGE2.tools.fpd.extract_fpd import plan_destinations, safe_path
from AGE2.tools.fpd.fpd_codec import FpdEntry


def entry(name: str) -> FpdEntry:
    return FpdEntry(name, 0, 1, 0)


class FpdExtractionPathTests(unittest.TestCase):
    def test_safe_path_accepts_only_canonical_relative_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(
                safe_path(root, "root/assets/file.webp"),
                root / "root" / "assets" / "file.webp",
            )
            for value in (
                "",
                "../escape",
                "root/../escape",
                "/absolute",
                r"Q:\outside\file",
                r"\\server\share\file",
                "root//file",
                "root/file/",
                "root/C:/file",
                "root/zero\x00file",
            ):
                with self.subTest(value=value):
                    with self.assertRaisesRegex(ValueError, "unsafe FPD member"):
                        safe_path(root, value)

    def test_plan_rejects_windows_case_and_file_directory_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "case-insensitive duplicate"):
                plan_destinations(
                    root,
                    [entry("root/UI/Button.webp"), entry("root/ui/button.WEBP")],
                )
            with self.assertRaisesRegex(ValueError, "file/directory"):
                plan_destinations(
                    root,
                    [entry("root/assets"), entry("root/assets/file.webp")],
                )

    def test_plan_is_complete_before_any_destination_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            planned = plan_destinations(
                root,
                [entry("root/a.bin"), entry("root/nested/b.bin")],
            )
            self.assertEqual(len(planned), 2)
            self.assertFalse(any(path.exists() for _row, path in planned))


if __name__ == "__main__":
    unittest.main()
