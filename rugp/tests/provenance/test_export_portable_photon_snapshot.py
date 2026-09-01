from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from rugp.tools.provenance import export_portable_photon_snapshot as MODULE


class PortablePhotonSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name).resolve()
        self.state = self.workspace / "checkpoint" / "production_state.json"
        self.ledger_json = self.workspace / "translations" / "translation_ledger.json"
        self.ledger_csv = self.workspace / "translations" / "translation_ledger.csv"

        candidate = self.workspace / "candidate" / "shared.png"
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(b"candidate-png-content")
        candidate_hash = MODULE.sha256_file(candidate)

        entries = []
        for index in (1, 2):
            raw = self.workspace / "raw" / f"asset-{index}.png"
            display = self.workspace / "display" / f"asset-{index}.png"
            qa = self.workspace / "qa" / f"asset-{index}.json"
            raw.parent.mkdir(parents=True, exist_ok=True)
            display.parent.mkdir(parents=True, exist_ok=True)
            qa.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(f"raw-{index}".encode())
            display.write_bytes(f"display-{index}".encode())
            qa.write_text("{}\n", encoding="utf-8")
            entries.append(
                {
                    "asset_id": f"pm:test:{index}",
                    "game": "pm",
                    "status": "ready_confirmed",
                    "raw_source_png": str(raw),
                    "raw_source_png_sha256": MODULE.sha256_file(raw),
                    "display_source_png": str(display),
                    "display_source_png_sha256": MODULE.sha256_file(display),
                    "candidate_png": str(candidate),
                    "candidate_png_sha256": candidate_hash,
                    "qa_path": str(qa),
                    "nested": {
                        "audit_report": str(self.workspace / "audit" / "report.json"),
                        "font_manifest": r"Z:\outside\private-font.json",
                    },
                }
            )

        state_value = {
            "schema": "synthetic-production-state/v1",
            "updated_utc": "2026-08-23T00:00:00Z",
            "entries": entries,
        }
        self.state.parent.mkdir(parents=True)
        self.state.write_text(
            json.dumps(state_value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        ledger_rows = [
            {
                "asset_id": "pm:test:1",
                "source_text": "原文一",
                "target_text": "译文一",
                "basis": str(self.workspace / "notes" / "basis-one.txt"),
            },
            {
                "asset_id": "pm:test:2",
                "source_text": "原文二",
                "target_text": "译文二",
                "basis": "manual-review",
            },
        ]
        self.ledger_json.parent.mkdir(parents=True)
        self.ledger_json.write_text(
            json.dumps({"entries": ledger_rows}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.ledger_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ledger_rows[0]))
            writer.writeheader()
            writer.writerows(ledger_rows)

        self.source_hashes = {
            "production_state": MODULE.sha256_file(self.state),
            "translation_ledger_json": MODULE.sha256_file(self.ledger_json),
            "translation_ledger_csv": MODULE.sha256_file(self.ledger_csv),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def export(self, output_name: str, *, copy_candidates: bool = False):
        return MODULE.export_snapshot(
            workspace_root=self.workspace,
            production_state_path=self.state,
            ledger_json_path=self.ledger_json,
            ledger_csv_path=self.ledger_csv,
            output_path=self.workspace / output_name,
            copy_candidate_files=copy_candidates,
            expected_state_sha256=self.source_hashes["production_state"],
            expected_ledger_json_sha256=self.source_hashes[
                "translation_ledger_json"
            ],
            expected_ledger_csv_sha256=self.source_hashes["translation_ledger_csv"],
        )

    def assert_sources_unchanged(self) -> None:
        self.assertEqual(MODULE.sha256_file(self.state), self.source_hashes["production_state"])
        self.assertEqual(
            MODULE.sha256_file(self.ledger_json),
            self.source_hashes["translation_ledger_json"],
        )
        self.assertEqual(
            MODULE.sha256_file(self.ledger_csv),
            self.source_hashes["translation_ledger_csv"],
        )

    def assert_no_absolute_path_leak(self, output: Path) -> None:
        self.assertEqual(MODULE.scan_text_outputs_for_absolute_paths(output), [])
        for path in output.rglob("*"):
            if path.is_file() and (
                path.suffix.lower() in MODULE.TEXT_SUFFIXES
                or path.name == ".gitattributes"
            ):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(str(self.workspace), text)
                self.assertNotIn(self.workspace.as_posix(), text)

    def test_default_export_is_metadata_only_and_portable(self) -> None:
        output = self.workspace / "snapshot-default"
        report = self.export(output.name)

        self.assertFalse((output / "assets").exists())
        self.assertFalse((output / ".gitattributes").exists())
        self.assertEqual(list(output.rglob("*.png")), [])
        self.assertEqual(report["unique_candidates_copied"], 0)
        self.assertEqual(report["candidate_bytes_copied"], 0)
        self.assertEqual(report["missing_resource_records"], 0)
        self.assertEqual(report["absolute_path_leaks"], 0)
        self.assertTrue(report["source_inputs_unchanged"])
        self.assertEqual(report["raw_display_steam_api_files_copied"], 0)

        manifest = json.loads((output / "portable_manifest.json").read_text("utf-8"))
        for entry in manifest["production_state"]["entries"]:
            self.assertTrue(entry["candidate_png"].startswith("workspace/"))
            self.assertTrue(entry["raw_source_png"].startswith("workspace/"))
            self.assertTrue(entry["display_source_png"].startswith("workspace/"))
            self.assertTrue(entry["qa_path"].startswith("workspace/"))
            self.assertTrue(
                entry["nested"]["font_manifest"].startswith("external/redacted/")
            )
        self.assertEqual(MODULE.absolute_value_count(manifest), 0)
        self.assert_no_absolute_path_leak(output)
        self.assert_sources_unchanged()

    def test_explicit_candidate_copy_is_deduplicated_and_lfs_ready(self) -> None:
        output = self.workspace / "snapshot-lfs"
        report = self.export(output.name, copy_candidates=True)

        copied = list((output / "assets" / "candidates").rglob("*.png"))
        self.assertEqual(len(copied), 1)
        self.assertEqual(report["unique_candidates_copied"], 1)
        self.assertEqual(report["candidate_bytes_copied"], copied[0].stat().st_size)
        self.assertEqual(
            (output / ".gitattributes").read_text("utf-8"),
            "assets/candidates/**/*.png filter=lfs diff=lfs merge=lfs -text\n",
        )

        manifest = json.loads((output / "portable_manifest.json").read_text("utf-8"))
        candidate_refs = {
            entry["candidate_png"] for entry in manifest["production_state"]["entries"]
        }
        self.assertEqual(candidate_refs, {copied[0].relative_to(output).as_posix()})
        self.assertEqual(MODULE.sha256_file(copied[0]).lower(), copied[0].stem)
        output_file_bytes = {
            path.read_bytes() for path in output.rglob("*") if path.is_file()
        }
        self.assertNotIn(b"raw-1", output_file_bytes)
        self.assertNotIn(b"raw-2", output_file_bytes)
        self.assertNotIn(b"display-1", output_file_bytes)
        self.assertNotIn(b"display-2", output_file_bytes)
        self.assert_no_absolute_path_leak(output)
        self.assert_sources_unchanged()

    def test_expected_hash_mismatch_fails_without_output(self) -> None:
        output = self.workspace / "snapshot-refused"
        with self.assertRaises(MODULE.SnapshotError):
            MODULE.export_snapshot(
                workspace_root=self.workspace,
                production_state_path=self.state,
                ledger_json_path=self.ledger_json,
                ledger_csv_path=self.ledger_csv,
                output_path=output,
                expected_state_sha256="0" * 64,
            )
        self.assertFalse(output.exists())
        self.assert_sources_unchanged()


if __name__ == "__main__":
    unittest.main()
