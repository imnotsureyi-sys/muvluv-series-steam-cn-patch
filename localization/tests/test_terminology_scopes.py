import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter

from localization.tools.terminology import GAMES, ROOT, candidate_terms, load_game, read_table


class TerminologyScopeTests(unittest.TestCase):
    def test_seven_games_explicitly_load_only_common_and_own_table(self):
        common = read_table(ROOT / "localization/glossaries/muv-luv.ja-zh-Hans.csv")
        for game, engine in GAMES.items():
            own = read_table(ROOT / "localization/glossaries" / f"{game}.ja-zh-Hans.csv")
            effective = load_game(game)
            self.assertEqual(set(effective), set(common) | set(own))
            self.assertNotIn("ァァ", effective)
            self.assertNotIn("ウチ", effective)
            self.assertNotIn("多分隊長", effective)
            self.assertFalse(any(r["cn"] == "轨道潜水员" for r in effective.values()))
        self.assertIn("ウィル", load_game("tda00"))
        self.assertNotIn("ウィル", load_game("photonflowers"))
        self.assertIn("ファング", load_game("imperial-capital-burns"))
        self.assertNotIn("ファング", load_game("tda00"))
        self.assertEqual(load_game("photonflowers")["ミキ"]["cn"], "壬姬")
        self.assertEqual(load_game("photonmelodies")["ピアティフ"]["cn"], "皮亚蒂芙")
        self.assertNotIn("ピアティフ", load_game("tda00"))
        self.assertEqual(load_game("photonmelodies")["武"]["cn"], "武")
        self.assertNotIn("量子電導脳", common)

    def test_longest_match_and_katakana_boundaries(self):
        glossary = load_game("tda00")
        self.assertFalse(candidate_terms("ウィルス", glossary))
        self.assertEqual([r["jp"] for r in candidate_terms("重レーザー級", glossary)], ["重レーザー級"])
        self.assertEqual([r["jp"] for r in candidate_terms("レーザー級", glossary)], ["レーザー級"])
        self.assertEqual([r["jp"] for r in candidate_terms("ウィル", glossary)], ["ウィル"])
        self.assertEqual(candidate_terms("anything", {}), [])

    def test_every_input_row_has_one_disposition_and_old_bytes_are_preserved(self):
        audit = json.loads((ROOT / "localization/terminology-history/scope-audit-20260908.json").read_text(encoding="utf-8"))
        for source in audit["sources"]:
            entries = [r for r in audit["records"] if r["source"] == source["name"]]
            self.assertEqual(len(entries), source["rows"])
            self.assertEqual({r["row"] for r in entries}, set(range(2, source["rows"] + 2)))
            self.assertTrue(all(r["state"] in ("scoped", "pending", "excluded") for r in entries))
        self.assertEqual(len(audit["records"]), 2568)
        self.assertEqual(dict(Counter(r["state"] for r in audit["records"])), audit["disposition_counts"])
        # This incomplete audit is retained as history, not a current-table oracle.
        self.assertEqual(audit['status'], 'withdrawn-incomplete-source-inventory')
        self.assertEqual(audit['superseded_by'], 'recovery-20260908.json')
        for source, filename in [("mixed", "mixed-20260908.csv"), ("imperial", "imperial-20260908.csv")]:
            raw = (ROOT / "localization/terminology-history" / filename).read_bytes()
            expected = next(s for s in audit["sources"] if s["name"] == source)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])
            records = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            entries = [r for r in audit["records"] if r["source"] == source]
            self.assertEqual([(r["jp"],r["cn"]) for r in records], [(r["jp"],r["cn"]) for r in entries])

    def test_no_duplicate_empty_or_control_bearing_terms(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "terms.csv"
            for content in ["jp,cn,context\n詞,词,test\n詞,词,test\n",
                            "jp,cn,context\n詞,,test\n",
                            "jp,cn,context\n詞,词,test\x03\n"]:
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_table(path)


if __name__ == "__main__":
    unittest.main()
