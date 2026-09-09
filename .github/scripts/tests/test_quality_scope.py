import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('quality_scope', Path(__file__).resolve().parents[1] / 'quality_scope.py')
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


class QualityScopeTests(unittest.TestCase):
    def test_translation_and_baseline_only(self):
        paths = ['AGE2/games/imperial-capital-burns/translations/main.ja-zh-Hans.csv',
                 'rUGP/games/photonmelodies/translations/章节.csv',
                 'AGE2/evidence/translations/snapshots/imperial-capital-burns.json',
                 'localization/paratranz/imperial-capital-burns/baseline.json']
        self.assertEqual({'windows': False, 'runtime': False}, scope.classify(paths))

    def test_localization_code_requires_windows(self):
        self.assertEqual({'windows': True, 'runtime': False}, scope.classify(['localization/tools/sync_icb_paratranz.py']))

    def test_runtime_and_unknown_paths_require_full_checks(self):
        for path in ['rUGP/runtime/include/photon_speaker_aliases.h',
                     'rUGP/evidence/photon/images/static-review-20260909/runtime-sync.json',
                     '.github/workflows/quality.yml', 'requirements-dev.txt', 'new-unknown.file']:
            with self.subTest(path=path):
                self.assertEqual({'windows': True, 'runtime': True}, scope.classify([path]))

    def test_code_disguised_under_data_path_is_not_exempt(self):
        self.assertTrue(scope.classify(['localization/paratranz/helper.py'])['windows'])

    def test_mixed_and_deleted_runtime_files_keep_full_checks(self):
        self.assertTrue(scope.classify(['docs/example.md', 'rUGP/runtime/removed.c'])['runtime'])

    def test_quality_is_read_only_without_secrets_or_historical_binary_lock(self):
        workflow = (Path(__file__).resolve().parents[2] / 'workflows/quality.yml').read_text(encoding='utf8')
        self.assertIn('contents: read', workflow)
        self.assertNotIn('pull_request_target:', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertNotIn('--verify-release-code', workflow)
        self.assertNotIn('installed_dll_sha256', workflow)
        self.assertEqual(3, workflow.count('persist-credentials: false'))


if __name__ == '__main__':
    unittest.main()
