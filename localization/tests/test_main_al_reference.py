import json
from pathlib import Path
import unittest

from localization.tools.export_main_al_reference import public_term

ROOT = Path(__file__).resolve().parents[1] / 'references/main-al-steam-20260909'


class MainAlReferenceTests(unittest.TestCase):
    def test_export_excludes_private_text(self):
        source = {'id': 'sample', 'record_sha256': 'a' * 64, 'ja': '原文句子', 'en': 'private sentence', 'zh': '私有例句'}
        term = {'jp': '用語', 'cn': '术语', 'occurrences': 1, 'source_ids': ['sample'],
                'examples': [{'source_id': 'sample', 'ja': '原文句子', 'en': 'private sentence'}],
                'file': 'C:/private/file'}
        result = json.dumps(public_term(term, {'sample': source}), ensure_ascii=False)
        for private in ('原文句子', 'private sentence', '私有例句', 'C:/private'):
            self.assertNotIn(private, result)

    def test_bad_count_is_rejected(self):
        with self.assertRaises(ValueError):
            public_term({'occurrences': 2, 'source_ids': []}, {})

    def test_published_counts_and_hashes(self):
        expected = {'ml-reference-terms': 101, 'al-reference-terms': 193,
                    'ml-speaker-terms': 167, 'al-speaker-terms': 296}
        for name, count in expected.items():
            terms = json.loads((ROOT / (name + '.json')).read_text(encoding='utf-8'))
            self.assertEqual(len(terms), count)
            for term in terms:
                self.assertNotIn('examples', term)
                self.assertTrue(term['evidence'])
                for evidence in term['evidence']:
                    self.assertEqual(set(evidence), {'source_id', 'record_sha256', 'ja_sha256', 'en_sha256', 'zh_sha256'})
                    for key, value in evidence.items():
                        if key.endswith('_sha256'):
                            self.assertRegex(value, r'^[0-9a-f]{64}$')

    def test_shared_entries_exist_in_both_games(self):
        sets = [{(r['jp'], r['cn']) for r in json.loads((ROOT / (g + '-reference-terms.json')).read_text(encoding='utf-8'))} for g in ('ml', 'al')]
        common = json.loads((ROOT / 'common-reference-terms.json').read_text(encoding='utf-8'))
        self.assertEqual(len(common), 84)
        self.assertEqual({(r['jp'], r['cn']) for r in common}, sets[0] & sets[1])


if __name__ == '__main__':
    unittest.main()
