"""Shared editable PPTX/PDF renderer for the IQ-noise scientific slides."""
import json
import math
from pathlib import Path
import sys
DEPS=Path('/tmp/codex-pptx-deps')
if DEPS.exists():sys.path.insert(0,str(DEPS))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle
from matplotlib import font_manager
from PIL import Image, ImageFont
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
W,H=13.333333,7.5
COLORS=['#007F86','#7657A6','#D98726']
NAVY,INK,MUTED,BG='#14283F','#24364B','#66768A','#F5F7FB'
FONT=font_manager.findfont('DejaVu Sans')

def wrap(text,width,size,bold=False):
    font=ImageFont.truetype(FONT,size=round(size*144/72))
    limit=width*144
    lines=[]
    for paragraph in text.split('\n'):
        if not paragraph:lines.append('');continue
        current=''
        for word in paragraph.split():
            candidate=(current+' '+word).strip()
            if current and font.getlength(candidate)>limit:lines.append(current);current=word
            else:current=candidate
        lines.append(current)
    return '\n'.join(lines)


class Deck:
    def __init__(self):self.slides=[]
    def new(self,title,subtitle='',source='',notes=''):
        slide={'title':title,'subtitle':subtitle,'source':source,'notes':notes,'items':[]};self.slides.append(slide)
        self.rect(slide,0,0,W,.075,'#007F86')
        self.text(slide,.55,.38,12.2,.7,title,30,bold=True,color=NAVY)
        if subtitle:self.text(slide,.58,1.12,12.1,.5,subtitle,14,color=MUTED)
        return slide
    def rect(self,s,x,y,w,h,color):s['items'].append({'kind':'rect','x':x,'y':y,'w':w,'h':h,'color':color})
    def text(self,s,x,y,w,h,text,size=19,bold=False,color=INK):
        wrapped=wrap(text,w,size,bold)
        needed=len(wrapped.splitlines())*size*1.15/72
        if needed>h+.12:raise ValueError(f'Text overflow on {s["title"]}: {text[:60]}, needs {needed:.2f} in, got {h}')
        if x+w>W+.01 or y+h>H+.01:raise ValueError('Item outside slide')
        s['items'].append(dict(kind='text',x=x,y=y,w=w,h=h,text=wrapped,size=size,bold=bold,color=color))
    def image(self,s,x,y,w,h,path):
        with Image.open(path) as im:ratio=im.width/im.height
        if w/h>ratio:nw=h*ratio; x+=(w-nw)/2;w=nw
        else:nh=w/ratio;y+=(h-nh)/2;h=nh
        s['items'].append(dict(kind='image',x=x,y=y,w=w,h=h,path=str(path)))
    def bullets(self,s,x,y,w,items,size=19,gap=.18):
        for text in items:
            wrapped=wrap(text,w-.25,size);height=len(wrapped.splitlines())*size*1.17/72+.05
            self.text(s,x,y,.18,height,'•',size,color=COLORS[0]);self.text(s,x+.25,y,w-.25,height,text,size)
            y+=height+gap
    def card(self,s,x,y,w,value,label,color=COLORS[0]):
        self.rect(s,x,y,w,1.08,'#FFFFFF');self.text(s,x+.18,y+.14,w-.36,.48,value,28,True,color);self.text(s,x+.18,y+.71,w-.36,.28,label,12,color=MUTED)


def rgb(color):return RGBColor.from_string(color.lstrip('#'))


def export(deck,out,version="v6",prepared="8 November 2026"):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    stem="iq_noise_summary_"+version
    prs=Presentation();prs.slide_width=Inches(W);prs.slide_height=Inches(H)
    pdf=PdfPages(out/(stem+'.pdf'))
    md=[f'# Three-resonance IQ noise analysis — draft {version}','',
        f'Prepared: {prepared}. Acquisition: 24–25 July 2026.','',
        'Native text and shapes are editable in the PPTX. Scientific plots are generated from the saved numeric outputs.','']
    previews=[]
    for idx,s in enumerate(deck.slides,1):
        slide=prs.slides.add_slide(prs.slide_layouts[6]);slide.background.fill.solid();slide.background.fill.fore_color.rgb=rgb(BG)
        fig=plt.figure(figsize=(W,H),facecolor=BG)
        for item in s['items']:
            x,y,w,h=[item[k] for k in ('x','y','w','h')]
            if item['kind']=='rect':
                sh=slide.shapes.add_shape(1,Inches(x),Inches(y),Inches(w),Inches(h));sh.fill.solid();sh.fill.fore_color.rgb=rgb(item['color']);sh.line.fill.background()
                fig.add_artist(Rectangle((x/W,1-(y+h)/H),w/W,h/H,transform=fig.transFigure,color=item['color'],linewidth=0))
            elif item['kind']=='image':
                slide.shapes.add_picture(item['path'],Inches(x),Inches(y),width=Inches(w),height=Inches(h))
                ax=fig.add_axes([x/W,1-(y+h)/H,w/W,h/H]);ax.imshow(Image.open(item['path']));ax.axis('off')
            else:
                sh=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=sh.text_frame
                tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0;tf.word_wrap=False
                for n,line in enumerate(item['text'].split('\n')):
                    p=tf.paragraphs[0] if n==0 else tf.add_paragraph();p.text=line;p.space_before=Pt(0);p.space_after=Pt(0);p.line_spacing=1.15
                    p.font.name='Arial';p.font.size=Pt(item['size']);p.font.bold=item['bold'];p.font.color.rgb=rgb(item['color'])
                fig.text(x/W,1-y/H,item['text'],ha='left',va='top',fontsize=item['size'],fontweight='bold' if item['bold'] else 'normal',color=item['color'],linespacing=1.15)
        footer=s.get('footer',f'IQ NOISE STUDY  |  PRELIMINARY · {version}')
        for x,text,width in ((.58,footer,5.3),(12.0,f'{idx:02d} / {len(deck.slides):02d}',.8)):
            sh=slide.shapes.add_textbox(Inches(x),Inches(7.12),Inches(width),Inches(.2));sh.text_frame.margin_top=0;sh.text_frame.margin_left=0;p=sh.text_frame.paragraphs[0];p.text=text;p.font.size=Pt(8);p.font.name='Arial';p.font.color.rgb=rgb(MUTED)
            fig.text(x/W,1-7.12/H,text,fontsize=8,va='top',color=MUTED)
        source=wrap(s['source'],11.8,7.5)
        sh=slide.shapes.add_textbox(Inches(.58),Inches(6.91),Inches(12),Inches(.18));sh.text_frame.margin_top=0;sh.text_frame.margin_left=0;p=sh.text_frame.paragraphs[0];p.text=source;p.font.size=Pt(7.5);p.font.name='Arial';p.font.color.rgb=rgb(MUTED)
        fig.text(.58/W,1-6.91/H,source,fontsize=7.5,va='top',color=MUTED)
        slide.notes_slide.notes_text_frame.text=s['notes']+'\n\n'+s['source']
        pdf.savefig(fig,dpi=160)
        preview=out/f'slide_{idx:02d}.png';fig.savefig(preview,dpi=100,facecolor=BG);previews.append(preview);plt.close(fig)
        md.extend([f'## {idx:02d}. {s["title"]}','',s['subtitle'],''])
        for item in s['items']:
            if item['kind']=='text' and item['text'] not in (s['title'],s['subtitle']):md.extend([item['text'].replace('\n',' '),''])
        md.extend(['Speaker notes: '+s['notes'],'','Data: '+s['source'],''])
    pdf.close();prs.save(out/(stem+'.pptx'))
    (out/'slides_en.md').write_text('\n'.join(md)+'\n')
    (out/'slide_model.json').write_text(json.dumps(deck.slides,indent=2,ensure_ascii=False)+'\n')
    thumbs=[]
    for path in previews:
        with Image.open(path) as im:thumbs.append(im.resize((640,360)))
    sheet=Image.new('RGB',(640*3,360*math.ceil(len(previews)/3)),'white')
    for n,im in enumerate(thumbs):sheet.paste(im,((n%3)*640,(n//3)*360))
    sheet.save(out/'contact_sheet.png')
    print(f'Created {len(deck.slides)} slides: PPTX, PDF, Markdown and previews in {out}')
