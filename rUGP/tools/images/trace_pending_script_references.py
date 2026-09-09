"""Read-only, bounded follow-up to the first PF/PM runtime capture.

The caller supplies the private reference-census directory. Published output contains
only identities, hashes, command coordinates, and existing Chinese review cues.
"""
import argparse,csv,hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--census-root',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
O=args.census_root
E=R/'rUGP/evidence/photon/images/static-review-20260909'
sys.path.insert(0,str(R));sys.dont_write_bytecode=True
from rUGP.formats.rio.crsa import read_crsa_record
from rUGP.formats.rio.crypto import decode_extent_offset
from rUGP.formats.rio.crsa_vm_stream import parse_crsa_vm_stream
read=lambda p:json.loads(Path(p).read_text('utf-8-sig'))
sha=lambda b:hashlib.sha256(b).hexdigest().upper()
c=read(O/'program_reference_census.json')
full=read(O/c['full_crsa_census']['evidence'])
cat={r['id']:r for r in read(E/'catalog.json')['rows']}
assets={a['id']:a for a in c['assets']}
pending=[(g['game'].lower(),b['group_id'])for g in read(E/'runtime-pending-groups.json')['groups'] for b in g['bindings']]+[('pm',i)for i in [2946,2961,2971,492]]
sources={(s['game'],s['name']):s for s in c['sources']}
owners={(r['game'],r['volume'],r['block_offset']):r for r in c['owners']}
records={(r['game'],r['volume'],r['block_offset']):r for r in full['rows']}
chapter={};chapter_hashes={}
for game,name in [('pf','photonflowers'),('pm','photonmelodies')]:
 p=R/f'rUGP/games/{name}/translations/chapters.json';chapter_hashes[game]=sha(p.read_bytes())
 for f in read(p)['files']:
  for s in f['scenes']:chapter[game,s['rio_file'],s['block_offset']+11]=f['file']
def owner_id(k):return f'{k[0]}:{k[1]}:0x{k[2]-11:08x}'
def typed(v,p='fields'):
 if isinstance(v,list):
  for i,x in enumerate(v):yield from typed(x,f'{p}[{i}]')
 elif isinstance(v,dict):
  if 'key'in v and 'size'in v:yield p,v
  for key,x in v.items():
   if key!='parent':yield from typed(x,p+'.'+key)
selected={}
for game,gid in pending:
 for aid in cat[gid]['refs']:
  if not aid.startswith(game+':'):continue
  for ref in assets[aid]['references']:
   if ref['storage']=='checksum_verified_plaintext_reference':selected.setdefault((game,ref['volume'],ref['block_offset']),[]).append((gid,aid,ref))
vms={};plaintexts={};proofs=[];hits={i:[]for _,i in pending}
for k,refs in selected.items():
 o=owners[k];source=sources[k[:2]];record=read_crsa_record(Path(source['path']),k[2]-11)
 assert sha(record.record)==records[k]['record_sha256'].upper()
 assert sha(record.plaintext)==o['plain_sha256'].upper()
 assert record.plaintext==(O/'program_data'/o['plain_file']).read_bytes()
 vm=parse_crsa_vm_stream(record.plaintext,k[0]);vms[k]=vm;plaintexts[k]=record.plaintext
 proofs.append(dict(id=owner_id(k),game=k[0],volume=k[1],record_offset=k[2]-11,
  record_sha256=sha(record.record),plaintext_sha256=sha(record.plaintext),
  command_count=len(vm['commands']),chapter=chapter.get(k),archive_record_verified=True))
 for gid,aid,ref in refs:
  pair=bytes.fromhex(assets[aid]['expected_pair']);pos=ref['position']
  assert record.plaintext[pos:pos+8]==pair
  cmd=next(cmd for cmd in vm['commands']if cmd['offset']<=pos<cmd['end'])
  paths=[(path,v) for path,v in typed(cmd['fields']) if v['key'].to_bytes(4,'little')+v['size'].to_bytes(4,'little')==pair]
  assert paths,(gid,pos)
  op=cmd['fields'].get('operation',{});op=op.get('name')if isinstance(op,dict)else None
  hits[gid].append(dict(asset_id=aid,owner=owner_id(k),command_order=cmd['order'],
    command_class=cmd['name'],native_operation=op,reference_position=pos,
    typed_fields=sorted(set(path for path,_ in paths)),resource_classes=sorted(set(v['name']for _,v in paths))))
 print('verified',owner_id(k),flush=True)
# Resolve only calls between the archive-verified owners above; do not promote
# a broad cached call graph to live entry-point proof.
bases={};base=0
for game in ['pf','pm']:
 base=0
 for s in sorted((s for s in c['sources']if s['game']==game),key=lambda s:s['name']):bases[game,s['name']]=base;base+=s['bytes']
logical={(k[0],bases[k[:2]]+k[2]-11):k for k in selected}
edges=[]
for k,vm in vms.items():
 for cmd in vm['commands']:
  if cmd['name']!='CVmCall':continue
  script=cmd['fields'].get('script',{})
  if 'key'not in script:continue
  dest=logical.get((k[0],decode_extent_offset(script['key'],4)))
  if dest:edges.append(dict(caller=owner_id(k),command_order=cmd['order'],callee=owner_id(dest)))
maps=read(O/'official_reference_mapping_replay.json');map_proofs=[]
for tab in maps['tables']:
 relevant=[x for x in tab['rows']if x['source']in set(cat[1668]['refs']+cat[3003]['refs'])or x['target']in set(cat[1668]['refs']+cat[3003]['refs'])]
 if not relevant:continue
 with Path(sources[tab['game'],tab['volume']]['path']).open('rb')as f:f.seek(tab['offset']);raw=f.read(tab['extent'])
 assert sha(raw)==tab['sha256'].upper()
 map_proofs.append(dict(game=tab['game'],volume=tab['volume'],offset=tab['offset'],extent=tab['extent'],sha256=sha(raw),
  rows=[dict(source=x['source'],target=x['target'])for x in relevant],scope='Previously typed mapping rechecked against archive bytes; no display entry proven.'))
# Four story segments cover the registration routes of 38 pending resources.
scenarios=[]
for game,vol,block in [('pf','photonflowers11.rio.002',501633651),('pf','photonflowers11.rio.002',1377793947),('pf','photonflowers11.rio.002',1602830779),('pm','photonmelodies11.rio.003',2010308831)]:
 k=(game,vol,block);oid=owner_id(k);reachable={oid}
 while True:
  updated=reachable|{x['callee']for x in edges if x['caller']in reachable}
  if updated==reachable:break
  reachable=updated
 groups=sorted(i for _,i in pending if any(x['owner']in reachable for x in hits[i]))
 # Match nearby native messages by UTF-8 source hash, never by legacy CSV
 # byte offsets (which can differ after text pool/layout changes).
 title='photonflowers' if game=='pf' else 'photonmelodies'
 cp=R/f'rUGP/games/{title}/translations'/chapter[k]
 zh={}
 with cp.open(encoding='utf-8-sig',newline='')as f:
  for row in csv.DictReader(f):
   if row['binding_id'].startswith(f'{game}:vm:{vol}:{block-11}:'):
    zh.setdefault(row['jp_utf8_sha256'],[]).append(row)
 cues=[];vm=vms[k];plain=plaintexts[k]
 orders=sorted({h['command_order']for gid in groups for h in hits[gid]if h['owner']==oid})
 targets=[orders[0]]+([1948]if block==1602830779 else [])
 for target in targets:
  for command in vm['commands']:
   if command['order']<=target or command['name']!='CVmMsg3':continue
   slots=command['fields']['first_records']
   if not slots:continue
   at=vm['pool_base']+slots[0][0]*2;end=at
   while end+2<=len(plain)and plain[end:end+2]!=b'\0\0':end+=2
   if end+2>len(plain):raise ValueError('Unterminated cue text')
   digest=hashlib.sha256(plain[at:end].decode('utf-16-le').encode('utf-8')).hexdigest()
   matched=zh.get(digest,[])
   if not matched or len({r['translated_text']for r in matched})!=1:continue
   cues.append(dict(image_reference_command=target,following_message_command=command['order'],
    source_utf8_sha256=digest,translated_text=matched[0]['translated_text'],
    translation_binding_ids=sorted(r['binding_id']for r in matched)))
   break
  else:raise ValueError('No hash-matched nearby cue')
 scenarios.append(dict(game=game,chapter=chapter[k].removesuffix('.csv'),owner=oid,registered_group_ids=groups,
  following_dialogue_cues=cues,translation_file_sha256=sha(cp.read_bytes()),
  scope='Static resource references and helper registrations, not proof that all members draw in one playthrough.'))
assert len(set(i for s in scenarios for i in s['registered_group_ids']))==38
rows=[]
for game,gid in pending:
 h=hits[gid]
 classification='script_resource_reference'
 if not h:classification='mapping_only_display_entry_unresolved'
 elif all(x['native_operation']=='OM_SpecifyPrefetchCommand'for x in h):classification='prefetch_only_native_widget_display_unresolved'
 elif gid==492:classification='prefetch_and_guarded_unlock_registration'
 rows.append(dict(game=game,group_id=gid,title=cat[gid]['title'],classification=classification,script_hits=h,runtime_status='still_unverified'))
assert len(rows)==44 and len({(r['game'],r['group_id'])for r in rows})==44
assert sum(bool(hits[i])for _,i in pending[:40])==38
assert {r['group_id']for r in rows if r['classification']=='prefetch_only_native_widget_display_unresolved'}=={2946,2961,2971}
unlock=vms['pm','photonmelodies11.rio.002',1544311867]['commands']
assert unlock[0]['fields']['a']['text']=='PM_WPOPEN_'
assert unlock[6]['fields']['operation']['name']=='OM_AccessGetValue'
assert unlock[7]['fields']['operation']==66
assert unlock[19]['fields']['arguments'][1]['text']=='1'
result=dict(schema='photon-pending-script-routes-v1',date='2026-09-09',
 input_hashes={'tool':sha(Path(__file__).read_bytes()),'catalog':sha((E/'catalog.json').read_bytes()),'pending_groups':sha((E/'runtime-pending-groups.json').read_bytes()),'reference_census':sha((O/'program_reference_census.json').read_bytes()),'full_crsa_census':sha((O/c['full_crsa_census']['evidence']).read_bytes()),'mapping_report':sha((O/'official_reference_mapping_replay.json').read_bytes()),'chapter_indexes':chapter_hashes},
 scope=dict(pending_crip008_bindings=40,pm_load_only_bindings=4,archive_verified_script_owners=len(proofs),known_crsa_census_records=len(full['rows']),script_referenced_crip008=38,mapping_only_crip008=2,prefetch_only_pm=3,guarded_unlock_pm=1),
 owners=proofs,verified_owner_calls=edges,mapping_checks=map_proofs,rows=rows,story_scenarios=scenarios,
 limitations=['Source-archive script analysis; does not execute the VM or game and does not validate installed script overlay branch equivalence.',
 'A reference, argument or registration is not a successful decode or draw. All 44 retain unverified runtime status.',
 'The CRsa census excludes other script/container formats. Missing direct references do not prove unused resources.',
 'Four story segments cover static references, not a guaranteed minimum number of gameplay actions or all language/input branches.',
 'The 40 exact-length offline replays passed. Additional caller padding remains unobserved; this is not a list of 40 known defects.'],game_writes=0,game_processes_started=0,computer_use=False)
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
print(result['scope'],flush=True)
