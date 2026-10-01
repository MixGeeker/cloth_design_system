"""Deterministic real-unit pattern exports; PDF pages sized to each cut piece."""
import html
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

def bounds(points):
 return min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)
def path_svg(points):return ' '.join(f'{x:.4f},{y:.4f}' for x,y in points)
def svg_pattern(p,path):
 x0,y0,x1,y1=bounds(p['outline']);w=max(210,x1-x0+40);h=max(150,y1-y0+85+5*len(p.get("seams",{})))
 def points(key):return path_svg([[x-x0+20,y-y0+40] for x,y in p[key]])
 s=f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.4f}mm" height="{h:.4f}mm" viewBox="0 0 {w:.4f} {h:.4f}">'
 s+=f'<title>{html.escape(p["id"])} 1:1 mm toile prototype</title><rect width="100%" height="100%" fill="white"/>'
 s+=f'<text x="10" y="9" font-size="4">{html.escape(p["id"])} | CUT {p["quantity"]} | 1:1 mm | PROTOTYPE</text>'
 s+=f'<text x="40" y="28" font-size="3">Fold: {p.get("cut_on_fold",False)} | mirrored pairs: {p.get("mirrored_pairs",False)}</text>'
 s+='<text x="10" y="16" font-size="3">Solid: cut / Dashed: stitch / Check square: 20 x 20 mm</text>'
 s+='<rect x="10" y="20" width="20" height="20" fill="none" stroke="black" stroke-width="0.25"/>'
 s+=f'<polygon points="{points("outline")}" fill="none" stroke="black" stroke-width="0.4"/>'
 s+=f'<polygon points="{points("stitchline")}" fill="none" stroke="#1677aa" stroke-width="0.3" stroke-dasharray="2 1"/>'
 s+=f'<polyline points="{points("grainline")}" fill="none" stroke="#888" stroke-width="0.3"/>'
 for index,(name,pts) in enumerate(p.get('seams',{}).items(),1):
  if pts:
   guide=path_svg([[x-x0+20,y-y0+40] for x,y in pts])
   s+=f'<polyline points="{guide}" fill="none" stroke="#b34a24" stroke-width="0.35" stroke-dasharray="1 1"/>'
   x,y=pts[len(pts)//2];s+=f'<text x="{x-x0+20:.3f}" y="{y-y0+40:.3f}" font-size="3">S{index}</text>'
   s+=f'<text x="10" y="{y1-y0+55+index*5:.3f}" font-size="3">S{index}: {html.escape(name)} (construction / stitch guide, not cut)</text>'
 Path(path).write_text(s+'</svg>')

def pattern_pdf(patterns,path,profile_id):
 c=canvas.Canvas(str(path),invariant=1)
 for p in patterns:
  x0,y0,x1,y1=bounds(p['outline']);w=max(210,x1-x0+40);h=max(150,y1-y0+85+5*len(p.get("seams",{})))
  c.setPageSize((w*mm,h*mm));c.setFont('Helvetica',9)
  c.drawString(10*mm,(h-10)*mm,f'{profile_id} / {p["id"]} / CUT {p["quantity"]} / 1:1 mm / TOILE PROTOTYPE')
  c.setFont('Helvetica',7);c.drawString(10*mm,(h-16)*mm,'Print ACTUAL SIZE. Do not fit page. Solid=cut; blue dashed=stitch. 20 mm calibration square.')
  c.rect(10*mm,(h-40)*mm,20*mm,20*mm)
  c.drawString(40*mm,(h-28)*mm,f'Fold: {p.get("cut_on_fold",False)} | mirrored pairs: {p.get("mirrored_pairs",False)}')
  for key,color,dash in [('outline',(0,0,0),[]),('stitchline',(0.1,0.45,0.7),[3,2]),('grainline',(.5,.5,.5),[])]:
   pts=p[key];q=c.beginPath()
   for i,(x,y) in enumerate(pts):
    fn=q.moveTo if i==0 else q.lineTo;fn((x-x0+20)*mm,(h-50-y+y0)*mm)
   if key!='grainline':q.close()
   c.setStrokeColorRGB(*color);c.setDash(dash);c.drawPath(q)
  c.setDash([]);c.setFillColorRGB(0,0,0);c.setFont('Helvetica',6)
  for index,(name,pts) in enumerate(p.get('seams',{}).items(),1):
   if pts:
    q=c.beginPath()
    for i,(x,y) in enumerate(pts):
     fn=q.moveTo if i==0 else q.lineTo;fn((x-x0+20)*mm,(h-50-y+y0)*mm)
    c.setStrokeColorRGB(.7,.29,.14);c.setDash([1,1]);c.drawPath(q);c.setDash([])
    x,y=pts[len(pts)//2];c.drawString((x-x0+20)*mm,(h-50-y+y0)*mm,'S'+str(index))
    c.drawString(10*mm,(h-(y1-y0+65+index*5))*mm,f'S{index}: {name} (construction / stitch guide, not cut)')
  c.showPage()
 c.save()

def instructions_pdf(lines,path):
 c=canvas.Canvas(str(path),pagesize=(210*mm,297*mm),invariant=1); y=280
 for line in lines:
  # Chinese CID font, conservative line length; preserve all content across pages.
  for start in range(0,max(len(line),1),44):
   if y<20:c.showPage();y=280
   c.setFont('STSong-Light',10);c.drawString(15*mm,y*mm,line[start:start+44]);y-=6
 c.save()
