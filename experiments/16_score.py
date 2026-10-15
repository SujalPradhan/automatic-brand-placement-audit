"""Accuracy of each method against the hand labels (every 10th second; every 5th in the 2-minute 2026 final — the
seconds are read from the CSV) and the precision audit.

Recall:    of the sponsor marks a person could identify in the sampled frames, how many did the method find?
           Reported for perimeter/LED boards (the story's subject) by size, and separately for kit/other marks.
Precision: of all detected appearances, how many were real? From the appearance-level audit (rejects.csv),
           expressed in brand-seconds.
Writes evidence/scores.json
"""
import csv
import json
import math

from common import EVIDENCE
from presence import VIDEO, presence, rejects


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def gt(tag):
    rows = []
    for r in csv.DictReader((EVIDENCE / "audit" / f"{tag}_gt.csv").open()):
        labs = [x.split(":") for x in r["labels"].split(";") if x]
        rows.append((int(r["t"]), labs))
    return rows


out = {}
for tag in VIDEO:
    G = gt(tag)
    res = {"frames_labelled": len(G), "board_marks_labelled": sum(1 for _, l in G for x in l if x[2] == "board")}
    for name, src in (("ocr", ("ocr",)), ("vi", ("vi",)), ("fused", ("ocr", "vi"))):
        P = presence(tag, src, audited=False)
        cnt = {}
        for t, labs in G:
            for b, size, kind in labs:
                if kind != "board":
                    continue  # kit / graphic marks are out of scope for this analysis
                key = "board_" + size
                c = cnt.setdefault(key, [0, 0])
                c[1] += 1
                c[0] += int(t in P.get(b, {}))
        boards = [sum(cnt.get(k, [0, 0])[i] for k in ("board_L", "board_S")) for i in (0, 1)]
        r = {k: {"found": v[0], "of": v[1], "recall": round(v[0] / v[1], 3), "ci95": wilson(*v)} for k, v in cnt.items()}
        r["board_all"] = {"found": boards[0], "of": boards[1], "recall": round(boards[0] / boards[1], 3),
                          "ci95": wilson(*boards)}
        # precision from the appearance audit, in brand-seconds
        bad = rejects(tag)
        det = sum(len(d) for d in P.values())
        fp = sum(1 for b, d in P.items() for t in d if (b, t) in bad)
        r["precision"] = {"verified": det - fp, "detected": det, "precision": round((det - fp) / det, 3) if det else None,
                          "ci95": wilson(det - fp, det)}
        res[name] = r
    # per-brand recall (boards, fused)
    P = presence(tag, ("ocr", "vi"), audited=False)
    pb = {}
    for t, labs in G:
        for b, size, kind in labs:
            if kind != "board":
                continue
            c = pb.setdefault(b, [0, 0])
            c[1] += 1
            c[0] += int(t in P.get(b, {}))
    res["per_brand_board_recall_fused"] = {b: {"found": v[0], "of": v[1], "ci95": wilson(*v)} for b, v in
                                           sorted(pb.items(), key=lambda x: -x[1][1])}
    out[tag] = res

(EVIDENCE / "scores.json").write_text(json.dumps(out, indent=1))
for tag, r in out.items():
    print(f"== {tag}: {r['frames_labelled']} frames, {r['board_marks_labelled']} board marks")
    for m in ("ocr", "vi", "fused"):
        x = r[m]
        print(f"  {m:6s} boards R={x['board_all']['recall']} {x['board_all']['ci95']} "
              f"L={x.get('board_L', {}).get('recall')} S={x.get('board_S', {}).get('recall')} "
              f"P={x['precision']['precision']} "
              f"({x['precision']['verified']}/{x['precision']['detected']})")
