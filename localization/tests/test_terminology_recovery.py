"""Guard against the demonstrated loss of historical per-game terminology."""
import csv
import hashlib
import json
from collections import Counter
import unittest
import tomllib

from localization.tools.terminology import ROOT, GAMES, load_game, read_table

COLS=['jp','cn','status','chapter','source','source_row','source_status','occurrences','basis']

def sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'localization/terminology-history/recovery-20260908.json').read_text(encoding='utf-8'))
        cls.baselines={}
        for game,engine in GAMES.items():
            with (ROOT/engine/'games'/game/'terminology/baseline.ja-zh-Hans.csv').open(encoding='utf-8',newline='') as stream:
                reader=csv.DictReader(stream)
                assert reader.fieldnames==COLS
                cls.baselines[game]=list(reader)

    def test_all_seven_baselines_are_explicit_and_counts_reconcile(self):
        for game,engine in GAMES.items():
            folder=ROOT/engine/'games'/game
            project=tomllib.loads((folder/'project.toml').read_text(encoding='utf-8'))
            self.assertEqual(project['terminology_baseline'],'terminology/baseline.ja-zh-Hans.csv')
            rows=self.baselines[game]; meta=self.manifest['games'][game]
            self.assertEqual(len(rows),meta['baseline_records'])
            self.assertEqual(len({r['jp'] for r in rows}),meta['baseline_unique_jp'])
            self.assertEqual(len({(r['source'],r['source_row']) for r in rows}),len(rows))
            self.assertEqual(sha(rows),meta['records_sha256'])
            self.assertEqual(dict(Counter(r['status'] for r in rows)),meta['status_counts'])
            self.assertEqual(dict(Counter(r['source'] for r in rows)),meta['source_counts'])
            # The recovery manifest remains a sealed historical snapshot.
            # Later reviewed additions carry their own current-table counts.
            later=json.loads((ROOT/'rUGP/evidence/photon/text/latin-review-20260909.json').read_text(encoding='utf-8'))['terminology_counts']
            expected_terms=meta['terms']
            if game in later:
                self.assertEqual(later[game]['before'],expected_terms)
                expected_terms=later[game]['after']
            self.assertEqual(len(read_table(ROOT/'localization/glossaries'/f'{game}.ja-zh-Hans.csv')),expected_terms)
            for row in rows:
                self.assertIn(row['source'],{s['name'] for s in self.manifest['sources']})
                self.assertEqual(set(row),set(COLS))
                self.assertIn(row['status'],{'confirmed','contextual','candidate','question','excluded'})
                self.assertTrue(row['jp'] and row['source'] and row['source_row'])
                self.assertFalse(any(ord(c)<32 for v in row.values() for c in v))

    def test_every_original_row_and_original_status_survives(self):
        expected_counts={'tda00-draft':369,'imperial-old':185,'pf-ex-table':88,'pf-ex-baseline':945,'pf-al-table':98,'pm-shard-table':417,'pm-shard-baseline':2321,'pm-ar-table':341}
        proof=self.manifest['historical_row_proofs']
        self.assertEqual(set(proof),set(expected_counts))
        for source,count in expected_counts.items():
            meta=proof[source]
            rows=[r for r in self.baselines[meta['game']] if r['source']==source]
            self.assertEqual(len(rows),count)
            self.assertEqual([int(r['source_row']) for r in rows],list(range(2,count+2)))
            self.assertEqual(sha([[r['source_row'],r['jp'],r['cn'],r['source_status']] for r in rows]),meta['projection_sha256'])
        pf=[r for r in self.baselines['photonflowers'] if r['source']=='pf-ex-baseline']
        pm=[r for r in self.baselines['photonmelodies'] if r['source']=='pm-shard-baseline']
        self.assertEqual(Counter(r['source_status'] for r in pf),{'confirmed':41,'candidate':49,'contextual':852,'question':3})
        self.assertEqual(Counter(r['source_status'] for r in pm),{'confirmed':357,'contextual':60,'candidate':1904})

    def test_all_tda_source_rows_matched_and_recovered_terms_are_scoped(self):
        for game,count in [('tda00',3713),('tda01',8565),('tda02',6589),('tda03',6913)]:
            self.assertEqual(self.manifest['coverage'][game]['verified_source_rows'],count)
            self.assertEqual(self.manifest['coverage'][game]['current_rows'],count)
            self.assertTrue(self.manifest['games'][game]['baseline_kind'].startswith('reconstructed'))
        self.assertIn('管制ユニット',load_game('photonflowers'))
        self.assertIn('総合戦闘技術評価演習',load_game('photonflowers'))
        self.assertIn('タケルちゃん',load_game('photonmelodies'))
        self.assertNotIn('タケルちゃん',load_game('tda00'))

    def test_candidates_are_not_automatically_promoted_and_bad_terms_stay_out(self):
        for game in GAMES:
            active=load_game(game)
            for jp in ['ァァ','ウチ','多分隊長']: self.assertNotIn(jp,active)
            self.assertEqual(active['レーザー級']['cn'],'光线级')
            self.assertEqual(active['重レーザー級']['cn'],'重光线级')
            self.assertFalse(any('激光级' in r['cn'] or '美纪' in r['cn'] for r in active.values()))
        self.assertTrue(any(r['jp']=='ァァ' and r['status']=='excluded' for r in self.baselines['imperial-capital-burns']))

if __name__=='__main__': unittest.main()
