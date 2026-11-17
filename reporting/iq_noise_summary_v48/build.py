"""Append Part IV to the frozen v47.1 presentation and verify preservation."""
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np
from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter
from pptx import Presentation

from figures import ROOT, MODES, DATA, TOY, NOM, OTHER, make_figures, rows

sys.path.insert(0,str(ROOT/"reporting"))
import slide_deck as sd

FROZEN = {
    "pdf":"483c810d3c369e8b23a993603655d837eea148ce8fd68c08d4160a860af79e5f",
    "pptx":"211588d16518075ace6a8c626ed773e16f11f2fe6b4dbaffc114c6b8bf00d192",
}
COUNT, TOTAL = 53, 65


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slides(assets):
    deck = sd.Deck()
    ledger = []

    def page(title, subtitle, notes, sources):
        n = COUNT+len(deck.slides)+1
        s = deck.new(title,subtitle,"Sources: "+", ".join(dict.fromkeys(path.split("/")[0].upper() for _,path,_ in sources))
                     +"  |  Explicit inputs and field selections in the v48 provenance CSV.",notes)
        s["footer"] = "FLASH | v48 | PART IV · RF CALIBRATION AND READOUT ELECTRONICS"
        for observable,path,selector in sources:
            p=ROOT/"docs"/path
            ledger.append(dict(slide=n,title=title,observable=observable,repository_path=str(p.relative_to(ROOT)),
                               selection_and_fields=selector,source_sha256=sha(p),approved_ancestor="a418b23"))
        return s

    def text(s,y,lines,x=.65,w=12,size=16):
        for line in lines:
            h=max(.34,len(sd.wrap(line,w,size).splitlines())*size*1.15/72+.055)
            deck.text(s,x,y,w,h,line,size)
            y+=h+.12

    def table(s,y,headers,values,widths,row_h=.46,size=15):
        x=.65
        for label,w in zip(headers,widths):
            deck.text(s,x,y,w-.08,row_h,label,size,True,sd.NAVY)
            x+=w
        for j,value in enumerate(values,1):
            x=.65
            for label,w in zip(value,widths):
                deck.text(s,x,y+j*row_h,w-.08,row_h,str(label),size)
                x+=w

    def graph(s,key,top,height,x=.52,w=12.3):
        deck.image(s,x,top,w,height,assets[key])

    comp=rows("step9c/powers.csv")
    intervals=rows("step9d/integrals.csv")
    def pick(records, mode, region, scenario=None):
        return next(r for r in records if r["mode"]==mode and r["region"]==region
                    and (region=="full" or r["offset_hz"]=="0") and
                    (scenario is None or r["scenario"]==scenario))

    s=page("Part IV — RF Calibration and Readout Electronics",
           "Absolute normalization | run 680 and the original RF assumptions",
           "A is the original toy's analytic expectation. Full-band data are run 680 AC moments as used in Step 9C. The original stochastic toy and its historical thermal pole retain their frozen form.",
           [("Original full-band RMS and run/expectation ratios","step9c/powers.csv","scenario=A; region=full; RMS_ADC_V, data_full_window_V2, data_over_model_dB"),
            ("Historical RF gain and equivalent receiver temperature","step9c/README.md","Scenari analitici; scenario A")])
    table(s,1.90,("Mode","Run 680 RMS (mV ADC)","Original A RMS (mV ADC)","Run / A power (dB)"),
          [(m,f'{1000*np.sqrt(float((r:=pick(comp,m,"full","A"))["data_full_window_V2"])):.3f}',
            f'{1000*float(r["RMS_ADC_V"]):.3f}',f'{float(r["data_over_model_dB"]):+.2f}') for m in MODES],
          (1.5,3.6,3.9,3.2),.62)
    text(s,4.65,["Original RF budget: 103.4 dB for every mode, with a 3.955 K equivalent receiver temperature.",
                 "Independent tests separate RF gain, coherent readout and image-band noise folding."],size=18)

    s=page("RF calibration starts with the reference planes",
           "The VNA, source calibration and DAQ tone probe different portions of the chain",
           "The tone path excludes the additional FET according to the normalization ledger. Its exact injection node and loss to the Marki were not measured. VNA L5 includes cabling within its measurement planes. The nominal FET gain and any cabling outside those planes remain systematic uncertainties.",
           [("Noise-source global calibration and RF planes","step9a/README.md","Temperatura, guadagno e piani di riferimento; Eqs. 6.1–6.2"),
            ("Generator reference, ADC scaling and cable audit","step9c/README.md","Tono e piani di riferimento; Verifica dei cavi"),
            ("Cable attenuation sensitivity","step9c/cable_sensitivity.csv","all five rows; diagnostic only")])
    text(s,1.82,["Cavity output → VNA L5 reference → external FET (36 dB nominal) → Marki RF → readout → ADC.",
                 "Noise source: 3.955 ± 0.468 K and 67.81 ± 0.39 dB globally. The published ± definition and mode curves remain unresolved.",
                 "DAQ tone: −60 dBm generator setpoint into 50 Ω (223.6 µV RMS nominal). The delivered power at the Marki remains unknown.",
                 "Integrated complex Hann tone yields kz in ADC volts / nominal generator volts. Calibration ±5 V and science ±2 V scales are already applied.",
                 "0–2 dB of unmeasured tone-path loss is a sensitivity check only. No gain, temperature or cable attenuation is fitted."],size=18)

    s=page("Independent VNA fits give three L5 gains",
           "24 July sweeps | left panels show measured and fitted magnitudes, right panels show residuals",
           "Fixed and simultaneous fits are shown. The statistical errors are conditional HAC standard errors. The fit covariance and fixture effects do not quantify systematic uncertainty. The original thesis fit code was not recovered.",
           [("Three VNA fit and residual figures","step9a/vna/TM010.png","approved plot; English marginal labels only"),
            ("Three VNA fit and residual figures","step9a/vna/TM011.png","approved plot; English marginal labels only"),
            ("Three VNA fit and residual figures","step9a/vna/TM012.png","approved plot; English marginal labels only"),
            ("Simultaneous L5, statistical uncertainty and printed-sign control","step9a/vna/fits.csv","fit=free_eq69; L5_dB,L5_stat_se_dB,plus_dB,relative_RMS"),
            ("Sign and original implementation limitation","step9a/vna/README.md","Controllo algebrico"),("Eq. 6.12–6.13 sign audit","step9a/README.md","Segno di L5")])
    graph(s,"vna",1.57,3.62)
    fits=[r for r in rows("step9a/vna/fits.csv") if r["fit"]=="free_eq69"]
    text(s,5.29,["L5 (dB, statistical SE)   "+"    |    ".join(f'{r["mode"]}  {float(r["L5_dB"]):.3f} ± {float(r["L5_stat_se_dB"]):.3f}' for r in fits),
                 "Topology: L5 = (D21 + D22 − D12)/2. The thesis prints +D12 in Eqs. 6.12–6.13.",
                 "Printed-sign control (dB):  "+" / ".join(f'{float(r["plus_dB"]):.2f}' for r in fits)+". Its use in the original implementation remains unverified."],size=13)

    s=page("Two LO configurations set the physical IF",
           "The FEMTO and branch filters see the primary IF. The BLP sees the final IF.",
           "The sequence is repeated for both I and Q. TM010 bypasses the band-pass and second mixer. Positive resonance coordinates use the physical resonance frequencies. LO generator settings do not determine delivered LO power.",
           [("Hardware topology and swapped I-side diagram labels","hardware/README.md","Original chain and routing limitations"),
            ("Calibration and science LO and IF mapping","step9b/README.md","Configurazioni e percorsi; settings and physical frequencies"),
            ("Nominal resonance RF and signed IF","step9b/gain_budget.csv","path=main; rf_MHz,primary_signed_MHz,final_MHz; both settings")])
    text(s,1.76,["Marki I/Q → FEMTO ×2 → four-way splitter ×2 → branch BPF and second mixer → BLP ×6 → ADC."],size=17)
    table(s,2.47,("Mode","RF (GHz)","Cal IF₁ / IF₂ (MHz)","Run 680 IF₁ / IF₂ (MHz)"),
          [(m,*({"TM010":("8.737119","2.209 / 2.209","1.250 / 1.250"),
                  "TM011":("8.780840","45.930 / 1.770","44.971 / 1.248"),
                  "TM012":("8.841182","106.272 / 1.882","105.313 / 1.256")}[m])) for m in MODES],
          (1.45,2.25,3.6,4.4),.52)
    text(s,4.88,["LO₁: 8.734910 GHz cal, 8.735869 GHz science. LO₂ TM011/012: 44.160/104.390 MHz cal, 43.723/104.057 MHz science.",
                 "Functional BPF: SIF-40+ for TM011, SBP-101+ for TM012. The original I-side labels are reversed. Installed routing remains unverified."],size=15)

    s=page("Manufacturer responses set the nominal budget",
           "Typical specifications and digitized FEMTO data | each component is evaluated in its own domain",
           "Marki per-quadrature conversion loss uses the specified typical value; the dashed line is its maximum. The table-driven BLP typical loss is 8.32 dB at 2.5 MHz versus 3 dB nominal. ZAD's 30 MHz IF sweep is a diagnostic; the budget uses 4.83 dB midband typical. Phase data remain incomplete.",
           [("Six component panels and validity limits","step9b/manufacturer.json","MMIQ-0520H; DHPVA-101; ZSC-4-1+; SIF-40+; SBP-101+; ZAD-1-1+; BLP-1.9+"),
            ("Digitization, missing phases and settings","step9b/README.md","Dati e dominio di validità")])
    graph(s,"components",1.56,4.70)
    text(s,6.31,["Splitter and tabulated BLP magnitude start at 100 kHz. FEMTO 10/100 MHz and AC/DC switch states are unverified."],size=13)

    s=page("Nominal gain and measured kz share a testable scale",
           "Complex RMS, matched 50 Ω | conditional on the nominal generator power reaching the Marki",
           "The curves show science nominal gain and the calibration-tone response multiplied by 0.01 in amplitude. Equal IF compares different RF frequencies. Equal RF shifts calibration IF by +959/+522/+626 kHz. The calibration-to-tone absolute comparison is tabulated at 1.250 MHz science IF. Nominal run 680 per-quadrature resonance gains are +1.55, −4.33, −8.46 dB. Ideal complex RMS gains add +3.010 dB.",
           [("Absolute coherent curves, same RF and same IF","step9c/coherent.csv","comparison=IF or RF; science_IF_hz,kz_science_scalar,HW_science_dB"),
            ("Transfer ratio and absolute offsets at 1.25 MHz","step9c/coherent.csv","science_IF_hz=1250000; excess_transfer_over_LF_setting_dB,HW_cal_over_kz_dB"),
            ("Per-quadrature and ideal complex gains","step9b/gain_budget.csv","path=main; I_functional_dB,summed_IQ_dB for both configurations")])
    graph(s,"coherent",1.53,3.74)
    text(s,5.31,["Mode order TM010/011/012. Nominal science resonance gain per quadrature: +1.55/−4.33/−8.46 dB. Ideal complex: +3.01 dB relative to each.",
                 "At 1.250 MHz science IF, nominal cal / kz is +0.65/+0.85/+0.91 dB at equal IF and −0.84/+0.67/+0.77 dB at equal RF.",
                 "Science/cal excess over −40 dB: 0.00/+0.06/+0.04 dB (same IF), +1.69/+0.28/+0.30 dB (same RF)."],size=13)

    s=page("The secondary mixers fold two RF bands",
           "Real mixers on I and Q with a common in-phase LO₂ and ideal quadratures",
           "For uncorrelated bands the terms sum in power. Equal RF PSD at the Marki in the main and image bands is an unverified hypothesis. The plotted increment is computed by frequency from the approved nominal image/main ratio. TM010 bypasses the secondary stage.",
           [("Signed-input mixing derivation","step9c/README.md","Folding del mixer secondario"),
            ("Frequency-dependent power multiplier","step9c/folding.csv","rho_1_fold_dB, analog_final_IF_hz; TM011 and TM012"),
            ("Difference from conjugate leakage","step9e/README.md","Risposta firmata e PSD diagnostica")])
    text(s,1.93,["Multiply z₁(t) by 2g cos(2π LO₂t + φ).",
                 "Z₂(f) ∝ e⁻ⁱφ Z₁(f + LO₂) + e⁺ⁱφ Z₁(f − LO₂).",
                 "Main RF: LO₁ + LO₂ + f. Image RF: LO₁ − LO₂ + f.",
                 "Equal RF PSD at the Marki is unverified. For incoherent bands use 1 + |Himage/Hmain|².",
                 "ADC aliases shift final IF by m × 5 MHz. I/Q conjugate leakage couples signed bins of the same tone."],w=6.0,size=16)
    graph(s,"folding",2.14,3.70,x=6.82,w=5.97)

    s=page("VNA gain and RF folding shift the power prediction",
           "Run 680 central FIR band | 50 kHz nominal bandwidth",
           "A is original toy; B changes only RF gain to the independent L5 plus 36 dB; D adds secondary image noise with equal RF PSD. Tn remains 3.955 K. The historical toy thermal term is preserved for this Step 9C comparison.",
           [("Central band gain and folding increments and residual","step9c/powers.csv","FIR; offset_hz=0; A,B,D; model_over_B_same_intervals_dB,data_over_model_dB"),
            ("Unequal input image PSD sensitivities","step9c/powers.csv","FIR; offset_hz=0; D_rho_0p5,D_rho_2; model_over_B_same_intervals_dB")])
    central = []
    for m in MODES:
        a = pick(comp,m,"FIR","A")
        d = pick(comp,m,"FIR","D")
        values = (-float(a["model_over_B_same_intervals_dB"]),float(d["model_over_B_same_intervals_dB"]),
                  float(a["data_over_model_dB"]),float(d["data_over_model_dB"]))
        central.append((m,*(f"{v:+.3f} dB" for v in values)))
    table(s,1.98,("Mode","B/A RF change","D/B folding","Run 680 / A","Run 680 / D"),
          central,(1.45,2.5,2.5,2.5,2.8),.58)
    text(s,4.72,["TM010 has no secondary mixer. TM011 and TM012 gain about 3.1 dB in the central band.",
                 "Changing image RF PSD from 0.5× to 2× main gives +1.82 to +4.89 dB (TM011) and +1.85 to +4.96 dB (TM012)."],size=17)

    s=page("Independent hardware PSD versus run 680",
           "Absolute bilateral PSD | identical signed spectral bins for both models and data",
           "Hybrid uses measured kz, scaled in amplitude by 0.01, and the nominal image/main power ratio. Nominal uses absolute hardware main and image responses. Both use VNA L5, FET 36 dB, Tn 3.955 K and the unverified equal RF PSD hypothesis. Both include alias orders 0 and ±1. Higher supported orders are separately tabulated. The physical cavity poles are 1.250, 1.248, 1.256 MHz. The historical toy remains frozen.",
           [("Absolute PSD curves and common mask","step9d/psd.csv","common_mask=1; observed_ADC_V2_per_Hz; sum main/image/cavity for direct and alias terms by model"),
            ("Shared assumptions and physical thermal poles","step9d/README.md","Due catene analitiche; PSD misurata, maschera e alias"),
            ("Common bin coverage","step9d/integrals.csv","region=full; known_bin_fraction")])
    graph(s,"psd",1.75,3.45)
    text(s,5.32,["Shared RF inputs: VNA L5 + 36 dB FET, Tn = 3.955 K, equal main/image RF PSD as an unverified hypothesis.",
                 "Common mask covers 96.002% of bins. |IF| < 100 kHz lacks tabulated hardware response. Main, folding and ADC aliases are tracked separately.",
                 "Step 9D thermal poles use physical IFs 1.250 / 1.248 / 1.256 MHz. The historical toy is preserved."],size=14)

    s=page("Absolute RMS and power in seven resonance bands",
           "Run 680, hybrid and nominal powers integrated over the same spectral mask",
           "Both rows show the same integrals in squared volts and RMS units. The listed central-band improvement compares original A's full FIR window with Step 9D's virtually complete FIR-weight coverage on the common mask. The estimators and support distinction are explicit. No gain has been rescaled to fit run 680.",
           [("Seven physical bands, measured and predicted masked powers","step9d/integrals.csv","region=FIR; offset_hz,observed_common_V2,hybrid_common_V2,nominal_common_V2"),
            ("Original and nominal central-band residuals","step9c/powers.csv","FIR; offset_hz=0; scenario=A; data_over_model_dB"),
            ("Original and nominal central-band residuals and mask weights","step9d/integrals.csv","FIR; offset_hz=0; data_over_nominal_dB,FIR_weight_covered")])
    graph(s,"bands",1.53,4.56)
    residual=" / ".join(f'{float(pick(intervals,m,"FIR")["data_over_nominal_dB"]):.2f}' for m in MODES)
    original=" / ".join(f'{float(pick(comp,m,"FIR","A")["data_over_model_dB"]):.2f}' for m in MODES)
    text(s,6.14,[f"Central run/model excess (dB), TM010/011/012: {original} original A → {residual} nominal.",
                 "Original A uses the full FIR window. The common mask retains virtually all central FIR weight."],size=12)

    s=page("TM010 calibration and science differ near DC",
           "Tone transfer is measured in signed bins. Science shows a depression in both quadratures.",
           "The right panel uses each tone quadrature's own shoulders at ±1.033 MHz and each science quadrature's own plateau. The calibration ratio from the independent check is 1.897 and the error is +41.13 degrees at +49.18 kHz. A conditional diagonal PSD uses H+(f) from the +f tone and the conjugate from the −f tone. This is neither secondary RF folding nor a full matrix determination.",
           [("Absolute main, conjugate and pair transfer","step9e/tones.csv","TM010; unaliased=1; |input_IF_hz|≤550000; Hplus_power,conjugate_transfer_power,pair_transfer_power"),
            ("Separate tone quadratures and leakage at ±49.18 kHz","step9e/iq_checks.csv","TM010; I_gain_RMS,Q_gain_RMS,chunk_ratio,quadrature_error_deg"),
            ("Science quadrature band powers","step9e/science_bands.csv","TM010; low_hz,high_hz,I_power_over_own_plateau,Q_power_over_own_plateau"),
            ("Spacing and physical interpretation","step9e/README.md","Confronti science, Step 7 e Step 8")])
    graph(s,"iq",1.70,3.55)
    text(s,5.34,["At ±49.18 kHz the tone retains ≈92% of I and ≈25% of Q shoulder power. The main + conjugate sum retains ≈58%.",
                 "Science suppresses both I and Q near DC. The ≈98.36 kHz tone spacing cannot resolve the ≈25 kHz-wide science feature."],size=14)

    s=page("The remaining laboratory measurements",
           "Independent RF gain and image folding explain part of the absolute discrepancy",
           "The nominal model reduces the central residual under its assumed hardware routing, RF PSD and operating conditions. No fitted gain, temperature or cable attenuation was used. The archived data and original 53 pages remain unchanged.",
           [("Residuals on the common seven-band mask","step9d/integrals.csv","FIR; offset_hz=0; data_over_nominal_dB"),
            ("RF calibration uncertainties","step9a/README.md","Inventario e dati mancanti; Temperatura, guadagno e piani di riferimento"),
            ("Manufacturer coverage and routing uncertainty","step9b/README.md","Dati e dominio di validità; Configurazioni e percorsi"),
            ("Missing complex I/Q calibration and different settings","step9e/README.md","Confronti science, Step 7 e Step 8"),
            ("Laboratory measurement scope","hardware/README.md","Proposed hardware characterization — future work only")])
    text(s,1.86,["Recover the original noise-source curves, fit uncertainties and measurement planes. Measure the tone level at the Marki and the installed FET response.",
                 "Verify I/Q BPF routing, splitter terminations, FEMTO bandwidth/coupling, and delivered LO power and phase.",
                 "Measure loaded complex I/Q responses for tones in both signed sidebands, with dense spacing near DC and the actual science settings.",
                 "Measure input noise in both RF bands and characterize response below 100 kHz. This tests the equal-PSD assumption independently.",
                 "The remaining central excess is 0.83 / 0.46 / 0.77 dB (TM010/011/012). No gain, temperature or cable attenuation was fitted."],size=17)
    assert len(deck.slides)==12 and {r["slide"] for r in ledger}==set(range(54,66))
    return deck,ledger


def append_pptx(base, patch, out):
    target, new = Presentation(base), Presentation(patch)
    rns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    for src in new.slides:
        dst = target.slides.add_slide(target.slide_layouts[6])
        dst.background.fill.solid()
        dst.background.fill.fore_color.rgb = sd.rgb(sd.BG)
        for shape in src.shapes:
            el = copy.deepcopy(shape.element)
            for node in el.iter():
                old = node.get(rns+"embed")
                if old:
                    rel = src.part.rels[old]
                    assert rel.reltype.endswith("/image")
                    _, new_id = dst.part.get_or_add_image_part(io.BytesIO(rel.target_part.blob))
                    node.set(rns+"embed",new_id)
            dst.shapes._spTree.insert_element_before(el,"p:extLst")
        dst.notes_slide.notes_text_frame.text = src.notes_slide.notes_text_frame.text
    # Preserve every original package member except the three append indexes.
    editable = {"[Content_Types].xml","ppt/presentation.xml","ppt/_rels/presentation.xml.rels"}
    intermediate = io.BytesIO()
    target.save(intermediate)
    with ZipFile(base) as old, ZipFile(intermediate) as candidate, ZipFile(out,"w",compression=8) as merged:
        old_names = set(old.namelist())
        assert old_names <= set(candidate.namelist())
        for name in candidate.namelist():
            merged.writestr(name,(old if name in old_names-editable else candidate).read(name))
    with ZipFile(base) as old, ZipFile(out) as result:
        unchanged = old_names-editable
        assert all(old.read(name)==result.read(name) for name in unchanged)
    old, final = Presentation(base), Presentation(out)
    assert len(old.slides)==COUNT and len(final.slides)==TOTAL
    assert [s.part.partname for s in old.slides]==[s.part.partname for s in list(final.slides)[:COUNT]]
    for src,dst in zip(new.slides,list(final.slides)[COUNT:]):
        assert [s.text for s in src.shapes if s.has_text_frame]==[s.text for s in dst.shapes if s.has_text_frame]
        assert src.notes_slide.notes_text_frame.text==dst.notes_slide.notes_text_frame.text
        assert [s.image.blob for s in src.shapes if s.shape_type == 13] == [
            s.image.blob for s in dst.shapes if s.shape_type == 13]
    return len(unchanged)


def compare_rendering(base, final, temp):
    for p,stem in ((base,"baseline"),(final,"final")):
        subprocess.run(["pdftoppm","-r","63","-f","1","-l",str(COUNT),"-png",str(p),str(temp/stem)],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    for i in range(1,COUNT+1):
        with Image.open(temp/f"baseline-{i:02d}.png") as a, Image.open(temp/f"final-{i:02d}.png") as b:
            assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None, i


def build(base_dir, out):
    pdf,pptx=(base_dir/f"iq_noise_summary_v47_1.{ext}" for ext in ("pdf","pptx"))
    assert sha(pdf)==FROZEN["pdf"] and sha(pptx)==FROZEN["pptx"]
    out.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix="v48-") as d:
        temp=Path(d)
        assets=make_figures(temp/"assets")
        deck,ledger=slides(assets)
        extension=temp/"part_iv"
        sd.export(deck,extension,"v48_part_iv","17 November 2026",page_offset=COUNT,total_pages=TOTAL)
        shutil.copy2(extension/"contact_sheet.png",out/"part_iv_contact_sheet.png")
        final_pdf=out/"iq_noise_summary_v48.pdf"
        final_pptx=out/"iq_noise_summary_v48.pptx"
        writer=PdfWriter(pdf,incremental=True)
        writer.append_pages_from_reader(PdfReader(extension/"iq_noise_summary_v48_part_iv.pdf"))
        with final_pdf.open("wb") as stream:
            writer.write(stream)
        assert final_pdf.read_bytes().startswith(pdf.read_bytes())
        old,final=PdfReader(pdf),PdfReader(final_pdf)
        assert len(old.pages)==COUNT and len(final.pages)==TOTAL
        assert all(a.get_contents().get_data()==b.get_contents().get_data()
                   for a,b in zip(old.pages,final.pages))
        compare_rendering(pdf,final_pdf,temp)
        members=append_pptx(pptx,extension/"iq_noise_summary_v48_part_iv.pptx",final_pptx)
        new=Presentation(final_pptx)
        for i,s in enumerate(deck.slides,COUNT):
            assert new.slides[i].shapes[1].text.replace("\n"," ")==s["title"]
            normalize = lambda value: "".join(c for c in value if c.isalnum())
            assert normalize(s["title"]) in normalize(final.pages[i].extract_text()), i+1
    with (out/"slide_observable_provenance.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(ledger)
    report=dict(base_commit="1b2cb10",approved_steps_commit="a418b23",baseline_hashes=FROZEN,
                pdf_pages=TOTAL,pptx_slides=TOTAL,preserved_pages=COUNT,appendix_pages=12,
                original_pdf_exact_prefix=True,pdf_content_streams_exact=53,pdf_pixel_identity_at_63_dpi=53,
                original_pptx_native_slides_and_order_exact=53,pptx_original_members_unchanged=members,
                allowed_pptx_differences=["[Content_Types].xml","ppt/presentation.xml","ppt/_rels/presentation.xml.rels"],
                explicit_observables=len(ledger),raw_reads=0,fits=0,simulations=0,
                output_hashes={p.name:sha(p) for p in (final_pdf,final_pptx)})
    (out/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"validation_report.md").write_text(f"""# v48 validation report

- Both files contain 65 pages or native slides. Part IV occupies 54–65.
- The two v47.1 inputs match the archived SHA-256 values recorded in validation.json.
- The complete original PDF is an exact byte prefix of v48. All 53 original content streams match and Poppler renders all 53 original pages pixel-identically at 63 dpi.
- All 53 PPTX slide parts retain their original bytes and order. {members} original ZIP members, including notes, masters, layouts and media, match byte for byte. The three shared package indexes are updated for the append.
- All 12 new page titles were checked in both outputs. Native slide text and notes match the appendix renderer.
- {len(ledger)} explicit slide/observable source selections record the approved repository paths, source SHA-256 and exact field or section selectors.
- The build reads only the frozen presentation and approved Step 9 inputs. Raw reads, calibration fits and simulations are zero.
""")
    print("Verified v48 append",report,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    build(args.baseline,args.output)
