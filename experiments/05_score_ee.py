"""Score OWLv2 (full/tiled) and Cloud Vision against ExposureEngine ground truth.

A) Class-agnostic logo localisation: box P/R at IoU>=0.5 (and 0.3), recall by logo size.
B) Brand identification (one-shot OWLv2 vs Vision names) for 6 target brands:
   frame-level presence P/R/F1 (what exposure-duration needs) and box-level P/R at IoU>=0.3.
   OWLv2 thresholds are chosen on the even-indexed half of the benchmark and reported on the odd half.
"""
import json
from pathlib import Path

import cv2
import numpy as np

from common import EE, EVIDENCE, load_obb_labels, match

split = json.loads((EVIDENCE / "ee_split.json").read_text())
names = json.loads((EVIDENCE / "ee_brand_names.json").read_text())
frames = [Path(p) for p in split["bench"]]
calib, test = frames[0::2], frames[1::2]

gt = {}
for p in frames:
    im = cv2.imread(str(p))
    h, w = im.shape[:2]
    lab = p.parent.parent / "labels" / f"{p.stem}.txt"
    gt[p.name] = {"wh": (w, h), "boxes": [(c, b) for c, b, _ in load_obb_labels(lab, w, h)]}


def size_bucket(b, wh):
    a = (b[2] - b[0]) * (b[3] - b[1]) / (wh[0] * wh[1]) * 100
    return "small(<0.1%)" if a < 0.1 else "medium(0.1-0.5%)" if a < 0.5 else "large(>=0.5%)"


def agnostic(preds_by_frame, frame_set, thr, iou_thr):
    tp = fp = fn = 0
    by_size = {}
    for p in frame_set:
        g = gt[p.name]
        gboxes = [b for _, b in g["boxes"]]
        preds = [d[:4] for d in preds_by_frame.get(p.name, []) if d[4] >= thr]
        t, f, n, matched = match(preds, gboxes, iou_thr)
        tp, fp, fn = tp + t, fp + f, fn + n
        hit = {j for _, j, _ in matched}
        for j, b in enumerate(gboxes):
            k = size_bucket(b, g["wh"])
            s = by_size.setdefault(k, [0, 0])
            s[0] += j in hit
            s[1] += 1
    return {"precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1), "tp": tp, "fp": fp, "fn": fn,
            "recall_by_size": {k: round(v[0] / v[1], 3) for k, v in sorted(by_size.items())},
            "gt_by_size": {k: v[1] for k, v in sorted(by_size.items())}}


def brand_eval(dets_for, c, frame_set, thr):
    """dets_for(frame_name) -> list of [x1,y1,x2,y2,score] for brand c."""
    ftp = ffp = ffn = 0
    btp = bfp = bfn = 0
    for p in frame_set:
        g = [b for cc, b in gt[p.name]["boxes"] if cc == c]
        d = [x[:4] for x in dets_for(p.name) if x[4] >= thr]
        present, predicted = bool(g), bool(d)
        ftp += present and predicted
        ffp += predicted and not present
        ffn += present and not predicted
        t, f, n, _ = match(d, g, 0.3)
        btp, bfp, bfn = btp + t, bfp + f, bfn + n
    fp_ = ftp / max(ftp + ffp, 1)
    fr = ftp / max(ftp + ffn, 1)
    return {"frame_precision": round(fp_, 3), "frame_recall": round(fr, 3),
            "frame_f1": round(2 * fp_ * fr / max(fp_ + fr, 1e-9), 3),
            "frames_with_brand": ftp + ffn, "frame_fp": ffp,
            "box_precision": round(btp / max(btp + bfp, 1), 3), "box_recall": round(btp / max(btp + bfn, 1), 3),
            "boxes_gt": btp + bfn}


report = {"benchmark_frames": len(frames), "calib_frames": len(calib), "test_frames": len(test),
          "gt_boxes": sum(len(g["boxes"]) for g in gt.values())}

# ---- A) class-agnostic ----
agn = {}
for tag in ["owlv2", "owlv2_tiled"]:
    f = EVIDENCE / f"ee_{tag}.json"
    if not f.exists():
        continue
    run = json.loads(f.read_text())
    preds = {k: v["text"] for k, v in run["detections"].items()}
    sweep = {t: agnostic(preds, calib, t, 0.5) for t in [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4]}
    best = max(sweep, key=lambda t: 2 * sweep[t]["precision"] * sweep[t]["recall"] /
               max(sweep[t]["precision"] + sweep[t]["recall"], 1e-9))
    agn[tag] = {"threshold": best, "sec_per_frame": run["sec_per_frame_mean"],
                "iou50": agnostic(preds, test, best, 0.5), "iou30": agnostic(preds, test, best, 0.3),
                "pr_curve_calib": {t: (round(s["precision"], 3), round(s["recall"], 3)) for t, s in sweep.items()}}
gcv = json.loads((EVIDENCE / "ee_gcv.json").read_text())
gpreds = {k: [d[:5] for d in v] for k, v in gcv["detections"].items()}
agn["cloud_vision"] = {"threshold": 0.0, "sec_per_frame": gcv["sec_per_frame_mean"],
                       "iou50": agnostic(gpreds, test, 0.0, 0.5), "iou30": agnostic(gpreds, test, 0.0, 0.3)}
report["class_agnostic"] = agn

# ---- B) brand identification ----
brand = {}
for tag in ["owlv2", "owlv2_tiled"]:
    f = EVIDENCE / f"ee_{tag}.json"
    if not f.exists():
        continue
    run = json.loads(f.read_text())
    res = {}
    for c in map(int, run["target"]):
        dets_for = lambda n, c=c: run["detections"][n]["brand"][str(c)]
        sweep = {t: brand_eval(dets_for, c, calib, t) for t in np.arange(0.5, 0.96, 0.025).round(3)}
        best = max(sweep, key=lambda t: (sweep[t]["frame_f1"], t))
        res[names[str(c)]] = {"threshold": float(best), **brand_eval(dets_for, c, test, best)}
    brand[tag] = res

# Cloud Vision: count a brand as detected if its returned description contains the brand name
gres = {}
for c in [600, 443, 274, 621, 157, 395]:
    nm = names[str(c)].lower()
    dets_for = lambda n, nm=nm: [d[:5] for d in gcv["detections"].get(n, []) if nm in d[5].lower()]
    gres[names[str(c)]] = brand_eval(dets_for, c, test, 0.0)
brand["cloud_vision"] = gres
desc_counts = {}
for v in gcv["detections"].values():
    for d in v:
        desc_counts[d[5]] = desc_counts.get(d[5], 0) + 1
report["cloud_vision_descriptions"] = dict(sorted(desc_counts.items(), key=lambda x: -x[1]))
report["brand_identification"] = brand

(EVIDENCE / "ee_scores.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
