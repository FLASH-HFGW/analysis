#!/usr/bin/env python3
"""Sequential, resumable campaign runner; completed products are never overwritten."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs', type=Path, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    runs = sorted({int(line.split('#')[0].strip()) for line in a.runs.read_text().splitlines()
                   if line.split('#')[0].strip()})
    a.output.mkdir(parents=True, exist_ok=True)
    source = a.output/'analyze_iq_filtered_bands.py'
    current = Path(__file__).with_name(source.name)
    if source.exists() and source.read_bytes() != current.read_bytes():
        p.error('Campaign source differs from current source; use a new output directory')
    if not source.exists():
        shutil.copyfile(current, source)
    missing = [r for r in runs if not (a.input/f'run{r:05d}.mid.gz').is_file()]
    if missing:
        p.error(f'Missing input runs: {missing}')
    for run in runs:
        final = a.output/f'run{run:05d}'
        if (final/'summary.json').exists():
            if not json.loads((final/'summary.json').read_text())['reached_eof']:
                raise ValueError(f'Incomplete final output {final}')
            continue
        pending = a.output/f'run{run:05d}.pending'
        print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} starting run {run}', flush=True)
        with (a.output/f'run{run:05d}.log').open('a') as log:
            subprocess.run([sys.executable,str(source),str(a.input/f'run{run:05d}.mid.gz'),
                            '--output',str(pending)],stdout=log,stderr=subprocess.STDOUT,check=True)
        if not json.loads((pending/'summary.json').read_text())['reached_eof']:
            raise ValueError(f'Run {run} did not reach EOF')
        pending.rename(final)
        print(f'completed run {run}',flush=True)
    (a.output/'COMPLETE.json').write_text(json.dumps({'runs':runs},indent=2)+'\n')


if __name__ == '__main__':
    main()
