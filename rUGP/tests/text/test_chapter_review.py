import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rUGP.tools.text.chapter_review import COLUMNS, cells, decoded, read_chapters, snapshot, visible


class ChapterReviewTests(unittest.TestCase):
    def test_committed_migration_is_exact_for_every_row_and_metadata_field(self):
        root = Path(__file__).resolve().parents[2] / "games"
        for title, count, files in [("photonflowers", 13025, 13), ("photonmelodies", 44698, 45)]:
            folder = root / title / "translations"
            result = read_chapters(folder, unchanged=True)
            self.assertEqual(len(result), count)
            self.assertEqual(result, snapshot(folder))
            manifest = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["files"]), files)

    def test_control_encoding_is_unambiguous_and_lossless(self):
        for value in ["甲\n乙\x01", "<0A>", "\u2060【姓名】正文", "\\A关闭回看",
                      "\x05正文\r\n", "", "<>\x03", "😀\ufeff"]:
            self.assertEqual(decoded(visible(value)), value)
        self.assertEqual(visible("<0A>\n"), "<3C>0A><0A>")
        for invalid in ["<0a>", "<000A>", "<41>", "\n", "<110000>"]:
            with self.assertRaises(ValueError):
                decoded(invalid)

    def test_choices_and_recovered_messages_stay_with_their_story(self):
        root = Path(__file__).resolve().parents[2] / "games"
        folder = root / "photonmelodies/translations"
        manifest = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
        tutorial = next(e for e in manifest["files"] if "打西瓜教程" in e["file"])
        with (folder / tutorial["file"]).open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 56)
        self.assertEqual(sum(r["kind"] == "recovered_message" for r in rows), 36)
        self.assertEqual(sum(r["kind"] == "cstring" for r in rows), 2)
        self.assertTrue(all(":871742696:" in r["binding_id"] for r in rows))

    def fixture(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        original = dict(binding_id="pf:vm:test:1:2:3", kind="cvm", game="pf",
                        rio_file="test", block_offset=1, translated_text="【姓名】正文\n续行\x01",
                        jp_utf8_sha256="a"*64, en_utf8_sha256=None, review_scope="layout_only",
                        command_offset=2, custom_metadata="must survive")
        source = folder.parent / "text-data" / "layout-baseline"
        source.mkdir(parents=True, exist_ok=True)
        raw = json.dumps([original]).encode()
        (source / "rows.json").write_bytes(raw)
        (source / "manifest.json").write_text(json.dumps(dict(rows=1,shards=[dict(
            file="rows.json",rows=1,sha256=hashlib.sha256(raw).hexdigest())])),encoding="utf-8")
        (folder / "chapters.json").write_text(json.dumps(dict(schema="photon-chapter-review/v1",rows=1,
            files=[dict(file="story.csv",rows=1,scenes=[dict(rio_file="test",block_offset=1)])])),encoding="utf-8")
        return original

    def write_csv(self, folder, rows):
        with (folder / "story.csv").open("w",encoding="utf-8",newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            writer.writerows(rows)

    def test_edit_overlays_text_only_and_preserves_opaque_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "translations"
            original = self.fixture(folder)
            row = cells(original)
            row[2] = "【姓名】正文续行<01>"
            self.write_csv(folder,[row])
            result = read_chapters(folder)[0]
            expected = dict(original,translated_text="【姓名】正文续行\x01")
            self.assertEqual(result, expected)
            with self.assertRaises(ValueError):
                read_chapters(folder,unchanged=True)

    def test_rejects_missing_duplicate_bad_metadata_and_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "translations"
            original = self.fixture(folder)
            row = cells(original)
            variants = [[], [row,row]]
            for index,value in [(0,"unknown"),(1,"cstring"),(2,"正文<03>"),
                                (2,"【姓<2060>名】正文"),(3,'{"bad":1}'),
                                (4,"changed"),(5,"b"*64),(6,"b"*64)]:
                changed = list(row)
                changed[index] = value
                variants.append([changed])
            for rows in variants:
                self.write_csv(folder,rows)
                with self.assertRaises(ValueError):
                    read_chapters(folder)


if __name__ == "__main__":
    unittest.main()
