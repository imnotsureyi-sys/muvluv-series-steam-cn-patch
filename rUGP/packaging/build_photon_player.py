"""Package an independently assembled PF/PM snapshot for the player installer.

This does not select translations or approve a runtime. Input identities must
already be frozen in archive-final.json and the two runtime build reports.
"""
from pathlib import Path
import argparse,json,shutil
from rUGP.packaging.build_photon_cn_beta01 import (
    GAMES,make_patch,sha256,sha256_range,hash_virtual_apply,artifact,
    build_deterministic_zip,assert_no_absolute_paths,verify_file,
)

def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def build(assembled:Path,clean:Path,steam:Path,output:Path,legacy_pm:Path|None=None,legacy_pf:Path|None=None):
    frozen=json.loads((assembled/'archive-final.json').read_text(encoding='utf8'))
    for game in ('pf','pm'):
        meta=GAMES[game.upper()];live=steam/meta['title'];final=assembled/game
        legacy=legacy_pf if game=='pf' else legacy_pm
        package=output/game;package.mkdir(parents=True,exist_ok=False)
        archives=[]
        for row in frozen:
            if row['game']!=game:continue
            name=row['target'];before=clean/game/name;after=final/name
            for path,key in [(before,'clean'),(live/name,'live'),(after,'final')]:
                verify_file(path,row[key+'_bytes'],row[key+'_sha256'],key+' '+name)
            patch=package/'patches'/(name+'.bin')
            additional=(live/name,) if row['live_sha256']!=row['final_sha256'] else ()
            legacy_identity=None
            if legacy is not None:
                historical=legacy/name
                legacy_identity=dict(bytes=historical.stat().st_size,sha256=sha256(historical))
                if legacy_identity['sha256'] not in (row['live_sha256'],row['clean_sha256'],row['final_sha256']):additional+=(historical,)
            delta=make_patch(before,after,patch,game+'/'+name,additional_bases=additional)
            delta['patch']['path']=patch.relative_to(package).as_posix()
            accepted=[]
            bases=[(before,'clean',row['clean_bytes'],row['clean_sha256']),(live/name,'live',row['live_bytes'],row['live_sha256'])]
            if legacy_identity is not None:bases.append((legacy/name,'historical-group-base',legacy_identity['bytes'],legacy_identity['sha256']))
            for source,key,base_size,base_hash in bases:
                virtual=hash_virtual_apply(source,patch,delta['segments'],row['final_bytes'])
                if virtual!=row['final_sha256']:raise ValueError('delta does not cover '+key+' '+name)
                accepted.append(dict(bytes=base_size,sha256=base_hash,ranges=[dict(length=min(s['length'],max(0,base_size-s['offset'])),sha256=sha256_range(source,s['offset'],min(s['length'],max(0,base_size-s['offset'])))) for s in delta['segments']]))
            archives.append(dict(target=name,before=dict(bytes=row['clean_bytes'],sha256=row['clean_sha256']),after=dict(bytes=row['final_bytes'],sha256=row['final_sha256']),accepted_bases=accepted,**delta))
        files=[];stock={r[0]:r for r in meta['fixed']}
        for src in sorted(final.rglob('*')):
            if not src.is_file():continue
            name=src.relative_to(final).as_posix()
            if any(r['target']==name for r in archives):continue
            category='asset' if name.startswith('PhotonR2Assets/') else 'fixed'
            dest=package/'files'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
            baseline=stock.get(name);before={'exists':False}
            if baseline and baseline[1]:before=dict(exists=True,bytes=baseline[2],sha256=baseline[3])
            current=live/name
            previous=dict(exists=True,bytes=current.stat().st_size,sha256=sha256(current)) if current.is_file() else {'exists':False}
            accepted_files=[before,previous]
            if category=='fixed' and baseline:accepted_files.append(dict(exists=True,bytes=baseline[4],sha256=baseline[5]))
            if category=='fixed' and legacy is not None and (legacy/name).is_file():accepted_files.append(dict(exists=True,bytes=(legacy/name).stat().st_size,sha256=sha256(legacy/name)))
            files.append(dict(target=name,category=category,before=before,accepted_bases=accepted_files,payload=artifact(dest,package)))
        manifest=dict(schema='photon-player-package/v1',package_id='Photon-'+game.upper()+'-20260910',version='2026.09.10',status='PASS_FULL_CLEAN_20260910_PACKAGE_SEALED',game=game.upper(),game_title=meta['title'],process_name=meta['process'],install_directory=meta['title'],exe=meta['exe'],appid='889700' if game=='pf' else '889710',asset_root='PhotonR2Assets',archives=archives,files=files,counts=dict(package_payload_files=len(archives)+len(files),final_files=len(files),patch_bytes=sum(r['patch']['bytes'] for r in archives),asset_files=sum(r['category']=='asset' for r in files)))
        assert_no_absolute_paths(manifest)
        write_json(package/'package_manifest.20260910.json',manifest)
        installer=Path(__file__).parent/'windows/Install-PhotonCN.ps1'
        (package/'Install-PhotonCN.ps1').write_text(installer.read_text(encoding='utf-8-sig'),encoding='utf-8-sig',newline='\r\n')
        seal=dict(package_id=manifest['package_id'],status='PASS',manifest=artifact(package/'package_manifest.20260910.json',package),installer=artifact(package/'Install-PhotonCN.ps1',package))
        write_json(package/'package_seal.20260910.json',seal)
        print('PACKAGE',game,'files',len(files),'patch MiB',manifest['counts']['patch_bytes']/2**20,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('assembled','clean','steam','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--legacy-pm',type=Path);p.add_argument('--legacy-pf',type=Path)
    a=p.parse_args();build(a.assembled,a.clean,a.steam,a.output,a.legacy_pm,a.legacy_pf)
