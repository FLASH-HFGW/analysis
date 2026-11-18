"""Append the homogeneous comparison and campaign supplement to frozen v49."""
import argparse,csv,hashlib,importlib.util,json,re,shutil,subprocess,sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops
from pypdf import PdfReader,PdfWriter
from pptx import Presentation

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("v48_append",ROOT/"reporting/iq_noise_summary_v48/build.py")
sys.path.insert(0,str(ROOT/"reporting/iq_noise_summary_v48"))
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
sd=base.sd
MODES=("TM010","TM011","TM012")
POPS=("data","v0","H","N")
NAMES={"data":"Run 680","v0":"Toy v0","H":"Toy v1 / H","N":"Model N","all":"All populations"}
TITLES={"times":"I and Q time series","iq":"Absolute and normalized constellations",
        "amplitude":"Amplitude, Rayleigh and phase","increments":"Circular phase increments",
        "spectra":"PSD and complementary spectrum","acf":"Complex autocorrelation",
        "fits":"Characteristic times from upper maxima","bands":"Resonance bands and excursions"}


def sha(p):
    digest=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(2**20),b""):digest.update(b)
    return digest.hexdigest()


def read(path):
    with path.open(newline="") as f:return list(csv.DictReader(f))


def write(path,rows):
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def make(work,products,out,freeze):
    dup=out/"figures"
    dup.mkdir(parents=True)
    shutil.copytree(freeze/"figures",dup/"v49")
    shutil.copytree(products/"figures",dup/"comparison")
    archive=out/"comparison_data"
    archive.mkdir()
    for source in products.iterdir():
        if source.is_file():
            shutil.copy2(source,archive/source.name)
    old=work/"reports/iq_noise_summary_v49_campaign_supplement"
    camp=out/"campaign_supplement"
    shutil.copytree(old,camp)
    obs={(r["mode"],r["population"],r["band"],r["observable"]):float(r["mean"])
         for r in read(archive/"observables.csv")}
    diff={(r["mode"],r["population"],r["band"],r["observable"]):float(r["distance"])
          for r in read(archive/"model_evolution.csv")}
    fit={(r["mode"],r["population"]):r for r in read(archive/"fits.csv")}
    historical=read(archive/"historical_fits.csv")
    deck=sd.Deck()
    ledger=[]
    index=[]
    for row in read(freeze/"figure_index.csv"):
        index.append(dict(slide=row["slide"],mode="legacy",family=row["title"],population="v49",
                          png="figures/v49/"+row["file"],
                          vector=next((str(p.relative_to(out)) for ext in (".pdf",".svg")
                                       if (p:=(dup/"v49"/row["file"]).with_suffix(ext)).exists()),""),
                          numerical_source=row["numerical_source"],meaning=row["result"],limits=row["limitations"]))
    hashes={}

    def page(title,subtitle,note,sources):
        s=deck.new(title,subtitle,"Numerical inputs, figure variants and conventions are listed in the v50 ledgers.",note)
        s["footer"]="HFGW | v50 · HOMOGENEOUS MODEL COMPARISON"
        for observable,file,selector in sources:
            if file not in hashes:hashes[file]=sha(file)
            ledger.append(dict(slide=85+len(deck.slides),title=title,observable=observable,
                               file=str(file.relative_to(out) if file.is_relative_to(out) else file),
                               selector=selector,sha256=hashes[file],limitation=note))
        return s

    def text(s,y,lines,size=16):
        for line in lines:
            h=max(.34,len(sd.wrap(line,12,size).splitlines())*size*1.15/72+.05)
            deck.text(s,.65,y,12,h,line,size)
            y+=h+.11
        assert y<=6.92,(s["title"],y)

    def table(s,y,headers,rows,widths,step=.52,size=15):
        for j,row in enumerate((headers,*rows)):
            x=.65
            for v,w in zip(row,widths):
                deck.text(s,x,y+j*step,w-.08,step,str(v),size,j==0)
                x+=w

    data_h5=work/"simulation/step10c/statistics.h5"
    s=page("v50 — A matched comparison of three readouts",
           "Run 680 · 4000 blocks per mode and population · 251659 common IF bins",
           "All inherited v49 pages are unchanged. New comparisons use the Step 10C ADC projection and estimators.",
           [("Population and ADC checks",archive/"validation.json","all fields"),
            ("Approved measured and H/N aggregates",data_h5,"mean and clusters"),
            ("Reproduced historical v0",archive/"validation_v0.json","first five SPECs and full-run power")])
    text(s,1.86,["Toy v0 uses Valeria-based kz, the original 103.4 dB RF scale and the frozen historical thermal pole.",
                 "Toy v1 / H uses the measured response with independently reconstructed RF gains and nominal secondary folding.",
                 "Model N shares the updated RF/noise physics and obtains downconversion independently from nominal specifications.",
                 "All four populations are compared on the same signed post-ADC mask. Historical unmasked results retain their separate scope.",
                 "The local figure atlas includes data + each model and all four populations for every mode and observable."])

    comments={
      "times":"First 200 samples of the first projected ADC block. Independent noise traces are not compared point by point.",
      "iq":"Top: common physical ADC axes. Bottom: own-block RMS units. Color is log probability per common histogram cell.",
      "amplitude":"ADC amplitude and shape remain separate. Rayleigh and uniform phase are proper-Gaussian references.",
      "increments":"Circular increments at 1, 10 and 100 samples. Each pair is within one projected block.",
      "spectra":"Same signed rectangular PSD estimator. C is the complementary spectrum; proper model means approach zero.",
      "acf":"Same linear estimator and lag normalization. Real, imaginary and modulus share the same lag axis.",
      "fits":"Fits use upper maxima over 0.3–4 µs. Only resolved descriptive fits are drawn; numerical failures are retained.",
      "bands":"FIR and full-band RMS are in ADC units. Episodes are contiguous within a block, not independent triggers."}
    observables={
      "times":"I_ADC_V,Qhardware_ADC_V,time_s","iq":"iq_absolute,iq_shape,IQ_edges",
      "amplitude":"amplitude_absolute,amplitude_shape,phase","increments":"phase_increment_1,10,100",
      "spectra":"PSD,complementary,frequency_Hz,common_mask","acf":"acf,acf_V2",
      "fits":"fits.csv and fit_details.json","bands":"observables.csv, tails.csv"}
    for m in MODES:
        for family,title in TITLES.items():
            sources=[("Measured and updated-model "+title,data_h5,f"mean/{m}/{{data,H,N}}/full: {observables[family]}"),
                     ("Toy v0 "+title,archive/"v0_statistics.h5",f"mean/{m}/v0/full: {observables[family]}")]
            if family=="times":
                sources=[(NAMES[p]+" projected snapshot",archive/f"{m}_{p}_time_panel.npz",observables[family]) for p in POPS]
            if family=="fits":
                sources.extend([("All slopes, offsets, goodness and validity",archive/"fits.csv",m),
                                ("Diagnostic uncertainty and alternate windows",archive/"fit_details.json",m)])
            if family=="bands":
                sources.extend((("Absolute and shape band values",archive/"observables.csv",m),
                                ("Threshold sample and episode counts",archive/"tails.csv",m)))
            s=page(m+" · "+title,"Common mask, estimator and plotting scales",
                   comments[family]+" Full per-population diagnostics are in the numerical tables.",sources)
            p=dup/"comparison"/f"{m}_{family}_all.png"
            deck.image(s,.52,1.57,12.3,4.75 if family not in ("fits","bands") else 3.98,p)
            if family=="fits":
                def short(pop):
                    row=fit[m,pop]
                    if row["fit_status"]!="resolved descriptive fit":
                        return f'{NAMES[pop]}: {row["fit_status"]}'
                    return f'{NAMES[pop]}: τ={float(row["tau_us"]):.3f} µs, R²={float(row["r2_selected_maxima"]):.3f}'
                text(s,5.68,[" | ".join(short(p) for p in POPS[:2]),
                             " | ".join(short(p) for p in POPS[2:])+f' | Cavity amplitude decay: {float(fit[m,"data"]["cavity_amplitude_decay_us"]):.3f} µs.'],12)
            else:
                y=5.69 if family=="bands" else 6.36
                text(s,y,[comments[family]],12)
                if family=="bands":
                    text(s,6.19,["Aggregate full-band RMS (mV ADC): "+" / ".join(
                        f'{1000*obs[m,p,"full","RMS_aggregate_V"]:.3f}' for p in POPS)+" (run 680 / v0 / H / N)."],12)
            for pop in ("all",*POPS[1:]):
                name=f"{m}_{family}_{pop}"
                index.append(dict(slide=85+len(deck.slides),mode=m,family=family,population=NAMES[pop],
                                  png=f"figures/comparison/{name}.png",vector=f"figures/comparison/{name}.pdf",
                                  numerical_source=" | ".join(str(r[1].relative_to(out) if r[1].is_relative_to(out) else r[1]) for r in sources),
                                  meaning=title,limits=comments[family]))

    s=page("Model evolution in absolute ADC RMS","Signed data/model power ratios on the same masked full-run population",
           "The all-observable table provides descriptive group-SE contrasts and the distance change relative to v0. No significance is inferred for uncalibrated hardware systematics.",
           [("Full-band RMS and group uncertainty",archive/"observables.csv","RMS_aggregate_V for full band"),
            ("Model evolution",archive/"model_evolution.csv","absolute and relative distances")])
    table(s,1.9,("Mode","Data / v0","Data / H","Data / N"),
          [(m,*(f'{20*np.log10(obs[m,"data","full","RMS_aggregate_V"]/obs[m,p,"full","RMS_aggregate_V"]):+.3f} dB'
                for p in POPS[1:])) for m in MODES],(1.65,3.15,3.15,3.15))
    text(s,4.50,["Read the signed residual together with the model's shape and covariance. A closer absolute level does not identify the correct transfer shape.",
                 "The v0→H comparison changes the RF gain, physical thermal pole and image folding as a package. The H/N cross-check changes downconversion."],16)
    s=page("Temporal and distribution residuals","Matched full-band distances to run 680",
           "No sample-IID p-values. Correlation times remain descriptive; the original slide 23 results are separately archived.",
           [("Complex ACF and PSD shape distances",archive/"model_evolution.csv","full; ACF_real, ACF_imag, PSD_shape"),
            ("Historical fits kept separate",archive/"historical_fits.csv","first five SPECs unmasked; v49 slide 23")])
    table(s,1.86,("Mode","PSD shape TV · v0 / H / N","Real ACF RMSE · v0 / H / N"),
          [(m," / ".join(f'{diff[m,p,"full","PSD_shape"]:.4f}' for p in POPS[1:]),
            " / ".join(f'{diff[m,p,"full","ACF_real"]:.4f}' for p in POPS[1:])) for m in MODES],(1.5,5.15,5.15))
    text(s,4.43,["Normalized amplitude and phase statistics, joint I/Q distributions and grouped moment contrasts are in the comparison tables.",
                 "All three scalar noise models are proper in expectation. The measured complementary spectrum and frequency-dependent covariance remain unresolved."],16)
    s=page("Campaign strain sensitivity · 260 runs","Approved supplement · 54,525.952 s live acquisition",
           "Conditional field 6.73 T, volume 0.139 L, reference CGW 0.01, unchanged coherent H/N gains. No exposure scaling for individual PBH events.",
           [("Campaign ASD and integration projections",camp/"summary.csv","all mode/model rows"),
            ("Phase and integration assumptions",camp/"README.md","Integration projections and practicability")])
    deck.image(s,.52,1.62,12.25,4.65,camp/"campaign.png")
    text(s,6.38,["Coherent: known phase. Run powers: no inter-run phase. Hann powers: archived short-window projection."],12)
    index.append(dict(slide=85+len(deck.slides),mode="all",family="campaign strain",population="H and N",
                      png="campaign_supplement/campaign.png",vector="campaign_supplement/campaign.pdf",
                      numerical_source="campaign_supplement/summary.csv; asd_curves.csv",meaning="Conditional strain projections",
                      limits="No verified phase coherence across the campaign"))
    s=page("Conclusion · calibration and signal searches","Frozen benchmark sensitivities retain their stated operating assumptions",
           "The need for hardware phase, complex transfer, and noise-wave measurements remains unchanged. The campaign supplement is separate from single-event simulations.",
           [("Conditional GW projection",camp/"validation.json","live time and calibration"),
            ("Unchanged PBH studies",freeze/"physics_tables/benchmarks.csv","all benchmarks")])
    text(s,1.96,["Gain changes and image folding alter absolute ADC power. H and N leave measured covariance residuals.",
                 "The masked comparison constrains the models only where calibrated responses exist. Original LF and long-term temperature studies remain in v49.",
                 "Campaign coherence requires a calibrated phase-continuous timebase, Doppler tracking and phase-aware calibration across gaps.",
                 "Single-transient PBH results still use their own crossing time and ring-down. Trigger performance requires validated injection studies."])
    return deck,ledger,index


def run(work,products,out):
    p=work/"reports/iq_noise_summary_v49"
    manifest=json.loads((p/"sha256.json").read_text())["outputs"]
    files={ext:p/f"iq_noise_summary_v49.{ext}" for ext in ("pdf","pptx")}
    for f in files.values():assert sha(f)==manifest[f.name]
    out.mkdir(exist_ok=False,parents=True)
    deck,led,index=make(work,products,out,p)
    n=85+len(deck.slides)
    base.COUNT,base.TOTAL=85,n
    with TemporaryDirectory(prefix="v50-") as tmp:
        temp=Path(tmp)
        ext=temp/"appendix"
        sd.export(deck,ext,"v50_appendix","18 November 2026",page_offset=85,total_pages=n)
        shutil.copy2(ext/"contact_sheet.png",out/"appendix_contact_sheet.png")
        target=out/"iq_noise_summary_v50.pdf"
        writer=PdfWriter()
        original=PdfReader(files["pdf"])
        writer.append_pages_from_reader(original)
        writer.append_pages_from_reader(PdfReader(ext/"iq_noise_summary_v50_appendix.pdf"))
        with target.open("wb") as f:writer.write(f)
        final=PdfReader(target)
        assert len(final.pages)==n and len(original.pages)==85
        assert all(a.get_contents().get_data()==b.get_contents().get_data() for a,b in zip(original.pages,final.pages))
        views={}
        for tag,source in (("v49",files["pdf"]),("v50",target)):
            subprocess.run(["pdftoppm","-r","63","-f","1","-l","85","-png",str(source),str(temp/tag)],
                           check=True,capture_output=True)
            views[tag]={int(f.stem.rsplit("-",1)[1]):f for f in temp.glob(tag+"-*.png")}
        assert len(views["v49"])==len(views["v50"])==85
        for i in range(1,86):
            with Image.open(views["v49"][i]) as a,Image.open(views["v50"][i]) as b:
                assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None,i
        ppt=out/"iq_noise_summary_v50.pptx"
        members=base.append_pptx(files["pptx"],ext/"iq_noise_summary_v50_appendix.pptx",ppt)
        prs=Presentation(ppt)
        for i,s in enumerate(deck.slides,85):
            assert re.sub(r"\s+"," ",prs.slides[i].shapes[1].text)==s["title"]
            clean=lambda x:"".join(ch for ch in x if ch.isalnum())
            assert clean(s["title"]) in clean(final.pages[i].extract_text()),i
    write(out/"figure_index.csv",index)
    write(out/"slide_observable_provenance.csv",read(p/"slide_observable_provenance.csv")+led)
    shutil.copy2(ROOT/"docs/v50/README.md",out/"README.md")
    summary=dict(slides=n,preserved_v49_slides=85,appendix_slides=len(deck.slides),
                preserved_PDF_pixels=85,preserved_PPTX_members=members,
                added_quantitative_figure_variants=96,figure_index_rows=len(index),
                new_provenance_rows=len(led),source_models_unchanged=True,
                comparison=json.loads((products/"validation.json").read_text()))
    (out/"validation.json").write_text(json.dumps(summary,indent=2)+"\n")
    (out/"validation_report.md").write_text(
        f"# v50 validation\n\n{n} slides in both formats. The original 85 PDF page streams and rendered pixels "
        f"match v49. The PPTX keeps {members} original package members byte-identical. "
        "New native text, notes, images and titles match the renderer.\n\n"
        "All three full-run v0 RMS values and the first five archived SPEC ADC words match the historical toy. "
        "All 12 population/mode PSD integrals reproduce aggregate RMS. The first data SPEC snapshot matches the validated bank hash. "
        "The fit table states when no characteristic time is resolved. The local atlas has 96 labeled figure variants.\n")
    (out/"sha256.json").write_text(json.dumps(dict(inputs={**{str(f):sha(f) for f in files.values()},
        **{r["file"]:r["sha256"] for r in led}},
        outputs={str(f.relative_to(out)):sha(f) for f in out.rglob("*") if f.is_file()}),indent=2)+"\n")
    print(n,"verified slides",len(index),"figure index rows",flush=True)


if __name__=="__main__":
    import numpy as np
    ap=argparse.ArgumentParser()
    for x in ("work","products","out"):ap.add_argument(x,type=Path)
    a=ap.parse_args()
    run(a.work,a.products,a.out)
