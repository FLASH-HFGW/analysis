"""Review figures/tables for the separate run680 resonance pilot; no fits or raw reads."""
from pathlib import Path
import argparse,csv,json,hashlib
import numpy as np,h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.signal import freqz
from scipy.stats import rayleigh
from iq_acquisition_metadata import MODES
DATA='#007F86';NAVY='#263952';OFF=np.array([-500,-250,-100,0,100,250,500]);LS=['-','--',':','-.',(0,(6,2)),(0,(2,2)),(0,(1,1))]

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--preview',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    pre=json.loads(a.preview.read_text());rows=[];details={};pdf=PdfPages(a.output/'run680_resonance_review.pdf')
    plt.rcParams.update({'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'legend.fontsize':6.5,'axes.grid':True,'grid.alpha':.2,'lines.linewidth':.9})
    def grid(nr=2,nc=3):
        f,x=plt.subplots(nr,nc,figsize=(12.8,7),squeeze=False);f.subplots_adjust(left=.07,right=.98,top=.88,bottom=.1,hspace=.6,wspace=.35);return f,x
    def finish(fig,name,title,scope):
        fig.suptitle(title,fontsize=15,y=.965);fig.text(.5,.925,scope,ha='center',fontsize=9);fig.text(.06,.025,'Data in ADC-equivalent volts. No post-demodulation centering, fitted gain, new physical model or full-campaign reconstruction.',fontsize=8);fig.savefig(a.output/(name+'.png'),dpi=170);pdf.savefig(fig);plt.close(fig)
    with h5py.File(a.input,'r') as h:
        root=h['filter_banks/resonance_ROI'];config=root['configuration'];coeff=config['FIR_coefficients'][:];fs=float(h['summary/fs_hz'][()]);outfs=float(h['summary/filtered_fs_hz'][()]);duration=float(h['summary/acquired_duration_s'][()]);rms={};power={};selected={}
        for m in MODES:
            groups=[root[f'modes/{m}/band_{bi:02d}'] for bi in range(7)];rms[m]=[];power[m]=[]
            for bi,g in enumerate(groups):
                mm=g['moments_ADC'];P=float(mm['total_squared_v2'][()]);r=np.sqrt(P);mu=complex(mm['mean_i_v'][()],mm['mean_q_v'][()]);count=int(mm['n'][()]);sigma=np.sqrt(float(mm['ac_squared_v2'][()])/2);expected=pre['modes'][m]['predicted_band_power_V2'][bi]
                row={'mode':m,'offset_hz':int(OFF[bi]*1000),'center_IF_hz':float(g['input_center_hz'][()]),'samples_filtered':count,'RMS_ADC_V':float(r),'AC_RMS_ADC_V':float(mm['ac_rms_v'][()]),'DC_abs_ADC_V':float(abs(mu)),'mean_I_ADC_V':mu.real,'mean_Qeff_ADC_V':mu.imag,'power_ADC_V2':P,'moment_sigma_q_ADC_V':float(sigma),'amplitude_mean_ADC_V':float(g['amplitude_mean_V'][()]),'existing_PSD_predicted_RMS_ADC_V':float(np.sqrt(expected)),'power_relative_to_PSD_prediction':float(P/expected-1),'amplitude_histogram_count':int(g['amplitude_counts'][:].sum())}
                assert row['amplitude_histogram_count']==count;rows.append(row);power[m].append(P);rms[m].append(r)
            side=np.mean(np.array(power[m])[[0,1,2,4,5,6]]);details[m]={'central_over_mean_six_side_power':power[m][3]/side,'symmetric_power_ratios':{str(d):power[m][6-i]/power[m][i] for i,d in enumerate([500,250,100])},'shared_plus1MHz':{k:h[f'consistency_with_electronic_bank/{m}/{k}'][()].item() if isinstance(h[f'consistency_with_electronic_bank/{m}/{k}'][()],np.generic) else h[f'consistency_with_electronic_bank/{m}/{k}'][()] for k in h[f'consistency_with_electronic_bank/{m}']}}
        fig,axs=grid()
        old=Path(h['filter_banks/electronic_DC_reference/source_HDF5'].asstr()[()])
        with h5py.File(old,'r') as legacy:
            for mi,m in enumerate(MODES):
                ax=axs[0,mi];ax.plot(OFF,np.array(rms[m])*1000,'o-',color=DATA,label='New full-run RMS');ax.plot(OFF,np.array(pre['modes'][m]['predicted_band_RMS_V'])*1000,'s--',mfc='white',color=NAVY,label='Existing-PSD prediction');ax.set(title=m,xlabel='Offset from BOR resonance [kHz]',ylabel='RMS [mV ADC]');ax.legend()
                g=root[f'modes/{m}/band_01'];new=g['events/RMS_ADC_V'][:];cor=float(h[f'acquisition_metadata/modes/{m}/ADC_peak_V'][()])/float(legacy['summary/input_range_v'][()]);oldr=legacy[f'filtered_bands/modes/{m}/band_08/events/rms_v'][:]*cor
                ax=axs[1,mi];ax.plot(np.arange(len(new))*duration/len(new),(new/oldr-1)*1e9,color=DATA);ax.set(title=m+' shared +1 MHz control',xlabel='Acquired run time [s]',ylabel='Relative RMS difference [1e-9]')
        finish(fig,'RMS_and_shared_band','Absolute resonance-band levels and shared-band verification','Full run 680: 209.7152 s input, 1000 SPEC; old electronic +1 MHz = new resonance offset −250 kHz.')
        fig,axs=grid()
        for mi,m in enumerate(MODES):
            ax=axs[0,mi];freq=np.linspace(.65e6,1.85e6,9000)
            for bi,off in enumerate(OFF):
                center=float(root[f'modes/{m}/band_{bi:02d}/input_center_hz'][()]);_,hh=freqz(coeff,worN=2*np.pi*(freq-center)/fs);ax.plot(freq/1e6,abs(hh)**2,color=NAVY,ls=LS[bi],label=f'{off:+g}kHz')
            ax.set(title=m+' actual digital FIR responses',xlabel='Input complex IF [MHz]',ylabel='Power transfer |H|²',ylim=(-.03,1.07));ax.legend(ncol=3)
            ax=axs[1,mi]
            for bi,off in enumerate(OFF):
                g=root[f'modes/{m}/band_{bi:02d}'];f=g['PSD_frequency_baseband_hz'][:];psd=g['PSD_total_V2_Hz'][:];ax.plot(f/1000,10*np.log10(np.maximum(psd,1e-30)),color=DATA,ls=LS[bi],label=f'{off:+g}kHz')
            ax.set(title=m+' filtered output PSD',xlabel='Frequency relative to each band [kHz]',ylabel='PSD [dB V²/Hz ADC]',xlim=(-70,70),ylim=(-235,-90));ax.legend(ncol=3)
        finish(fig,'PSD_and_filters','Measured filtered PSD and the implemented filter response','FIR plots are numerical transfer functions, not fitted analog responses. Full-run Welch PSD: detrend=False.')
        fig,axs=grid()
        for mi,m in enumerate(MODES):
            ax=axs[0,mi]
            for bi,off in enumerate(OFF):
                g=root[f'modes/{m}/band_{bi:02d}'];e=g['amplitude_edges_V'][:];c=g['amplitude_counts'][:];ax.stairs(np.maximum(c/c.sum()/np.diff(e)/1000,1e-14),e*1000,color=DATA,ls=LS[bi],label=f'{off:+g}kHz')
            sigma=np.sqrt(power[m][3]/2);xx=np.linspace(0,max(rms[m])*6,400);ax.plot(xx*1000,rayleigh(scale=sigma).pdf(xx)/1000,color=NAVY,label='Central moment Rayleigh');ax.set(title=m+' full-run amplitude density',xlabel='Raw filtered amplitude [mV ADC]',ylabel='Density [mV^-1]',yscale='log',ylim=(1e-7,2),xlim=(0,20));ax.legend(ncol=2)
            z=root[f'modes/{m}/band_03/selected_first5SPEC_output_V'][:];ax=axs[1,mi];z=z[:5000];ax.plot(z.real*1000,z.imag*1000,'.',color=DATA,alpha=.2,ms=1.6);lim=4*max(max(v) for v in rms.values())*1000;ax.set(title=m+' central-band selected IQ',xlabel='I [mV ADC]',ylabel='Qeff [mV ADC]',xlim=(-lim,lim),ylim=(-lim,lim));ax.set_aspect('equal',adjustable='box')
        finish(fig,'amplitudes_and_IQ','Amplitude distributions without output-mean subtraction','Histograms: all 52,428,700 filtered samples per band. IQ: 5000 points from first 5 SPEC. Navy: moment reference, no fit.')
        fig,axs=grid()
        # White input shaped by the known FIR: an estimator/filter check, no cavity fit.
        ac=np.correlate(coeff,coeff,'full')[len(coeff)-1:];expected_g=ac[::20]/ac[0];lag_ref=np.arange(len(expected_g))/outfs
        for mi,m in enumerate(MODES):
            for bi,off in enumerate(OFF):
                g=root[f'modes/{m}/band_{bi:02d}'];lag=g['selected_lag_s'][:];co=g['selected_total_g1'][:];ok=lag<=200e-6
                axs[0,mi].plot(lag[ok]*1e6,co.real[ok],marker='o',ms=2,color=DATA,ls=LS[bi],label=f'{off:+g}kHz');axs[1,mi].plot(lag[ok]*1e6,co.imag[ok],marker='s',mfc='white',ms=2,color=DATA,ls=LS[bi])
            axs[0,mi].plot(lag_ref*1e6,expected_g,color=NAVY,lw=1.5,label='White PSD × FIR');axs[0,mi].set(title=m+' Re total g1',xlabel='Lag [us]',ylabel='Re R[k]/R[0]',xlim=(0,200),ylim=(-.4,1.05));axs[0,mi].legend(ncol=3,fontsize=5)
            axs[1,mi].set(title=m+' Im total g1',xlabel='Lag [us]',ylabel='Im R[k]/R[0]',xlim=(0,200),ylim=(-.015,.015));axs[1,mi].axhline(0,color=NAVY,lw=.6)
        finish(fig,'complex_autocorrelation','Complex total autocorrelation: physical mean retained','First 5 input SPEC (1.048576 s); markers every 4 us. Correlation times reflect the 50 kHz filter, not intrinsic cavity decay.')
        fig,axs=grid()
        for mi,m in enumerate(MODES):
            ds=[100,250,500];vals=[details[m]['symmetric_power_ratios'][str(d)] for d in ds];ax=axs[0,mi]
            ax.plot(ds,vals,'o-',color=DATA);ax.axhline(1,color=NAVY,ls=':');ax.set(title=m+' central / mean six sides = '+f"{details[m]['central_over_mean_six_side_power']:.5f}",xlabel='Symmetric offset [kHz]',ylabel='P(+offset) / P(-offset)',ylim=(.96,1.07),xticks=ds)
            ax=axs[1,mi];ax.axis('off');cells=[[f'{int(off):+d}',f'{1000*rms[m][bi]:.6f}',f'{1e6*power[m][bi]:.6f}'] for bi,off in enumerate(OFF)]
            tab=ax.table(cellText=cells,colLabels=['Offset [kHz]','RMS [mV ADC]','Power [mV² ADC]'],loc='center',cellLoc='center');tab.auto_set_font_size(False);tab.set_fontsize(9);tab.scale(1,1.7)
        finish(fig,'ratios_and_absolute_values','Central and symmetric resonance-band power ratios','Complete run 680. Central/side uses the arithmetic mean of six noncentral resonance-band powers; all output means retained.')
        # Seven rows x three columns, all bands individually visible for detailed review.
        for mi,m in enumerate(MODES):
            fig,axs=plt.subplots(7,3,figsize=(12.8,14));fig.subplots_adjust(left=.07,right=.985,top=.93,bottom=.045,hspace=.65,wspace=.35)
            for bi,off in enumerate(OFF):
                g=root[f'modes/{m}/band_{bi:02d}'];e=g['amplitude_edges_V'][:];c=g['amplitude_counts'][:];axs[bi,0].stairs(c/c.sum()/np.diff(e)/1000,e*1000,color=DATA);axs[bi,0].set(title=f'{off:+g}kHz amplitude',xlabel='A [mV ADC]',ylabel='Density [mV^-1]',xlim=(0,max(rms[m])*5*1000))
                f=g['PSD_frequency_baseband_hz'][:];pp=g['PSD_total_V2_Hz'][:];axs[bi,1].plot(f/1000,10*np.log10(np.maximum(pp,1e-30)),color=DATA);axs[bi,1].set(title='Full-run filtered PSD',xlabel='Relative frequency [kHz]',ylabel='dB V²/Hz',xlim=(-60,60))
                lag=g['selected_lag_s'][:]*1e6;co=g['selected_total_g1'][:];idx=lag<=150;axs[bi,2].plot(lag[idx],co.real[idx],'o-',ms=2,color=DATA,label='Re');axs[bi,2].plot(lag[idx],co.imag[idx],'s--',ms=2,mfc='white',color=DATA,label='Im');axs[bi,2].set(title='Selected total g1',xlabel='Lag [us]',ylabel='g1',ylim=(-.4,1.05));axs[bi,2].legend()
            fig.suptitle(m+' — seven resonance bands, separate diagnostics',fontsize=15,y=.98);fig.savefig(a.output/(m+'_all_bands.png'),dpi=130);pdf.savefig(fig);plt.close(fig)
        summary={'scope':'run680 complete only;no260-runreconstruction;v46paused','input_duration_s':duration,'filtered_samples_per_band':int(root['modes/TM010/band_03/moments_ADC/n'][()]),'filtered_sample_interval_s':1/outfs,'bands':rows,'mode_ratios':details,'ratio_definition':'central power / arithmetic mean of six noncentral resonance-band powers; symmetric +offset / -offset','no_post_demodulation_mean_subtraction':True,'no_physical_fit':True,'autocorrelation_scope':'first5SPEC,uncentered total covariance;not a full-run or intrinsic cavity fit','electronic_reference_source':str(old)}
    pdf.close();(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with open(a.output/'band_statistics.csv','w') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    (a.output/'README.md').write_text('# Run680 resonance-bank review\n\nFull-run voltage moments, amplitude histograms and Welch PSD; selected first-five-SPEC total complex autocorrelation. No output centering or physical fit.\n\nSee `band_statistics.csv`, `summary.json`, and `run680_resonance_review.pdf`. The existing electronic +1MHz bank is the exact shared control at resonance offset−250kHz. The central/side ratio averages six resonance-side powers and is different from the historical eight-electronic-side definition.\n\nAll units are ADC-equivalent volts; no input-referred gain is applied. The generic ComplexMoments gain=1 legacy `_input_` fields within `moments_ADC` are aliases of ADC quantities, not cavity-input calibration, and are not used by this review.\n')
    print(json.dumps({'output':str(a.output),'RMS_central_mV':{m:1000*rms[m][3] for m in MODES},'ratios':details},indent=2))
if __name__=='__main__':main()
