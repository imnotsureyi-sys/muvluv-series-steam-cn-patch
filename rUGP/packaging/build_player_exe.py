"""Embed one verified player package in a standalone Windows GUI executable."""
from pathlib import Path
import argparse,json,subprocess
from rUGP.packaging import build_photon_cn_beta01 as archive_builder

def build(package:Path,output:Path,work:Path,csc:Path):
    package=package.resolve(strict=True);output=output.resolve();work=work.resolve()
    if output.exists():raise ValueError('executable already exists')
    work.mkdir(parents=True,exist_ok=False);output.parent.mkdir(parents=True,exist_ok=True)
    archive_builder.OUTPUT=package
    archive_builder.build_deterministic_zip(package,work/'payload.zip')
    source=Path(__file__).parent/'windows/PhotonInstaller.cs'
    lines=['/nologo','/target:winexe','/platform:anycpu','/optimize+',
           '/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.Web.Extensions.dll',
           '/r:System.IO.Compression.dll','/r:System.IO.Compression.FileSystem.dll',
           '/out:"'+str(output)+'"','/resource:"'+str(work/'payload.zip')+'",payload.zip',
           '"'+str(source.resolve())+'"']
    response=work/'compile.rsp';response.write_text('\n'.join(lines),encoding='utf-8-sig')
    result=subprocess.run([str(csc),'@'+str(response)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf8',errors='replace')
    (work/'compiler.log').write_text(result.stdout,encoding='utf8')
    if result.returncode:raise RuntimeError(result.stdout)
    report=dict(executable=output.name,bytes=output.stat().st_size,sha256=archive_builder.sha256(output),source_sha256=archive_builder.sha256(source),payload_sha256=archive_builder.sha256(work/'payload.zip'),manifest_sha256=archive_builder.sha256(package/'package_manifest.20260910.json'))
    (work/'build.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('package','output','work','csc'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();build(args.package,args.output,args.work,args.csc)
