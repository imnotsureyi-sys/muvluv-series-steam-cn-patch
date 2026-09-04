from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from rUGP.formats.rio.crsa import CRSA_PREFIX, encode_crsa_encrypted, read_crsa_record
from rUGP.formats.rio.crsa_vm_edit import digest
from rUGP.formats.rio.crypto import encode_extent_offset, decode_extent_offset
from rUGP.formats.rio.ruo import build_ruo, read_footer
from rUGP.tests.formats.rio.test_crsa_vm_edit import fixture, entries_for
from rUGP.tools.text.build_crsa_native_increment import build


class NativeIncrementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'sample.rio'
        self.base = self.root / 'base.ruo'
        self.output = self.root / 'candidate.ruo'
        self.payload = fixture()
        self.record = CRSA_PREFIX + bytes(5) + encode_crsa_encrypted(self.payload)
        offset2 = (64 + len(self.record) + 3) // 4 * 4
        self.source.write_bytes(bytes(64) + self.record
                                + bytes(offset2 - 64 - len(self.record)) + self.record)
        self.protected_key = encode_extent_offset(512, 4)
        self.protected = b'unchanged-image-or-layout-route'
        # The second CRsa is inherited, exercising both effective input paths.
        build_ruo(self.base, 4, [(self.protected_key, self.protected),
                                 (encode_extent_offset(offset2, 4), self.record)])
        self.spec = dict(schema='photon-crsa-native-increment/v1', game='pf', unit_size=4,
                         base_ruo_sha256=digest(self.base.read_bytes()),
                         volumes=[dict(name=self.source.name, bytes=self.source.stat().st_size,
                                       sha256=digest(self.source.read_bytes()), logical_offset=0)],
                         blocks=[])
        for ordinal, offset in enumerate((64, offset2)):
            entries = entries_for(self.payload)
            for entry in entries:
                entry['stable_id'] = f'{ordinal}:{entry["stable_id"]}'
            self.spec['blocks'].append(dict(volume=self.source.name, block_offset=offset,
                source_raw_key=hex(encode_extent_offset(offset, 4)),
                effective_record_sha256=digest(self.record), payload_sha256=digest(self.payload),
                entries=entries))

    def test_multi_block_build_preserves_inherited_route_and_input_files(self):
        before = self.source.read_bytes(), self.base.read_bytes()
        report = build(self.spec, self.root, self.output, self.base)
        self.assertEqual(3, report['redirect_count'])
        self.assertEqual(4, report['entry_count'])
        self.assertEqual(before, (self.source.read_bytes(), self.base.read_bytes()))
        _, old_routes = read_footer(self.base, 4)
        _, new_routes = read_footer(self.output, 4)
        old = next(r for r in old_routes if r.source_raw_offset == self.protected_key)
        new = next(r for r in new_routes if r.source_raw_offset == self.protected_key)
        self.assertEqual(old, new)
        offset = decode_extent_offset(new.ruo_raw_offset, 4)
        self.assertEqual(self.protected, self.output.read_bytes()[offset:offset + len(self.protected)])
        for block in self.spec['blocks']:
            route = next(r for r in new_routes if r.source_raw_offset == int(block['source_raw_key'], 0))
            actual = read_crsa_record(self.output, decode_extent_offset(route.ruo_raw_offset, 4))
            self.assertIn('Synthetic tool'.encode('utf-16le'), actual.plaintext)
            self.assertIn('note:中文说明'.encode('utf-16le'), actual.plaintext)
        self.assertFalse(report['native_increment_validation']['runtime_tested'])

    def test_rejects_whole_input_hash_changes_and_missing_required_base(self):
        for field in ('volume', 'base', 'record', 'payload'):
            changed = deepcopy(self.spec)
            if field == 'volume': changed['volumes'][0]['sha256'] = '0' * 64
            if field == 'base': changed['base_ruo_sha256'] = '0' * 64
            if field == 'record': changed['blocks'][0]['effective_record_sha256'] = '0' * 64
            if field == 'payload': changed['blocks'][0]['payload_sha256'] = '0' * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'hash'):
                build(changed, self.root, self.output, self.base)
            self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(ValueError, 'requires'):
            build(self.spec, self.root, self.output)

    def test_rejects_duplicate_route_or_stable_identity_before_output(self):
        duplicate_route = deepcopy(self.spec)
        duplicate_route['blocks'].append(deepcopy(duplicate_route['blocks'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate CRsa'):
            build(duplicate_route, self.root, self.output, self.base)
        duplicate_id = deepcopy(self.spec)
        duplicate_id['blocks'][1]['entries'][0]['stable_id'] = duplicate_id['blocks'][0]['entries'][0]['stable_id']
        with self.assertRaisesRegex(ValueError, 'duplicate stable'):
            build(duplicate_id, self.root, self.output, self.base)
        self.assertFalse(self.output.exists())

    def test_rejects_mismatched_logical_extent_and_overwrites(self):
        changed = deepcopy(self.spec)
        changed['blocks'][0]['block_offset'] += 4
        with self.assertRaisesRegex(ValueError, 'physical extent'):
            build(changed, self.root, self.output, self.base)
        self.output.write_bytes(b'existing candidate')
        with self.assertRaisesRegex(ValueError, 'new files'):
            build(self.spec, self.root, self.output, self.base)
        self.assertEqual(b'existing candidate', self.output.read_bytes())

    def test_rejects_pm_specs_in_favor_of_volume_staging(self):
        changed = deepcopy(self.spec)
        changed['game'] = 'pm'
        with self.assertRaisesRegex(ValueError, 'fixed-extent volume staging'):
            build(changed, self.root, self.output, self.base)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
