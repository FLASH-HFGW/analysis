"""Build an incremental local index and report compatible Run3 spectra."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from iq_products import json_value, open_product, write_json


def extract(path):
    with open_product(path) as p:
        f = p.file
        configuration = {name: p.metadata.get(name) for name in
                         ("fs_hz", "iq_convention", "pairs_json", "bor_lo_json")}
        adc = json.loads(p.metadata["bor_settings_json"])
        configuration["ranges"] = adc.get("Channel_range_mV")
        coordinates = hashlib.sha256(p.edges.tobytes()).hexdigest()
        compatibility = json.dumps(dict(configuration, frequency_edges_sha256=coordinates), sort_keys=True)
        calibration = f.get("calibration")
        saved = None
        if calibration is not None:
            fields = json.loads(calibration.attrs["odb_fields_json"])["BOR"]
            saved = {key: value for key, value in fields.items() if isinstance(value, (str, int, float, bool))
                     and any(token in key.lower() for token in ("twpa", "pump", "freq_mode", "fit/result"))}
        quality = dict(f["quality"].attrs)
        info = dict(run=p.run, start=p.time_start, stop=p.time_stop, quality=quality, apparatus=saved,
                    schema=f.attrs["schema_version"], commit=p.metadata.get("software_commit"),
                    source=p.metadata.get("source"), compatibility=compatibility, modes={},
                    temperatures={name: dict(unit=unit, mean=np.mean(values[np.isfinite(values)])
                                  if np.any(np.isfinite(values)) else np.nan)
                                  for name, unit, _, values in p.temperatures()})
        spectra = {}
        for mode in p.modes:
            stats = dict(f[f"statistics/{mode}"].attrs)
            weights = len(p.windows)
            fine = p.spectra[mode]["mean_psd"][:]
            first = int(p.spectra.attrs["frequency_first_hz"])
            starts = np.rint(p.edges[:-1] - (first-.5)).astype(int)
            spectra[mode] = np.add.reduceat(fine, starts, dtype=np.float64) / p.widths
            info["modes"][mode] = dict(stats=stats, windows=weights,
                                       power=np.dot(spectra[mode], p.widths),
                                       anomalies=p.excursions(mode))
        return json_value(info), p.edges, spectra


def index_file(db, path):
    path = path.resolve()
    stat = path.stat()
    row = db.execute("SELECT size,mtime,document FROM products WHERE path=?", (str(path),)).fetchone()
    if row and row[:2] == (stat.st_size, stat.st_mtime_ns):
        return json.loads(row[2])
    info, edges, spectra = extract(path)
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
        checksum = digest.hexdigest()
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        raise ValueError(f"file changed during indexing: {path}")
    info.update(path=str(path), sha256=checksum)
    with db:
        db.execute("INSERT OR REPLACE INTO products VALUES (?,?,?,?)",
                   (str(path), stat.st_size, stat.st_mtime_ns, json.dumps(info)))
        db.execute("DELETE FROM spectra WHERE path=?", (str(path),))
        for mode, spectrum in spectra.items():
            db.execute("INSERT INTO spectra VALUES (?,?,?,?)",
                       (str(path), mode, edges.astype("<f8").tobytes(), spectrum.astype("<f8").tobytes()))
    return info


def correlation(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 12:
        return dict(n=len(pairs), r=None)
    x, y = np.asarray(pairs).T
    return dict(n=len(pairs), r=float(np.corrcoef(x, y)[0,1]) if x.std() and y.std() else None)


def pooled_statistics(entries):
    # Merge populations using total variance and covariance identities.
    data = [entry["stats"] for entry in entries if entry["stats"].get("temporal_samples", 0)]
    if not data:
        return {}
    weights = np.array([row["temporal_samples"] for row in data], dtype=float)
    def average(key):
        return float(np.average([row[key] for row in data], weights=weights))

    mi, mq = average("mean_I_V"), average("mean_Qhardware_V")
    di = np.array([row["mean_I_V"]-mi for row in data])
    dq = np.array([row["mean_Qhardware_V"]-mq for row in data])
    vi = average("var_I_V2") + np.average(di**2, weights=weights)
    vq = average("var_Q_V2") + np.average(dq**2, weights=weights)
    cov = average("cov_I_Qhardware_V2") + np.average(di*dq, weights=weights)
    return dict(samples=int(weights.sum()), mean_i_v=mi, mean_qhardware_v=mq,
                var_i_v2=vi, var_q_v2=vq, covariance_v2=cov,
                rms_v=np.sqrt(vi+vq+mi**2+mq**2), ac_rms_v=np.sqrt(vi+vq))


def report(db, rows, output):
    by_config = {}
    for row in rows:
        by_config.setdefault(row["compatibility"], []).append(row)
    results = []
    for index, (config, group) in enumerate(by_config.items()):
        group.sort(key=lambda row: (row["start"], row["run"]))
        exposure = 0.
        prev_stop = None
        gaps = []
        for row in group:
            row["exposure_s"] = row["quality"]["temporal_samples"] / json.loads(config)["fs_hz"]
            exposure += row["exposure_s"]
            if prev_stop is not None and row["start"] > prev_stop:
                gaps.append([prev_stop, row["start"]])
            prev_stop = max(prev_stop or row["stop"], row["stop"])
        modes = sorted(set.union(*(set(row["modes"]) for row in group)))
        fig, axes = plt.subplots(len(modes), 2, figsize=(12, 3*len(modes)), squeeze=False)
        mode_summary = {}
        for mode, (ax, sp) in zip(modes, axes):
            selected = [row for row in group if mode in row["modes"]]
            sums = None
            count = 0
            spectra = []
            for row in selected:
                array = row["modes"][mode]
                edge_bytes, data_bytes = db.execute(
                    "SELECT edges,psd FROM spectra WHERE path=? AND mode=?",
                    (row["path"], mode)).fetchone()
                edges = np.frombuffer(edge_bytes, dtype="<f8")
                psd = np.frombuffer(data_bytes, dtype="<f8")
                if sums is None:
                    sums = np.zeros_like(psd)
                sums += psd * array["windows"]
                count += array["windows"]
                spectra.append(psd)
            np.savez(output / f"group-{index}-{mode}.npz", edges_hz=edges, mean_psd=sums/count,
                     run_psd=np.stack(spectra), runs=[row["run"] for row in selected])
            data = [row["modes"][mode] for row in selected]
            ax.plot([row["run"] for row in selected], [x["stats"]["rms_V"] for x in data], ".-", label="total RMS")
            ax.plot([row["run"] for row in selected], [x["stats"]["ac_rms_V"] for x in data], ".-", label="AC RMS")
            ax.set(xlabel="Run", ylabel=f"{mode} (V)")
            ax.legend()
            sp.semilogy((edges[1:]+edges[:-1])/2, sums/count)
            sp.set(xlabel="Frequency (Hz)", ylabel="Exposure-weighted PSD (V²/Hz)")
            thresholds = sorted({key for entry in data for key in entry["anomalies"]})
            fs = json.loads(config)["fs_hz"]
            rates = {}
            for key in thresholds:
                observed = [entry["anomalies"][key] for entry in data if key in entry["anomalies"]]
                total = sum(o["observed_samples"] for o in observed)
                rates[key] = sum(o["episodes"] for o in observed) * fs / total if total else None
            sensors = sorted({name for row in selected for name in row["temperatures"]})
            mode_summary[mode] = dict(fft_windows=count, event_rate_per_second=rates,
                pooled_statistics=pooled_statistics(data),
                temperature_correlations={name: correlation(
                    [x["power"] for x in data],
                    [row["temperatures"].get(name, {}).get("mean") for row in selected])
                    for name in sensors})
        fig.tight_layout()
        fig.savefig(output / f"group-{index}.png", dpi=130)
        plt.close(fig)
        results.append(dict(configuration=json.loads(config), runs=group, modes=mode_summary,
                            exposure_s=exposure, gaps_header_unix=gaps,
                            mode_correlations={f"{a}/{b}": correlation(
                                [row["modes"].get(a, {}).get("power") for row in group],
                                [row["modes"].get(b, {}).get("power") for row in group])
                                for i, a in enumerate(modes) for b in modes[i+1:]}))
    write_json(output / "history.json", results)
    with (output / "runs.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["run", "start_unix_header", "mode", "rms_v", "ac_rms_v", "power_v2",
                         "var_i_v2", "var_q_v2"])
        for row in rows:
            for name, mode in row["modes"].items():
                stats = mode["stats"]
                writer.writerow([row["run"], row["start"], name, stats["rms_V"], stats["ac_rms_V"],
                                 mode["power"], stats["var_I_V2"], stats["var_Q_V2"]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-range", nargs=2, type=int)
    parser.add_argument("--time-range", nargs=2, help="ISO-8601; naive dates interpreted as UTC")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    paths = (item for path in args.paths for item in (sorted((*path.glob("run*_iq_v3.h5"), *path.glob("run*_iq_v3.root"), *path.glob("run*_iq_v3.1.root"))) if path.is_dir() else [path]))
    if args.time_range:
        dates = [datetime.fromisoformat(text) for text in args.time_range]
        time_range = [int((dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()) for dt in dates]
    else:
        time_range = None
    with sqlite3.connect(args.output / "index.sqlite") as db:
        db.executescript("CREATE TABLE IF NOT EXISTS products(path PRIMARY KEY,size,mtime,document);"
                         "CREATE TABLE IF NOT EXISTS spectra(path,mode,edges,psd,PRIMARY KEY(path,mode));")
        by_run = {}
        for path in paths:
            row = index_file(db, path)
            if args.run_range and not args.run_range[0] <= row["run"] <= args.run_range[1]:
                continue
            if time_range and not (row["start"] < time_range[1] and row["stop"] > time_range[0]):
                continue
            if row["run"] in by_run and by_run[row["run"]]["sha256"] != row["sha256"]:
                raise ValueError(f"multiple distinct products for run {row['run']}")
            by_run[row["run"]] = row
        report(db, list(by_run.values()), args.output)


if __name__ == "__main__":
    main()
