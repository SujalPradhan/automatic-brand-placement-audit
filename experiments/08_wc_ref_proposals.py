"""Render numbered OWLv2 'logo' proposals on candidate reference frames (outside the GT segment),
so reference boxes can be picked by eye and written to evidence/wc_final/refs.json.

Usage: python 08_wc_ref_proposals.py <frame_index> [<frame_index> ...]
"""
import json
import sys

import cv2
import torch
from torchvision.ops import nms
from transformers import Owlv2ForObjectDetection, Owlv2Processor

from common import DATA, EVIDENCE

MODEL_ID = "google/owlv2-base-patch16-ensemble"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
proc = Owlv2Processor.from_pretrained(MODEL_ID)
model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID).to(DEV).eval()
PROMPTS = [["a logo", "a brand logo", "advertising text", "a brand name"]]
out_dir = EVIDENCE / "wc_final" / "ref_proposals"
out_dir.mkdir(parents=True, exist_ok=True)
props = {}
for idx in map(int, sys.argv[1:]):
    p = DATA / "wc_final" / "frames_1fps" / f"f_{idx:04d}.jpg"
    im = cv2.imread(str(p))
    h, w = im.shape[:2]
    inputs = proc(text=PROMPTS, images=cv2.cvtColor(im, cv2.COLOR_BGR2RGB), return_tensors="pt").to(DEV)
    with torch.no_grad():
        o = model(**inputs)
    side = max(h, w)
    r = proc.post_process_object_detection(o, threshold=0.08, target_sizes=torch.tensor([[side, side]]))[0]
    keep = nms(r["boxes"].cpu(), r["scores"].cpu(), 0.3)[:40]
    boxes = [[round(v) for v in r["boxes"][k].tolist()] for k in keep]
    props[idx] = boxes
    vis = im.copy()
    for n, b in enumerate(boxes):
        cv2.rectangle(vis, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 2)
        cv2.putText(vis, str(n), (b[0], max(20, b[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 5)
        cv2.putText(vis, str(n), (b[0], max(20, b[1] - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    cv2.imwrite(str(out_dir / f"p_{idx:04d}.jpg"), cv2.resize(vis, (1440, 810)), [cv2.IMWRITE_JPEG_QUALITY, 80])
f = out_dir / "proposals.json"
allp = json.loads(f.read_text()) if f.exists() else {}
allp.update({str(k): v for k, v in props.items()})
f.write_text(json.dumps(allp))
print("done", list(props))
