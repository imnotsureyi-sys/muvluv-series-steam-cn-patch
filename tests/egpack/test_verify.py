from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from tools.egpack.egpack_codec import EgpackChange, apply_changes
from tools.egpack.repack_egpack import CHANGE_COLUMNS
from tools.egpack.verify_egpack import EgpackVerificationError, main, verify_patched_bytes

from .fixtures import build_egpack


class EgpackVerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = build_egpack(
            [{"id": "game_t00000", "jp": "日本語", "en": "English"}]
        )
        self.change = EgpackChange(
            "scene.egpack",
            "game_t00000",
            "jp",
            "日本語",
            "中文",
        )

    def test_accepts_exact_authorized_output(self) -> None:
        patched = apply_changes(self.original, [self.change], source="scene.egpack")

        verify_patched_bytes(self.original, patched, [self.change], source="scene.egpack")

    def test_rejects_unauthorized_en_change(self) -> None:
        patched = apply_changes(self.original, [self.change], source="scene.egpack")
        patched = apply_changes(
            patched,
            [EgpackChange("scene.egpack", "game_t00000", "en", "English", "未经授权")],
            source="scene.egpack",
        )

        with self.assertRaisesRegex(EgpackVerificationError, "unauthorized|differs"):
            verify_patched_bytes(self.original, patched, [self.change], source="scene.egpack")

    def test_rejects_changed_id_order_or_value(self) -> None:
        patched = apply_changes(self.original, [self.change], source="scene.egpack")
        corrupted = patched.replace(b"game_t00000", b"game_t99999", 1)

        with self.assertRaisesRegex(EgpackVerificationError, "unauthorized|differs"):
            verify_patched_bytes(self.original, corrupted, [self.change], source="scene.egpack")

    def test_rejects_bad_declared_length(self) -> None:
        patched = bytearray(apply_changes(self.original, [self.change], source="scene.egpack"))
        patched[8:12] = (len(patched) + 1).to_bytes(4, "little")

        with self.assertRaisesRegex(EgpackVerificationError, "declared size"):
            verify_patched_bytes(self.original, bytes(patched), [self.change], source="scene.egpack")

    def test_rejects_byte_change_outside_target(self) -> None:
        patched = bytearray(apply_changes(self.original, [self.change], source="scene.egpack"))
        patched[4] ^= 0x01

        with self.assertRaisesRegex(EgpackVerificationError, "unauthorized|differs"):
            verify_patched_bytes(self.original, bytes(patched), [self.change], source="scene.egpack")

    def test_cli_verifies_files_and_rejects_missing_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original_root = root / "original"
            patched_root = root / "patched"
            changes_path = root / "changes.csv"
            original_path = original_root / "scene.egpack"
            patched_path = patched_root / "scene.egpack"
            original_root.mkdir()
            patched_root.mkdir()
            original_path.write_bytes(self.original)
            self._write_changes(changes_path)

            with self.assertRaisesRegex(EgpackVerificationError, "missing patched"):
                main([
                    str(original_root),
                    str(patched_root),
                    "--changes",
                    str(changes_path),
                ])

            patched_path.write_bytes(apply_changes(self.original, [self.change], source="scene.egpack"))
            result = main([
                str(original_root),
                str(patched_root),
                "--changes",
                str(changes_path),
            ])

        self.assertEqual(result, 0)

    def _write_changes(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CHANGE_COLUMNS)
            writer.writeheader()
            writer.writerow({
                "relative_path": "scene.egpack",
                "id": "game_t00000",
                "slot": "jp",
                "expected_text": "日本語",
                "replacement_text": "中文",
            })


if __name__ == "__main__":
    unittest.main()
