import csv
import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MainAlAlignmentTests(unittest.TestCase):
    def test_ten_fragment_repairs_preserve_identity_and_do_not_repeat_next_line(self):
        audit = json.loads((ROOT/'localization/reviews/tda-fragment-repairs-20260909.json').read_text(encoding='utf-8'))
        self.assertEqual(len(audit['edits']), 10)
        tables = {}
        for edit in audit['edits']:
            if edit['file'] not in tables:
                with (ROOT/edit['file']).open(encoding='utf-8-sig', newline='') as stream:
                    tables[edit['file']] = {r['id']: r for r in csv.DictReader(stream)}
            row = tables[edit['file']][edit['id']]
            self.assertEqual(row['source_text_sha256'], edit['source_text_sha256'])
            self.assertEqual(row['cn_text'], edit['after'])
            self.assertNotEqual(edit['before'], edit['after'])
        rows = tables['AGE2/games/tda03/translations/ja-zh-Hans.csv']
        self.assertIn('G弹', rows['tda03_t99999']['cn_text'])
        self.assertNotEqual(rows['tda03_t99999']['cn_text'], rows['tda03_t05504']['cn_text'])

    def test_common_rank_rules_are_available_to_all_seven_games(self):
        from localization.tools.terminology import GAMES, load_game
        expected = {'少佐':'少校','中佐':'中校','大佐':'上校','大尉':'上尉',
                    '曹長':'上士','臨時曹長':'临时上士','軍曹':'中士','伍長':'下士'}
        for game in GAMES:
            active = load_game(game)
            for jp, cn in expected.items():
                self.assertEqual(active[jp]['cn'], cn, (game, jp))

    def test_every_record_is_an_authorized_target_field_change(self):
        audit = json.loads((ROOT/'localization/reviews/main-al-alignment-20260909.json').read_text(encoding='utf-8'))
        tables = {}
        seen = set()
        for edit in audit['edits']:
            key = (edit['file'], edit['id'], edit['column'])
            self.assertNotIn(key, seen)
            seen.add(key)
            if edit['file'] not in tables:
                with (ROOT/edit['file']).open(encoding='utf-8-sig', newline='') as stream:
                    tables[edit['file']] = list(csv.DictReader(stream))
            rows = [r for r in tables[edit['file']] if r.get('binding_id', r.get('id', '')) == edit['id']]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][edit['column']], edit['after'])
            expected = edit['before']
            for before, after in edit['replacements']:
                self.assertIn([before, after], audit['replacements'])
                expected = (re.sub(r'DreamCos(?!t)', after, expected) if before == 'DreamCos'
                            else expected.replace(before, after))
            self.assertEqual(expected, edit['after'])
            self.assertEqual(re.findall(r'<[0-9A-F]+>|\\[wp]', edit['before']),
                             re.findall(r'<[0-9A-F]+>|\\[wp]', edit['after']))
            if '樱花盛开之前' in edit['file']:
                self.assertEqual(edit['replacements'], [['钻头牛奶拳', '牛奶钻钻拳']])


if __name__ == '__main__':
    unittest.main()
