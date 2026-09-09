"""Select expensive CI checks conservatively; Linux validation always runs."""
import json
import os
from pathlib import Path
import re
import subprocess


def classify(paths):
    windows = runtime = False
    for path in paths:
        # These are review data, not build inputs. Their contracts are tested on Linux.
        data = (
            (path.startswith(('AGE2/games/', 'rUGP/games/')) and '/translations/' in path)
            or path.startswith(('AGE2/evidence/translations/', 'localization/glossaries/',
                                'localization/references/', 'localization/reviews/',
                                'localization/paratranz/'))
        ) and Path(path).suffix in ('.csv', '.tsv', '.json')
        if data or path.endswith('.md'):
            continue
        # AGE2/localization Python cannot change the Photon DLL; still test on Windows.
        if path.startswith(('AGE2/', 'localization/')) and Path(path).suffix in ('.py', '.txt'):
            windows = True
            continue
        # Unknown files, workflows, runtime headers, image manifests and dependencies
        # all retain full checks. A rename is reported as both old and new paths.
        windows = runtime = True
    return {'windows': windows, 'runtime': runtime}


def main():
    base = os.environ.get('QUALITY_BASE', '')
    if not re.fullmatch(r'[0-9a-f]{40}', base) or set(base) == {'0'}:
        result = {'windows': True, 'runtime': True}
    else:
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', base], check=True)
        changed = subprocess.check_output(['git', 'diff', '--no-renames', '--name-only', '-z', base, 'HEAD'])
        result = classify(changed.decode('utf8').strip('\0').split('\0') if changed else [])
    print(json.dumps(result))
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf8') as stream:
        for key, value in result.items():
            stream.write(f'{key}={str(value).lower()}\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf8') as stream:
        stream.write(f"Linux validates all text/data contracts. Additional checks: {json.dumps(result)}\n")


if __name__ == '__main__':
    main()
