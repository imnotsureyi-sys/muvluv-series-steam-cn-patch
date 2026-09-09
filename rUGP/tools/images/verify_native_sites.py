"""Check production native hook preconditions against local EXEs as inert data."""
import argparse
import json
from pathlib import Path
import subprocess

from rUGP.tools.images.replay_crip008_routes import compile_fixture, runtime_identity, sha


def run(exes: dict[str, Path], zig: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    sources = runtime_identity()
    results = {}
    for game, path in exes.items():
        before = sha(path.read_bytes())
        fixture = compile_fixture(zig, game, output, 'native_sites_offline.c')
        completed = subprocess.run([str(fixture), str(path)], capture_output=True, text=True, timeout=30)
        if completed.returncode not in (0, 1):
            raise RuntimeError(f'{game} site fixture failed: {completed.returncode} {completed.stderr}')
        result = json.loads(completed.stdout)
        if len(result['sites']) != 9 or len({s['rva'] for s in result['sites']}) != 9:
            raise ValueError('Incomplete native site matrix')
        if completed.returncode or not result['passed']:
            raise ValueError(f'{game} actual EXE does not satisfy pinned native hook preconditions: {result}')
        if sha(path.read_bytes()) != before:
            raise ValueError('EXE changed during inspection')
        results[game] = dict(exe_sha256=before, **result)
    if runtime_identity() != sources:
        raise ValueError('Runtime changed during inspection')
    report = dict(schema='photon-native-sites-offline-v1', runtime_sources=sources, games=results,
                  compiler_sha256=sha(zig.read_bytes()), game_files_modified=False,
                  selector_sites_exercised=True, assembly_wrapper_executed=True,
                  assembly_wrapper_scope='four decoder families, gate-off passthrough only',
                  original_decoder_synthetic=True)
    (output/'verification.json').write_text(json.dumps(report, indent=2)+'\n','utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('pf-exe','pm-exe','zig','output'):
        parser.add_argument('--'+field, required=True,type=Path)
    args=parser.parse_args()
    report=run({'PF':args.pf_exe,'PM':args.pm_exe},args.zig,args.output)
    print(json.dumps(report['games'],indent=2))


if __name__ == '__main__':
    main()
