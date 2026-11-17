"""English slide figures assembled exclusively from published Step 9 products."""
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
MODES = ("TM010", "TM011", "TM012")
DATA, TOY, NOM, OTHER = "#007F86", "#7657A6", "#D98726", "#263952"


def rows(path):
    with (ROOT/"docs"/path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(row, key):
    return float(row[key]) if row[key] else np.nan


def by_mode(data, mode):
    return [r for r in data if r["mode"] == mode]


def figure(out, fig, name):
    path = out/(name+".png")
    fig.savefig(path, dpi=180, facecolor="white", bbox_inches="tight", pad_inches=.12)
    plt.close(fig)
    return path


def make_figures(out):
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size":10,"axes.grid":True,"grid.alpha":.20,
                         "legend.fontsize":8,"lines.linewidth":1.25})
    assets = {}
    # Translate the margins of the approved fit plots. The axes and data pixels stay intact.
    montage = Image.new("RGB",(4200,1260),"white")
    font = ImageFont.truetype(font_manager.findfont("DejaVu Sans"),24)
    for j, mode in enumerate(MODES):
        with Image.open(ROOT/f"docs/step9a/vna/{mode}.png") as inp:
            im = inp.convert("RGB")
        assert im.size == (1400,1260)
        draw = ImageDraw.Draw(im)
        draw.rectangle((0,0,1399,44),fill="white")
        draw.text((700,25),f"{mode} · linear VNA magnitude",font=font,fill="black",anchor="mm")
        draw.rectangle((840,57,1250,89),fill="white")
        draw.text((1070,77),"Model − measurement",font=font,fill="black",anchor="mm")
        draw.rectangle((100,1220,1340,1259),fill="white")
        for x in (365,1070):
            draw.text((x,1242),"Frequency relative to Table 6.1 (MHz)",font=font,fill="black",anchor="mm")
        montage.paste(im,(1400*j,0))
    assets["vna"] = out/"vna.png"
    montage.save(assets["vna"])

    h = json.loads((ROOT/"docs/step9b/manufacturer.json").read_text())
    fig, axes = plt.subplots(2,3,figsize=(13,5.25),layout="constrained")
    ax = axes.flat
    mark = h["MMIQ-0520H"]
    ax[0].hlines([mark["typical_CL_per_quadrature_dB"],mark["max_CL_per_quadrature_dB"]],
                 0,200,colors=[DATA,OTHER],linestyles=["-","--"])
    ax[0].set(title="Marki MMIQ-0520H",xlabel="Primary IF (MHz)",ylabel="Conversion loss / quadrature (dB)",ylim=(10,17))
    femto=h["DHPVA-101"]
    for gain,color in ((20,DATA),(60,TOY)):
        ax[1].semilogx(femto["f_MHz"],gain+np.array(femto[f"relative_{gain}_dB"]),".-",color=color,label=f"{gain} dB setting")
    ax[1].axvline(100,color=OTHER,ls=":")
    ax[1].set(title="FEMTO · 100 MHz digitized",xlabel="Primary IF (MHz)",ylabel="Voltage gain (dB)")
    ax[1].legend()
    split=h["ZSC-4-1+"]
    for port in (1,2,3,4):
        ax[2].semilogx(split["f_MHz"],split[f"S{port}_loss_dB"],".-",label=f"Port {port}")
    ax[2].set(title="ZSC-4-1+ · total loss",xlabel="Primary IF (MHz)",ylabel="Loss (dB)")
    ax[2].legend(ncol=2)
    for name,color in (("SIF-40+",DATA),("SBP-101+",TOY)):
        table=h[name]
        ax[3].plot(table["f_MHz"],table["loss_dB"],".-",color=color,label=name)
    ax[3].set(title="Primary IF band-pass filters",xlabel="Primary IF (MHz)",ylabel="Insertion loss (dB)",xlim=(30,115))
    ax[3].legend()
    zad=h["ZAD-1-1+"]
    ax[4].plot(zad["rf_MHz"],zad["loss_dB"],".-",label="30 MHz IF sweep",color=DATA)
    ax[4].hlines(zad["midband_typical_loss_dB"],.2,250,color=OTHER,ls="--",label="Midband typical used")
    ax[4].set(title="ZAD-1-1+ · secondary mixer",xlabel="Mixer RF input (MHz)",ylabel="Conversion loss (dB)")
    ax[4].legend()
    lpf=h["BLP-1.9+"]
    ax[5].plot(lpf["f_MHz"],lpf["loss_dB"],".-",label="Typical table",color=DATA)
    ax[5].plot(2.5,3,"x",color=NOM,label="Nominal cutoff")
    ax[5].set(title="BLP-1.9+ · final low-pass",xlabel="Final IF (MHz)",ylabel="Insertion loss (dB)",xlim=(0,4.5))
    ax[5].legend()
    assets["components"] = figure(out,fig,"components")

    c = rows("step9c/coherent.csv")
    fig, axes = plt.subplots(2,3,figsize=(12,4.8),sharex=True,layout="constrained")
    for j, mode in enumerate(MODES):
        for i, coord in enumerate(("IF","RF")):
            sel=[r for r in by_mode(c,mode) if r["comparison"]==coord]
            f=[float(r["science_IF_hz"])/1e6 for r in sel]
            axes[i,j].plot(f,[number(r,"HW_science_dB") for r in sel],color=NOM,label="Nominal science")
            z=np.array([number(r,"kz_science_scalar") for r in sel])
            axes[i,j].plot(f,20*np.log10(z),color=TOY,label="0.01 × measured kz")
            axes[i,j].set(title=f"{mode} · same {coord}",ylim=(-19,7))
            if not j:
                axes[i,j].set_ylabel("Complex gain (dB)")
            if i:
                axes[i,j].set_xlabel("Science IF (MHz)")
    axes[0,0].legend()
    assets["coherent"]=figure(out,fig,"coherent")

    f = rows("step9c/folding.csv")
    fig, ax = plt.subplots(figsize=(7.2,3.5),layout="constrained")
    for mode,color in (("TM011",TOY),("TM012",NOM)):
        sel=by_mode(f,mode)
        ax.plot([float(r["analog_final_IF_hz"])/1e6 for r in sel],
                [float(r["rho_1_fold_dB"]) for r in sel],color=color,label=mode)
    ax.set(xlabel="Analog final IF (MHz)",ylabel="Electronic power increment (dB)")
    ax.axhline(10*np.log10(2),color=OTHER,ls=":",lw=.8)
    ax.legend()
    assets["folding"]=figure(out,fig,"folding")

    p = rows("step9d/psd.csv")
    fig, axes = plt.subplots(1,3,figsize=(12.4,4.1),layout="constrained")
    for ax,mode in zip(axes,MODES):
        sel=by_mode(p,mode)
        f=np.array([float(r["IF_hz"])/1e6 for r in sel])
        valid=np.array([r["common_mask"]=="1" for r in sel])
        ax.axvspan(-.1,.1,color="#ebedf0")
        data=[float(r["observed_ADC_V2_per_Hz"]) for r in sel]
        ax.semilogy(f,np.where(valid,data,np.nan),color=DATA,lw=.7,label="Run 680")
        for model,color in (("hybrid",TOY),("nominal",NOM)):
            y=[sum(number(r,f"{model}{alias}_{term}") for alias in ("","_alias") for term in ("main","image","cavity")) for r in sel]
            ax.semilogy(f,np.where(valid,y,np.nan),color=color,label=model.title())
        ax.set(title=mode,xlabel="Signed final IF (MHz)",xlim=(-2.5,2.5))
    axes[0].set_ylabel("Bilateral PSD (V²/Hz ADC)")
    axes[0].legend()
    assets["psd"]=figure(out,fig,"psd")

    p = rows("step9d/integrals.csv")
    fig, axes = plt.subplots(2,3,figsize=(12.6,5.0),sharex=True,layout="constrained")
    for j,mode in enumerate(MODES):
        sel=sorted((r for r in by_mode(p,mode) if r["region"]=="FIR"),key=lambda r:float(r["offset_hz"]))
        x=np.array([float(r["offset_hz"])/1e3 for r in sel])
        for model,color in (("observed",DATA),("hybrid",TOY),("nominal",NOM)):
            val=np.array([float(r[f"{model}_common_V2"]) for r in sel])
            axes[0,j].plot(x,np.sqrt(val)*1e3,"o-",color=color,label={"observed":"Run 680","hybrid":"Hybrid","nominal":"Nominal"}[model])
            axes[1,j].plot(x,val*1e6,"o-",color=color)
        axes[0,j].set_title(mode)
        axes[1,j].set_xlabel("Offset from resonance center (kHz)")
    axes[0,0].set_ylabel("RMS (mV ADC)")

    axes[1,0].set_ylabel("Power (mV² ADC)")
    axes[0,0].legend()
    assets["bands"]=figure(out,fig,"bands")

    sel=by_mode(rows("step9e/tones.csv"),"TM010")
    checks=by_mode(rows("step9e/iq_checks.csv"),"TM010")
    sb=by_mode(rows("step9e/science_bands.csv"),"TM010")
    fig,(a,b)=plt.subplots(1,2,figsize=(12.0,4.1),layout="constrained")
    for key,label,color in (("Hplus_power","Main",DATA),("conjugate_transfer_power","Conjugate",NOM),("pair_transfer_power","Sum",TOY)):
        pts=[r for r in sel if r["unaliased"]=="1" and abs(float(r["input_IF_hz"]))<=.55e6]
        a.semilogy([float(r["input_IF_hz"])/1e3 for r in pts],[float(r[key]) for r in pts],"o",ms=4,label=label,color=color)
    a.set(xlabel="Tone input IF (kHz)",ylabel="Power / nominal generator power",title="Complex tone · assigned bins")
    a.legend()
    for q,color in (("I",DATA),("Q",TOY)):
        divisor=np.mean([float(r[q+"_gain_RMS"])**2 for r in checks if abs(float(r["input_IF_hz"]))>1e6])
        b.semilogx([abs(float(r["input_IF_hz"]))/1e3 for r in checks],[float(r[q+"_gain_RMS"])**2/divisor for r in checks],"o",color=color,label=f"Tone {q}")
        for j,r in enumerate(sb):
            b.hlines(float(r[q+"_power_over_own_plateau"]),max(.2,float(r["low_hz"])/1e3),float(r["high_hz"])/1e3,color=color,ls="--",label=f"Science {q}" if not j else None)
    b.set(xlabel="|IF| (kHz)",ylabel="Power / own shoulder or plateau",title="Separate quadratures · distinct estimators",yscale="log")
    b.legend(ncol=2)
    assets["iq"]=figure(out,fig,"iq")
    return assets
