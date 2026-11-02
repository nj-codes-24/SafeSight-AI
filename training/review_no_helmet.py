import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

root=Path("data/processed/common_test/cppe"); m=YOLO("models/best.pt")
cells=[]; areas=[]; out=Path("reports/eval/final_m2_cppe_test"); rows=[]
for p in sorted((root/"images/test").iterdir()):
    lb=(root/"labels/test"/f"{p.stem}.txt").read_text().split("\n")
    gt=[list(map(float,l.split())) for l in lb if l.strip() and l.split()[0]=="2"]
    if not gt: continue
    im=cv2.imread(str(p)); h,w=im.shape[:2]
    r=m.predict(im,conf=.25,verbose=False,device=0)[0]
    bx=r.boxes.xyxy.cpu().numpy(); cl=r.boxes.cls.cpu().numpy().astype(int); cf=r.boxes.conf.cpu().numpy()
    for g in gt:
        x,y,bw,bh=g[1]*w,g[2]*h,g[3]*w,g[4]*h; a=[x-bw/2,y-bh/2,x+bw/2,y+bh/2]
        best=(0,None,0)
        for b,c,f in zip(bx,cl,cf):
            if c==0: continue
            i=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
            u=bw*bh+(b[2]-b[0])*(b[3]-b[1])-i; iou=i/u
            if iou>best[0]: best=(iou,c,f)
        tag="hit" if best[0]>.5 and best[1]==2 and best[2]>=.3 else "helmet" if best[0]>.3 and best[1]==1 else "miss"
        rows.append(dict(img=p.name,w=int(bw),h=int(bh),tag=tag,iou=round(float(best[0]),2),conf=round(float(best[2]),2)))
        pad=int(max(bw,bh)*.5); c=im[max(0,int(a[1])-pad):int(a[3])+pad,max(0,int(a[0])-pad):int(a[2])+pad]
        c=cv2.resize(c,(150,150)); col={"hit":(0,200,0),"helmet":(0,160,255),"miss":(0,0,255)}[tag]
        cv2.rectangle(c,(0,0),(149,149),col,3); cv2.putText(c,f"{int(bw)}x{int(bh)}",(4,145),0,.45,(255,255,255),1); cells.append(c)
while len(cells)%8: cells.append(np.zeros((150,150,3),np.uint8))
cv2.imwrite(str(out/"no_helmet_gt_review.jpg"),np.vstack([np.hstack(cells[i:i+8]) for i in range(0,len(cells),8)]))
json.dump(rows,open(out/"no_helmet_gt_review.json","w"),indent=0)
s=[r["h"] for r in rows]; print(len(rows),"median height",int(np.median(s)),"images",len({r["img"] for r in rows}))
from collections import Counter  # noqa: I001

print(Counter(r["tag"] for r in rows))
print("rows by tag median h",{t:int(np.median([r["h"] for r in rows if r["tag"]==t])) for t in {r["tag"] for r in rows}})
print("gpu mem")
