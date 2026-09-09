import json
from pathlib import Path
import unittest
from localization.tools.export_independent_main_al import evidence

ROOT=Path(__file__).resolve().parents[1]/'references/main-al-independent-20260909'

class IndependentTests(unittest.TestCase):
    def test_evidence_omits_full_text(self):
        result=evidence({'source_id':'test','ja':'private JP','en':'private EN','zh':'private CN','path':'C:/private'})
        self.assertEqual(set(result),{'source_id','ja_sha256','en_sha256','zh_sha256'})
        self.assertNotIn('private',json.dumps(result))

    def test_counts_variants_hashes_and_nonautomatic_scope(self):
        for game,n,v,s in [('ml',403,406,167),('al',529,551,296)]:
            terms=json.loads((ROOT/(game+'-independent-baseline.json')).read_text(encoding='utf8'))
            speakers=json.loads((ROOT/(game+'-speaker-baseline.json')).read_text(encoding='utf8'))
            self.assertEqual((len(terms),sum(len(t['variants']) for t in terms),len(speakers)),(n,v,s))
            self.assertEqual(len({t['term_id'] for t in terms}),n)
            for t in terms+speakers:
                self.assertFalse(t['automatic_replacement_authorized'])
            for t in terms:
                for variant in t['variants']:
                    self.assertTrue(variant['evidence'])
                    for e in variant['evidence']:
                        self.assertEqual(set(e),{'source_id','ja_sha256','en_sha256','zh_sha256'})
                        for k in ('ja_sha256','en_sha256','zh_sha256'):self.assertRegex(e[k],r'^[0-9a-f]{64}$')
        shared=json.loads((ROOT/'shared-forms.json').read_text(encoding='utf8'))
        self.assertEqual(len(shared),77)
        self.assertTrue(all(not s['promotion_to_common_authorized'] for s in shared))
