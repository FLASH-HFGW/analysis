"""Produce the FLASH/QUAX VNA slides from a compact validated analysis snapshot."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from slide_deck import Deck, export
from chronology import append_slides, build_table, plot_timelines, stage_appendix, write_table


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def stage(work, reference):
    """Verify summary totals against the source and bundle only deck inputs."""
    timeline = work / "cavity-characterization-timeline-20261125"
    validity = work / "vna-validity-intervals-20261125"
    phase = work / "calibration-phase-a-20261125"
    fit = work / "vna-fit-extension-20261125"
    pilot = work / "run1429-vna-pilot"
    doc = json.loads((timeline / "cavity_timeline.json").read_text())
    mapping = rows(timeline / "run_mode_characterizations.csv")
    counts = Counter(r["characterization_status"] for r in mapping)
    assert counts == {"CONDITIONAL": 324, "AMBIGUOUS": 276, "UNASSIGNED": 4752}
    assert len(mapping) == 5352 and len({r["run"] for r in mapping}) == 1784
    assert len(doc["fitted_triplets"]) == 41
    assert sum(int(r["count"]) > 1 for r in rows(validity / "recorded_configuration_intervals.csv")) == 27
    assert len(rows(fit / "fit_summary.csv")) == 32
    scope = json.loads((phase / "from-run680/scope.json").read_text())
    assert scope["files"]["included"] == 131 and scope["sets"] == 6 and scope["fits"] == 8
    assert not any(r["accurate_covariance"] for r in doc["fitted_triplets"])
    assert sum(r["measurement_clock"].startswith("VERIFIED") for r in doc["fitted_triplets"]) == 5
    assert all(r["operational_selection"] == "UNVERIFIED" for r in mapping)
    quality = []
    for mode in ("TM010", "TM011", "TM012"):
        all_fits = [r for r in doc["fitted_triplets"] if r["mode"] == mode]
        added = [r for r in all_fits if r["fit_source"] == "extension offline fit"]
        chi = [r["parameters"]["chi2_ndof"] for r in added]
        quality.append([mode, len(all_fits), len(added), sum(r["valid"] for r in added),
                        sum(r["accurate_covariance"] for r in all_fits),
                        f"{min(chi):.2f}–{max(chi):.2f}"])
    tm010 = [r for r in doc["fitted_triplets"] if r["mode"] == "TM010"]
    assert len(tm010) == 17 and all(r["fit_quality_flags"] for r in tm010)
    assert sum((r["seed_f0_spread_hz"] or 0) > 1000 for r in tm010) == 2
    spans = [(r["first_run"], r["last_run"]) for r in doc["conditional_intervals"]
             if r["mode"] == "TM012" and r["first_run"] != 680]
    assert spans == [(1148,1219), (1426,1428), (1429,1669)]
    change, = [r for r in doc["successive_changes"] if r["earlier_fit"] == "46764bdf344d1744"
               and r["later_fit"] == "19db7a371c6db01f"]
    assert round(change["delta_f0_hz"]/1e6, 3) == .780 and round(change["loaded_Q_change_pct"], 1) == 18.5
    comparison = json.loads((pilot / "evidence.json").read_text())["spectral_comparison"]
    assert comparison["common_rf_hz"] == [8846093000,8848093000]
    assert not comparison["known_line_in_common_band"]
    figures = {f"1429_{m}.png": reference / "figures" / f"1429_{m}.png"
               for m in ("TM010", "TM011", "TM012")}
    figures.update({f"{name}.png": timeline / f"{name}.png"
                    for name in ("resonance_frequency", "loaded_q")})
    figures["tm012-vna-versus-psd.png"] = pilot / "tm012-vna-versus-psd.png"
    validation_sources = {
        "phase_a_report": phase / "odb_calibration_audit.md",
        "timestamp_report": phase / "followup-run680/run680_timestamp_report.txt",
        "extension_report": fit / "REPORT.md",
        "validity_report": validity / "REPORT.md",
        "timeline_report": timeline / "REPORT.md",
        "pilot_report": pilot / "REPORT.md",
        "fit_validation_report": reference / "VALIDATION_REPORT.md",
        "timeline_data": timeline / "cavity_timeline.json",
        "run_mode_data": timeline / "run_mode_characterizations.csv",
        "configuration_intervals": validity / "recorded_configuration_intervals.csv",
        "pilot_evidence": pilot / "evidence.json",
    }
    assets = HERE / "figures"
    assets.mkdir(exist_ok=True)
    for name, source in figures.items():
        shutil.copyfile(source, assets / name)
    provenance = {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for name, path in (figures | validation_sources).items()}
    snapshot = dict(quality=quality, scope=scope, coverage=dict(counts), spans=spans,
                    change=change, comparison=comparison, provenance=provenance)
    stage_appendix(HERE, work, reference, snapshot)
    plot_timelines(snapshot["appendix"], assets)
    for name in ("resonance_frequency.png", "loaded_q.png"):
        source = provenance[name]
        provenance[f"original_{name}"] = dict(source)
        provenance[name] = dict(path="Regenerated from the saved cavity timeline; historical controls excluded",
                                sha256=hashlib.sha256((assets / name).read_bytes()).hexdigest())
    with (HERE / "source_snapshot.json").open("w") as stream:
        json.dump(snapshot, stream, indent=2)
        stream.write("\n")


def build(snapshot, chronological):
    deck = Deck()
    def slide(title, subtitle, source, notes=""):
        page = deck.new(title, subtitle, source, notes)
        page["footer"] = "FLASH / QUAX  |  VNA CALIBRATION"
        return page

    def points(title, subtitle, items, source, notes=""):
        page = slide(title, subtitle, source, notes)
        deck.bullets(page, .8, 1.8, 11.75, items, 21, .28)
        return page

    def figure(title, subtitle, asset, caption, source):
        page = slide(title, subtitle, source)
        deck.image(page, .65, 1.55, 12.03, 4.65, HERE / "figures" / asset)
        deck.text(page, .8, 6.27, 11.75, .53, caption, 13)

    def table(page, headers, data, widths, top=2.05):
        for index, row in enumerate([headers, *data]):
            x = .82
            y = top + index*.56
            for value, width in zip(row, widths):
                deck.rect(page, x, y, width-.04, .51, "#DDE9EC" if index == 0 else
                          "#FFFFFF" if index % 2 else "#EDF1F6")
                deck.text(page, x+.09, y+.10, width-.23, .34, str(value), 15, index == 0)
                x += width

    page = slide("FLASH/QUAX", "VNA Calibration and Cavity Characterization",
                 "Source: validated FLASH/QUAX analyses, 25 November 2026")
    deck.text(page, .82, 2.05, 11.3, 1.08, "From archived scattering measurements to conditional cavity characterizations", 32, True)
    for x, value, label in ((.82,"41","Fitted triplets"), (4.72,"1,784","Runs"), (8.62,"324","Conditional run-mode rows")):
        deck.card(page, x, 4.25, 3.45, value, label)
    deck.text(page, .82, 5.75, 11.5, .5, "Scientific review • 25 November 2026", 16)
    points("What the VNA data contribute", "Cavity shape and frequency registration",
           ["Track fitted resonance frequency and loaded Q by mode.",
            "Use exact scattering traces and fit provenance to build candidate characterizations.",
            "Compare those characterizations with archived ADC spectra on a common frequency axis.",
            "Carry timing, configuration and fit uncertainty into later axion-spectrum work."],
           "Source: cavity-characterization timeline and Run 1429 pilot reports")
    points("The calibration evidence base", "Measurements, fit records and scope",
           ["The strict Run 680 BOR inventory includes 131 files.",
            "Six in-scope triplets were already fitted. Three pre-cutoff triplets are historical controls.",
            "The extension added 32 complete, distinct candidates. Two incomplete groups were left unfitted.",
            "Exact file hashes identify fit inputs. A session inferred from a shared grid remains provisional."],
           "Source: Phase A strict scope; VNA fit extension")
    points("A simultaneous three-path fit", "The original magnitude-only procedure",
           ["Fit |S12|, |S21| and |S22| over the measured sweeps with relative weights of 5%, 2% and 2%.",
            "Run MIGRAD and HESSE from three Q₀ seeds and retain the lowest objective.",
            "Extract f₀ and QL = Q₀ / (1 + β₁ + β₂), with coupling, amplitude and conditional path-gain terms.",
            "The observed phases are preserved for diagnostics. The model fits magnitudes."],
           "Source: original FitCall/FitFunctions and reference validation report")
    page = slide("Fit quality and numerical limitations", "All 32 new fits returned valid optimizer minima",
                 "Source: cavity timeline diagnostics and fit extension; χ² ranges are for new fits")
    table(page, ["Mode","All fits","New fits","Valid new","Accurate cov.","New χ²/ndof"],
          snapshot["quality"], [1.48,1.58,1.58,1.85,2.45,2.65])
    deck.bullets(page, .83, 4.66, 11.7, [
        "All 17 TM010 fits carry the large-residual flag. Two shift by more than 1 kHz across starting values.",
        "Formal errors and covariance diagnostics are retained. None is an accurate covariance determination."
    ], 17, .13)
    figure("Resonance frequency evolved by mode", "Measured sweep dates and conditional run coverage",
           "resonance_frequency.png",
           "Fitted f₀ by in-scope sweep. Crosses flag fit quality. Green spans mark conditional run coverage.",
           "Source: conditional cavity-characterization timeline; both clock hypotheses retained in source")
    figure("Loaded Q also changed between sweeps", "Q derived from the common three-path model",
           "loaded_q.png",
           "Loaded Q by in-scope sweep. Open markers use inferred clock times. Green spans show conditional coverage.",
           "Source: conditional cavity-characterization timeline")
    points("A timestamp can be verified independently", "BOR/EOR content, key write epochs and original files",
           ["Fifteen trace files agree with Europe/Rome filename time and exact archived array content.",
            "Run 1426 contains the newer TM012 arrays while its shared fit pointer names the older triplet.",
            "Configuration signatures cover LO, switch, pump, available gain and bias fields, and fit state.",
            "The archive supports 27 multi-run configuration intervals. Selection and physical applicability remain unverified."],
           "Source: validity-interval audit and Run 680 timestamp report")
    page = slide("Coverage and uncertainty", "Every run-mode row is classified",
                 "Source: run_mode_characterizations.csv; conditional includes three historical Run 680 rows")
    table(page, ["Classification","Rows","Meaning"], [
        ["Conditional", f'{snapshot["coverage"]["CONDITIONAL"]:,}', "Trace and configuration support a cavity candidate"],
        ["Ambiguous", f'{snapshot["coverage"]["AMBIGUOUS"]:,}', "Evidence exists; applicability remains unresolved"],
        ["Unassigned", f'{snapshot["coverage"]["UNASSIGNED"]:,}', "Evidence is insufficient for a fit assignment"],
        ["Total","5,352","1,784 runs × three modes"]], [2.48,1.55,7.48])
    deck.text(page, .88, 5.33, 11.5, .7, "Coverage uses trace evidence and recorded boundaries. No nearest-in-time assignments were made.", 19)
    page = slide("TM012 has three supported Run 3 spans", "Conditional use of fitted cavity shape",
                 "Source: conditional_run_intervals.csv and successive_fit_changes.csv")
    table(page, ["Runs","Anchor","Disposition"], [
        ["1148–1219","1148","Stops at the Run 1220 snapshot gap"],
        ["1426–1428","1426","Newer arrays verified despite inherited fit pointer"],
        ["1429–1669","1429","Stops at the Run 1670 configuration transition"]], [2.38,1.65,7.48])
    shift = snapshot["change"]
    deck.card(page, .83, 4.64, 4.8, f'+{shift["delta_f0_hz"]/1e6:.3f} MHz', "Fitted resonance change, 1426 → 1429")
    deck.card(page, 6.08, 4.64, 4.8, f'+{shift["loaded_Q_change_pct"]:.1f}%', "Fitted loaded-Q change, 1426 → 1429")
    figure("Run 1429 | VNA response and ADC PSD", "TM012 nominal main branch, RF = 8.845843 GHz + signed IF",
           "tm012-vna-versus-psd.png",
           "Measured S-parameters and 1 Hz ADC PSD share 8.846093–8.848093 GHz. PSD is in V²/Hz.",
           "Source: Run 1429 TM012 comparison; the known −492.75 kHz IF line is outside this band")
    points("What carries forward to axion analysis", "Use conditional shapes and preserve evidence grades",
           ["Use TM012 conditional spans for cavity-shape comparisons and retain uncertainty labels.",
            "Track RF registration, sideband evidence and candidate spectral lines on the original PSD grid.",
            "Resolve sweep routing and mode-qualified selection where records permit.",
            "Keep comparisons at the ADC plane. This campaign establishes neither an RF-to-ADC correction nor absolute noise temperature."],
           "Source: characterization timeline and Run 1429 VNA-versus-PSD pilot")
    assert len(deck.slides) == 12
    append_slides(deck, chronological, HERE / "figures")
    assert len(deck.slides) == 57
    return deck


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, help="Refresh inputs from analysis-work")
    parser.add_argument("--reference", type=Path, help="Original reference rf-calibration directory")
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    if args.work or args.reference:
        if not (args.work and args.reference):
            parser.error("--work and --reference must be used together")
        stage(args.work, args.reference)
    snapshot = json.loads((HERE / "source_snapshot.json").read_text())
    logbook = HERE / "acquisition_snapshot.json"
    assert hashlib.sha256(logbook.read_bytes()).hexdigest() == snapshot["provenance"][logbook.name]["sha256"]
    chronological = build_table(snapshot["appendix"], json.loads(logbook.read_text()))
    for path in (HERE / "figures").glob("*.png"):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == snapshot["provenance"][path.name]["sha256"]
    args.output.mkdir(parents=True, exist_ok=True)
    write_table(chronological, args.output)
    with (args.output / "fit_quality.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["mode", "all_fits", "new_fits", "valid_new", "accurate_covariance", "new_chi2_ndof_range"])
        writer.writerows(snapshot["quality"])
    with (args.output / "coverage.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["classification", "run_mode_rows"])
        writer.writerows(snapshot["coverage"].items())
    with (args.output / "tm012_intervals.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["first_run", "last_run"])
        writer.writerows(snapshot["spans"])
    with tempfile.TemporaryDirectory() as scratch:
        export(build(snapshot, chronological), scratch, "vna_calibration", prepared="25 November 2026")
        for extension in ("pptx", "pdf"):
            shutil.copyfile(Path(scratch) / f"iq_noise_summary_vna_calibration.{extension}",
                            args.output / f"flash_quax_vna_calibration.{extension}")
        shutil.copyfile(Path(scratch) / "contact_sheet.png", args.output / "contact_sheet.png")


if __name__ == "__main__":
    main()
