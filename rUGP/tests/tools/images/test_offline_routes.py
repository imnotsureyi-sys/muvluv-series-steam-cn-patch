from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import unittest

from rUGP.tools.images.replay_cr6ti_routes import validate_cases
from rUGP.tools.images.reconcile_native_trace import reconcile, zero_extended_hash


class Cr6MatrixTests(unittest.TestCase):
    def report(self):
        return dict(required_failures=0,cases=[dict(active=a,alt=b,compose=c,sign=d,slack=e,
                    prepared=True,pixels_ok=True,guards_ok=True,before_clean=True,passed=True)
                    for a,b,c,d,e in product((0,1),(0,1),(0,1),(-1,1),(0,16))])

    def test_complete_and_incomplete(self):
        report=self.report()
        validate_cases(report,0)
        report['cases'].pop()
        with self.assertRaises(ValueError): validate_cases(report,0)

    def test_duplicate_and_contradictory(self):
        report=self.report()
        report['cases'][-1]=report['cases'][0]
        with self.assertRaises(ValueError): validate_cases(report,0)
        report=self.report()
        report['cases'][0]['pixels_ok']=False
        with self.assertRaises(ValueError): validate_cases(report,0)

    def test_failed_exit_required(self):
        report=self.report()
        report['cases'][0]['passed']=False
        report['required_failures']=1
        with self.assertRaises(ValueError): validate_cases(report,0)
        validate_cases(report,1)


class TraceTests(unittest.TestCase):
    def manifest(self):
        return {'rows':[dict(game='PF',aliases=['pf:rio000:0x01'],selected_group_id=1,
                    runtime_identity=dict(payload_bytes=10,payload_fnv1a64='0123456789ABCDEF',codec='CRip008'))]}

    def event(self,**changes):
        return dict(dict(pid=1,ordinal=1,payload_bytes=10,payload_fnv1a64='0123456789ABCDEF',
                         event='crip008_ordinary_commit',overlay_status=0,transaction_status=0,
                         destination_committed=1,requested_rgba_fnv1a64='1111111111111111',
                         readback_rgba_fnv1a64='1111111111111111'),**changes)

    def test_absence_and_load_are_not_commit(self):
        r=reconcile(self.manifest(),[],'PF')
        self.assertEqual(r['statuses'],{'not_observed':1})
        r=reconcile(self.manifest(),[self.event(event='load')],'PF')
        self.assertEqual(r['statuses'],{'seen_without_commit':1})

    def test_commit_requires_write_and_readback(self):
        r=reconcile(self.manifest(),[self.event()],'PF')
        self.assertEqual(r['statuses'],{'commit_readback_observed':1})
        self.assertFalse(r['current_build_runtime_verified'])
        for changes in (dict(destination_committed=0),dict(overlay_status=1),
                        dict(transaction_status=6),dict(readback_rgba_fnv1a64='2222222222222222')):
            with self.subTest(changes=changes):
                r=reconcile(self.manifest(),[self.event(**changes)],'PF')
                self.assertEqual(r['statuses'],{'observed_failure':1})

    def test_padding_matches_failure_without_crediting_success(self):
        event=self.event(payload_bytes=13,payload_fnv1a64=zero_extended_hash('0123456789ABCDEF',3),
                         event='crip008_ordinary_identity_not_targeted')
        r=reconcile(self.manifest(),[event],'PF')
        self.assertEqual(r['statuses'],{'observed_failure':1})
        self.assertEqual(r['rows'][0]['zero_padding_matches'],1)

    def test_failure_is_not_hidden_by_later_success(self):
        r=reconcile(self.manifest(),[self.event(event='crip008_surface_rejected'),self.event(ordinal=2)],'PF')
        self.assertEqual(r['statuses'],{'observed_failure':1})
        self.assertEqual(r['rows'][0]['commits'],1)

    def test_duplicate_and_conflicting_session(self):
        event=self.event()
        r=reconcile(self.manifest(),[event,deepcopy(event)],'PF')
        self.assertEqual(r['rows'][0]['commits'],1)
        self.assertEqual(r['duplicate_events_ignored'],1)
        with self.assertRaises(ValueError):
            reconcile(self.manifest(),[event,self.event(event='load')],'PF')

    def test_ambiguous_withheld_and_wrong_game(self):
        m=self.manifest()
        m['rows'].append(deepcopy(m['rows'][0]))
        r=reconcile(m,[self.event()],'PF')
        self.assertEqual(r['ambiguous_events'],1)
        self.assertEqual(r['statuses'],{'not_observed':2})
        m=self.manifest()
        m['withheld_keys']=[['PF',10,'0123456789ABCDEF']]
        self.assertEqual(reconcile(m,[self.event()],'PF')['expected_bindings'],0)
        self.assertEqual(reconcile(self.manifest(),[self.event()],'PM')['expected_bindings'],0)

    def test_capture_cap_is_not_exhaustive_coverage(self):
        r=reconcile(self.manifest(),[self.event(ordinal=8192)],'PF')
        self.assertTrue(r['capture_cap_reached'])
        self.assertFalse(r['capture_exhaustive'])


class PublishedOfflineEvidenceTests(unittest.TestCase):
    root=Path(__file__).resolve().parents[4]/'rUGP/evidence/photon/images/static-review-20260909'

    def read(self,name):
        return json.loads((self.root/name).read_text('utf-8'))

    def test_replay_and_pending_counts(self):
        report=self.read('cr6ti-replay.json')
        self.assertEqual(len(report['rows']),188)
        self.assertEqual(sum(r['case_count'] for r in report['rows']),6016)
        self.assertEqual(sum(r['required_failures'] for r in report['rows']),0)
        self.assertEqual(sum(r['game']=='PF' for r in report['rows']),85)
        self.assertFalse(report['game_started'])
        self.assertFalse(report['assembly_wrapper_executed'])
        pending=self.read('runtime-pending-groups.json')
        self.assertEqual(len(pending['groups']),10)
        self.assertEqual(sum(len(g['bindings']) for g in pending['groups']),40)

    def test_hook_and_diagnostic_boundaries(self):
        report=self.read('native-sites-offline.json')
        for game in ('PF','PM'):
            row=report['games'][game]
            self.assertTrue(row['passed'])
            self.assertEqual(row['negative_sites_rejected'],9)
            self.assertEqual(row['abi_passthrough_cases_passed'],8)
            self.assertEqual(row['selector_positive_and_negative_sites_passed'],4 if game=='PF' else 1)
            self.assertFalse(row['game_code_executed'])
        diagnostics=self.read('diagnostics-ready.json')
        self.assertTrue(diagnostics['diagnostic_only'])
        self.assertFalse(diagnostics['installed'])
        self.assertTrue(all(r['double_build_equal'] for r in diagnostics['games'].values()))

    def test_old_failures_are_not_current_runtime_acceptance(self):
        report=self.read('pf-historical-trace-reconciliation.json')
        self.assertFalse(report['current_build_runtime_verified'])
        self.assertEqual({r['group_id'] for r in report['rows'] if r['status']=='observed_failure'},{2018,2019})
        self.assertEqual(report['statuses']['not_observed'],1182)


if __name__ == '__main__':
    unittest.main()
