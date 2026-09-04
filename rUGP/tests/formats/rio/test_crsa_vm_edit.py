from __future__ import annotations

from copy import deepcopy
import struct
import unittest

from rUGP.formats.rio.crsa_vm_edit import digest, text_digest, edit_native_fields
from rUGP.formats.rio.crsa_vm_stream import parse_crsa_vm_stream, native_message_commands
from rUGP.formats.rio.crsa_vm_fields import inventory_vm_pool
from rUGP.tests.catalog.test_rio_inventory import class_ref
from rUGP.tests.formats.rio.test_crsa_vm_stream import archive, common


def fixture(auxiliary=True, source_text='Source example', orphan_text=None):
    callee = 0xC634C9DC
    resource=class_ref('CRsa',5)+struct.pack('<HIIHB',0xC108,callee,0,0,0)
    weapon='Synthetic tool'
    field=b'\xff\xfe\xff'+bytes([len(weapon)])+weapon.encode('utf-16le')
    arguments=struct.pack('<III',2,2,1)+field+struct.pack('<I',2)
    arguments+=(struct.pack('<IH',0,0))*3
    call=class_ref('CVmCall',21)+common()+b'\0'+resource+struct.pack('<H',7)+arguments+b'\0'
    pool=bytearray(b'\0\0')
    def cell(text):
        index=len(pool)//2;pool.extend((text+'\0').encode('utf-16le'));return index
    source=cell(source_text)
    source_aux=cell('Source:source reading')
    display=cell('\x05Example note')
    display_aux=cell('note:old annotation')
    if orphan_text is not None:
        cell(orphan_text)
    # Both auxiliary fields initially point to an interior of the preceding
    # primary. Their correct ownership can still be recovered by adjacency.
    values=(source,source+1 if auxiliary else 0,0,display,display+1 if auxiliary else 0,0)
    msg=class_ref('CVmMsg3',21)+struct.pack('<IIHHBB6I',16,0,1,0,2,0,*values)
    return archive(call+msg,2,bytes(pool))


def entries_for(payload):
    parsed=parse_crsa_vm_stream(payload,'pf')
    pool=inventory_vm_pool(payload,native_message_commands(parsed),parsed['pool_base'])
    refs={(r.language,r.role):r for r in pool.references}
    base=dict(status='reviewed',review_status='keep',command_order=2,command_target=16,
              source_message_sha256=text_digest(refs[0,'message'].text),
              display_message_sha256=text_digest(refs[1,'message'].text),
              source_message_index=refs[0,'message'].index,display_message_index=refs[1,'message'].index)
    def binding(a):
        return dict(language=a.language,sha256=text_digest(a.cell.text),native_index=a.native_index,
                    cell_offset=a.cell.offset,index_field_offset=a.index_field_offset,binding=a.binding)
    if pool.annotations:
        source=next(a for a in pool.annotations if a.language==0)
        display=next(a for a in pool.annotations if a.language==1)
        repair=dict(base,stable_id='synthetic:source-ruby',action='repair_source_annotation',annotation_source=binding(source))
        note=dict(base,stable_id='synthetic:display-ruby',action='set_display_annotation',
                  annotation_sources=[binding(source),binding(display)],display_annotation_index=display.native_index,
                  target_text='note:中文说明')
        return [repair,note]
    return [dict(base,stable_id='synthetic:display',action='replace_display_message',target_text='\x05中文提示')]


class NativeEditTests(unittest.TestCase):
    def test_rebinds_both_annotations_and_preserves_unrelated_cstring(self):
        before=fixture();entries=entries_for(before)
        result=edit_native_fields(before,'pf',entries,digest(before))
        parsed=parse_crsa_vm_stream(result.payload,'pf')
        self.assertEqual('Synthetic tool',parsed['strings'][0]['text'])
        self.assertEqual(0,result.report['serialized_prefix_delta'])
        self.assertEqual(result.report['old_pool_units'],result.report['new_pool_units'])
        self.assertTrue(result.report['validation']['pool_size_preserved'])
        inv=inventory_vm_pool(result.payload,native_message_commands(parsed),parsed['pool_base'])
        self.assertEqual((),inv.issues)
        self.assertEqual(['exact_native_reference']*2,[a.binding for a in inv.annotations])
        self.assertEqual('note:中文说明',inv.annotations[1].cell.text)
        self.assertEqual('\x05Example note',next(r.text for r in inv.references if r.language==1 and r.role=='message'))
        self.assertTrue(result.report['validation']['all_source_messages_preserved'])

    def test_source_controls_only_can_receive_complete_chinese_message(self):
        before=fixture(auxiliary=False, source_text='\x05\n');entries=entries_for(before)
        result=edit_native_fields(before,'pf',entries,digest(before))
        parsed=parse_crsa_vm_stream(result.payload,'pf')
        inv=inventory_vm_pool(result.payload,native_message_commands(parsed),parsed['pool_base'])
        self.assertEqual('\x05中文提示',next(r.text for r in inv.references if r.language==1 and r.role=='message'))

    def test_missing_chinese_annotation_can_be_added_from_japanese_source(self):
        before=fixture();parsed=parse_crsa_vm_stream(before,'pf')
        command=native_message_commands(parsed)[0]
        data=bytearray(before);struct.pack_into('<I',data,command.translation_index_field+4,0);before=bytes(data)
        entries=entries_for(fixture())
        entries[-1]['annotation_sources']=entries[-1]['annotation_sources'][:1]
        entries[-1]['display_annotation_index']=0
        result=edit_native_fields(before,'pf',entries,digest(before))
        self.assertEqual(2,result.report['changed_indices'])

    def test_rejects_unreviewed_or_unresolved_entry(self):
        before=fixture();entries=entries_for(before)
        for status in ('translated','question','blocked'):
            altered=deepcopy(entries);altered[0]['status']=status
            with self.assertRaisesRegex(ValueError,'reviewed'):
                edit_native_fields(before,'pf',altered,digest(before))

    def test_rejects_changed_payload_field_or_command_binding(self):
        before=fixture();entries=entries_for(before)
        with self.assertRaisesRegex(ValueError,'hash'):
            edit_native_fields(before,'pf',entries,'0'*64)
        altered=deepcopy(entries);altered[0]['source_message_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):edit_native_fields(before,'pf',altered,digest(before))
        altered=deepcopy(entries);altered[0]['command_target']=8
        with self.assertRaisesRegex(ValueError,'target'):edit_native_fields(before,'pf',altered,digest(before))
        altered=deepcopy(entries);altered[0]['annotation_source']['cell_offset']=0
        with self.assertRaisesRegex(ValueError,'binding'):edit_native_fields(before,'pf',altered,digest(before))

    def test_rejects_embedded_nul_and_unapproved_padding(self):
        before=fixture();entries=entries_for(before)
        for target in ('中文\0填充','中文\u2060','', '中文\n字段'):
            altered=deepcopy(entries);altered[-1]['target_text']='note:'+target
            with self.assertRaises(ValueError):edit_native_fields(before,'pf',altered,digest(before))

    def test_rejects_annotation_key_absent_from_current_translation(self):
        before=fixture();entries=entries_for(before);entries[-1]['target_text']='stale key:中文说明'
        with self.assertRaisesRegex(ValueError,'key absent'):
            edit_native_fields(before,'pf',entries,digest(before))

    def test_rejects_annotation_recovery_hash_mismatch(self):
        before=fixture();entries=entries_for(before);entries[-1]['annotation_sources'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):
            edit_native_fields(before,'pf',entries,digest(before))

    def test_rejects_control_change_and_duplicate_targets(self):
        before=fixture(auxiliary=False);entries=entries_for(before)
        altered=deepcopy(entries);altered[-1]['target_text']='中文提示'
        with self.assertRaisesRegex(ValueError,'control sequence'):
            edit_native_fields(before,'pf',altered,digest(before))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            edit_native_fields(before,'pf',entries+[entries[0]],digest(before))

    def test_astral_annotation_length_is_counted_in_utf16_units(self):
        before=fixture();entries=entries_for(before);entries[-1]['target_text']='note:模拟\U00020000器材'
        result=edit_native_fields(before,'pf',entries,digest(before))
        parsed=parse_crsa_vm_stream(result.payload,'pf')
        inv=inventory_vm_pool(result.payload,native_message_commands(parsed),parsed['pool_base'])
        self.assertEqual('note:模拟\U00020000器材',inv.annotations[-1].cell.text)

    def test_pool_growth_requires_an_explicit_storage_contract(self):
        before=fixture();entries=entries_for(before)
        entries[-1]['target_text']='note:'+'中文说明'*12
        with self.assertRaisesRegex(ValueError,'explicit storage contract'):
            edit_native_fields(before,'pf',entries,digest(before))
        entries[-1]['storage']={'kind':'append'}
        result=edit_native_fields(before,'pf',entries,digest(before))
        self.assertGreater(result.report['appended_pool_units'],0)
        self.assertFalse(result.report['validation']['pool_size_preserved'])

    def test_nonempty_orphan_reuse_is_hash_and_capacity_bound(self):
        before=fixture(orphan_text='reviewed orphan storage cell')
        entries=entries_for(before)
        entries[-1]['target_text']='note:'+'中文说明'*5
        parsed=parse_crsa_vm_stream(before,'pf')
        inv=inventory_vm_pool(before,native_message_commands(parsed),parsed['pool_base'])
        orphan=next(cell for cell in inv.unclaimed_cells if cell.text=='reviewed orphan storage cell')
        entries[-1]['storage']={
            'kind':'reuse_unclaimed_cell','index':orphan.index,
            'sha256':text_digest(orphan.text),'capacity_units':len(orphan.raw)//2-1,
        }
        result=edit_native_fields(before,'pf',entries,digest(before))
        self.assertEqual(0,result.report['appended_pool_units'])
        self.assertEqual(1,result.report['storage_placements']['reviewed_unclaimed_cell'])
        altered=deepcopy(entries);altered[-1]['storage']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):
            edit_native_fields(before,'pf',altered,digest(before))


if __name__=='__main__':unittest.main()
