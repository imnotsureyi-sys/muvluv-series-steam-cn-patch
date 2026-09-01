from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rugp.formats.rio.crsa import CRSA_PREFIX, UNICODE_MARKER, encode_crsa_encrypted
from rugp.tools.text.extract_crsa_text import (
    CrsaTextExtractError,
    main,
    run,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root: Path, *, ambiguous_ascii: bool = False) -> tuple[Path, Path, int]:
    inline = "選択肢\\|Choice"
    payload = (
        b"serialized-prefix"
        + UNICODE_MARKER
        + bytes((len(inline),))
        + inline.encode("utf-16le")
        + b"\x02\x00\x00\x00"
        + b"serialized-suffix"
    )
    if ambiguous_ascii:
        payload += b"\xff\xff" + (
            "First\x02" + chr(0) + "Second\x02" + chr(0)
        ).encode("utf-16le")
    record = CRSA_PREFIX + bytes(5) + encode_crsa_encrypted(payload)
    offset = 0x40
    volume = root / "fixture.rio"
    volume.write_bytes(bytes(offset) + record + b"untouched-tail")
    inventory = {
        "schema": "muvluv-rugp-rio-inventory/v1",
        "mode": "read_only",
        "source": {"ici_name": "fixture.rio.ici", "main_rio_name": "fixture.rio"},
        "nodes": [
            {
                "logical_path": "script/menu",
                "class": "CRsa",
                "kind": "script",
                "volume": "fixture.rio",
                "volume_offset": offset,
                "global_offset": offset,
                "extent": len(record),
            }
        ],
    }
    inventory_path = root / "inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False),
        encoding="utf-8",
    )
    return inventory_path, volume, offset


class ExtractCrsaTextCliTests(unittest.TestCase):
    def test_read_only_run_writes_local_audit_and_hash_only_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory, volume, offset = fixture(root)
            before = sha256(volume)
            local = root / "out" / "local.csv"
            template = root / "out" / "template.csv"

            report = run(
                inventory_path=inventory,
                volume_arguments=(f"fixture.rio={volume}",),
                game_id="synthetic",
                local_output=local,
                template_output=template,
            )

            self.assertEqual(report["mode"], "read_only_inputs")
            self.assertEqual(report["records"], 1)
            self.assertEqual(report["slots"], 1)
            self.assertEqual(before, sha256(volume))
            with local.open("r", encoding="utf-8-sig", newline="") as stream:
                local_rows = list(csv.DictReader(stream))
            with template.open("r", encoding="utf-8", newline="") as stream:
                template_rows = list(csv.DictReader(stream))
            self.assertEqual(local_rows[0]["source_text"], "選択肢")
            self.assertEqual(local_rows[0]["existing_translation_text"], "Choice")
            self.assertEqual(
                local_rows[0]["stable_id"],
                f"synthetic:static:fixture.rio:{offset:010d}:00000021",
            )
            self.assertNotIn("source_text", template_rows[0])
            self.assertEqual(template_rows[0]["target_text"], "")
            self.assertEqual(template_rows[0]["review_status"], "untranslated")
            self.assertNotIn(str(root), local.read_text(encoding="utf-8-sig"))
            self.assertNotIn("選択肢", template.read_text(encoding="utf-8"))

    def test_main_reports_only_portable_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory, volume, _offset = fixture(root)
            template = root / "template.csv"
            stdout = io.StringIO()
            result = main(
                [
                    "--inventory",
                    str(inventory),
                    "--volume",
                    f"fixture.rio={volume}",
                    "--game-id",
                    "synthetic",
                    "--template-output",
                    str(template),
                ],
                stdout=stdout,
            )
            self.assertEqual(result, 0)
            output = stdout.getvalue()
            self.assertIn('"template_output": "template.csv"', output)
            self.assertNotIn(str(root), output)

    def test_refuses_output_collision_and_extent_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory, volume, _offset = fixture(root)
            before = sha256(volume)
            with self.assertRaisesRegex(CrsaTextExtractError, "must not overwrite"):
                run(
                    inventory_path=inventory,
                    volume_arguments=(f"fixture.rio={volume}",),
                    game_id="synthetic",
                    local_output=volume,
                    template_output=None,
                )
            self.assertEqual(before, sha256(volume))

            existing = root / "existing.csv"
            existing.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(CrsaTextExtractError, "without --force"):
                run(
                    inventory_path=inventory,
                    volume_arguments=(f"fixture.rio={volume}",),
                    game_id="synthetic",
                    local_output=existing,
                    template_output=None,
                )
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

            overwritten = run(
                inventory_path=inventory,
                volume_arguments=(f"fixture.rio={volume}",),
                game_id="synthetic",
                local_output=existing,
                template_output=None,
                overwrite=True,
            )
            self.assertEqual(overwritten["slots"], 1)
            self.assertNotEqual(existing.read_text(encoding="utf-8-sig"), "keep")

            document = json.loads(inventory.read_text(encoding="utf-8"))
            document["nodes"][0]["extent"] += 1
            inventory.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(CrsaTextExtractError, "extent mismatch"):
                run(
                    inventory_path=inventory,
                    volume_arguments=(f"fixture.rio={volume}",),
                    game_id="synthetic",
                    local_output=root / "local.csv",
                    template_output=None,
                )

    def test_expected_slot_count_is_a_prewrite_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory, volume, _offset = fixture(root)
            local = root / "local.csv"
            with self.assertRaisesRegex(CrsaTextExtractError, "slot count mismatch"):
                run(
                    inventory_path=inventory,
                    volume_arguments=(f"fixture.rio={volume}",),
                    game_id="synthetic",
                    local_output=local,
                    template_output=None,
                    expect_slots=2,
                )
            self.assertFalse(local.exists())

            existing = root / "existing.csv"
            existing.write_text("reviewed output", encoding="utf-8")
            with self.assertRaisesRegex(CrsaTextExtractError, "slot count mismatch"):
                run(
                    inventory_path=inventory,
                    volume_arguments=(f"fixture.rio={volume}",),
                    game_id="synthetic",
                    local_output=existing,
                    template_output=None,
                    expect_slots=2,
                    overwrite=True,
                )
            self.assertEqual(existing.read_text(encoding="utf-8"), "reviewed output")

            report = run(
                inventory_path=inventory,
                volume_arguments=(f"fixture.rio={volume}",),
                game_id="synthetic",
                local_output=local,
                template_output=None,
                expect_slots=1,
            )
            self.assertEqual(report["expected_slots"], 1)
            self.assertTrue(local.is_file())

    def test_fail_on_warning_is_a_prewrite_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory, volume, _offset = fixture(root, ambiguous_ascii=True)
            local = root / "local.csv"
            with self.assertRaisesRegex(CrsaTextExtractError, "warning"):
                run(
                    inventory_path=inventory,
                    volume_arguments=(f"fixture.rio={volume}",),
                    game_id="synthetic",
                    local_output=local,
                    template_output=None,
                    fail_on_warning=True,
                )
            self.assertFalse(local.exists())

            report = run(
                inventory_path=inventory,
                volume_arguments=(f"fixture.rio={volume}",),
                game_id="synthetic",
                local_output=local,
                template_output=None,
            )
            self.assertTrue(report["warnings"])


if __name__ == "__main__":
    unittest.main()
