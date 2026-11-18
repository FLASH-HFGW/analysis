"""Export light validation tables and a diagnostic plot from Step 10A metrics."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def write(path, rows):
    with path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows({k:format(v,".11g") if isinstance(v,float) else v
                          for k,v in row.items()} for row in rows)


def export(metrics, output):
    output.mkdir(exist_ok=True,parents=True)
    full, bands, sources = [], [], []
    for mode, entry in metrics["modes"].items():
        for model, data in entry["models"].items():
            label=dict(mode=mode, model=model)
            full.append({**label, **{k:v for k,v in data.items() if k not in ("bands","components")},
                         "mask_bins":entry["mask_bins"],"mask_fraction":entry["mask_fraction"],
                         "thermal_IF_Hz":entry["thermal_IF_Hz"],
                         "step9d_PSD_max_relative_difference":entry["legacy_grid_max_relative_error"]})
            bands.extend({**label, **row} for row in data["bands"])
            sources.extend({**label, **row} for row in data["components"])
    for name,rows in (("validation",full),("bands",bands),("components",sources)):
        write(output/(name+".csv"),rows)
    fig, axes=plt.subplots(1,2,figsize=(9,3.5),layout="constrained")
    labels=[r["mode"]+" "+r["model"] for r in full]
    x=np.arange(len(full))
    for key, marker, name, color in (("expected_RMS_V","o","Analytical","#7657A6"),
                                     ("ADC_RMS_V","x","Quantized","#007F86")):
        axes[0].plot(x,[1e3*r[key] for r in full],marker,ms=7,label=name,color=color)
    axes[0].set(ylabel="RMS (mV ADC)",xticks=x,xticklabels=labels)
    axes[0].tick_params(axis="x",labelrotation=45)
    axes[0].legend(fontsize=8)
    for i,r in enumerate(full):
        filtered=[b["z_score"] for b in bands if b["mode"]==r["mode"] and b["model"]==r["model"]]
        axes[1].scatter([i]*len(filtered),filtered,s=13,alpha=.6,color="#7657A6")
        axes[1].plot(i,r["z_score"],"x",color="#007F86",ms=8)
    axes[1].axhline(0,color=".5",lw=.7)
    axes[1].axhspan(-2,2,color=".9",zorder=-2)
    axes[1].set(ylabel="Analog power deviation / expected sample SD",
                title="Full-band × and seven FIR bands •",xticks=x,xticklabels=labels)
    axes[1].tick_params(axis="x",labelrotation=45)
    fig.savefig(output/"validation.png",dpi=135)
    plt.close(fig)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    export(json.loads(args.metrics.read_text()),args.output)
