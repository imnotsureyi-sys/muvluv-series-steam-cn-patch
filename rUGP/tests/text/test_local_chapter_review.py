import json
from pathlib import Path
import tempfile
import unittest

from rUGP.tests.text import test_chapter_review as fixtures
from rUGP.tools.text.chapter_review import COLUMNS, cells, read_chapters
from rUGP.tools.text.local_chapter_review import (
    LOCAL_COLUMNS, csv_bytes, export, import_edits, read_csv, sha,
)


class LocalChapterReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.folder = self.root / "rUGP/games/photonflowers/translations"
        self.local = self.root / "local-internal/session/pf"
        row = fixtures.ChapterReviewTests().fixture(self.folder)
        row["jp_utf8_sha256"] = sha("原文\x03\n<0A>\x01")
        baseline = self.folder.parent / "text-data/layout-baseline"
        raw = json.dumps([row]).encode()
        (baseline / "rows.json").write_bytes(raw)
        import hashlib
        (baseline / "manifest.json").write_text(json.dumps(dict(rows=1,shards=[dict(
            file="rows.json",rows=1,sha256=hashlib.sha256(raw).hexdigest())])),encoding="utf-8")
        fixtures.ChapterReviewTests().write_csv(self.folder, [cells(row)])
        self.source = self.root / "source.jsonl"
        self.source.write_text(json.dumps(dict(binding_id=row["binding_id"], game="pf",
            kind="cvm", jp="原文\x03\n<0A>\x01", en=None, cn="obsolete Chinese")) + "\n", encoding="utf-8")

    def edit(self, **changes):
        rows = read_csv(self.local / "story.csv", LOCAL_COLUMNS)
        rows[0].update(changes)
        (self.local / "story.csv").write_bytes(csv_bytes(LOCAL_COLUMNS, rows))

    def test_export_exact_sources_and_current_chinese_noop_import(self):
        original = (self.folder / "story.csv").read_bytes()
        self.assertEqual(export(self.folder,self.source,self.local),dict(files=1,rows=1))
        row = read_csv(self.local / "story.csv",LOCAL_COLUMNS)[0]
        self.assertEqual(row["jp_text"],"原文<03><0A><3C>0A><01>")
        self.assertEqual(row["en_text"],"")
        self.assertNotIn("obsolete",row["translated_text"])
        self.assertEqual(import_edits(self.folder,self.local,apply=True)["changed_rows"],0)
        self.assertEqual((self.folder / "story.csv").read_bytes(),original)
        with self.assertRaises(ValueError):
            export(self.folder,self.source,self.local)

    def test_chinese_edit_dry_run_apply_and_idempotency(self):
        export(self.folder,self.source,self.local)
        original = read_chapters(self.folder)[0]
        self.edit(translated_text="【姓名】正文续行<01>",cn_annotations='["审核注释"]')
        self.assertEqual(import_edits(self.folder,self.local)["changed_rows"],1)
        self.assertEqual(read_chapters(self.folder)[0],original)
        import_edits(self.folder,self.local,apply=True)
        expected = dict(original,translated_text="【姓名】正文续行\x01",cn_annotations=["审核注释"])
        self.assertEqual(read_chapters(self.folder)[0],expected)
        self.assertEqual(import_edits(self.folder,self.local,apply=True)["changed_rows"],0)

    def test_source_mismatch_and_public_output_rejected(self):
        with self.assertRaises(ValueError):
            export(self.folder,self.source,self.root / "public")
        source = json.loads(self.source.read_text(encoding="utf-8"))
        source["jp"] = "错文"
        self.source.write_text(json.dumps(source),encoding="utf-8")
        with self.assertRaises(ValueError):
            export(self.folder,self.source,self.local)
        self.assertFalse(self.local.exists())

    def test_read_only_fields_and_controls_rejected_without_writes(self):
        export(self.folder,self.source,self.local)
        original = (self.folder / "story.csv").read_bytes()
        local = (self.local / "story.csv").read_bytes()
        for changes in [dict(jp_text="改了"),dict(en_text="invented"),dict(kind="cstring"),
                        dict(binding_id="unknown"),dict(translated_text="正文<03>"),
                        dict(translated_text="【姓<2060>名】"),dict(cn_annotations="{}")]:
            (self.local / "story.csv").write_bytes(local)
            self.edit(**changes)
            with self.assertRaises(ValueError):
                import_edits(self.folder,self.local,apply=True)
            self.assertEqual((self.folder / "story.csv").read_bytes(),original)

    def test_stale_review_cannot_overwrite_new_public_edit(self):
        export(self.folder,self.source,self.local)
        rows = read_csv(self.folder / "story.csv", COLUMNS)
        rows[0]["translated_text"] = "新的中文<01>"
        data = csv_bytes(COLUMNS,rows)
        (self.folder / "story.csv").write_bytes(data)
        self.edit(translated_text="旧审核的修改<01>")
        with self.assertRaises(ValueError):
            import_edits(self.folder,self.local,apply=True)
        self.assertEqual((self.folder / "story.csv").read_bytes(),data)

    def test_missing_duplicate_and_extra_rows_rejected(self):
        export(self.folder,self.source,self.local)
        rows = read_csv(self.local / "story.csv",LOCAL_COLUMNS)
        for modified in [[],rows+rows]:
            (self.local / "story.csv").write_bytes(csv_bytes(LOCAL_COLUMNS,modified))
            with self.assertRaises(ValueError):
                import_edits(self.folder,self.local)


if __name__ == "__main__":
    unittest.main()
