from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import struct
import unittest

from rUGP.formats.rio.crsa_vm_stream import VmStreamError
from rUGP.formats.rio.crypto import decode_extent_offset
from rUGP.tools.text.audit_crsa_native_text import audit, latin_sentence, inline_category, source_hashes
from rUGP.tests.formats.rio.test_crsa_vm_stream import archive, common
from rUGP.tests.catalog.test_rio_inventory import class_ref


class NativeAuditClassificationTests(unittest.TestCase):
    def test_public_schema_and_glossary_hash_contracts_match_committed_bytes(self) -> None:
        root = Path(__file__).resolve().parents[3]
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest().upper()
        glossary = root / "localization/glossaries/muv-luv.ja-zh-Hans.csv"
        glossary_hash = digest(glossary)
        for game in ("photonflowers", "photonmelodies"):
            spec = json.loads((root / f"rUGP/games/{game}/translations/increments/crsa-native-20260904.json").read_text(encoding="utf-8"))
            self.assertEqual(glossary_hash, spec["glossary_sha256"])
        for name in ("crsa-native-review-20260904.json", "crsa-native-terms-20260904.json"):
            evidence = json.loads((root / "rUGP/evidence/photon/text" / name).read_text(encoding="utf-8"))
            self.assertEqual(glossary_hash, evidence["glossary_sha256"])
        schema_hash = digest(root / "rUGP/formats/rio/crsa_vm_schema.json")
        audit = json.loads((root / "rUGP/evidence/photon/text/crsa-native-text-20260903.json").read_text(encoding="utf-8"))
        self.assertEqual({schema_hash}, {game["schema_sha256"] for game in audit["games"].values()})

    def test_failed_refresh_invalidates_an_older_complete_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, output = root/"cache", root/"audit"
            cache.mkdir()
            output.mkdir()
            data = archive(class_ref("CVmUnimplemented", 21)+common(), 1)
            (cache/"fixture.rio.0000000000.plain").write_bytes(data)
            manifest = dict(volumes=[dict(name="fixture.rio", bytes=4096, blocks=[dict(
                offset=0, plaintext_bytes=len(data), payload_sha256=hashlib.sha256(data).hexdigest())])])
            (cache/"census.json").write_text(json.dumps(manifest), encoding="utf-8")
            (output/"audit.json").write_text('{"audit_state":"complete"}', encoding="utf-8")
            with self.assertRaisesRegex(VmStreamError, "unimplemented command"):
                audit("pf", cache, output, [])
            self.assertEqual("incomplete", json.loads((output/"audit.json").read_text("utf-8"))["audit_state"])

    def test_source_identity_accepts_old_escaping_without_crossing_nul(self) -> None:
        digest = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
        self.assertIn(digest("【人】<03>台词<01>"), source_hashes("【人】\x03台词\x01"))
        self.assertIn(digest("【人】\x03台词\x01"), source_hashes("【人】\x03台词\x01"))
        self.assertIn(digest("原文<01>"), source_hashes("\x10原文\x01"))
        self.assertNotIn(digest("following"), source_hashes("\x01\0following"))

    def test_weapon_parameter_is_classified_by_proven_callee(self) -> None:
        field = dict(text="36mmチェーンガン", role="call.argument.2")
        command = dict(name="CVmCall", fields=dict(script=dict(key=0xC634C9DC)))
        self.assertEqual("excluded_weapon_parameter", inline_category(field, command, "pf"))
        command["fields"]["script"]["key"] = 0
        self.assertEqual("unresolved_inline_semantics", inline_category(field, command, "pf"))

    def test_weapon_parameters_remain_in_inventory_but_not_omission_queues(self) -> None:
        key = 0xC634C9DC
        offset = decode_extent_offset(key, 4)
        resource = class_ref("CRsa", 5) + struct.pack("<HIIHB", 0xC108, key, 0, 0, 0)
        label = "36mmチェーンガン"
        body = common() + b"\0" + resource + struct.pack("<H", 3)
        body += (struct.pack("<I", 1) + b"\0") * 2
        body += struct.pack("<I", 1) + b"\xff\xfe\xff" + bytes((len(label),)) + label.encode("utf-16le")
        data = archive(class_ref("CVmCall", 21) + body + b"\0", 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, output = root / "cache", root / "audit"
            cache.mkdir()
            (cache / f"fixture.rio.{offset:010d}.plain").write_bytes(data)
            census = dict(volumes=[dict(name="fixture.rio", bytes=offset+len(data), blocks=[dict(
                offset=offset, plaintext_bytes=len(data), payload_sha256=hashlib.sha256(data).hexdigest())])])
            (cache / "census.json").write_text(json.dumps(census), encoding="utf-8")
            report = audit("pf", cache, output, [])
            self.assertTrue(report["validation_passed"])
            self.assertEqual(1, report["current_categories"]["excluded_weapon_parameter"])
            for filename in ("missing-current-text.csv", "unreviewed-fields.csv"):
                with (output / filename).open(encoding="utf-8-sig", newline="") as stream:
                    self.assertEqual([], list(csv.DictReader(stream)))
            with (output / "all-inline-fields.csv").open(encoding="utf-8-sig", newline="") as stream:
                fields = list(csv.DictReader(stream))
            self.assertEqual([label], [r["text"] for r in fields if r["category"] == "excluded_weapon_parameter"])

    def test_templates_and_font_names_are_retained_without_false_translation_claims(self) -> None:
        self.assertEqual("font_identifier", inline_category(dict(text="ＭＳ ゴシック", role="generic.OM_SetFont.フェイス名"), {}, "pf"))
        self.assertEqual("save_slot_template", inline_category(dict(text="%Y年%m月%d日\\|%Y/%m/%d", role="call.argument.1"), {}, "pf"))
        self.assertEqual("unresolved_inline_display", inline_category(dict(text="原文\\|New hidden sentence", role="call.argument.1"), {}, "pf"))
        self.assertFalse(latin_sentence("【Aquila 1】「……！」\x01"))
        self.assertTrue(latin_sentence("【Aquila 1】「All Aquilas—Call in!」\x01"))


if __name__ == "__main__":
    unittest.main()
