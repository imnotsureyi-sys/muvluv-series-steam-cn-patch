from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from rUGP.formats.rio.crsa import CRSA_PREFIX, encode_crsa_encrypted, read_crsa_record
from rUGP.formats.rio.crsa_vm_edit import digest
from rUGP.formats.rio.crypto import encode_extent_offset
from rUGP.tests.formats.rio.test_crsa_vm_edit import entries_for, fixture
from rUGP.tools.text.build_crsa_native_volume_patch import REPORT_NAME, build


class NativeVolumePatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "clean"
        self.source.mkdir()
        self.output = self.root / "stage"
        self.payload = fixture()
        self.record = CRSA_PREFIX + bytes(5) + encode_crsa_encrypted(self.payload)

        self.offsets: dict[str, list[int]] = {}
        for name, prefix, count in (("one.rio", 64, 2), ("two.rio", 80, 1)):
            raw = bytearray(bytes([0x91]) * prefix)
            offsets = []
            for ordinal in range(count):
                offsets.append(len(raw))
                raw.extend(self.record)
                raw.extend(bytes((-len(raw)) % 4))
                raw.extend(bytes([0x41 + ordinal]) * 16)
            raw.extend(bytes([0xE7]) * 32)
            raw.extend(bytes((-len(raw)) % 4))
            (self.source / name).write_bytes(raw)
            self.offsets[name] = offsets
        (self.source / "unused.rio").write_bytes(bytes([0x55]) * 128)

        volumes = []
        logical = 0
        for name in ("one.rio", "two.rio", "unused.rio"):
            path = self.source / name
            volumes.append(dict(
                name=name,
                bytes=path.stat().st_size,
                sha256=digest(path.read_bytes()),
                logical_offset=logical,
            ))
            logical += path.stat().st_size
        logical_by_name = {row["name"]: row["logical_offset"] for row in volumes}
        blocks = []
        for name in ("one.rio", "two.rio"):
            for ordinal, offset in enumerate(self.offsets[name]):
                entries = entries_for(self.payload)
                for entry in entries:
                    entry["stable_id"] = f"{name}:{ordinal}:{entry['stable_id']}"
                blocks.append(dict(
                    volume=name,
                    block_offset=offset,
                    source_raw_key=hex(encode_extent_offset(logical_by_name[name] + offset, 4)),
                    effective_record_sha256=digest(self.record),
                    payload_sha256=digest(self.payload),
                    entries=entries,
                ))
        self.spec = dict(
            schema="photon-crsa-native-increment/v1",
            game="pm",
            unit_size=4,
            base_ruo_sha256=None,
            volumes=volumes,
            blocks=blocks,
        )
        self.source_before = {
            path.name: path.read_bytes() for path in self.source.iterdir() if path.is_file()
        }

    def test_stages_multiple_fixed_records_and_volumes_without_touching_sources(self):
        report = build(self.spec, self.source, self.output)

        self.assertEqual(3, report["block_count"])
        self.assertEqual(6, report["entry_count"])
        self.assertEqual(2, report["modified_volume_count"])
        self.assertFalse(report["native_increment_validation"]["runtime_tested"])
        self.assertTrue(report["native_increment_validation"]["fixed_record_extents"])
        self.assertEqual(report, json.loads((self.output / REPORT_NAME).read_text(encoding="utf-8")))
        self.assertFalse((self.output / "unused.rio").exists())

        for name, before in self.source_before.items():
            self.assertEqual(before, (self.source / name).read_bytes())
        for name in ("one.rio", "two.rio"):
            before = self.source_before[name]
            after = (self.output / name).read_bytes()
            self.assertEqual(len(before), len(after))
            changed_ranges = [
                (offset, offset + len(self.record)) for offset in self.offsets[name]
            ]
            for position, (old, new) in enumerate(zip(before, after)):
                if not any(start <= position < end for start, end in changed_ranges):
                    self.assertEqual(old, new)
            for offset in self.offsets[name]:
                actual = read_crsa_record(self.output / name, offset)
                self.assertIn("Synthetic tool".encode("utf-16le"), actual.plaintext)
                self.assertIn("note:中文说明".encode("utf-16le"), actual.plaintext)

    def test_rejects_hash_drift_and_existing_output_before_writing(self):
        changed = deepcopy(self.spec)
        changed["volumes"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash"):
            build(changed, self.source, self.output)
        self.assertFalse(self.output.exists())

        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_text("untouched", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must be new"):
            build(self.spec, self.source, self.output)
        self.assertEqual("untouched", sentinel.read_text(encoding="utf-8"))

    def test_rejects_an_extent_changing_append(self):
        changed = deepcopy(self.spec)
        changed["game"] = "pf"
        changed["blocks"] = [changed["blocks"][0]]
        entry = changed["blocks"][0]["entries"][-1]
        entry["target_text"] = "note:" + "中文说明" * 12
        entry["storage"] = {"kind": "append"}
        with self.assertRaisesRegex(ValueError, "fixed-extent"):
            build(changed, self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_inherited_ruo_and_mismatched_route(self):
        inherited = deepcopy(self.spec)
        inherited["base_ruo_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "without an inherited RUO"):
            build(inherited, self.source, self.output)
        changed = deepcopy(self.spec)
        changed["blocks"][0]["block_offset"] += 4
        with self.assertRaisesRegex(ValueError, "logical route"):
            build(changed, self.source, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
