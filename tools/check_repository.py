#!/usr/bin/env python3
"""Check that the Git index contains software, not generated campaign files."""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
GENERATED_SUFFIXES = {'.npz', '.npy', '.h5', '.hdf5', '.root', '.csv', '.tsv',
                      '.png', '.jpg', '.jpeg', '.pdf', '.pptx', '.zip', '.tar',
                      '.sqlite', '.db', '.log', '.stdout', '.stderr'}
SOURCE_LOCKS = {'poetry.lock', 'uv.lock', 'Pipfile.lock'}


def reason(path):
    if any(part.startswith('job_to_submit') or part in ('results', 'logs', 'noise_relaunch_staging')
           for part in path.parts):
        return 'generated output or runtime directory'
    if path.suffix.lower() in GENERATED_SUFFIXES or '.sqlite-' in path.name or '.mid' in path.suffixes:
        return 'data, rendered report or runtime artifact'
    if path.suffix == '.lock' and path.name not in SOURCE_LOCKS:
        return 'runtime lock'
    if path.name.startswith(('stdout-', 'stderr-', 'job_state')):
        return 'per-job runtime state'
    if path.suffix == '.json' and not (
            path.parts[0] == 'config' or 'fixtures' in path.parts
            or path.name in ('package.json', 'package-lock.json')):
        return 'JSON outside source configuration or synthetic test fixtures'
    return None


def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    errors = []
    checked = 0
    for name in filter(None, paths):
        path = Path(name)
        checked += 1
        problem = reason(path)
        if problem:
            errors.append(f'{name}: {problem}')
        if path.suffix == '.ipynb':
            # Inspect staged notebook contents, not a possibly different working copy.
            result = subprocess.run(['git', 'show', ':' + name], cwd=ROOT, capture_output=True, check=True)
            notebook = json.loads(result.stdout)
            if any(cell.get('outputs') or cell.get('execution_count') is not None
                   for cell in notebook.get('cells', []) if cell.get('cell_type') == 'code'):
                errors.append(f'{name}: notebook contains saved execution output')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f'OK: {checked} files in the Git index; no generated data or job state')


if __name__ == '__main__':
    main()
