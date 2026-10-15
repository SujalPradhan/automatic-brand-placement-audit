"""Precision audit sheets: one row per detected appearance (run of seconds) per brand, showing the first, middle
and last second's crop with context. Reviewed by eye; false appearances go to evidence/audit/<tag>_rejects.csv.

Usage: python 15_audit_sheets.py <tag> [Brand,Brand ...]   (brand filter re-audits only those brands,
       hiding seconds already rejected)
"""
import sys

import cv2
import numpy as np

from common import DATA, EVIDENCE
from presence import presence, runs

TAG = sys.argv[1]
FR = DATA / TAG / "frames_1fps"
OUT = EVIDENCE / "audit" / "sheets"
OUT.mkdir(parents=True, exist_ok=True)
CW, CH = 300, 110


def crop(t, box):
    im = cv2.imread(str(FR / f"f_{t + 1:04d}.jpg"))
    h, w = im.shape[:2]
    x1, y1, x2, y2 = box
    bw, bh = max(x2 - x1, 20), max(y2 - y1, 12)
    px, py = int(bw * 0.6) + 20, int(bh * 1.5) + 15
    X1, Y1, X2, Y2 = max(0, x1 - px), max(0, y1 - py), min(w, x2 + px), min(h, y2 + py)
    c = im[Y1:Y2, X1:X2].copy()
    cv2.rectangle(c, (x1 - X1, y1 - Y1), (x2 - X1, y2 - Y1), (0, 255, 255), 2)
    s = min(CW / c.shape[1], CH / c.shape[0])
    c = cv2.resize(c, (max(1, int(c.shape[1] * s)), max(1, int(c.shape[0] * s))))
    tile = np.zeros((CH, CW, 3), np.uint8)
    tile[:c.shape[0], :c.shape[1]] = c
    return tile


ONLY = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
pres = presence(TAG, audited=bool(ONLY))
rows = []
for b in sorted(pres):
    if ONLY and b not in ONLY:
        continue
    for s, e in runs(pres[b].keys()):
        picks = sorted({s, (s + e) // 2, e})
        tiles = [crop(t, pres[b][t]["box"]) for t in picks if t in pres[b]]
        tiles += [np.zeros((CH, CW, 3), np.uint8)] * (3 - len(tiles))
        lab = np.full((CH, 260, 3), 30, np.uint8)
        srcs = {pres[b][t]["src"] for t in range(s, e + 1) if t in pres[b]}
        cv2.putText(lab, b[:16], (6, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        cv2.putText(lab, f"{s}-{e}s ({e - s + 1})", (6, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        cv2.putText(lab, "/".join(sorted(srcs)), (6, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        rows.append(np.hstack([lab] + tiles))
per = 14
for i in range(0, len(rows), per):
    cv2.imwrite(str(OUT / f"{TAG}_{'re' if ONLY else 'prec'}_{i // per:02d}.jpg"), np.vstack(rows[i:i + per]), [cv2.IMWRITE_JPEG_QUALITY, 82])
print(TAG, "appearances", len(rows), "sheets", (len(rows) + per - 1) // per)
