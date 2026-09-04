from __future__ import annotations
import copy
from pathlib import Path
import struct
import tempfile
import unittest

from rUGP.formats.rio.crsa import CRSA_PREFIX, encode_crsa_encrypted, read_crsa_record
from rUGP.formats.rio.crsa_vm_pool import CVM_MSG3_DECLARATION, find_vm_message_commands, parse_direct_pool
from rUGP.formats.rio.crypto import encode_extent_offset, decode_extent_offset
from rUGP.formats.rio.ruo import build_ruo, read_footer
from rUGP.tools.text.audit_crsa_display_gaps import sha
from rUGP.tools.text.build_crsa_display_increment import append_translations, build


def body(offset):
    return struct.pack('<IIHHBB',offset,1,1,0,2,0)+struct.pack('<III',1,0,0)+struct.pack('<III',3,0,0)


class DisplayIncrementTests(unittest.TestCase):
    def test_rejects_superseded_partial_manifest_before_reading_inputs(self):
        with self.assertRaisesRegex(ValueError, 'superseded'):
            build({'status': 'superseded'}, Path('missing.rio'), Path('missing.ruo'), Path('candidate.ruo'))

    def setUp(self):
        commands=CVM_MSG3_DECLARATION+body(4)+struct.pack('<H',0x802b)+body(8)
        pool='\x00\x05\x00\x05Go!\x00'.encode('utf-16le')
        self.payload=commands+b'\xa5'*(124-len(commands))+struct.pack('<I',len(pool)//2)+pool+b'suffix'
        pair, _=parse_direct_pool(self.payload,find_vm_message_commands(self.payload),128).command_slots
        s,t=pair
        self.entry=dict(stable_id='test:display:1',command_order=1,command_offset=4,
            source_offset=s.offset,translation_offset=t.offset,source_slot_sha256=sha(s.raw),
            display_slot_sha256=sha(t.raw),target_text='<05>前进！')

    def test_alias_source_and_other_translation_are_preserved(self):
        result=append_translations(self.payload,128,[self.entry])
        pairs=parse_direct_pool(result,find_vm_message_commands(result),128).command_slots
        self.assertEqual(pairs[0][0],pairs[1][0])
        self.assertEqual(pairs[0][1].text,'\x05前进！')
        self.assertEqual(pairs[1][1].text,'\x05Go!')

    def test_rejects_binding_and_control_changes(self):
        for key,value in [('command_order',0),('display_slot_sha256','0'*64),('target_text','前进！')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                entry={**self.entry,key:value}
                append_translations(self.payload,128,[entry])

    def test_cumulative_build_preserves_route_bytes_and_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.rio';base=root/'base.ruo';output=root/'candidate.ruo'
            record=CRSA_PREFIX+bytes(5)+encode_crsa_encrypted(self.payload)
            source.write_bytes(bytes(64)+record)
            protected=b'protected-existing-date-route'
            build_ruo(base,4,[(encode_extent_offset(512,4),protected)])
            spec=dict(unit_size=4,source_raw_key=hex(encode_extent_offset(64,4)),block_offset=64,
                source_logical_byte_offset=64,base_ruo_sha256=sha(base.read_bytes()),
                effective_record_sha256=sha(record),pool_base=128,entries=[self.entry])
            before=(source.read_bytes(),base.read_bytes())
            report=build(spec,source,base,output)
            self.assertEqual(report['redirect_count'],2)
            self.assertEqual((source.read_bytes(),base.read_bytes()),before)
            _,routes=read_footer(output,4)
            target=next(r for r in routes if r.source_raw_offset==int(spec['source_raw_key'],0))
            actual=read_crsa_record(output,decode_extent_offset(target.ruo_raw_offset,4))
            self.assertIn('前进！'.encode('utf-16le'),actual.plaintext)
            self.assertIn(protected,output.read_bytes())
            bad=copy.deepcopy(spec);bad['base_ruo_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'base RUO'):
                build(bad,source,base,root/'bad.ruo')


if __name__=='__main__':
    unittest.main()
