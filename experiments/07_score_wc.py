"""Score per-second brand presence on the hand-labelled WC final segment (t=140..319 s).

GT: evidence/wc_final/gt_presence.csv ("clear" must be found; "partial" is don't-care).
Sources:
  vi    - Video Intelligence tracks (present at second t if a track box falls in [t-0.5, t+0.5))
  owlv2 - evidence/wc_owlv2.json per-frame brand detections (if present)
"""
import csv
import json

from common import EVIDENCE, VI_ALIASES as ALIASES, norm_brand as norm

GT = EVIDENCE / "wc_final" / "gt_presence.csv"
rows = list(csv.DictReader(GT.open()))
brands = [b for b in rows[0] if b not in ("frame", "t_sec")]
T = [int(r["t_sec"]) for r in rows]


def vi_presence(path):
    vi = json.loads(path.read_text())
    pres = {}
    unmapped = {}
    for l in vi["logos"]:
        key = ALIASES.get(norm(l["entity"]))
        for tr in l["tracks"]:
            for b in tr["boxes"]:
                t = round(b[0])
                if key:
                    pres.setdefault(t, set()).add(key)
                else:
                    unmapped[l["entity"]] = unmapped.get(l["entity"], 0) + 1
    return pres, unmapped


def score(pres):
    per = {}
    for b in brands:
        tp = fp = fn = 0
        for r, t in zip(rows, T):
            g = r[b]
            p = b in pres.get(t, set())
            if g == "clear":
                tp += p
                fn += not p
            elif g == "" and p:
                fp += 1
        n_clear = tp + fn
        if n_clear == 0 and fp == 0:
            continue
        per[b] = {"clear_secs": n_clear, "tp": tp, "fn": fn, "fp": fp,
                  "recall": round(tp / n_clear, 3) if n_clear else None,
                  "precision": round(tp / (tp + fp), 3) if tp + fp else None}
    TP = sum(v["tp"] for v in per.values())
    FN = sum(v["fn"] for v in per.values())
    FP = sum(v["fp"] for v in per.values())
    return {"micro_recall": round(TP / max(TP + FN, 1), 3), "micro_precision": round(TP / max(TP + FP, 1), 3),
            "tp": TP, "fn": FN, "fp": FP, "per_brand": per}


out = {}
vi_path = EVIDENCE / "vi_wc_final.json"
if vi_path.exists():
    pres, unmapped = vi_presence(vi_path)
    out["vi"] = score(pres)
    out["vi_unmapped_entities"] = unmapped
oc = EVIDENCE / "wc_ocr.json"
if oc.exists():
    det = json.loads(oc.read_text())["per_second"]
    out["ocr"] = score({int(t): set(d) for t, d in det.items()})
if "vi" in out and "ocr" in out:
    vp, _ = vi_presence(vi_path)
    op = {int(t): set(d) for t, d in json.loads(oc.read_text())["per_second"].items()}
    out["fused"] = score({t: vp.get(t, set()) | op.get(t, set()) for t in set(vp) | set(op)})
ow = EVIDENCE / "wc_owlv2.json"
if ow.exists():
    det = json.loads(ow.read_text())
    for thr_name, thr in det["thresholds"].items():
        pres = {}
        for t, d in det["per_second"].items():
            pres[int(t)] = {b for b, s in d.items() if s >= thr[b]} if isinstance(thr, dict) else {b for b, s in d.items() if s >= thr}
        out[f"owlv2_{thr_name}"] = score(pres)
(EVIDENCE / "wc_scores.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
