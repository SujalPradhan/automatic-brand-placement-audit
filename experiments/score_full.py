"""Recall (hand labels) + precision (audited random sample) for a full-match tag. Usage: score_full.py <tag> <srcs csv> <false idx csv>"""
import csv,json,math,sys,random
from common import EVIDENCE
from presence import presence
def wilson(k,n,z=1.96):
    if n==0: return [None,None]
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(max(0,c-h),3),round(min(1,c+h),3)]
tag=sys.argv[1]; fullsrc=tuple(sys.argv[2].split(','))
falses={int(x) for x in sys.argv[3].split(',') if x}
G=[(int(r['t']),[x.split(':') for x in r['labels'].split(';') if x]) for r in csv.DictReader((EVIDENCE/'audit'/f'{tag}_gt.csv').open())]
out={'frames_labelled':len(G),'board_marks':sum(1 for _,l in G for x in l if x[2]=='board')}
methods=[('ocr',('ocr',))]+([('vi',('vi',)),('fused',('ocr','vi'))] if 'vi' in fullsrc else [])
for name,src in methods:
    P=presence(tag,src,audited=False); cnt={}
    for t,labs in G:
        for b,sz,k in labs:
            if k!='board': continue
            for key in ('all',sz):
                c=cnt.setdefault(key,[0,0]); c[1]+=1; c[0]+=int(t in P.get(b,{}))
    out[name]={('large' if k=='L' else 'small' if k=='S' else k):{'found':v[0],'of':v[1],'recall':round(v[0]/v[1],3) if v[1] else None,'ci95':wilson(*v)} for k,v in cnt.items()}
    # unlabelled detections on labelled frames (sanity): not scored as precision
# precision sample
sample=json.load(open(f'/private/tmp/claude-501/sc/prec_{tag}/index.json'))
bysrc={}
for i,b,t,s in sample:
    x=bysrc.setdefault(s,[0,0]); x[1]+=1; x[0]+=int(i not in falses)
tot=[sum(v[0] for v in bysrc.values()),sum(v[1] for v in bysrc.values())]
out['precision_sample']={'all':{'true':tot[0],'n':tot[1],'precision':round(tot[0]/tot[1],3),'ci95':wilson(*tot)},
  **{s:{'true':v[0],'n':v[1],'precision':round(v[0]/v[1],3),'ci95':wilson(*v)} for s,v in bysrc.items()}}
# OCR-only precision = ocr+both samples (detections the OCR produced); VI = vi+both
def comb(keys):
    v=[sum(bysrc.get(k,[0,0])[0] for k in keys),sum(bysrc.get(k,[0,0])[1] for k in keys)]
    return {'true':v[0],'n':v[1],'precision':round(v[0]/v[1],3) if v[1] else None,'ci95':wilson(*v)}
out['precision_sample']['ocr_detections(ocr+both)']=comb(['ocr','both'])
if 'vi' in fullsrc: out['precision_sample']['vi_detections(vi+both)']=comb(['vi','both'])
out['false_idx']=sorted(falses)
out['false_log']=[[i,b,t,s] for i,b,t,s in sample if i in falses]
(EVIDENCE/'audit'/f'{tag}_scores.json').write_text(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
