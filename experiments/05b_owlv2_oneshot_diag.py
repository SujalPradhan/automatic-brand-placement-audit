"""Why one-shot OWLv2 fails at brand identity: where does the true logo box rank among all proposals?

Reference = largest Unibet (class 600) box in the reference pool; checked on 4 benchmark frames containing Unibet.
Scores compared: raw cosine, mean-centred cosine, and OWLv2's own (sigmoid) image-conditioned logit.
"""
import json
from pathlib import Path

import cv2
import torch
import torch.nn.functional as F

from common import EVIDENCE, iou, load_obb_labels
from owl import embed, model

split = json.loads((EVIDENCE / "ee_split.json").read_text())
C = 600


def lab(p):
    return Path(p.replace("/images/", "/labels/")).with_suffix(".txt")


def rgb(p):
    return cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)


def gt(p, c):
    h, w = cv2.imread(p).shape[:2]
    return [b for cc, b, _ in load_obb_labels(lab(p), w, h) if cc == c]


best = max(((b[2] - b[0]) * (b[3] - b[1]), p, b) for p in split["ref"][:300] for b in gt(p, C))
_, rp, rb = best
boxes, feats, cemb = embed(rgb(rp))
q = cemb[int(torch.tensor([iou(b, rb) for b in boxes.cpu().tolist()]).argmax())]

rows = []
for p in [p for p in split["bench"] if gt(p, C)][:4]:
    gts = gt(p, C)
    boxes, feats, cemb = embed(rgb(p))
    on = [k for k, b in enumerate(boxes.cpu().tolist()) if max(iou(b, g) for g in gts) > 0.3]
    mu = cemb.mean(0)
    with torch.no_grad():
        logits, _ = model.class_predictor(feats[None], q[None, None])
    variants = {"cosine": cemb @ q,
                "centred": F.normalize(cemb - mu, dim=-1) @ F.normalize(q - mu, dim=-1),
                "owl_logit": torch.sigmoid(logits[0, :, 0])}
    for name, s in variants.items():
        order = torch.argsort(s, descending=True)
        rank = min(int((order == k).nonzero()) for k in on) + 1
        rows.append({"frame": Path(p).name, "score": name, "best_true_box_rank": rank, "proposals": len(s)})
        print(rows[-1])
(EVIDENCE / "ee_owlv2_oneshot_diag.json").write_text(json.dumps(rows, indent=1))
