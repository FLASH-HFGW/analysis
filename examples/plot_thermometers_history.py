#!/usr/bin/env python3
"""Plot the cavity and mixing-chamber temperatures from an extracted CSV."""

import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

DEFAULT_INPUT = Path('/home/mazzitel/HFGW/analysis-runtime/autoreco/Run2/'
                     'thermometers/thermometers_00680_00939.csv')
SENSORS = ((15, 'Dale1.5K Cavità T [mK]'),
           (16, 'CMN143 MC T [mK]'), (17, 'CMN130 MC T [mK]'))


def load_history(path, run_range=None):
    if not path.is_file():
        raise ValueError(f'CSV non disponibile: {path}. Attendere l’esportazione o specificare il percorso del CSV.')
    schema_path = path.with_suffix('.schema.json')
    if not schema_path.is_file():
        raise ValueError(f'Schema non disponibile: {schema_path}. Usare il CSV con il relativo .schema.json.')
    metadata = json.loads(schema_path.read_text())
    mappings = {}
    for identifier, schema in metadata['schemas'].items():
        if schema['equipment'].casefold() != 'temp_avs':
            continue
        if not schema.get('documented_layout_length_matches'):
            raise ValueError(f'Schema AVS {identifier}: disposizione dei canali non verificata')
        selected = []
        for index, label in SENSORS:
            channels = [c for c in schema['channels'] if c['index'] == index]
            if len(channels) != 1 or channels[0]['unit'].strip().casefold() != 'mk':
                raise ValueError(f'Schema AVS {identifier}: canale {index} assente o unità diversa da mK')
            selected.append(channels[0]['column'])
        mappings[identifier] = selected
    if not mappings:
        raise ValueError('Nessuno schema Temp_AVS disponibile')
    series = [[] for _ in SENSORS]
    skipped = 0
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'schema_id', 'time_unix', 'run', 'source_status'}
        required.update(column for columns in mappings.values() for column in columns)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'Colonne mancanti: {sorted(missing)}')
        for row in reader:
            columns = mappings.get(row['schema_id'])
            if columns is None:
                continue
            if run_range and not run_range[0] <= int(row['run']) <= run_range[1]:
                continue
            if row['source_status'] != 'complete':
                skipped += 1
                continue
            timestamp = float(row['time_unix'])
            if not math.isfinite(timestamp):
                raise ValueError('Timestamp non finito nel CSV')
            for points, column in zip(series, columns):
                value = float(row[column]) if row[column] else float('nan')
                points.append((timestamp, value))
    for points, (_, label) in zip(series, SENSORS):
        points.sort(key=lambda point: point[0])
        if not any(math.isfinite(value) for _, value in points):
            raise ValueError(f'Nessun campione finito per {label}')
    return series, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, help='PNG o PDF; default: accanto al CSV')
    parser.add_argument('--timezone', default='Europe/Rome', help='Fuso asse temporale (default: Europe/Rome)')
    parser.add_argument('--run-range', nargs=2, type=int, metavar=('START', 'END'))
    parser.add_argument('--gap-seconds', type=float, default=300,
                        help='Interrompe le linee con intervalli maggiori (default: 300 s)')
    args = parser.parse_args()
    if args.gap_seconds <= 0 or not math.isfinite(args.gap_seconds):
        parser.error('--gap-seconds deve essere positivo e finito')
    if args.run_range and args.run_range[0] > args.run_range[1]:
        parser.error('Intervallo run invertito')
    try:
        tz = ZoneInfo(args.timezone)
        series, skipped = load_history(args.input, args.run_range)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 1, sharex=True, figsize=(14, 9), constrained_layout=True)
        for axis, points, (_, label), color in zip(axes, series, SENSORS, ('C0', 'C1', 'C2')):
            times, values = [], []
            previous = None
            for timestamp, value in points:
                instant = datetime.fromtimestamp(timestamp, timezone.utc)
                if previous is not None and timestamp - previous > args.gap_seconds:
                    times.append(instant)
                    values.append(float('nan'))
                times.append(instant)
                values.append(value if math.isfinite(value) else float('nan'))
                previous = timestamp
            axis.plot(times, values, color=color, linewidth=0.8, marker='.', markersize=2)
            axis.set_title(label, loc='left')
            axis.set_ylabel('T [mK]')
            axis.grid(alpha=0.3)
            print(f'{label}: {sum(math.isfinite(v) for _, v in points)} campioni finiti')
        locator = mdates.AutoDateLocator(tz=tz)
        axes[-1].xaxis.set_major_locator(locator)
        axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=tz))
        axes[-1].set_xlabel(f'Tempo ({args.timezone})')
        fig.suptitle('Storia temporale delle temperature')
        output = args.output or args.input.with_name(args.input.stem + '_history.png')
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=180)
        plt.close(fig)
        print(f'Grafico: {output}')
        if skipped:
            print(f'Escluse {skipped} bank da input non completi', file=sys.stderr)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        parser.exit(1, f'Errore: {exc}\n')


if __name__ == '__main__':
    main()
