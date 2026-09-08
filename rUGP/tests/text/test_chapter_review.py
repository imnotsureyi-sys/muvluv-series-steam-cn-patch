import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rUGP.tools.text.chapter_review import COLUMNS, cells, decoded, read_chapters, snapshot, visible


class ChapterReviewTests(unittest.TestCase):
    def test_committed_chapters_preserve_baseline_except_audited_corrections(self):
        root = Path(__file__).resolve().parents[2] / "games"
        audit = json.loads((root.parent / "evidence/photon/text/terminology-20260908.json").read_text(encoding="utf-8"))
        edits = {e["binding_id"]: e for e in audit["edits"]}
        self.assertEqual(len(edits), 15)
        self.assertEqual(len(audit["edits"]), len(edits))
        reviewed = json.loads((root.parent / "evidence/photon/text/latin-decisions-20260909.json").read_text(encoding="utf-8"))
        latest = {e["binding_id"]: e for e in reviewed["edits"]}
        self.assertEqual(len(latest), 103)
        round2 = json.loads((root.parent / "evidence/photon/text/latin-decisions-20260909-round2.json").read_text(encoding="utf-8"))
        followup = {e["binding_id"]: e for e in round2["edits"]}
        self.assertEqual(len(followup), 59)
        followup_seen = set()
        round3 = json.loads((root.parent / "evidence/photon/text/latin-decisions-20260909-round3.json").read_text(encoding="utf-8"))
        final = {e["binding_id"]: e for e in round3["edits"]}
        self.assertEqual(len(final), 8)
        final_seen = set()
        latest_seen = set()
        seen = set()
        for title, count, files in [("photonflowers", 13025, 13), ("photonmelodies", 44698, 45)]:
            folder = root / title / "translations"
            result = read_chapters(folder)
            self.assertEqual(len(result), count)
            expected = snapshot(folder)
            for row in expected:
                if row["binding_id"] in edits:
                    edit = edits[row["binding_id"]]
                    self.assertEqual(visible(row["translated_text"]), edit["before"])
                    row["translated_text"] = decoded(edit["after"])
                    seen.add(row["binding_id"])
                if row["binding_id"] in latest:
                    edit = latest[row["binding_id"]]
                    self.assertEqual(visible(row["translated_text"]), edit["before"])
                    row["translated_text"] = decoded(edit["after"])
                    latest_seen.add(row["binding_id"])
                if row["binding_id"] in followup:
                    edit = followup[row["binding_id"]]
                    self.assertEqual(visible(row["translated_text"]), edit["before"])
                    row["translated_text"] = decoded(edit["after"])
                    followup_seen.add(row["binding_id"])
                if row["binding_id"] in final:
                    edit = final[row["binding_id"]]
                    self.assertEqual(visible(row["translated_text"]), edit["before"])
                    row["translated_text"] = decoded(edit["after"])
                    final_seen.add(row["binding_id"])
            self.assertEqual(result, expected)
            manifest = json.loads((folder / "chapters.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["files"]), files)
        self.assertEqual(seen, set(edits))
        self.assertEqual(latest_seen, set(latest))
        self.assertEqual(followup_seen, set(followup))
        self.assertEqual(final_seen, set(final))

    def test_final_latin_ledger_accounts_for_all_candidates(self):
        import re
        root = Path(__file__).resolve().parents[2]
        folder = root / 'evidence/photon/text'
        ledger = json.loads((folder/'latin-review-20260909.json').read_text(encoding='utf-8'))
        self.assertEqual(ledger['total_script_rows'], 57723)
        records = ledger['records']
        self.assertEqual(len(records), 352)
        self.assertEqual({r['candidate'] for r in records}, set(range(1,353)))
        self.assertEqual(len({r['binding_id'] for r in records}), 352)
        self.assertEqual([g['number'] for g in ledger['groups']], list(range(1,81)))
        protected = {r['candidate'] for r in records if r['state']=='protected'}
        covered = {i for g in ledger['groups'] for i in g['candidates']}
        self.assertEqual(len(protected), 15)
        self.assertEqual(covered | protected, set(range(1,353)))
        self.assertFalse(covered & protected)
        audited = {}
        for name in ['latin-decisions-20260909.json','latin-decisions-20260909-round2.json','latin-decisions-20260909-round3.json']:
            audit = json.loads((folder/name).read_text(encoding='utf-8'))
            for edit in audit['edits']:
                self.assertEqual(re.findall(r'<(?!0A>)[0-9A-F]+>',edit['before']), re.findall(r'<(?!0A>)[0-9A-F]+>',edit['after']))
                self.assertNotIn('<03>',edit['after'])
                audited[edit['binding_id']] = edit
        self.assertEqual(len(audited), 170)
        current = {r['binding_id']:visible(r['translated_text']) for game in ['photonflowers','photonmelodies'] for r in read_chapters(root/'games'/game/'translations')}
        for record in records:
            identity = record['binding_id']
            self.assertEqual(hashlib.sha256(current[identity].encode()).hexdigest(),record['after_sha256'])
            self.assertEqual(record['state']=='changed',identity in audited)
            if record['state']!='changed':
                self.assertEqual(record['before_sha256'],record['after_sha256'])
            self.assertEqual(record['groups'],[g['number'] for g in ledger['groups'] if record['candidate'] in g['candidates']])

    def test_second_latin_review_preserves_sources_controls_and_protection(self):
        import re
        root = Path(__file__).resolve().parents[2]
        audit = json.loads((root / "evidence/photon/text/latin-decisions-20260909-round2.json").read_text(encoding="utf-8"))
        self.assertEqual(audit['approved_decisions'], [3,19,20,23,24,25,37,39,43,44,45,46,47,48,49,55,61,63,64,66])
        self.assertEqual(hashlib.sha256((root.parent / audit['protected_file']).read_bytes()).hexdigest(), audit['protected_sha256'])
        for edit in audit['edits']:
            self.assertNotEqual(edit['file'], audit['protected_file'])
            self.assertNotEqual(edit['before'], edit['after'])
            self.assertEqual(re.findall(r'<(?!0A>)[0-9A-F]+>',edit['before']), re.findall(r'<(?!0A>)[0-9A-F]+>',edit['after']))
            self.assertNotIn('<03>', edit['after'])
            self.assertNotIn('<2060>', edit['after'])

    def test_user_latin_decisions_preserve_controls_and_protected_chapter(self):
        import re
        root = Path(__file__).resolve().parents[2]
        audit = json.loads((root / "evidence/photon/text/latin-decisions-20260909.json").read_text(encoding="utf-8"))
        protected = root.parent / audit["protected_file"]
        self.assertEqual(hashlib.sha256(protected.read_bytes()).hexdigest(), audit["protected_sha256"])
        self.assertEqual(audit["approved_decisions"], [1, 2, 4, 13, 26, 35, 36, 38, 40, 41, 42])
        rules = {
            1: [(r"Mach 15", "15马赫")], 2: [(r"DELETE", "删除")],
            4: [(r"Amen", "阿门")], 13: [(r"PLEASE", "求你了")],
            26: [(r"Euro Fightas", "尤罗法伊塔斯公司")],
            35: [(r"HIVE", "HIVE（巢穴）")],
            36: [(r"Aquila\s*(\d+)", r"大鹫\1"), (r"Aquilas", "大鹫队"), (r"Aquila", "大鹫"), (r"All大鹫队", "All 大鹫队")],
            38: [(r"Lightning\s*(\d+)", r"闪电\1"), (r"Lightning", "闪电")],
            40: [(r"Dancer\s*(\d+)", r"舞者\1"), (r"Dancer", "舞者")],
            41: [(r"Ghost\s*(\d+)", r"幽灵\1"), (r"Ghost", "幽灵")],
            42: [(r"Hunter\s*(\d+)", r"猎人\1"), (r"Hunter", "猎人")],
        }
        for edit in audit["edits"]:
            self.assertNotEqual(edit["file"], audit["protected_file"])
            expected = edit["before"]
            for decision in edit["decisions"]:
                for pattern, replacement in rules[decision]:
                    expected = re.sub(pattern, replacement, expected)
            self.assertEqual(expected, edit["after"])
            self.assertEqual(re.findall(r"<[0-9A-F]+>", edit["before"]), re.findall(r"<[0-9A-F]+>", edit["after"]))

    def test_terminology_fixes_are_narrow_and_do_not_regress(self):
        import re
        root = Path(__file__).resolve().parents[2]
        audit = json.loads((root / "evidence/photon/text/terminology-20260908.json").read_text(encoding="utf-8"))
        replacements = {"激光级":"光线级", "美纪":"壬姬", "Enigma":"恩尼格玛", "Rafale":"阵风", "鸡奸":"爆菊"}
        slang_edits = [e for e in audit['edits'] if '鸡奸' in e['before']]
        self.assertEqual(len(slang_edits), 3)
        self.assertTrue(all(e['file'] == 'rUGP/games/photonflowers/translations/赎罪.csv' for e in slang_edits))
        for edit in audit["edits"]:
            expected = edit["before"]
            for before, after in replacements.items():
                expected = expected.replace(before, after)
            self.assertEqual(expected, edit["after"])
            self.assertEqual(re.findall(r"<[0-9A-F]+>", edit["before"]),
                             re.findall(r"<[0-9A-F]+>", edit["after"]))
        for title in ("photonflowers", "photonmelodies"):
            for row in read_chapters(root / "games" / title / "translations"):
                text = re.sub(r"[\x00-\x1f\u2060]", "", row["translated_text"])
                self.assertNotIn("激光级", text)
                self.assertNotIn("鸡奸", text)
                if "【壬姬】" in text:
                    self.assertNotIn("美纪", text)
        with (root.parent / "localization/glossaries/muv-luv.ja-zh-Hans.csv").open(encoding="utf-8-sig", newline="") as stream:
            glossary = {r["jp"]:r["cn"] for r in csv.DictReader(stream)}
        for term in ("光線級", "レーザー級"):
            self.assertEqual(glossary[term], "光线级")
        for term in ("重光線級", "重レーザー級"):
            self.assertEqual(glossary[term], "重光线级")
        self.assertEqual(glossary["レーザー"], "激光")

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
