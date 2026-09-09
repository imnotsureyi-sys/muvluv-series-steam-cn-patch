from pathlib import Path
import json,hashlib,shutil,subprocess,sys,os,argparse
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from rUGP.packaging.build_photon_cn_beta01 import make_patch,sha256,sha256_range,artifact
parser=argparse.ArgumentParser(description='Exercise the Windows player installer with synthetic files only.')
parser.add_argument('--output',type=Path,required=True)
OUT=parser.parse_args().output.resolve();OUT.mkdir(parents=True,exist_ok=False)
PS=Path('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
def put(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
def doc(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def digest(b):return hashlib.sha256(b).hexdigest().upper()
def snapshot(root):return {str(p.relative_to(root)):digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
def run(package,action,root,sessions,expect=0):
    command=[str(PS),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(package/'Install-PhotonCN.ps1'),'-Action',action,'-GameRoot',str(root)]
    if action=='Install':command+=['-Apply']
    env=dict(os.environ,PSModulePath='C:/Windows/System32/WindowsPowerShell/v1.0/Modules;C:/Program Files/WindowsPowerShell/Modules')
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf8',errors='replace',env=env)
    (OUT/(str(len(list(OUT.glob('*.log'))))+'-'+action+'.log')).write_text(result.stdout,encoding='utf8')
    if result.returncode!=expect:raise AssertionError(result.stdout)
    return result.stdout
def reseal(package):
    doc(package/'package_seal.20260910.json',dict(package_id='fixture-PF',status='PASS',manifest=artifact(package/'package_manifest.20260910.json',package),installer=artifact(package/'Install-PhotonCN.ps1',package)))
def fixture(name,old=False):
    home=OUT/name;game=home/'steamapps/common/Fixture PF';game.mkdir(parents=True)
    clean=bytes(200000);previous=bytearray(clean);previous[90000:90003]=b'OLD';final=bytearray(clean);final[100:103]=b'NEW'
    put(home/'clean.rio',clean);put(home/'old.rio',bytes(previous));put(home/'final.rio',bytes(final))
    put(game/'fixture.rio',bytes(previous) if old else clean);put(game/'Fixture.exe',b'exe-original')
    if old:put(game/'PhotonR2Assets/old.txt',b'original-user-asset')
    acf='"AppState" { "appid" "889700" "name" "Muv-Luv photonmelodies♬" "UserConfig" { "language" "english" } "MountedConfig" { "language" "english" } }'
    put(home/'steamapps/appmanifest_889700.acf',acf.encode())
    package=home/'package';package.mkdir()
    delta=make_patch(home/'clean.rio',home/'final.rio',package/'patches/archive.bin','fixture',additional_bases=(home/'old.rio',))
    delta['patch']['path']='patches/archive.bin'
    variants=[]
    for p in [home/'clean.rio',home/'old.rio']:
        variants.append(dict(bytes=p.stat().st_size,sha256=sha256(p),ranges=[dict(length=s['before_length'],sha256=sha256_range(p,s['offset'],s['before_length'])) for s in delta['segments']]))
    archive=dict(target='fixture.rio',before=dict(bytes=len(clean),sha256=digest(clean)),after=dict(bytes=len(final),sha256=digest(final)),accepted_bases=variants,**delta)
    files=[]
    for target,value,category in [('Fixture.exe',b'exe-translated','fixed'),('Runtime.dll',b'new-runtime','fixed'),('PhotonR2Assets/new.txt',b'new-image','asset')]:
        p=package/'files'/target;put(p,value)
        before=dict(exists=True,sha256=digest(b'exe-original'),bytes=12) if target=='Fixture.exe' else dict(exists=False)
        files.append(dict(target=target,category=category,before=before,accepted_bases=[before],payload=artifact(p,package)))
    manifest=dict(status='PASS_FULL_CLEAN_20260910_PACKAGE_SEALED',package_id='fixture-PF',game='PF',game_title='Fixture PF',exe='Fixture.exe',process_name='PhotonInstallerTestProcessNeverRunning',install_directory='Fixture PF',appid='889700',asset_root='PhotonR2Assets',archives=[archive],files=files,counts=dict(package_payload_files=4,patch_bytes=delta['patch']['bytes'],final_files=3,asset_files=1))
    doc(package/'package_manifest.20260910.json',manifest)
    shutil.copyfile(ROOT/'rUGP/packaging/windows/Install-PhotonCN.ps1',package/'Install-PhotonCN.ps1');reseal(package)
    return package,game,home/'sessions'
passed=[]
for old in (False,True):
    package,game,sessions=fixture('upgrade' if old else 'clean',old)
    before=snapshot(game)
    run(package,'VerifyPackage',game,sessions)
    run(package,'Install',game,sessions)
    installed=snapshot(game);assert (game/'Runtime.dll').is_file()
    if old:assert (game/'PhotonR2Assets/old.txt').read_bytes()==b'original-user-asset'
    run(package,'Install',game,sessions);assert snapshot(game)==installed
    assert not sessions.exists()
    assert set(installed)==set(before)|{'Runtime.dll','PhotonR2Assets\\new.txt'}
    passed.append('upgrade' if old else 'clean')

# A failure after an actual archive write must disclose the selected no-backup
# policy and leave that write in place; it must not create a hidden rollback.
package,game,sessions=fixture('write-failure')
installer=package/'Install-PhotonCN.ps1'
source=installer.read_text(encoding='utf-8-sig')
assert source.count('    Install-PackageFiles $manifest $root')==1
installer.write_text(source.replace('    Install-PackageFiles $manifest $root',"    throw 'synthetic write failure'"),encoding='utf-8-sig')
reseal(package)
before=snapshot(game)
message=run(package,'Install',game,sessions,expect=1)
assert '不备份或回滚' in message and 'Steam' in message
assert (game/'fixture.rio').read_bytes()==(game.parents[2]/'final.rio').read_bytes()
assert (game/'Fixture.exe').read_bytes()==b'exe-original'
assert set(snapshot(game))==set(before) and not sessions.exists()
passed.append('write-failure-no-backup')
for failure in ('unknown-base','bad-payload','wrong-language','duplicate-language','wrong-appid','malformed-manifest'):
    package,game,sessions=fixture(failure)
    if failure=='unknown-base':
        with (game/'fixture.rio').open('r+b') as f:f.seek(1);f.write(b'X')
    elif failure=='bad-payload':put(package/'files/Runtime.dll',b'damaged')
    elif failure=='wrong-language':
        acf=game.parents[1]/'appmanifest_889700.acf';acf.write_text(acf.read_text(encoding='utf8').replace('english','japanese'),encoding='utf8')
    elif failure=='duplicate-language':
        acf=game.parents[1]/'appmanifest_889700.acf';acf.write_text(acf.read_text(encoding='utf8').replace('"language" "english"','"language" "english" "Language" "english"',1),encoding='utf8')
    elif failure=='wrong-appid':
        acf=game.parents[1]/'appmanifest_889700.acf';acf.write_text(acf.read_text(encoding='utf8').replace('889700','889710'),encoding='utf8')
    else:
        acf=game.parents[1]/'appmanifest_889700.acf';acf.write_text(acf.read_text(encoding='utf8')[:-1],encoding='utf8')
    before=snapshot(game);run(package,'Install',game,sessions,expect=1);assert snapshot(game)==before
    passed.append(failure)
doc(OUT/'results.json',dict(passed=passed,status='PASS'))
print('PASS',passed)
