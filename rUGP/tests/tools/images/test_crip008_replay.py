"""A truncated or contradictory replay must not produce a passing report."""
from itertools import product
import unittest

from rUGP.tools.images.replay_crip008_routes import validate_replay


class ReplayReportTests(unittest.TestCase):
    def report(self):
        return {
            'cases': [dict(direct=d, stride_sign=s, row_slack=p, variant=v,
                           prepared=v < 3 or v == 5, before_clean=True,
                           pixels_ok=True, guards_ok=True, passed=True)
                      for d, s, p, v in product((0, 1), (-1, 1), (0, 16), range(6))],
            'required_failures': 0,
            'runtime_initialization_exercised': False,
            'assembly_wrapper_executed': False,
            'proprietary_decoder_executed': False,
        }

    def test_complete_matrix(self):
        validate_replay(self.report(), 0)

    def test_empty_missing_duplicate_cases(self):
        for kind in ('empty', 'missing', 'duplicate'):
            with self.subTest(kind=kind):
                report = self.report()
                if kind == 'empty':
                    report['cases'] = []
                elif kind == 'missing':
                    report['cases'].pop()
                else:
                    report['cases'][-1] = report['cases'][0]
                with self.assertRaises(ValueError):
                    validate_replay(report, 0)

    def test_failed_case_requires_matching_count_and_exit(self):
        report = self.report()
        report['cases'][0]['passed'] = False
        with self.assertRaises(ValueError):
            validate_replay(report, 0)
        report['required_failures'] = 1
        with self.assertRaises(ValueError):
            validate_replay(report, 0)
        validate_replay(report, 1)

    def test_string_false_is_not_a_boolean(self):
        report = self.report()
        report['cases'][0]['passed'] = 'false'
        with self.assertRaises(ValueError):
            validate_replay(report, 0)

    def test_cannot_claim_unexecuted_coverage(self):
        for field in ('runtime_initialization_exercised', 'assembly_wrapper_executed',
                      'proprietary_decoder_executed'):
            with self.subTest(field=field):
                report = self.report()
                report[field] = True
                with self.assertRaises(ValueError):
                    validate_replay(report, 0)


if __name__ == '__main__':
    unittest.main()
