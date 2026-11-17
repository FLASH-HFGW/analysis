"""Hardware documentation update only: reuse frozen v41 and step 8 products."""
import argparse, copy, hashlib, json, shutil, sys
from pathlib import Path
sys.path.insert(0, '/tmp/v18-python-deps')
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'reporting'))
import slide_deck as sd
ROOT=REPO.parent/'analysis-work/Run2'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def slide(d,title,subtitle='',notes=''):
    s=d.new(' ',subtitle,'Hardware inventory: docs/hardware/README.md; original chain slides 1–2; manufacturer pages cited in notes.',notes)
    s['title']=title;s['items'][1]['text']=title;s['items'][1]['size']=25
    return s

def box(d,s,x,y,w,h,title,body,color=sd.COLORS[0]):
    d.rect(s,x,y,w,h,'#FFFFFF');d.rect(s,x,y,w,.06,color)
    d.text(s,x+.1,y+.13,w-.2,.3,title,13,True,color)
    d.text(s,x+.1,y+.52,w-.2,h-.55,body,11)

def chain():
    d=sd.Deck();s=slide(d,'Acquisition chain — documented hardware','Functional routing; installed wiring and switch states are not independently verified.',
        'Original QUAX_multimode_v2.pptx slides 1–2. Marki pp.4–5; FEMTO pp.1–4; ZSC/SIF/BLP p.1; SBP pp.1–2; ZAD pp.1–2. Original I-side BPF labels appear transposed. Fourth splitter port termination unknown. Model alternatives in RF block must not be interpreted as cascading. No gain, loss or response is added to kz. ADC logical mode pairs shown without adopting unverified original channel numbering.')
    box(d,s,.6,1.8,3.75,1.35,'Cavity → cryogenic chain','QuinStar QCY-G0801202; Silent Waves TWPA\nLNF-LNC4_16B HEMT; operating state unverified')
    box(d,s,4.55,1.8,3.7,1.35,'RF amplification → primary IQ','MITEQ: two alternative IDs in original\nMarki MMIQ-0520H family; LO R&S SMA100B')
    box(d,s,8.45,1.8,4.2,1.35,'I and Q: amplification → division','2 × FEMTO DHPVA-101 → 2 × ZSC-4-1+\nEach splitter is four-way; three mode paths used')
    rows=[('TM010','Direct primary-IF path','No secondary mixer',sd.COLORS[0]),('TM011','2 × SIF-40+ (35–49 MHz)','2 × ZAD-1-1+; secondary LO',sd.COLORS[1]),('TM012','2 × SBP-101+ (94–108 MHz)','2 × ZAD-1-1+; secondary LO',sd.COLORS[2])]
    for n,(mode,bpf,mix,c) in enumerate(rows):
        y=3.6+n*.73;d.text(s,.7,y,1.2,.3,mode,16,True,c)
        d.text(s,2,y,4,.5,bpf,13,color=c);d.text(s,6.15,y,4,.5,mix,12)
        d.text(s,10.1,y,2.5,.5,'→ BLP-1.9+ → ADC',12,color=c)
    d.text(s,.7,6,11.9,.65,'Six final channels: Spectrum NETBOX DN2.592-08, 5 MS/s, 16 bit. Secondary LOs: T3AFG500. BPF assignment follows passbands; original I-side labels need confirmation.',12)
    return d

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output-root',type=Path,default=ROOT/'reports');args=ap.parse_args()
    old=ROOT/'reports/iq_noise_summary_v41_partI/slide_model.json'
    prior=json.loads(old.read_text());out=args.output_root/'iq_noise_summary_v42_partI';out.mkdir(parents=True,exist_ok=True)
    frozen={};d=sd.Deck();d.slides=copy.deepcopy(prior)
    for s in d.slides:
        s['footer']='IQ NOISE STUDY | v42 · hardware documentation update'
        for item in s['items']:
            if item['kind']=='image':
                src=Path(item['path']);dst=out/'assets'/src.name;dst.parent.mkdir(exist_ok=True);shutil.copy2(src,dst)
                frozen[str(src)]=sha(src);item['path']=str(dst)
    d.slides[1]=chain().slides[0]
    d.slides[8]['notes']+=' Hardware update: retain existing kz, ADC scales and gain ledger without change; manufacturer component losses are not applied again. See docs/hardware/README.md.'
    sd.export(d,out,'v42_partI','17 November 2026')
    c=chain();sd.export(c,args.output_root/'iq_noise_chain_v42','v42_chain','17 November 2026')
    e=sd.Deck()
    s=slide(e,'Hardware evidence: what the specifications establish','Discussion insert — place after the unchanged toy/data comparison.',
        'SPEC: ZSC-4-1+ p.1; FEMTO DHPVA-101 pp.1–2; BLP-1.9+ p.1. SETTING: gains 60/20 dB from Valeria communication. MEASURED: step7 DC diagnostics. HYPOTHESIS: splitter attribution unverified.')
    box(e,s,.65,1.85,5.85,2,'ZSC-4-1+: plausible candidate','Specified 0.1–200 MHz, before mode separation.\nBelow 100 kHz the response is unspecified.\nThe band edge does not establish a cutoff or notch width.')
    box(e,s,6.8,1.85,5.85,2,'FEMTO DHPVA-101: important constraints','Nominal AC lower cutoff: 10 Hz.\nManufacturer states gain-independent response.\nNeither establishes a 25 kHz-wide attenuation.')
    e.bullets(s,.75,4.2,11.7,['The 20 kHz FEMTO noise corner concerns added noise, not a high-pass cutoff.','Calibration/acquisition gains differ (60/20 dB); actual coupling and bandwidth switches remain unverified.','Component specifications motivate tests. They do not replace an in-situ chain measurement.'],size=17)
    s=slide(e,'Different mode paths, unresolved hardware details','The splitter acts on primary IF, before secondary downconversion.',
        'Primary IF centers from existing run680/reference records; original chain slide2. Manufacturer specified passbands do not define transfer functions below band. Full model numbers and wiring limitations in hardware inventory.')
    e.bullets(s,.8,1.9,11.7,['TM010 follows the direct low-IF path; TM011 and TM012 reach the splitter near 45 and 105 MHz before secondary mixing.','A primary-IF low-frequency effect can therefore affect the modes differently; this remains a hypothesis.','Resolve original I-side BPF label transposition, fourth-port terminations, RF amplifier identity and installed I/Q routing.','Gain-independent FEMTO response weakens a change of intrinsic LF response caused solely by the gain setting; loading and switch states remain open.'],size=19,gap=.25)
    s=slide(e,'Step 8 remains a phenomenological description','Existing predictions are retained; no hardware parameters are inferred.',
        'Existing step8_LF_initial_20261116 products reused byte-for-byte. Initial fc=12.5 kHz and epsilon=0.02 are phenomenological, not manufacturer splitter parameters. No new fit or response. See original step8 metrics for observables and residual discrepancies.')
    fig=ROOT/'simulation/step8_LF_initial_20261116/PSD_and_complex_correlation.png'
    e.image(s,.65,1.8,8.3,4.8,fig)
    e.text(s,9.15,2,3.45,3.8,'Initial values:\nfc = 12.5 kHz\nepsilon = 0.02\n\nCompare PSD and negative autocorrelation together.\n\nAgreement in shape does not establish a hardware cause.',18)
    s=slide(e,'What remains unexplained','Discrepancies are results, not targets for gain tuning.',
        'Retain previous step7/8 diagnostics and independent-floor versus finite-DC-attenuation interpretations. No new fit, simulation or calibrated transfer function. Step6 absolute normalization remains unchanged.')
    e.bullets(s,.8,1.9,11.7,['Keep the original step 6 reference and its absolute normalization. Measured kz already maps the toy onto the chain.','Do not multiply the datasheet losses or a hypothesized suppression into kz again. Calibration and science responses must be distinguished.','The existing step 8 model does not resolve all mode amplitudes, correlation times and long-time mean-variance behavior.','Finite residual response and noise added at a different location can share a spectrum. I/Q imbalance, DC drift and source position require independent evidence.'],size=19,gap=.24)
    s=slide(e,'Proposed hardware characterization','Future work only — additional laboratory measurements are not possible at this stage.',
        'No measurements are being scheduled or performed. Detailed proposal in docs/hardware/README.md. These measurements discriminate hypotheses; no new fit or transfer function is introduced in this presentation.')
    e.bullets(s,.8,1.85,11.7,['Recover settings and wiring: installed models, port loads, coupling/bandwidth switches, ADC ranges, gain and LO delivery, separately for calibration and science.','Measure complex splitter response below and above 100 kHz with actual loads; compare I/Q outputs, fourth-port terminations and bypass.','Measure FEMTO main-output response and added noise at 20/60 dB, recording coupling, bandwidth, offset and headroom.','Inject a defined signal/noise before and after candidate stages; test full mode paths, mixer LO power and I/Q balance.','Use long terminated-input records to test DC stability, additive noise and the predicted mean-variance crossover.'],size=17,gap=.18)
    dout=args.output_root/'iq_noise_summary_v42_hardware_discussion'
    # Keep the discussion portable, reusing—not recalculating—the scientific figure.
    for s in e.slides:
        for item in s['items']:
            if item['kind']=='image':
                src=Path(item['path']);dst=dout/'assets'/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);frozen[str(src)]=sha(src);item['path']=str(dst)
    sd.export(e,dout,'v42_hardware_discussion','17 November 2026')
    assert all(sha(p)==h for p,h in frozen.items())
    for i in [0,2,3,4,5,6,7,8,9]:
        a=copy.deepcopy(prior[i]);b=copy.deepcopy(d.slides[i]);a.pop('footer',None);b.pop('footer',None)
        if i==8:b['notes']=a['notes']
        for s in (a,b):
            for item in s['items']:
                if item['kind']=='image':item['path']=Path(item['path']).name
        assert a==b, i
    (out/'hardware_update_validation.json').write_text(json.dumps({'unchanged_source_assets':frozen,'unchanged_slides':[1,3,4,5,6,7,8,9,10],'modified_slide':2,'new_scientific_processing':False},indent=2)+'\n')

if __name__=='__main__':main()
