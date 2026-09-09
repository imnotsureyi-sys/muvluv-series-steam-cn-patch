import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from localization.tools import sync_series_paratranz as sync
from rUGP.tools.text.chapter_review import COLUMNS, cells


class SeriesSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)

    def save(self,path,data):
        target=self.repo/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)

    def csv(self,path,rows):
        self.save(path,sync.csv_bytes(dict(raw=b'',fields=list(rows[0]),rows=rows)))

    def fixture(self,slug='pf'):
        originals=[]
        if slug in ('pf','pm'):
            title=sync.PROFILES[slug][1]
            root=Path('rUGP/games')/title
            original=dict(binding_id=f'{slug}:vm:test:1:2:3',kind='cvm',game=slug,rio_file='test',block_offset=1,
                          translated_text='【姓名】旧文\n续行\x01',jp_utf8_sha256=sync.sha('原文\x03\x01'),
                          en_utf8_sha256=None,review_scope='layout_only')
            payload=sync.packed([original]); digest=sync.sha(payload.decode())
            self.save(root/'text-data/layout-baseline/rows.json',payload)
            self.save(root/'text-data/layout-baseline/manifest.json',sync.packed(dict(rows=1,shards=[dict(file='rows.json',rows=1,sha256=digest)])))
            self.save(root/'translations/chapters.json',sync.packed(dict(schema='photon-chapter-review/v1',rows=1,
                files=[dict(file='故事.csv',rows=1,scenes=[dict(rio_file='test',block_offset=1)])])))
            self.path=root/'translations/故事.csv'
            row=dict(zip(COLUMNS,cells(original)))
            self.csv(self.path,[row])
            originals=[dict(key=original['binding_id'],original='原文<03><01>',translation=row['translated_text'],stage=1)]
        else:
            ledger={'translation_inputs':{}}
            for i in range(4):
                game=f'tda0{i}';path=Path(f'AGE2/games/{game}/translations/ja-zh-Hans.csv')
                row=dict(id='t1',egpack='scene.egpack',source_text_sha256=sync.sha('原文\\p'),record_kind='text',cn_text='旧文\\p')
                self.csv(path,[row])
                data=(self.repo/path).read_bytes()
                self.save(Path(f'AGE2/evidence/translations/snapshots/{game}.json'),sync.packed(dict(output_bytes=len(data),output_sha256=sync.sha(data.decode()).upper(),source_sha256='preserve')))
                ledger['translation_inputs'][game.upper()]=dict(bytes=len(data),sha256=sync.sha(data.decode()).upper(),rows=1)
                originals.append(dict(key=f'{game.upper()}|scene.egpack|t1',original='原文\\p',translation='旧文\\p',stage=1))
                if i==0:self.path=path
            self.save(Path('AGE2/evidence/translations/review-ledger/manifest.json'),sync.packed(ledger))
            self.save(sync.SUPPLEMENTS,sync.packed([dict(key='TDA00|ui|s1',source_sha256=sync.sha('结果 %s'),translation='结果 %s')]))
            originals.append(dict(key='TDA00|ui|s1',original='结果 %s',translation='结果 %s',stage=1))
        for i,row in enumerate(originals):row.update(id=i+1,fileId=10)
        self.slug=slug
        self.snapshot=[dict(file=dict(id=10,name='测试.json',project=sync.PROFILES[slug][0],total=len(originals)),rows=originals)]
        for path,data in sync.bootstrap(self.repo,slug,self.snapshot,'fixture').items():self.save(path,data)

    def apply(self):
        outputs,summary=sync.plan(self.repo,self.slug,self.snapshot)
        for path,data in outputs.items():self.save(path,data)
        return outputs,summary

    def local_edit(self):
        path=self.repo/self.path
        path.write_bytes(path.read_bytes().replace('旧文'.encode(),'本地改文'.encode()))

    def test_noop_all_projects(self):
        for slug in sync.PROFILES:
            with self.subTest(slug=slug):
                self.fixture(slug)
                self.assertEqual({},sync.plan(self.repo,slug,self.snapshot)[0])

    def test_photon_edit_preserves_metadata_layout_and_is_idempotent(self):
        self.fixture()
        self.snapshot[0]['rows'][0]['translation']='【姓名】新文<0A>续行<01>'
        outputs,summary=self.apply()
        self.assertEqual(1,summary['changed_translations'])
        row=next(csv.DictReader(io.StringIO(outputs[self.path].decode())))
        self.assertEqual('layout_only',row['review_scope'])
        self.assertEqual('[]',row['cn_annotations'])
        self.assertEqual({},self.apply()[0])

    def test_tda_edit_updates_only_its_output_and_pending_input_metadata(self):
        self.fixture('tda')
        self.snapshot[0]['rows'][0]['translation']='少佐的新文\\p'
        outputs,report=self.apply()
        self.assertIn('少校',outputs[self.path].decode())
        self.assertEqual(1,report['changed_translations'])
        side=json.loads(outputs[Path('AGE2/evidence/translations/snapshots/tda00.json')])
        self.assertEqual(len(outputs[self.path]),side['output_bytes'])
        self.assertEqual('preserve',side['source_sha256'])
        ledger=json.loads(outputs[Path('AGE2/evidence/translations/review-ledger/manifest.json')])
        self.assertEqual(side['output_sha256'],ledger['translation_inputs']['TDA00']['sha256'])
        self.assertEqual({},self.apply()[0])

    def test_tda_supplement_updates_review_only_table(self):
        self.fixture('tda')
        self.snapshot[0]['rows'][-1]['translation']='显示结果 %s'
        outputs,_=self.apply()
        self.assertEqual({sync.SUPPLEMENTS,sync.folder('tda')/'baseline/10.json'},set(outputs))

    def test_local_only_is_not_overwritten(self):
        self.fixture();self.local_edit()
        outputs,report=self.apply()
        self.assertEqual(0,report['changed_translations'])
        self.assertNotIn(self.path,outputs)
        self.assertEqual({},outputs)
        self.snapshot[0]['rows'][0]['translation']='【姓名】后续线上改文<0A>续行<01>'
        with self.assertRaisesRegex(ValueError,'both_sides_changed'):self.apply()

    def test_tda_structural_empty_is_preserved_and_not_fillable(self):
        self.fixture('tda')
        tables,_=sync.load_tables(self.repo,'tda')
        table=tables[self.path]
        table['rows'][0].update(record_kind='structural_empty',cn_text='',source_text_sha256=sync.sha(''))
        self.save(self.path,sync.csv_bytes(table))
        row=self.snapshot[0]['rows'][0]
        row.update(original='',translation='',stage=-1)
        for path,data in sync.bootstrap(self.repo,'tda',self.snapshot,'fixture').items():self.save(path,data)
        self.assertEqual({},self.apply()[0])
        row.update(translation='补字',stage=1)
        with self.assertRaisesRegex(ValueError,'Structural empty'):self.apply()

    def test_conflict_stops_before_writes(self):
        self.fixture();self.local_edit()
        before=(self.repo/self.path).read_bytes()
        self.snapshot[0]['rows'][0]['translation']='【姓名】线上改文<0A>续行<01>'
        with self.assertRaisesRegex(ValueError,'both_sides_changed'):self.apply()
        self.assertEqual(before,(self.repo/self.path).read_bytes())

    def test_held_edit_repeats_until_review_state_changes(self):
        self.fixture()
        row=self.snapshot[0]['rows'][0]
        row.update(stage=2,translation='【姓名】新文<0A>续行<01>')
        for _ in range(2):self.assertEqual(1,self.apply()[1]['held_rows'])
        row['stage']=1
        self.assertEqual(1,self.apply()[1]['changed_translations'])

    def test_photon_controls_and_name_injections_rejected(self):
        self.fixture()
        for bad in ['【姓名】正文<03><0A>续行<01>','【姓<2060>名】正文<0A>续行<01>',
                    '【姓名】正文<01>','【姓名】正文<0a>续行<01>','']:
            with self.subTest(bad=bad):
                self.snapshot[0]['rows'][0]['translation']=bad
                with self.assertRaises(ValueError):self.apply()

    def test_original_file_id_and_key_mismatches_rejected(self):
        self.fixture()
        initial=copy.deepcopy(self.snapshot)
        for field,value in [('original','别的原文'),('id',99),('key','other')]:
            self.snapshot=copy.deepcopy(initial);self.snapshot[0]['rows'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.apply()
        self.snapshot=copy.deepcopy(initial);self.snapshot[0]['file']['name']='改名'
        with self.assertRaises(ValueError):self.apply()

    def test_bootstrap_refuses_to_swallow_unreconciled_edits(self):
        self.fixture();self.local_edit()
        with self.assertRaisesRegex(ValueError,'Reconcile'):sync.bootstrap(self.repo,'pf',self.snapshot,'new')

    def test_ui_placeholder_change_is_rejected(self):
        self.fixture('tda');self.snapshot[0]['rows'][-1]['translation']='显示结果 %d'
        with self.assertRaises(ValueError):self.apply()

    def test_baseline_path_cannot_escape_project(self):
        self.fixture();path=self.repo/sync.folder('pf')/'manifest.json'
        manifest=json.loads(path.read_text(encoding='utf8'));manifest['files'][0]['baseline']='../../outside.json'
        path.write_bytes(sync.packed(manifest))
        with self.assertRaisesRegex(ValueError,'Unsafe baseline path'):self.apply()

    def test_live_committed_project_coverage_and_source_fields(self):
        repo=Path(__file__).resolve().parents[2]
        for slug,total in [('pf',13025),('pm',44698),('tda',26696)]:
            manifest=json.loads((repo/sync.folder(slug)/'manifest.json').read_text(encoding='utf8'))
            tables,index=sync.load_tables(repo,slug)
            self.assertEqual(total,len(index))
            self.assertEqual(total,sum(f['rows'] for f in manifest['files']))
            seen=set()
            for entry in manifest['files']:
                for row in json.loads((repo/sync.folder(slug)/entry['baseline']).read_text(encoding='utf8')):
                    self.assertNotIn(row['key'],seen);seen.add(row['key'])
                    self.assertEqual(index[row['key']]['source'],row['source_sha256'])
            self.assertEqual(seen,set(index))


if __name__=='__main__':unittest.main()
