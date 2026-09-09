import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from localization.tools import sync_icb_paratranz as sync


class IcbSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        folder = self.repo / sync.FOLDER
        folder.mkdir(parents=True)
        fixtures = {
            'main.ja-zh-Hans.csv': {'id': 't1', 'egpack': 'scene.egpack', 'source_text_sha256': sync.sha('原文\\w\\p'), 'scene': 'scene', 'cn_text': '旧正文\\p'},
            'speakers.ja-zh-Hans.csv': {'relative_path': 'speakers.egpack', 'id': 's1', 'slot': 'jp', 'expected_text': '姓名', 'replacement_text': '姓名'},
            'choices.ja-zh-Hans.csv': {'relative_path': 'scene.egpack', 'id': 'c1', 'slot': 'jp', 'expected_text': '选项', 'replacement_text': '选项'},
            'ui-strings.ja-zh-Hans.tsv': {'id': '1', 'jp': '结果 %s', 'zh_cn': '结果 %s'},
        }
        remote = []
        for index, (name, row) in enumerate(fixtures.items(), 1):
            with (folder / name).open('w', encoding='utf8', newline='') as stream:
                writer = csv.DictWriter(stream, row.keys(), delimiter=sync.TABLES[name][1], lineterminator='\n')
                writer.writeheader()
                writer.writerow(row)
            remote.append({'id': index, 'key': sync.table_key(name, row), 'original': '原文\\w\\p' if index == 1 else row.get('expected_text', row.get('jp')),
                'translation': row[sync.TABLES[name][0]], 'context': '保留上下文', 'stage': 1, 'fileId': 10})
        self.snapshot = [{'file': {'id': 10, 'name': 'test.json', 'project': sync.PROJECT, 'total': 4}, 'rows': remote}]
        self.base = sync.bootstrap(self.repo, self.snapshot, 'fixture-commit')
        self.save_base(self.base)

    def save_base(self, value):
        path = self.repo / sync.BASELINE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')

    def change_local(self, old, new):
        path = self.repo / sync.FOLDER / 'main.ja-zh-Hans.csv'
        path.write_bytes(path.read_bytes().replace(old.encode(), new.encode()))

    def test_noop(self):
        outputs, report = sync.plan(self.repo, self.snapshot, self.base)
        self.assertEqual({}, outputs)
        self.assertEqual(0, report['changed_translations'])

    def test_remote_edit_and_repeat_are_idempotent(self):
        self.snapshot[0]['rows'][0]['translation'] = '新正文\\p'
        outputs, report = sync.plan(self.repo, self.snapshot, self.base)
        self.assertEqual(1, report['changed_translations'])
        for name, data in outputs.items():
            (self.repo / name).write_bytes(data)
        next_base = json.loads((self.repo / sync.BASELINE).read_text(encoding='utf8'))
        self.assertEqual({}, sync.plan(self.repo, self.snapshot, next_base)[0])
        _, index = sync.load_tables(self.repo)
        self.assertEqual('scene', index['ICB|scene.egpack|t1']['row']['scene'])

    def test_local_only_edit_survives(self):
        self.change_local('旧正文', 'Git人工修改')
        outputs, report = sync.plan(self.repo, self.snapshot, self.base)
        self.assertEqual(0, report['changed_translations'])
        self.assertEqual({sync.BASELINE}, set(outputs))

    def test_conflict_refuses_all_writes(self):
        self.change_local('旧正文', 'Git修改')
        self.snapshot[0]['rows'][0]['translation'] = '在线修改\\p'
        before = (self.repo / sync.FOLDER / 'main.ja-zh-Hans.csv').read_bytes()
        with self.assertRaisesRegex(ValueError, 'both_sides_changed'):
            sync.plan(self.repo, self.snapshot, self.base)
        self.assertEqual(before, (self.repo / sync.FOLDER / 'main.ja-zh-Hans.csv').read_bytes())

    def test_identical_concurrent_edits_are_allowed(self):
        self.change_local('旧正文', '共同修改')
        self.snapshot[0]['rows'][0]['translation'] = '共同修改\\p'
        self.assertEqual(0, sync.plan(self.repo, self.snapshot, self.base)[1]['changed_translations'])

    def test_rank_is_normalized_without_writing_remote(self):
        self.snapshot[0]['rows'][0]['translation'] = '少佐到了\\p'
        before = copy.deepcopy(self.snapshot)
        outputs, report = sync.plan(self.repo, self.snapshot, self.base)
        self.assertIn('少校到了', outputs[sync.FOLDER / 'main.ja-zh-Hans.csv'].decode())
        self.assertEqual(1, report['hard_rank_normalizations'])
        self.assertEqual(before, self.snapshot)

    def test_disputed_and_hidden_are_held(self):
        for stage in (0, 2, -1):
            with self.subTest(stage=stage):
                self.snapshot[0]['rows'][0].update(translation='待确认\\p', stage=stage)
                _, report = sync.plan(self.repo, self.snapshot, self.base)
                self.assertEqual(1, report['held_rows'])
                self.assertEqual(0, report['changed_translations'])

    def test_control_and_newline_regressions_are_rejected(self):
        for text in ('新文', '新文\\w\\p', '新文\\n\\p', '新文\n\\p', '新文<03>\\p', ''):
            with self.subTest(text=text):
                self.snapshot[0]['rows'][0]['translation'] = text
                with self.assertRaises(ValueError):
                    sync.plan(self.repo, self.snapshot, self.base)

    def test_ui_placeholder(self):
        self.snapshot[0]['rows'][3]['translation'] = '结果 %d'
        with self.assertRaisesRegex(ValueError, 'placeholders'):
            sync.plan(self.repo, self.snapshot, self.base)

    def test_source_and_identity_changes_stop(self):
        for field, value in [('original', '原文改动'), ('id', 999), ('fileId', 999)]:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.snapshot)
                changed[0]['rows'][0][field] = value
                with self.assertRaises(ValueError):
                    sync.plan(self.repo, changed, self.base)

    def test_missing_duplicate_and_foreign_project_stop(self):
        for mode in ('missing', 'duplicate', 'foreign'):
            changed = copy.deepcopy(self.snapshot)
            if mode == 'missing':
                changed[0]['rows'].pop()
            elif mode == 'duplicate':
                changed[0]['rows'][1]['key'] = changed[0]['rows'][0]['key']
            else:
                changed[0]['file']['project'] = 19505
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                sync.plan(self.repo, changed, self.base)

    def test_no_auth_does_not_contact_network(self):
        with self.assertRaisesRegex(ValueError, 'not configured'):
            sync.fetch_snapshot(None)

    def test_redirect_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'redirect refused'):
            sync.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')


if __name__ == '__main__':
    unittest.main()
