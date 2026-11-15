"""Editable calibration reference-plane diagram; the injection node is unresolved."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def draw(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 fig,ax=plt.subplots(figsize=(13,5));ax.set_xlim(0,13);ax.set_ylim(0,5);ax.axis('off')
 boxes=[(.25,2.35,2.5,'Cavity + readout line','Gline ≈ 67.4 dB','#007F86'),(3.2,2.35,2.3,'External RF FET','GFET ≈ 36 dB','#D98726'),(6.2,2.35,3.0,'I/Q conversion + filters','Mode-dependent response','#7657A6'),(10,2.35,2.7,'ADC / recorded counts','Calibration ±5 V; science ±2 V','#14283F')]
 for x,y,w,title,body,color in boxes:
  ax.add_patch(Rectangle((x,y),w,1.1,facecolor='#F5F7FB',edgecolor=color,lw=2));ax.text(x+w/2,y+.76,title,ha='center',fontsize=11,fontweight='bold',color=color);ax.text(x+w/2,y+.30,body,ha='center',fontsize=9)
 for start,end in [(2.75,3.2),(5.5,6.2),(9.2,10)]:ax.annotate('',xy=(end,2.9),xytext=(start,2.9),arrowprops=dict(arrowstyle='->',lw=1.6,color='#14283F'))
 ax.plot([2.95,2.95],[1.6,2.9],'--',color='#D98726',lw=2);ax.plot([5.85,5.85],[1.6,2.9],'--',color='#D98726',lw=2)
 ax.text(2.95,1.38,'A: upstream of FET',ha='center',fontsize=11,color='#D98726');ax.text(5.85,1.38,'B: downstream of FET',ha='center',fontsize=11,color='#D98726')
 ax.text(6.5,4.5,'Toy simulation: which stages are already included in kz(f)?',ha='center',fontsize=17,fontweight='bold',color='#14283F')
 ax.text(6.5,.72,'Calibration tone: −60 dBm. Its injection node relative to the external FET must be confirmed.',ha='center',fontsize=12)
 ax.text(6.5,.25,'If injected at A, kz includes the FET. If injected at B, the FET remains a separate gain stage.',ha='center',fontsize=12,color='#14283F')
 fig.tight_layout()
 for ext in ('png','svg','pdf'):fig.savefig(out/f'calibration_reference_planes.{ext}',dpi=180,bbox_inches='tight')
 plt.close(fig)
if __name__=='__main__':draw('/home/mazzitel/HFGW/analysis-work/Run2/reports/iq_noise_summary_v22/assets')
