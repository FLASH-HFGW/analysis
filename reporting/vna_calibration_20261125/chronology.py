"""Build the archival appendix from saved fits and acquisition epochs."""
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from math import log10
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROME = "if_filename_is_Europe_Rome"
UTC = "if_filename_is_UTC"
MODES = ("TM010", "TM011", "TM012")
HISTORICAL = "pre-cutoff context only"


def stamp(value):
    return datetime.fromisoformat(value).timestamp()


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")


def compact(value):
    return value.replace("T", " ").replace("+00:00", "")


def stage_appendix(here, work, reference, snapshot):
    timeline = work / "cavity-characterization-timeline-20261125/cavity_timeline.json"
    doc = json.loads(timeline.read_text())
    fits = doc["fitted_triplets"]
    extension = work / "vna-fit-extension-20261125/figures"
    logbook = here / "acquisition_snapshot.json"
    lookup = {r["id"]: r for r in fits}
    assert len(lookup) == len(fits) == 41
    original = json.loads((reference / "fit_details.json").read_text())
    for fit in fits:
        if fit["fit_source"] == "extension offline fit":
            path = extension / (fit["id"] + ".png")
        else:
            hashes = set(fit["sha256"].values())
            match, = [r for r in original
                      if hashes == {entry["sha256"] for entry in r["files"].values()}]
            record = match["summary"]
            path = reference / "figures" / f"{record['run']}_{record['mode']}.png"
            assert record["f0_hz"] == fit["parameters"]["f0_hz"]
        name = f"fit-{fit['id']}.png"
        shutil.copyfile(path, here / "figures" / name)
        snapshot["provenance"][name] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    snapshot["provenance"]["acquisition_snapshot.json"] = dict(
        path=logbook.name, sha256=hashlib.sha256(logbook.read_bytes()).hexdigest())
    snapshot["appendix"] = dict(fits=fits, conditional_intervals=doc["conditional_intervals"])


def build_table(appendix, logbook):
    fits = appendix["fits"]
    runs = logbook["rows"]
    measured = defaultdict(dict)
    for fit in fits:
        for zone in (ROME, UTC):
            effective_zone = ROME if fit["measurement_clock"] == "VERIFIED_EUROPE_ROME" else zone
            measured[fit["mode"], zone][fit["id"]] = tuple(map(stamp, fit["sweep_windows_utc"][effective_zone]))
    coverage = {}
    overlaps = {}
    for (mode, zone), windows in measured.items():
        ordered = sorted(windows, key=lambda key: windows[key])
        for index, key in enumerate(ordered):
            _, end = windows[key]
            next_key = ordered[index+1] if index+1 < len(ordered) else None
            stop = windows[next_key][0] if next_key else None
            contained = [r for r in runs if r["start_epoch"] >= end and
                         (stop is None or r["end_epoch"] < stop)]
            excluded = [r["run"] for r in runs if (
                r["start_epoch"] < end <= r["end_epoch"] or (
                    stop is not None and r["start_epoch"] < stop <= r["end_epoch"]))]
            coverage[key, zone] = dict(
                first=contained[0] if contained else None,
                last=contained[-1] if contained else None,
                count=len(contained), run_ids=[r["run"] for r in contained], excluded_overlap=excluded,
                next_fit=next_key, next_sweep_start_utc=iso(stop) if stop is not None else None,
                right_censored=stop is None)
            overlaps[key, zone] = bool(stop is not None and stop <= end)
    refs = {mode: min((f for f in fits if f["mode"] == mode and f["scope"] != HISTORICAL),
                      key=lambda f: f["display_time_utc"]) for mode in MODES}
    table = []
    for fit in sorted(fits, key=lambda f: (f["display_time_utc"], f["mode"], f["id"])):
        key, mode = fit["id"], fit["mode"]
        p = fit["parameters"]
        support = [span for span in appendix["conditional_intervals"] if span["fit_id"] == key]
        table.append(dict(fit_id=key, mode=mode, scope="Historical reference" if fit["scope"] == HISTORICAL else "In scope",
                          clock=fit["measurement_clock"], sweep_windows_utc=fit["sweep_windows_utc"],
                          trace_files=fit["files"], trace_sha256=fit["sha256"],
                          f0_MHz=p["f0_hz"]/1e6, loaded_Q=p["Q_loaded"],
                          reference_fit=refs[mode]["id"],
                          delta_f0_MHz=(p["f0_hz"]-refs[mode]["parameters"]["f0_hz"])/1e6,
                          fitted_Abs21_dB=20*log10(p["Abs21"]), chi2_ndof=p["chi2_ndof"],
                          accurate_covariance=fit["accurate_covariance"], quality_flags=fit["fit_quality_flags"],
                          candidate_windows={zone: coverage[key, zone] for zone in (ROME, UTC)},
                          overlapping_sweep_hypotheses=[zone for zone in (ROME, UTC) if overlaps[key, zone]],
                          evidence_supported_intervals=support,
                          scientific_status="Conditional" if support else "Ambiguous or unassigned",
                          operational_selection="Unverified", physical_applicability="Unverified"))
    return table


def write_table(table, output):
    with (output / "chronological_calibrations.json").open("w") as stream:
        json.dump(table, stream, indent=2)
        stream.write("\n")
    flat = []
    for record in table:
        row = {k: v if isinstance(v, (str, int, float, bool)) else json.dumps(v, sort_keys=True)
               for k,v in record.items() if k != "candidate_windows"}
        for label, zone in (("rome", ROME), ("alternate", UTC)):
            coverage = record["candidate_windows"][zone]
            for boundary in ("first", "last"):
                run = coverage[boundary]
                row[f"{label}_{boundary}_run"] = run["run"] if run else ""
                for field in ("start", "end"):
                    row[f"{label}_{boundary}_{field}_utc"] = iso(run[f"{field}_epoch"]) if run else ""
            for field in ("count", "next_fit", "next_sweep_start_utc", "right_censored"):
                row[f"{label}_{field}"] = coverage[field]
            row[f"{label}_crossing_runs"] = json.dumps(coverage["excluded_overlap"])
        flat.append(row)
    with (output / "chronological_calibrations.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(flat)


def plot_timelines(appendix, assets):
    for field, divisor, filename, label in (
            ("f0_hz", 1e9, "resonance_frequency.png", "Fitted resonance (GHz)"),
            ("Q_loaded", 1, "loaded_q.png", "Fitted loaded Q")):
        fig, axes = plt.subplots(3, 1, figsize=(13, 6), sharex=True, layout="constrained")
        for ax, mode in zip(axes, MODES):
            for fit in appendix["fits"]:
                if fit["mode"] != mode or fit["scope"] == HISTORICAL:
                    continue
                y = fit["parameters"][field] / divisor
                t = datetime.fromisoformat(fit["display_time_utc"])
                verified = fit["measurement_clock"] == "VERIFIED_EUROPE_ROME"
                if fit["fit_quality_flags"]:
                    ax.scatter(t, y, s=28, marker="x", c="#a44526")
                else:
                    ax.scatter(t, y, s=26, edgecolors="#235780",
                               facecolors="#235780" if verified else "none")
                for span in appendix["conditional_intervals"]:
                    if span["fit_id"] == fit["id"]:
                        ax.hlines(y, datetime.fromisoformat(span["first_BOR_utc"]),
                                  datetime.fromisoformat(span["last_EOR_utc"]), color="#37885a", lw=2.8)
            ax.set_ylabel(f"{mode}\n{label}")
            ax.ticklabel_format(axis="y", useOffset=False)
            ax.grid(alpha=.2)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b", tz=timezone.utc))
        axes[-1].set_xlabel("Calibration time (UTC under Europe/Rome filename interpretation)")
        fig.suptitle("Open circles: inferred clock   ×: fit-quality flag   Green: conditional acquisition coverage")
        fig.savefig(assets / filename, dpi=145)
        plt.close(fig)


def append_slides(deck, table, assets):
    def page(title, subtitle, source, notes=""):
        slide = deck.new(title, subtitle, source, notes)
        slide["footer"] = "FLASH / QUAX  |  CHRONOLOGICAL APPENDIX"
        return slide

    for index in range(0, len(table), 4):
        items = table[index:index+4]
        slide = page(f"Chronological calibration table | {index+1:02d}–{index+len(items):02d}",
                     "Candidate intervals use UTC acquisition epochs and the Europe/Rome trace-clock interpretation.",
                     "Source: FLASH-logbook / log; chronology and alternate clock windows in the companion CSV")
        for offset, r in enumerate(items):
            y = 1.62 + offset*1.19
            window = r["candidate_windows"][ROME]
            deck.rect(slide,.64,y,12.0,1.10,"#FFFFFF" if offset%2==0 else "#EDF1F6")
            title = (f'{r["mode"]}  |  {r["fit_id"]}  |  '
                     f'{compact(r["sweep_windows_utc"][ROME][0])} UTC'
                     + ("  |  HISTORICAL REFERENCE" if r["scope"] == "Historical reference" else ""))
            deck.text(slide,.80,y+.08,11.55,.30,title,14,True)
            if window["first"]:
                a,b = window["first"],window["last"]
                bounds = (f'Runs {a["run"]}–{b["run"]}  •  first start {compact(iso(a["start_epoch"]))}'
                          f'  •  last end {compact(iso(b["end_epoch"]))} UTC')
                if window["right_censored"]:
                    bounds += "  •  logbook cutoff"
            else:
                bounds = "No complete acquisition lies inside this chronological window."
            deck.text(slide,.80,y+.40,11.55,.28,bounds,12)
            alternate = r["candidate_windows"][UTC]
            clock = "verified Rome clock" if r["clock"].startswith("VERIFIED") else "inferred Rome clock"
            if window["run_ids"] != alternate["run_ids"]:
                clock += "; alternate window in CSV"
            metric = (f'f₀ {r["f0_MHz"]:.6f} MHz  |  QL {r["loaded_Q"]:,.0f}  |  '
                      f'Abs21 {r["fitted_Abs21_dB"]:+.2f} dB  |  {clock}  |  {r["scientific_status"]}')
            deck.text(slide,.80,y+.72,11.55,.27,metric,12)
    for index, r in enumerate(table, 1):
        scope = r["scope"]
        time = compact(r["sweep_windows_utc"][ROME][0])
        slide = page(f'Scattering fit {index:02d} / 41  |  {r["mode"]}',
                     f'{time} UTC  •  {scope}  •  {r["fit_id"]}',
                     "Source: original fitted S12/S21/S22 input files; bottom plot row is fractional magnitude residual")
        deck.image(slide,.55,1.53,8.15,4.96,assets/f'fit-{r["fit_id"]}.png')
        deck.text(slide,8.66,1.69,3.89,.68,
                  f'f₀  {r["f0_MHz"]:.6f} MHz\nQL  {r["loaded_Q"]:,.0f}',16,True)
        deck.text(slide,8.66,2.40,3.89,.65,
                  f'20 log₁₀(Abs21)  {r["fitted_Abs21_dB"]:+.2f} dB\nχ²/ndof  {r["chi2_ndof"]:.2f}',13)
        window = r["candidate_windows"][ROME]
        candidate = (f'{window["first"]["run"]}–{window["last"]["run"]}' if window["first"] else "No complete run")
        support = ", ".join(f'{s["first_run"]}–{s["last_run"]}' for s in r["evidence_supported_intervals"])
        deck.text(slide,8.66,3.13,3.89,.60,
                  f'Chronological candidate: {candidate}\nConditional: {support or "unassigned"}',12)
        flags = ["Inaccurate covariance"] + [
            "Large fractional residuals" if x.startswith("Large") else "Starting-value instability"
            for x in r["quality_flags"]]
        deck.text(slide,8.66,3.82,3.89,.79,"\n".join(flags),13,True,"#A44526")
        deck.text(slide,8.66,4.72,3.89,1.22,"\n".join(r["trace_files"].values()),10)
        deck.text(slide,8.66,6.10,3.89,.42,
                  "Clock verified" if r["clock"].startswith("VERIFIED") else "Europe/Rome clock inferred",11)
        deck.text(slide,.62,6.56,11.6,.25,
                  "Measured and fitted magnitudes; phase is diagnostic. Acquisition selection and applicability remain unverified.",11)
