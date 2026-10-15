"""One-shot OWLv2 brand detection over every 1 fps frame of the WC final.

Reference boxes (hand-picked on frames outside the GT segment) come from evidence/wc_final/refs.json:
  {"Brand": [[frame_index, [x1,y1,x2,y2]], ...], ...}
Output evidence/wc_owlv2.json:
  per_second[t][brand] = max cosine similarity; boxes[t][brand] = NMS'd boxes with cosine >= 0.5
"""
import json
import time

import cv2
import torch

from common import DATA, EVIDENCE
from owl import DEV, embed, ref_embedding, top_boxes

FR = DATA / "wc_final" / "frames_1fps"
refs = json.loads((EVIDENCE / "wc_final" / "refs.json").read_text())


def rgb(idx):
    return cv2.cvtColor(cv2.imread(str(FR / f"f_{idx:04d}.jpg")), cv2.COLOR_BGR2RGB)


brands = sorted(refs)
q, owner = [], []
for b in brands:
    for idx, box in refs[b]:
        q.append(ref_embedding(rgb(idx), box))
        owner.append(b)
Q = torch.stack(q)

per_second, boxes_out, times = {}, {}, []
frames = sorted(FR.glob("f_*.jpg"))
for p in frames:
    idx = int(p.stem[2:])
    t = idx - 1
    t0 = time.perf_counter()
    boxes, _, cemb = embed(rgb(idx))
    sim = cemb @ Q.T  # (N boxes, refs)
    if DEV == "mps":
        torch.mps.synchronize()
    times.append(time.perf_counter() - t0)
    per_second[t], boxes_out[t] = {}, {}
    for b in brands:
        cols = [i for i, o in enumerate(owner) if o == b]
        s = sim[:, cols].max(-1).values
        per_second[t][b] = round(float(s.max()), 4)
        bx = top_boxes(boxes, s, 0.5)
        if bx:
            boxes_out[t][b] = bx
    if idx % 100 == 0:
        print(idx, f"{sum(times) / len(times):.3f}s/frame", flush=True)

ee = json.loads((EVIDENCE / "ee_scores.json").read_text())
ee_thr = ee.get("owlv2_cosine_global_threshold", 0.75)
(EVIDENCE / "wc_owlv2.json").write_text(json.dumps({
    "brands": brands, "refs": refs, "sec_per_frame_mean": round(sum(times[5:]) / len(times[5:]), 3),
    "thresholds": {"ee_global": ee_thr}, "per_second": per_second, "boxes": boxes_out,
}))
print("done", len(frames), "frames")
