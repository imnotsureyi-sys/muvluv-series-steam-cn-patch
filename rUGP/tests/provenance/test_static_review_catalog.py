from collections import Counter
import json
from pathlib import Path
import unittest

from rUGP.tools.provenance.export_static_review import catalog_counts, REF, SHA
from rUGP.runtime.build import GAMES

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "rUGP/evidence/photon/images/static-review-20260909"


class StaticReviewCatalogTests(unittest.TestCase):
    def test_runtime_sync_distinguishes_default_and_installed_profiles(self):
        report = json.loads((EVIDENCE / "runtime-sync.json").read_text("utf-8"))
        for game, record in report["games"].items():
            self.assertTrue(record["reproduced_byte_exact"])
            self.assertEqual(record["default_dll_sha256"], GAMES[game]["approved_normalized_sha256"])
            for profile in ("default", "installed"):
                build = json.loads((EVIDENCE / f"{game}-{profile}.build.json").read_text("utf-8"))
                self.assertEqual(build["output"]["sha256"], record[f"{profile}_dll_sha256"])
                self.assertEqual(build["speaker_color_candidate"], profile == "installed")
                self.assertTrue(build["authorization_compiled"])
                self.assertTrue(build["deterministic_double_compile_after_pe_normalization"])
        self.assertFalse(report["game_started"])
        self.assertFalse(report["game_files_modified"])

    def test_snapshot_counts_identities_and_states_are_consistent(self):
        catalog = json.loads((EVIDENCE / "catalog.json").read_text("utf-8"))
        rows = catalog["rows"]
        self.assertEqual(len(rows), 1791)
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        self.assertEqual(catalog["counts"], catalog_counts(rows))
        self.assertEqual({r["id"] for r in rows if r["placeholder"]}, {1030, 1049})
        self.assertEqual({r["id"] for r in rows if r["status"] == "人工成品 · 已绑定安装"},
                         {1286, 1287, 4138, 4147, 3698, 3725})
        self.assertEqual(sum(r["status"] == "术语新修订 · 未安装" for r in rows), 54)
        for row in rows:
            self.assertTrue(all(REF.fullmatch(ref) for ref in row["refs"]))
            if row["placeholder"]:
                self.assertFalse(row["official"])
                self.assertIsNone(row["candidate"])
            else:
                for identity in [*row["official"].values(), row["candidate"]]:
                    self.assertRegex(identity["sha256"], SHA)
                    self.assertEqual(len(identity["size"]), 2)
                    self.assertTrue(all(type(n) is int and n > 0 for n in identity["size"]))
        matrix = json.loads((EVIDENCE / "oval-state-matrix.json").read_text("utf-8"))
        ids, states = [], Counter()
        self.assertEqual(len(matrix["characters"]), 18)
        for character in matrix["characters"].values():
            for state, groups in character.items():
                if state != "green_disabled":
                    self.assertEqual(len(groups), 1)
                ids.extend(groups)
                states[state] += len(groups)
        self.assertEqual(len(ids), 58)
        self.assertEqual(len(set(ids)), 58)
        self.assertTrue(set(ids) <= {r["id"] for r in rows})
        self.assertEqual(states, dict(green_unframed=18, green_white_rim=18,
                                     pink_yellow_rim=18, green_disabled=4))


if __name__ == "__main__":
    unittest.main()
