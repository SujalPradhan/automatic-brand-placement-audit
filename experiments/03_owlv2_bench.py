"""OWLv2 on the ExposureEngine benchmark frames.

Two modes, one forward pass per image (tile):
  text  - class-agnostic "logo" text prompts (zero-shot)
  brand - one-shot image-conditioned queries: for each target brand, the OWLv2 box embedding
          that best matches a GT box on reference-pool frames (as in the OWL-ViT paper).

Usage: python 03_owlv2_bench.py [--tiled]
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision.ops import nms
from transformers import Owlv2ForObjectDetection, Owlv2Processor

from common import DATA, EVIDENCE, iou, load_obb_labels

TILED = "--tiled" in sys.argv
MODEL_ID = "google/owlv2-base-patch16-ensemble"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
TEXT_PROMPTS = ["a logo", "a brand logo", "a sponsor logo", "advertising text", "a brand name"]
BRANDS = json.loads((EVIDENCE / "ee_brand_names.json").read_text())  # {class_id: name}
TARGET = [600, 443, 274, 621, 157, 395]  # Unibet, Puma, Intersport, Volkswagen, Elkedjan, Nordic Wellness
REFS_PER_BRAND = 4
KEEP_THR = 0.05

proc = Owlv2Processor.from_pretrained(MODEL_ID)
model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID).to(DEV).eval()


def tiles_for(w, h):
    if not TILED:
        return [(0, 0, w, h)]
    s = min(w, h)  # two overlapping squares across the width
    return [(0, 0, s, s), (w - s, 0, w, s)]


@torch.no_grad()
def embed(im_rgb):
    """Return boxes (N,4 xyxy px in im coords), class embeds (N,D), image feats for scoring."""
    h, w = im_rgb.shape[:2]
    out_boxes, out_feats = [], []
    for x0, y0, x1, y1 in tiles_for(w, h):
        tile = im_rgb[y0:y1, x0:x1]
        pv = proc(images=tile, return_tensors="pt")["pixel_values"].to(DEV)
        fmap, _ = model.image_embedder(pixel_values=pv)
        b, ph, pw, d = fmap.shape
        feats = fmap.reshape(b, ph * pw, d)
        boxes = model.box_predictor(feats, fmap)[0]  # cxcywh normalised to padded square
        side = max(tile.shape[:2])
        cx, cy, bw, bh = boxes.unbind(-1)
        xyxy = torch.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], -1) * side
        xyxy[:, [0, 2]] += x0
        xyxy[:, [1, 3]] += y0
        out_boxes.append(xyxy)
        out_feats.append(feats[0])
    return torch.cat(out_boxes), torch.cat(out_feats)


@torch.no_grad()
def scores(feats, query_embeds):
    logits, class_embeds = model.class_predictor(feats[None], query_embeds[None])
    return torch.sigmoid(logits[0]), class_embeds[0]


@torch.no_grad()
def text_queries():
    t = proc(text=TEXT_PROMPTS, return_tensors="pt").to(DEV)
    out = model.owlv2.get_text_features(input_ids=t["input_ids"], attention_mask=t["attention_mask"])
    return out.pooler_output if hasattr(out, "pooler_output") else out


def pick(dets, thr=KEEP_THR):
    """dets: boxes (N,4), score (N,) -> NMS'd list [[x1,y1,x2,y2,score]]"""
    boxes, s = dets
    keep = s > thr
    boxes, s = boxes[keep], s[keep]
    if len(s) == 0:
        return []
    k = nms(boxes.float().cpu(), s.float().cpu(), 0.3)
    return [[*map(lambda v: round(float(v), 1), boxes[i].tolist()), round(float(s[i]), 4)] for i in k]


split = json.loads((EVIDENCE / "ee_split.json").read_text())
tq = text_queries()

# --- one-shot brand query embeddings from the reference pool ---
ref_embeds, ref_used = {}, {}
for c in TARGET:
    cands = []
    for p in split["ref"]:
        lab = Path(p.replace("/images/", "/labels/")).with_suffix(".txt")
        im = cv2.imread(p)
        h, w = im.shape[:2]
        for cls, box, _ in load_obb_labels(lab, w, h):
            if cls == c:
                cands.append(((box[2] - box[0]) * (box[3] - box[1]), p, box))
    cands.sort(reverse=True)
    chosen, seen = [], set()
    for area, p, box in cands:  # largest examples, one per frame
        if p not in seen:
            chosen.append((p, box))
            seen.add(p)
        if len(chosen) == REFS_PER_BRAND:
            break
    embs = []
    for p, box in chosen:  # embedding of the predicted box that best overlaps the GT box
        im = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
        boxes, feats = embed(im)
        _, cemb = scores(feats, tq)
        ious = torch.tensor([iou(b, box) for b in boxes.cpu().tolist()])
        embs.append(F.normalize(cemb[int(ious.argmax())], dim=-1))
    ref_embeds[c] = torch.stack(embs)
    ref_used[c] = [(Path(p).name, [round(v) for v in box]) for p, box in chosen]

all_q = torch.cat([ref_embeds[c] for c in TARGET])  # (B*R, D)
q_owner = [c for c in TARGET for _ in range(REFS_PER_BRAND)]

# --- benchmark frames ---
results, times = {}, []
for p in split["bench"]:
    im = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2RGB)
    if DEV == "mps":
        torch.mps.synchronize()
    t0 = time.perf_counter()
    boxes, feats = embed(im)
    s_text, cemb = scores(feats, tq)
    # Image-conditioned OWLv2 logits are only meaningful relative to each frame's max (HF rescales them per
    # image), so use raw cosine similarity between box and reference embeddings, which is comparable across frames.
    s_brand = F.normalize(cemb, dim=-1) @ all_q.T
    if DEV == "mps":
        torch.mps.synchronize()
    times.append(time.perf_counter() - t0)
    rec = {"text": pick((boxes, s_text.max(-1).values)), "brand": {}}
    for c in TARGET:
        cols = [i for i, o in enumerate(q_owner) if o == c]
        rec["brand"][str(c)] = pick((boxes, s_brand[:, cols].max(-1).values), thr=0.5)
    results[Path(p).name] = rec

tag = "owlv2_tiled" if TILED else "owlv2"
out = {
    "model": MODEL_ID, "device": DEV, "tiled": TILED, "text_prompts": TEXT_PROMPTS,
    "target": {c: BRANDS[str(c)] for c in TARGET}, "refs": ref_used,
    "sec_per_frame_mean": round(float(np.mean(times[3:])), 3), "frames": len(times),
    "detections": results,
}
(EVIDENCE / f"ee_{tag}.json").write_text(json.dumps(out))
print(tag, "frames", len(times), "s/frame", out["sec_per_frame_mean"])
