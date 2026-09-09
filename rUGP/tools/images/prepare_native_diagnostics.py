"""Build PF/PM diagnostic DLLs locally; never install or start a game.

Diagnostics are separate from approved normal releases. This compiles existing
trace instrumentation and checks determinism; it is not runtime acceptance.
"""
import argparse
import json
from pathlib import Path
import subprocess

from rUGP.runtime import build as runtime_build
from rUGP.tools.images.replay_crip008_routes import runtime_identity, sha


def run(zig: Path, output: Path) -> dict:
    zig, output = zig.resolve(strict=True), output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    sources=runtime_identity()
    report=dict(runtime_sources=sources,compiler_sha256=sha(zig.read_bytes()),games={},
                diagnostic_only=True,installed=False,game_started=False,game_files_modified=False,
                trace_event_limit_per_process=8192)
    for game in ('pf','pm'):
        root=output/game
        root.mkdir()
        runtime_build.prepare_generated(root/'generated',True)
        hashes=[]
        for number in (1,2):
            part=root/str(number)
            part.mkdir()
            dll=part/'Ages3ResT.dll'
            command=runtime_build._compile_command(zig=str(zig),game=game,generated=str(root/'generated'),
                output=str(dll),authorized=True,portable_paths=False,speaker_color_candidate=True)
            command.insert(2,'-DPHOTON_V6_NATIVE_DIAGNOSTIC_TRACE=1')
            completed=subprocess.run(command,cwd=runtime_build.ROOT,capture_output=True,text=True,timeout=180)
            (part/'compile.log').write_text(completed.stdout+completed.stderr,'utf-8')
            if completed.returncode:
                raise RuntimeError(f'{game} diagnostic build failed: {completed.stderr[-3000:]}')
            dll.write_bytes(runtime_build.normalize_pe_reproducibility_fields(dll.read_bytes()))
            hashes.append(sha(dll.read_bytes()))
        if hashes[0]!=hashes[1]:
            raise ValueError(f'{game} diagnostic build not deterministic')
        report['games'][game]=dict(sha256=hashes[0],double_build_equal=True)
    if runtime_identity()!=sources:
        raise ValueError('Runtime changed during diagnostic builds')
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zig',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.zig,args.output)
    print(json.dumps(report['games'],indent=2))


if __name__=='__main__':
    main()
