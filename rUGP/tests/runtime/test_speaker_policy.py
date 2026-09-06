from pathlib import Path
import json
import re
import unittest

from rUGP.tools.text.rebase_speaker_prefix_repairs import rebase_delimiters

ROOT = Path(__file__).resolve().parents[2]


class SpeakerPolicyTests(unittest.TestCase):
    def test_compiled_aliases_match_reviewed_game_specific_pairs(self):
        header = (ROOT/'runtime/include/photon_speaker_aliases.h').read_text(encoding='utf-8')
        for game, title in [('PF', 'photonflowers'), ('PM', 'photonmelodies')]:
            block = header.split('defined(PHOTON_BUILD_'+game+')', 1)[1].split('#', 1)[0]
            compiled = [(json.loads(cn), json.loads(jp)) for cn, jp in re.findall(
                r'\{L("[^"\n]+"), L("[^"\n]+")\}', block)]
            reviewed = json.loads((ROOT/'games'/title/'translations/increments/speaker-colors-20260906.json').read_text(encoding='utf-8'))
            self.assertEqual(compiled, [(r['target'], r['source']) for r in reviewed['aliases']])

    def test_all_reviewed_prefix_repairs_are_only_structural_and_idempotent(self):
        counts = []
        for title in ['photonflowers', 'photonmelodies']:
            spec = json.loads((ROOT/'games'/title/'translations/increments/speaker-prefixes-20260906.json').read_text(encoding='utf-8'))
            count = 0
            for block in spec['blocks']:
                for row in block['entries']:
                    before, target = row['before_text'], row['target_text']
                    self.assertEqual(rebase_delimiters(before, before, target), target)
                    self.assertEqual(rebase_delimiters(target, before, target), target)
                    count += 1
            counts.append(count)
        self.assertEqual(counts, [53, 1])


if __name__ == '__main__':
    unittest.main()
